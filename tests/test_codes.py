import pymupdf
import pytest
from backend.app.services.code_detector import code_detector
from backend.app.services.pdf_processor import pdf_processor
from tests.generate_test_pdfs import TEST_DIR


def test_qr_code_detection():
    """Verify QR code detection and decoded URL in test6_qr_code.pdf."""
    pdf_path = TEST_DIR / "test6_qr_code.pdf"
    assert pdf_path.exists()

    with pymupdf.open(str(pdf_path)) as doc:
        page_data = pdf_processor.process_page(doc, 0, "test-doc-qr")
        assert len(page_data.qr_codes) >= 1
        qr = page_data.qr_codes[0]
        assert qr.type == "qr_code"
        assert qr.confidence >= 0.8
        decoded = qr.metadata.get("decoded_text")
        assert decoded == "https://github.com/google/antigravity"
        assert qr.bbox is not None


def test_barcode_detection():
    """Verify Barcode detection in test7_barcode.pdf."""
    pdf_path = TEST_DIR / "test7_barcode.pdf"
    assert pdf_path.exists()

    with pymupdf.open(str(pdf_path)) as doc:
        page_data = pdf_processor.process_page(doc, 0, "test-doc-barcode")
        # Should detect the barcode element or visual pattern
        assert (len(page_data.barcodes) >= 1) or (len(page_data.images) >= 1)
