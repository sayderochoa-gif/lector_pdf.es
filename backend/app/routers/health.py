import os
import pytesseract
from fastapi import APIRouter
from backend.app.config import settings
from backend.app.services.visual_classifier import visual_classifier

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check():
    # Check tesseract
    tess_ok = False
    tess_version = "unavailable"
    try:
        tess_version = str(pytesseract.get_tesseract_version())
        tess_ok = True
    except Exception:
        pass

    # Check onnx model
    onnx_ok = visual_classifier.session is not None

    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.version,
        "ocr_available": tess_ok,
        "tesseract_version": tess_version,
        "vision_model_loaded": onnx_ok,
    }
