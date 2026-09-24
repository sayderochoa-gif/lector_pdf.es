import uuid
import pymupdf
import pytest
from backend.app.services.background_worker import _sync_process_document
from backend.app.database import create_document, get_all_pages_data, get_document
from backend.app.services.pdf_processor import pdf_processor
from backend.app.services.query_interpreter import query_interpreter
from tests.generate_test_pdfs import TEST_DIR


def test_pdf_test5_blurry_enhancement():
    """TEST 5: PDF with blurry / degraded text processed through CLAHE & sharpening."""
    pdf_path = TEST_DIR / "test5_blurry.pdf"
    assert pdf_path.exists()

    with pymupdf.open(str(pdf_path)) as doc:
        p_data = pdf_processor.process_page(doc, 0, f"blurry-{uuid.uuid4().hex[:6]}")
        assert p_data.ocr_applied is True
        text_lower = p_data.text.lower()
        # Should extract text despite the Gaussian blur
        assert len(p_data.text) > 10


def test_pdf_test10_mixed_multimodal():
    """TEST 10: PDF with mixed layout (text + photo of tree + table + signature line)."""
    pdf_path = TEST_DIR / "test10_mixed.pdf"
    assert pdf_path.exists()

    with pymupdf.open(str(pdf_path)) as doc:
        p_data = pdf_processor.process_page(doc, 0, f"mixed-{uuid.uuid4().hex[:6]}")
        # Must have digital text layer
        assert p_data.has_text_layer is True
        assert "INFORME INTEGRAL" in p_data.text
        # Must detect embedded photo
        assert len(p_data.images) >= 1
        # Must detect table grid
        assert len(p_data.tables) >= 1


def test_pdf_test13_difficult_page_deskew_and_denoise():
    """TEST 13: PDF with noisy, tilted, low-contrast page."""
    pdf_path = TEST_DIR / "test13_difficult.pdf"
    assert pdf_path.exists()

    with pymupdf.open(str(pdf_path)) as doc:
        p_data = pdf_processor.process_page(doc, 0, f"difficult-{uuid.uuid4().hex[:6]}")
        assert p_data.ocr_applied is True
        assert len(p_data.text) > 0
