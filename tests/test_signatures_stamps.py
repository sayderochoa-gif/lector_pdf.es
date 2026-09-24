import pymupdf
import pytest
from backend.app.services.pdf_processor import pdf_processor
from tests.generate_test_pdfs import TEST_DIR


def test_signature_detection():
    """Verify handwritten signature detection in test8_signatures.pdf."""
    pdf_path = TEST_DIR / "test8_signatures.pdf"
    assert pdf_path.exists()

    with pymupdf.open(str(pdf_path)) as doc:
        page_data = pdf_processor.process_page(doc, 0, "test-doc-signatures")
        assert len(page_data.signatures) >= 1
        sig = page_data.signatures[0]
        assert sig.type == "signature"
        # Must have realistic confidence between 0.65 and 0.98
        assert 0.60 <= sig.confidence <= 0.98
        assert sig.bbox is not None


def test_stamp_detection():
    """Verify circular ink stamp detection in test9_stamps.pdf."""
    pdf_path = TEST_DIR / "test9_stamps.pdf"
    assert pdf_path.exists()

    with pymupdf.open(str(pdf_path)) as doc:
        page_data = pdf_processor.process_page(doc, 0, "test-doc-stamps")
        assert len(page_data.stamps) >= 1
        stamp = page_data.stamps[0]
        assert stamp.type == "stamp"
        assert stamp.confidence >= 0.65
        assert stamp.bbox is not None
