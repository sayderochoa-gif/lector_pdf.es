import asyncio
import os
import re
import uuid
from pathlib import Path
from typing import List, Optional
import pymupdf
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from backend.app.config import PAGE_IMAGES_DIR, UPLOAD_DIR, settings
from backend.app.database import (
    create_document,
    get_all_pages_data,
    get_document,
    get_page_data,
    list_documents,
)
import threading
from backend.app.models.schemas import DocumentDetail, DocumentStatus, PageData
from backend.app.services.background_worker import _sync_process_document, process_document_task
from backend.app.services.pdf_processor import pdf_processor

router = APIRouter(prefix="/api/documents", tags=["documents"])


def sanitize_filename(filename: str) -> str:
    """Removes path traversal components and unsafe characters."""
    filename = Path(filename).name
    # Keep alphanumeric, dot, hyphen, underscore, and spaces
    clean = re.sub(r"[^\w\.\-\s]", "_", filename).strip()
    return clean or "document.pdf"


@router.post("/upload", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    # 1. Validation: Filename and Extension
    filename = sanitize_filename(file.filename or "uploaded.pdf")
    ext = Path(filename).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no permitido. Solo se aceptan archivos PDF (extensión .pdf).",
        )

    # 2. Validation: Content-Type MIME (flexible check, primary trust is on binary magic header %PDF-)
    if file.content_type:
        clean_mime = file.content_type.lower().split(";")[0].strip()
        if clean_mime and clean_mime not in settings.allowed_mime_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tipo MIME inválido. El archivo debe ser de tipo application/pdf.",
            )

    # 3. Read initial chunk to check magic number (%PDF-)
    initial_bytes = await file.read(1024)
    if not initial_bytes.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no es un documento PDF válido (cabecera corrupta o formato falso).",
        )

    # 4. Save file safely while checking size limit
    doc_id = str(uuid.uuid4())
    saved_path = UPLOAD_DIR / f"{doc_id}.pdf"
    total_size = len(initial_bytes)

    try:
        with open(saved_path, "wb") as f:
            f.write(initial_bytes)
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                total_size += len(chunk)
                if total_size > settings.max_upload_size_bytes:
                    saved_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"El archivo excede el tamaño máximo permitido ({settings.max_upload_size_bytes // (1024 * 1024)} MB).",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando el archivo: {str(e)}",
        )

    # 5. Verify PDF integrity and password protection with PyMuPDF
    try:
        with pymupdf.open(str(saved_path)) as test_doc:
            if test_doc.is_encrypted:
                saved_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El archivo PDF está protegido con contraseña. Debe cargarse sin encriptar.",
                )
            page_count = len(test_doc)
            if page_count == 0:
                saved_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El archivo PDF no contiene ninguna página.",
                )
    except HTTPException:
        raise
    except Exception as e:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El archivo PDF está dañado o no puede ser abierto: {str(e)}",
        )

    # 6. Initialize document record in SQLite immediately without blocking HTTP upload response
    doc_detail = create_document(
        doc_id=doc_id,
        filename=filename,
        filepath=str(saved_path),
        filesize=total_size,
        page_count=page_count,
        document_type="procesando",
        validation_details="Validación y procesamiento automatizado iniciado...",
    )

    # 7. Dispatch background processing immediately in detached worker thread
    worker_thread = threading.Thread(
        target=_sync_process_document,
        args=(doc_id, str(saved_path)),
        daemon=True,
    )
    worker_thread.start()

    return doc_detail


@router.get("", response_model=List[DocumentDetail])
async def get_all_documents():
    return list_documents()


@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document_by_id(doc_id: str):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")
    return doc


@router.get("/{doc_id}/status", response_model=DocumentDetail)
async def get_document_status(doc_id: str):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")
    return doc


@router.get("/{doc_id}/file")
async def get_original_file(doc_id: str):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")
    file_path = UPLOAD_DIR / f"{doc_id}.pdf"
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo físico no encontrado.")
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=doc.filename,
    )


@router.get("/{doc_id}/pages/{page_num}", response_model=PageData)
async def get_page_info(doc_id: str, page_num: int):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")
    page = get_page_data(doc_id, page_num)
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Página {page_num} aún no procesada o no existe.")
    return page


@router.get("/{doc_id}/pages/{page_num}/image")
async def get_page_image(doc_id: str, page_num: int):
    image_path = PAGE_IMAGES_DIR / f"{doc_id}_page_{page_num}.webp"
    if not image_path.exists():
        # Fallback check for png
        image_path_png = PAGE_IMAGES_DIR / f"{doc_id}_page_{page_num}.png"
        if image_path_png.exists():
            return FileResponse(str(image_path_png), media_type="image/png")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen de la página no encontrada.")
    return FileResponse(str(image_path), media_type="image/webp")
