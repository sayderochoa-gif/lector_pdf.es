import io
import time
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.schemas import PageData, VisualDetection, DetectionType
from backend.app.services.chat_service import chat_service
from backend.app.services.rag_chatbot import rag_chatbot
from tests.generate_test_pdfs import TEST_DIR


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_chat_service_direct_questions():
    """Prueba que el servicio 'chat' responde preguntas directas y simples."""
    dummy_page1 = PageData(
        page=1,
        width=595,
        height=842,
        text="Factura comercial número 001. Contrato firmado en Bogotá.",
        has_text_layer=True,
    )
    dummy_page2 = PageData(
        page=2,
        width=595,
        height=842,
        text="Detalle de la factura y anexos del contrato.",
        has_text_layer=True,
    )
    pages = [dummy_page1, dummy_page2]

    # 1. Conteo de páginas con una palabra
    resp_count = chat_service.process_chat("¿Cuántas páginas contienen la palabra factura?", pages)
    assert resp_count.found is True
    assert resp_count.intent == "chat_count"
    assert "2 página(s)" in resp_count.explanation
    assert resp_count.pages_found == [1, 2]

    # 2. Resumen básico de página específica
    resp_summary = chat_service.process_chat("¿Qué contiene la página 1?", pages)
    assert resp_summary.found is True
    assert resp_summary.intent == "chat_page_summary"
    assert "Página 1" in resp_summary.explanation

    # 3. Búsqueda de identificador
    dummy_id_page = PageData(
        page=1,
        width=595,
        height=842,
        text="Identificación tributaria: NIT 900.123.456-7 perteneciente a la empresa.",
        has_text_layer=True,
    )
    resp_id = chat_service.process_chat("¿Existe el número de identificación 900.123.456-7?", [dummy_id_page])
    assert resp_id.found is True
    assert resp_id.intent == "chat_text_search"
    assert "900.123.456-7" in resp_id.explanation


def test_chatbot_rag_complex_questions():
    """Prueba que el servicio 'chatbot' (RAG con IA) responde preguntas complejas."""
    sig_detection = VisualDetection(
        id="sig-1",
        type=DetectionType.SIGNATURE,
        label="Firma manuscrita",
        confidence=0.95,
        metadata={"kind": "manuscrita"},
    )
    qr_detection = VisualDetection(
        id="qr-1",
        type=DetectionType.QR_CODE,
        label="Código QR",
        confidence=0.99,
        metadata={"decoded_text": "https://validar.gov.co/doc/12345"},
    )
    bc_detection = VisualDetection(
        id="bc-1",
        type=DetectionType.BARCODE,
        label="Código de barras",
        confidence=0.98,
        metadata={"format": "EAN-13", "decoded_text": "7701234567890"},
    )

    page_multimodal = PageData(
        page=1,
        width=595,
        height=842,
        text="Contrato de Prestación de Servicios suscrito entre las partes.",
        has_text_layer=True,
        signatures=[sig_detection],
        qr_codes=[qr_detection],
        barcodes=[bc_detection],
    )
    pages = [page_multimodal]

    # 1. ¿El documento tiene firmas?
    resp_sig = rag_chatbot.process_chatbot("¿El documento tiene firmas?", pages)
    assert resp_sig.found is True
    assert resp_sig.intent == "chatbot_rag_signatures"
    assert "Sí, el documento tiene firmas detectadas" in resp_sig.explanation
    assert 1 in resp_sig.pages_found

    # 2. ¿Hay código QR en el documento?
    resp_qr = rag_chatbot.process_chatbot("¿Hay código QR en el documento?", pages)
    assert resp_qr.found is True
    assert resp_qr.intent == "chatbot_rag_qr"
    assert "Sí, hay código QR en el documento" in resp_qr.explanation
    assert "https://validar.gov.co/doc/12345" in resp_qr.explanation
    assert 1 in resp_qr.pages_found

    # 3. ¿Hay código de barras dentro del documento?
    resp_bc = rag_chatbot.process_chatbot("¿Hay código de barras dentro del documento?", pages)
    assert resp_bc.found is True
    assert resp_bc.intent == "chatbot_rag_barcode"
    assert "Sí, hay código de barras dentro del documento" in resp_bc.explanation
    assert "7701234567890" in resp_bc.explanation
    assert 1 in resp_bc.pages_found

    # 4. ¿De qué trata este documento? (Síntesis RAG)
    resp_summary = rag_chatbot.process_chatbot("¿De qué trata este documento?", pages)
    assert resp_summary.found is True
    assert resp_summary.intent == "chatbot_rag_summary"
    assert "Contrato" in resp_summary.explanation


