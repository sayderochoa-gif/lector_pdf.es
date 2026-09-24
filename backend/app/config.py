import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
PROCESSED_DIR = STORAGE_DIR / "processed"
PAGE_IMAGES_DIR = STORAGE_DIR / "pages"
MODELS_DIR = BASE_DIR / "models"
DB_PATH = STORAGE_DIR / "lector_pdf.db"

# Ensure all directories exist
for directory in [STORAGE_DIR, UPLOAD_DIR, PROCESSED_DIR, PAGE_IMAGES_DIR, MODELS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


class Settings(BaseModel):
    app_name: str = "LectorPDF - AI Document Vision & OCR"
    version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "false").lower() in ("true", "1")
    
    # Upload limits
    max_upload_size_bytes: int = int(os.getenv("MAX_UPLOAD_SIZE", str(100 * 1024 * 1024)))  # 100MB
    allowed_extensions: set[str] = {".pdf"}
    allowed_mime_types: set[str] = {
        "application/pdf",
        "application/x-pdf",
        "application/acrobat",
        "applications/vnd.pdf",
        "text/pdf",
        "application/octet-stream",
        "binary/octet-stream",
    }
    
    # OCR settings
    tesseract_cmd: str = os.getenv("TESSERACT_CMD", "/usr/bin/tesseract")
    tesseract_lang: str = os.getenv("TESSERACT_LANG", "spa+eng")
    
    # Rendering DPI for page analysis and viewer
    render_dpi: int = int(os.getenv("RENDER_DPI", "150"))
    
    # AI / Vision model
    onnx_model_path: Path = MODELS_DIR / "mobilenetv2-7.onnx"
    onnx_model_url: str = os.getenv(
        "ONNX_MODEL_URL",
        "https://github.com/onnx/models/raw/main/validated/vision/classification/mobilenet/model/mobilenetv2-7.onnx"
    )
    enable_cloud_ai: bool = os.getenv("ENABLE_CLOUD_AI", "false").lower() in ("true", "1")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY", None)


settings = Settings()
