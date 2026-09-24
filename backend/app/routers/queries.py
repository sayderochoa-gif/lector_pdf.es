from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.app.database import (
    get_all_pages_data,
    get_document,
    get_document_detections,
)
from backend.app.models.schemas import (
    DocumentStatus,
    QueryRequest,
    QueryResponse,
    SearchResponse,
)
from backend.app.services.chat_service import chat_service
from backend.app.services.query_interpreter import query_interpreter
from backend.app.services.rag_chatbot import rag_chatbot
from backend.app.services.search_engine import search_engine

router = APIRouter(prefix="/api/documents", tags=["queries"])


@router.post("/{doc_id}/chatbot", response_model=QueryResponse)
async def chatbot_document(doc_id: str, request: QueryRequest):
    """
    Proceso 'Chatbot': Utiliza RAG con IA para preguntas más complejas:
    - ¿El documento tiene firmas?
    - ¿Hay código QR en el documento?
    - ¿Hay código de barras dentro del documento?
    - Sellos, tablas estructuradas, elementos visuales y razonamiento semántico profundo.
    """
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")

    pages = get_all_pages_data(doc_id)
    if not pages:
        if doc.status == DocumentStatus.PROCESSING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El documento aún se está procesando. Por favor espere unos segundos.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se encontraron páginas indexadas para este documento.",
        )

    response = rag_chatbot.process_chatbot(
        query=request.query,
        pages_data=pages,
        doc_filename=doc.filename,
    )
    return response


@router.post("/{doc_id}/chat", response_model=QueryResponse)
async def chat_document(doc_id: str, request: QueryRequest):
    """
    Proceso 'Chat': Responde preguntas directas y no tan complejas:
    - Búsqueda textual directa (palabras o frases exactas/parciales)
    - Conteo de ocurrencias ("¿Cuántas páginas contienen la palabra X?")
    - Búsqueda de identificadores (NIT, Cédula)
    - Resumen básico de página específica ("¿Qué contiene la página X?")
    """
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")

    pages = get_all_pages_data(doc_id)
    if not pages:
        if doc.status == DocumentStatus.PROCESSING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El documento aún se está procesando. Por favor espere unos segundos.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se encontraron páginas indexadas para este documento.",
        )

    response = chat_service.process_chat(
        query=request.query,
        pages_data=pages,
        doc_filename=doc.filename,
    )
    return response


@router.post("/{doc_id}/query", response_model=QueryResponse)
async def query_document(doc_id: str, request: QueryRequest):
    """
    Endpoint compatible: enruta preguntas según complejidad entre Chatbot (RAG) y Chat directo.
    """
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")

    pages = get_all_pages_data(doc_id)
    if not pages:
        if doc.status == DocumentStatus.PROCESSING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El documento aún se está procesando. Por favor espere unos segundos.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se encontraron páginas indexadas para este documento.",
        )

    response = query_interpreter.interpret_and_execute(
        query=request.query,
        pages_data=pages,
        doc_filename=doc.filename,
    )
    return response


@router.get("/{doc_id}/search", response_model=SearchResponse)
async def search_document_text(
    doc_id: str,
    q: str = Query(..., min_length=1, description="Término o frase a buscar"),
    exact: bool = Query(False, description="Coincidencia exacta de palabra"),
    case_sensitive: bool = Query(False, description="Sensible a mayúsculas/minúsculas"),
):
    """
    Performs full-text search across all pages with accent insensitivity,
    partial word matching, and snippet extraction.
    """
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")

    pages = get_all_pages_data(doc_id)
    if not pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se encontraron páginas indexadas para este documento.",
        )

    matches = search_engine.search_text_in_pages(
        pages_data=pages,
        query=q,
        exact_match=exact,
        case_sensitive=case_sensitive,
    )

    return SearchResponse(
        query=q,
        total_matches=len(matches),
        matches=matches,
    )


@router.get("/{doc_id}/results")
async def get_document_results(
    doc_id: str,
    type: Optional[str] = Query(None, description="Filtrar por tipo: qr_code, barcode, signature, stamp, table, visual, photo"),
):
    """
    Returns all visual and structural detections found across all pages of the document.
    """
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")

    detections = get_document_detections(doc_id, detection_type=type)
    return {
        "document_id": doc_id,
        "filename": doc.filename,
        "filter_type": type,
        "total_detections": len(detections),
        "detections": detections,
    }