def test_api_endpoints_chat_and_chatbot(client):
    """Prueba los endpoints HTTP /api/documents/{doc_id}/chat y /chatbot en FastAPI."""
    # 1. Probar con documento mixto (test10_mixed.pdf tiene firmas y tablas)
    pdf_path = TEST_DIR / "test10_mixed.pdf"
    assert pdf_path.exists()

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    res_upload = client.post(
        "/api/documents/upload",
        files={"file": ("test10_mixed.pdf", io.BytesIO(file_bytes), "application/pdf")},
    )
    assert res_upload.status_code == 201
    doc_id = res_upload.json()["id"]

    for _ in range(25):
        st = client.get(f"/api/documents/{doc_id}/status").json()
        if st["status"] == "completed":
            break
        time.sleep(0.4)

    # 1.1 Endpoint /chat (Preguntas simples)
    res_chat = client.post(
        f"/api/documents/{doc_id}/chat",
        json={"query": "¿Qué contiene la página 1?"},
    )
    assert res_chat.status_code == 200
    chat_data = res_chat.json()
    assert chat_data["found"] is True
    assert 1 in chat_data["pages_found"]

    # 1.2 Endpoint /chatbot: ¿El documento tiene firmas? -> Sí
    res_bot_sig = client.post(
        f"/api/documents/{doc_id}/chatbot",
        json={"query": "¿El documento tiene firmas?"},
    )
    assert res_bot_sig.status_code == 200
    bot_sig_data = res_bot_sig.json()
    assert bot_sig_data["found"] is True
    assert "firmas" in bot_sig_data["explanation"].lower()

    # 1.3 Endpoint /chatbot: ¿Hay código QR en este documento? -> No tiene QR (precisión sin alucinaciones)
    res_bot_no_qr = client.post(
        f"/api/documents/{doc_id}/chatbot",
        json={"query": "¿Hay código QR en el documento?"},
    )
    assert res_bot_no_qr.status_code == 200
    assert res_bot_no_qr.json()["found"] is False

    # 2. Probar con documento con código QR (test6_qr_code.pdf)
    pdf_qr_path = TEST_DIR / "test6_qr_code.pdf"
    assert pdf_qr_path.exists()

    with open(pdf_qr_path, "rb") as f:
        qr_bytes = f.read()

    res_upload_qr = client.post(
        "/api/documents/upload",
        files={"file": ("test6_qr_code.pdf", io.BytesIO(qr_bytes), "application/pdf")},
    )
    assert res_upload_qr.status_code == 201
    qr_doc_id = res_upload_qr.json()["id"]

    for _ in range(25):
        st = client.get(f"/api/documents/{qr_doc_id}/status").json()
        if st["status"] == "completed":
            break
        time.sleep(0.4)

    res_bot_qr = client.post(
        f"/api/documents/{qr_doc_id}/chatbot",
        json={"query": "¿Hay código QR en el documento?"},
    )
    assert res_bot_qr.status_code == 200
    bot_qr_data = res_bot_qr.json()
    assert bot_qr_data["found"] is True
    assert "código qr" in bot_qr_data["explanation"].lower() or "qr" in bot_qr_data["explanation"].lower()

    # 3. Probar con documento con código de barras (test7_barcode.pdf)
    pdf_bc_path = TEST_DIR / "test7_barcode.pdf"
    assert pdf_bc_path.exists()

    with open(pdf_bc_path, "rb") as f:
        bc_bytes = f.read()

    res_upload_bc = client.post(
        "/api/documents/upload",
        files={"file": ("test7_barcode.pdf", io.BytesIO(bc_bytes), "application/pdf")},
    )
    assert res_upload_bc.status_code == 201
    bc_doc_id = res_upload_bc.json()["id"]

    for _ in range(25):
        st = client.get(f"/api/documents/{bc_doc_id}/status").json()
        if st["status"] == "completed":
            break
        time.sleep(0.4)

    res_bot_bc = client.post(
        f"/api/documents/{bc_doc_id}/chatbot",
        json={"query": "¿Hay código de barras dentro del documento?"},
    )
    assert res_bot_bc.status_code == 200
    bot_bc_data = res_bot_bc.json()
    assert bot_bc_data["found"] is True
    assert "código de barras" in bot_bc_data["explanation"].lower() or "barras" in bot_bc_data["explanation"].lower()
