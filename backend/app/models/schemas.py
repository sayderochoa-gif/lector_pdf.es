from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DetectionType(str, Enum):
    TEXT = "text"
    VISUAL = "visual"
    QR_CODE = "qr_code"
    BARCODE = "barcode"
    SIGNATURE = "signature"
    STAMP = "stamp"
    TABLE = "table"
    DIAGRAM = "diagram"
    LOGO = "logo"
    PHOTO = "photo"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class BoundingBox(BaseModel):
    x: float = Field(..., description="Left coordinate in normalized or pixel coordinates")
    y: float = Field(..., description="Top coordinate in normalized or pixel coordinates")
    width: float = Field(..., description="Width")
    height: float = Field(..., description="Height")
    page_width: float = 1.0
    page_height: float = 1.0


class VisualDetection(BaseModel):
    id: str
    type: DetectionType
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: Optional[BoundingBox] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PageData(BaseModel):
    page: int
    width: float
    height: float
    text: str = ""
    has_text_layer: bool = False
    ocr_applied: bool = False
    page_type: str = "texto"  # "imagen" | "texto"
    extracted_by: str = "pymupdf"  # "tesseract" | "pymupdf"
    opencv_review: Optional[Dict[str, Any]] = None
    objects: List[VisualDetection] = Field(default_factory=list)
    qr_codes: List[VisualDetection] = Field(default_factory=list)
    barcodes: List[VisualDetection] = Field(default_factory=list)
    signatures: List[VisualDetection] = Field(default_factory=list)
    stamps: List[VisualDetection] = Field(default_factory=list)
    images: List[VisualDetection] = Field(default_factory=list)
    tables: List[VisualDetection] = Field(default_factory=list)
    confidence: Dict[str, float] = Field(default_factory=dict)
    image_url: str = ""


class DocumentSummaryCounts(BaseModel):
    document_type: str = "desconocido"  # "imagen" | "texto" | "mixto"
    validation_status: str = "validado"
    validation_details: str = ""
    text_pages: int = 0
    ocr_pages: int = 0
    qr_codes: int = 0
    barcodes: int = 0
    signatures: int = 0
    stamps: int = 0
    images: int = 0
    tables: int = 0
    visual_objects: int = 0


class DocumentDetail(BaseModel):
    id: str
    filename: str
    filesize: int
    page_count: int
    status: DocumentStatus
    document_type: str = "desconocido"  # "imagen" | "texto" | "mixto"
    validation_details: Optional[str] = None
    current_page: int = 0
    current_step: str = ""
    progress_percent: int = 0
    created_at: str
    updated_at: str
    error_message: Optional[str] = None
    summary_counts: DocumentSummaryCounts = Field(default_factory=DocumentSummaryCounts)


class QueryMatch(BaseModel):
    page: int
    type: str  # text, visual, qr, barcode, signature, stamp, table, diagram, logo
    confidence: float
    label: str
    snippet: Optional[str] = None
    bbox: Optional[BoundingBox] = None
    metadata: Optional[Dict[str, Any]] = None


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    found: bool
    status: str  # found, possible, not_found
    query: str
    intent: str
    explanation: str
    matches: List[QueryMatch] = Field(default_factory=list)
    total_matches: int = 0
    pages_found: List[int] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    exact_match: bool = False
    case_sensitive: bool = False


class SearchResponse(BaseModel):
    query: str
    total_matches: int
    matches: List[QueryMatch] = Field(default_factory=list)
