import uuid
import pymupdf
import pytest
from backend.app.models.schemas import DocumentSummaryCounts
from backend.app.services.background_worker import _sync_process_document
from backend.app.services.query_interpreter import query_interpreter
from backend.app.database import get_all_pages_data, get_document, create_document
from tests.generate_test_pdfs import TEST_DIR


def test_e2e_20_pages_pdf():
    """TEST 3: End-to-end processing of a 22-page document."""
    pdf_path = TEST_DIR / "test3_20_pages.pdf"
    assert pdf_path.exists()

    doc_id = f"e2e-20-pages-{uuid.uuid4().hex[:6]}"
    # Create DB entry
    create_document(
        doc_id=doc_id,
        filename="test3_20_pages.pdf",
        filepath=str(pdf_path),
        filesize=pdf_path.stat().st_size,
        page_count=22,
    )

    # Process all 22 pages synchronously
    _sync_process_document(doc_id, str(pdf_path))

    # Verify document status
    doc = get_document(doc_id)
    assert doc.status == "completed"
    assert doc.page_count == 22
    assert doc.progress_percent == 100

    # Verify all pages indexed in SQLite
    pages = get_all_pages_data(doc_id)
    assert len(pages) == 22

    # Query for specific page contents
    resp_p7 = query_interpreter.interpret_and_execute("¿En qué páginas se menciona la palabra cliente?", pages)
    assert resp_p7.found is True
    assert 7 in resp_p7.pages_found

    resp_p15 = query_interpreter.interpret_and_execute("¿Qué contiene la página 15?", pages)
    assert resp_p15.found is True
    assert "especificaciones técnicas" in resp_p15.explanation


def test_e2e_qr_and_barcode_queries():
    """TEST 6 & 7: End-to-end QR and Barcode queries."""
    # Process QR pdf
    qr_pdf = TEST_DIR / "test6_qr_code.pdf"
    doc_id_qr = f"e2e-qr-{uuid.uuid4().hex[:6]}"
    create_document(doc_id_qr, "test6_qr_code.pdf", str(qr_pdf), qr_pdf.stat().st_size, 1)
    _sync_process_document(doc_id_qr, str(qr_pdf))
    pages_qr = get_all_pages_data(doc_id_qr)

    # Ask "¿Hay un código QR?"
    resp_qr = query_interpreter.interpret_and_execute("¿Hay un código QR?", pages_qr)
    assert resp_qr.found is True
    assert "Código QR encontrado" in resp_qr.explanation
    assert "https://github.com/google/antigravity" in resp_qr.explanation


def test_e2e_signatures_and_stamps_queries():
    """TEST 8 & 9: End-to-end Signatures and Stamps queries."""
    # Signatures
    sig_pdf = TEST_DIR / "test8_signatures.pdf"
    doc_id_sig = f"e2e-sig-{uuid.uuid4().hex[:6]}"
    create_document(doc_id_sig, "test8_signatures.pdf", str(sig_pdf), sig_pdf.stat().st_size, 1)
    _sync_process_document(doc_id_sig, str(sig_pdf))
    pages_sig = get_all_pages_data(doc_id_sig)

    resp_sig = query_interpreter.interpret_and_execute("¿Hay una firma?", pages_sig)
    assert resp_sig.found is True
    assert resp_sig.status in ["found", "possible"]

    # Stamps
    stamp_pdf = TEST_DIR / "test9_stamps.pdf"
    doc_id_stamp = f"e2e-stamp-{uuid.uuid4().hex[:6]}"
    create_document(doc_id_stamp, "test9_stamps.pdf", str(stamp_pdf), stamp_pdf.stat().st_size, 1)
    _sync_process_document(doc_id_stamp, str(stamp_pdf))
    pages_stamp = get_all_pages_data(doc_id_stamp)

    resp_stamp = query_interpreter.interpret_and_execute("¿Existe un sello?", pages_stamp)
    assert resp_stamp.found is True
    assert resp_stamp.status == "found"
