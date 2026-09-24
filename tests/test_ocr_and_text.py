import numpy as np
import pytest
from PIL import Image, ImageDraw
import pymupdf

from backend.app.services.ocr_engine import ocr_engine
from backend.app.services.pdf_processor import pdf_processor
from tests.generate_test_pdfs import TEST_DIR


def test_ocr_engine_preprocessing():
    """Verify all image preprocessing steps execute properly."""
    # Create sample RGB image
    sample = np.full((300, 400, 3), 200, dtype=np.uint8)
    cv2_img = sample.copy()

    processed = ocr_engine.preprocess_image(
        cv2_img, deskew=True, denoise=True, enhance_contrast=True, sharpen=True, binarize=True
    )
    assert len(processed.shape) == 2  # Converted to 2D grayscale/binary
    assert processed.shape[0] >= 300
    assert processed.shape[1] >= 400


def test_ocr_extraction_on_scanned_pdf():
    """Verify OCR extracts text from scanned PDF (TEST 2)."""
    pdf_path = TEST_DIR / "test2_scanned_text.pdf"
    assert pdf_path.exists()

    with pymupdf.open(str(pdf_path)) as doc:
        page_data = pdf_processor.process_page(doc, 0, "test-doc-scanned")
        assert page_data.ocr_applied is True
        assert page_data.has_text_layer is False
        assert len(page_data.text) > 0
        text_lower = page_data.text.lower()
        # Should extract key words from the scanned text
        assert any(w in text_lower for w in ["documento", "escaneado", "prueba", "contrato", "factura", "tesseract"])


def test_smart_ocr_decision_on_digital_text():
    """Verify that a digital text PDF does NOT trigger unnecessary OCR (TEST 1)."""
    pdf_path = TEST_DIR / "test1_digital_text.pdf"
    assert pdf_path.exists()

    with pymupdf.open(str(pdf_path)) as doc:
        page_data = pdf_processor.process_page(doc, 0, "test-doc-digital")
        assert page_data.ocr_applied is False
        assert page_data.has_text_layer is True
        assert page_data.page_type == "texto"
        assert page_data.extracted_by == "pymupdf"
        assert "CONTRATO DE PRESTACIÓN DE SERVICIOS" in page_data.text
        assert "123456789" in page_data.text


def test_pymupdf_document_validation():
    """Verify PyMuPDF validates whether PDF is primarily image or digital text."""
    # 1. Digital text document
    digital_pdf = TEST_DIR / "test1_digital_text.pdf"
    v_digital = pdf_processor.validate_pdf_document(str(digital_pdf))
    assert v_digital["document_type"] == "texto"
    assert v_digital["text_pages"] == 1
    assert v_digital["image_pages"] == 0

    # 2. Scanned / image document
    scanned_pdf = TEST_DIR / "test2_scanned_text.pdf"
    v_scanned = pdf_processor.validate_pdf_document(str(scanned_pdf))
    assert v_scanned["document_type"] == "imagen"
    assert v_scanned["text_pages"] == 0
    assert v_scanned["image_pages"] == 1
    assert "OpenCV" in v_scanned["verdict"]
    assert "Tesseract" in v_scanned["verdict"]


def test_opencv_image_review_and_diagnostics():
    """Verify OpenCV reviews image quality (sharpness, blur, contrast, skew, noise)."""
    scanned_pdf = TEST_DIR / "test2_scanned_text.pdf"
    with pymupdf.open(str(scanned_pdf)) as doc:
        page_data = pdf_processor.process_page(doc, 0, "test-doc-opencv-review")
        assert page_data.opencv_review is not None
        rev = page_data.opencv_review
        assert "sharpness_score" in rev
        assert "is_blurry" in rev
        assert "brightness" in rev
        assert "contrast" in rev
        assert "skew_angle" in rev
        assert "diagnosis" in rev
        assert "corrections_applied" in rev
        assert len(rev["corrections_applied"]) >= 1


def test_tesseract_qa_scanned_pdf():
    """Verify that user questions are answered based on what Tesseract extracted from scanned PDF."""
    from backend.app.services.query_interpreter import query_interpreter

    scanned_pdf = TEST_DIR / "test2_scanned_text.pdf"
    with pymupdf.open(str(scanned_pdf)) as doc:
        page_data = pdf_processor.process_page(doc, 0, "test-doc-qa-scanned")
    pages = [page_data]

    # 1. Summary of document content
    res_summary = query_interpreter.interpret_and_execute("¿De qué trata el documento?", pages)
    assert res_summary.found is True
    assert "Tesseract OCR" in res_summary.explanation
    assert "Escaneado" in res_summary.explanation

    # 2. Query what Tesseract extracted
    res_tess = query_interpreter.interpret_and_execute("¿Qué información extrajo Tesseract?", pages)
    assert res_tess.found is True
    assert "Tesseract OCR" in res_tess.explanation
    assert "OpenCV" in res_tess.explanation

    # 3. Query document date
    res_date = query_interpreter.interpret_and_execute("¿Cuál es la fecha del documento?", pages)
    assert res_date.found is True
    assert any(w in res_date.explanation for w in ["Septiembre", "2026", "Fecha"])

    # 4. Query identification / NIT
    res_nit = query_interpreter.interpret_and_execute("¿Cuál es el NIT?", pages)
    assert res_nit.found is True
    assert "NIT" in res_nit.explanation or "Identificación" in res_nit.explanation


def test_content_qa_digital_pdf():
    """Verify that user questions about content are answered from digital text."""
    from backend.app.services.query_interpreter import query_interpreter

    digital_pdf = TEST_DIR / "test1_digital_text.pdf"
    with pymupdf.open(str(digital_pdf)) as doc:
        page_data = pdf_processor.process_page(doc, 0, "test-doc-qa-digital")
    pages = [page_data]

    # 1. Contractor
    res_party = query_interpreter.interpret_and_execute("¿Quién es el contratista?", pages)
    assert res_party.found is True
    assert any(w in res_party.explanation for w in ["JUAN PÉREZ", "EMPRESA TECNOLÓGICA", "contratista"])

    # 2. Duration / Vigencia
    res_vigencia = query_interpreter.interpret_and_execute("¿Cuál es la vigencia del contrato?", pages)
    assert res_vigencia.found is True
    assert any(w in res_vigencia.explanation for w in ["seis meses", "duración", "VIGENCIA"])
