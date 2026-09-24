import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional
from backend.app.config import DB_PATH
from backend.app.models.schemas import (
    BoundingBox,
    DetectionType,
    DocumentDetail,
    DocumentStatus,
    DocumentSummaryCounts,
    PageData,
    VisualDetection,
)


def get_current_iso_time() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                filesize INTEGER NOT NULL,
                page_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                document_type TEXT NOT NULL DEFAULT 'desconocido',
                validation_details TEXT,
                current_page INTEGER NOT NULL DEFAULT 0,
                current_step TEXT NOT NULL DEFAULT '',
                progress_percent INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                summary_counts_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        # Run safe migrations if columns don't exist
        cols = [c[1] for c in conn.execute("PRAGMA table_info(documents)").fetchall()]
        if "document_type" not in cols:
            conn.execute("ALTER TABLE documents ADD COLUMN document_type TEXT NOT NULL DEFAULT 'desconocido'")
        if "validation_details" not in cols:
            conn.execute("ALTER TABLE documents ADD COLUMN validation_details TEXT")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                document_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                width REAL NOT NULL,
                height REAL NOT NULL,
                text TEXT NOT NULL,
                has_text_layer INTEGER NOT NULL DEFAULT 0,
                ocr_applied INTEGER NOT NULL DEFAULT 0,
                data_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (document_id, page_number),
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                type TEXT NOT NULL,
                label TEXT NOT NULL,
                confidence REAL NOT NULL,
                bbox_json TEXT,
                metadata_json TEXT,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pages_doc ON pages(document_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_doc ON detections(document_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_type ON detections(document_id, type);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_label ON detections(document_id, label);")


def create_document(
    doc_id: str,
    filename: str,
    filepath: str,
    filesize: int,
    page_count: int,
    document_type: str = "desconocido",
    validation_details: Optional[str] = None,
) -> DocumentDetail:
    now = get_current_iso_time()
    summary = DocumentSummaryCounts(
        document_type=document_type,
        validation_details=validation_details or "",
    )
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO documents (
                id, filename, filepath, filesize, page_count, status,
                document_type, validation_details,
                current_page, current_step, progress_percent,
                summary_counts_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id, filename, filepath, filesize, page_count,
            DocumentStatus.PENDING.value, document_type, validation_details, 0, "En cola", 0,
            summary.model_dump_json(), now, now
        ))
    return DocumentDetail(
        id=doc_id,
        filename=filename,
        filesize=filesize,
        page_count=page_count,
        status=DocumentStatus.PENDING,
        document_type=document_type,
        validation_details=validation_details,
        current_page=0,
        current_step="En cola",
        progress_percent=0,
        created_at=now,
        updated_at=now,
        summary_counts=summary,
    )


def get_document(doc_id: str) -> Optional[DocumentDetail]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            return None
        summary_json = row["summary_counts_json"]
        summary = DocumentSummaryCounts.model_validate_json(summary_json) if summary_json else DocumentSummaryCounts()
        doc_type = row["document_type"] if "document_type" in row.keys() else summary.document_type
        val_details = row["validation_details"] if "validation_details" in row.keys() else summary.validation_details
        return DocumentDetail(
            id=row["id"],
            filename=row["filename"],
            filesize=row["filesize"],
            page_count=row["page_count"],
            status=DocumentStatus(row["status"]),
            document_type=doc_type or summary.document_type,
            validation_details=val_details,
            current_page=row["current_page"],
            current_step=row["current_step"],
            progress_percent=row["progress_percent"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error_message=row["error_message"],
            summary_counts=summary,
        )


def list_documents() -> List[DocumentDetail]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        docs = []
        for row in rows:
            summary_json = row["summary_counts_json"]
            summary = DocumentSummaryCounts.model_validate_json(summary_json) if summary_json else DocumentSummaryCounts()
            doc_type = row["document_type"] if "document_type" in row.keys() else summary.document_type
            val_details = row["validation_details"] if "validation_details" in row.keys() else summary.validation_details
            docs.append(DocumentDetail(
                id=row["id"],
                filename=row["filename"],
                filesize=row["filesize"],
                page_count=row["page_count"],
                status=DocumentStatus(row["status"]),
                document_type=doc_type or summary.document_type,
                validation_details=val_details,
                current_page=row["current_page"],
                current_step=row["current_step"],
                progress_percent=row["progress_percent"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                error_message=row["error_message"],
                summary_counts=summary,
            ))
        return docs


def update_document_progress(
    doc_id: str,
    current_page: int,
    current_step: str,
    progress_percent: int,
    status: DocumentStatus = DocumentStatus.PROCESSING,
    document_type: Optional[str] = None,
    validation_details: Optional[str] = None,
) -> None:
    now = get_current_iso_time()
    with get_db() as conn:
        if document_type:
            conn.execute("""
                UPDATE documents
                SET current_page = ?, current_step = ?, progress_percent = ?, status = ?,
                    document_type = ?, validation_details = COALESCE(?, validation_details), updated_at = ?
                WHERE id = ?
            """, (current_page, current_step, progress_percent, status.value, document_type, validation_details, now, doc_id))
        else:
            conn.execute("""
                UPDATE documents
                SET current_page = ?, current_step = ?, progress_percent = ?, status = ?, updated_at = ?
                WHERE id = ?
            """, (current_page, current_step, progress_percent, status.value, now, doc_id))


def mark_document_completed(doc_id: str, summary_counts: DocumentSummaryCounts) -> None:
    now = get_current_iso_time()
    with get_db() as conn:
        conn.execute("""
            UPDATE documents
            SET status = ?, current_step = 'Completado', progress_percent = 100,
                document_type = ?, validation_details = ?,
                summary_counts_json = ?, updated_at = ?
            WHERE id = ?
        """, (
            DocumentStatus.COMPLETED.value,
            summary_counts.document_type,
            summary_counts.validation_details,
            summary_counts.model_dump_json(),
            now,
            doc_id,
        ))


def mark_document_error(doc_id: str, error_message: str) -> None:
    now = get_current_iso_time()
    with get_db() as conn:
        conn.execute("""
            UPDATE documents
            SET status = ?, error_message = ?, current_step = 'Error de procesamiento', updated_at = ?
            WHERE id = ?
        """, (DocumentStatus.ERROR.value, error_message, now, doc_id))


def save_page_data(doc_id: str, page_data: PageData) -> None:
    now = get_current_iso_time()
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO pages (
                document_id, page_number, width, height, text,
                has_text_layer, ocr_applied, data_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id, page_data.page, page_data.width, page_data.height,
            page_data.text, 1 if page_data.has_text_layer else 0,
            1 if page_data.ocr_applied else 0,
            page_data.model_dump_json(), now
        ))
        
        # Save individual detections for fast indexed search
        all_detections: List[VisualDetection] = (
            page_data.objects +
            page_data.qr_codes +
            page_data.barcodes +
            page_data.signatures +
            page_data.stamps +
            page_data.images +
            page_data.tables
        )
        for det in all_detections:
            bbox_json = det.bbox.model_dump_json() if det.bbox else None
            metadata_json = json.dumps(det.metadata) if det.metadata else None
            conn.execute("""
                INSERT OR REPLACE INTO detections (
                    id, document_id, page_number, type, label, confidence, bbox_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                det.id, doc_id, page_data.page, det.type.value,
                det.label, det.confidence, bbox_json, metadata_json
            ))


def get_page_data(doc_id: str, page_number: int) -> Optional[PageData]:
    with get_db() as conn:
        row = conn.execute("""
            SELECT data_json FROM pages WHERE document_id = ? AND page_number = ?
        """, (doc_id, page_number)).fetchone()
        if not row:
            return None
        return PageData.model_validate_json(row["data_json"])


def get_all_pages_data(doc_id: str) -> List[PageData]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT data_json FROM pages WHERE document_id = ? ORDER BY page_number ASC
        """, (doc_id,)).fetchall()
        return [PageData.model_validate_json(r["data_json"]) for r in rows]


def get_document_detections(doc_id: str, detection_type: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db() as conn:
        if detection_type:
            rows = conn.execute("""
                SELECT * FROM detections WHERE document_id = ? AND type = ? ORDER BY page_number ASC
            """, (doc_id, detection_type)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM detections WHERE document_id = ? ORDER BY page_number ASC
            """, (doc_id,)).fetchall()
        
        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "document_id": r["document_id"],
                "page_number": r["page_number"],
                "type": r["type"],
                "label": r["label"],
                "confidence": r["confidence"],
                "bbox": json.loads(r["bbox_json"]) if r["bbox_json"] else None,
                "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else {},
            })
        return results
