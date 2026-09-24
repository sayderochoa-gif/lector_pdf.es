import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from tests.generate_test_pdfs import TEST_DIR


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["ocr_available"] is True


def test_upload_invalid_extension(client):
    fake_file = io.BytesIO(b"Hello world")
    response = client.post(
        "/api/documents/upload",
        files={"file": ("document.txt", fake_file, "text/plain")},
    )
    assert response.status_code == 400
    assert "Solo se aceptan archivos PDF" in response.json()["detail"]


def test_upload_corrupt_header(client):
    fake_pdf = io.BytesIO(b"NOT_A_PDF_CONTENT")
    response = client.post(
        "/api/documents/upload",
        files={"file": ("fake.pdf", fake_pdf, "application/pdf")},
    )
    assert response.status_code == 400
    assert "no es un documento PDF válido" in response.json()["detail"]


def test_full_document_api_lifecycle(client):
    """Test full document lifecycle: upload -> status -> pages -> search -> query."""
    pdf_path = TEST_DIR / "test1_digital_text.pdf"
    assert pdf_path.exists()

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    # 1. Upload
    res_upload = client.post(
        "/api/documents/upload",
        files={"file": ("test1_digital_text.pdf", io.BytesIO(file_bytes), "application/pdf")},
    )
    assert res_upload.status_code == 201
    doc_data = res_upload.json()
    doc_id = doc_data["id"]
    assert doc_id is not None
    assert doc_data["page_count"] == 1

    # 2. Get document detail
    res_get = client.get(f"/api/documents/{doc_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == doc_id

    # 3. Wait briefly for background worker to process single page
    import time
    for _ in range(20):
        res_status = client.get(f"/api/documents/{doc_id}/status")
        if res_status.json()["status"] == "completed":
            break
        time.sleep(0.3)

    assert res_status.json()["status"] == "completed"

    # 4. Get page 1 data
    res_page = client.get(f"/api/documents/{doc_id}/pages/1")
    assert res_page.status_code == 200
    page_info = res_page.json()
    assert page_info["page"] == 1
    assert "CONTRATO" in page_info["text"]

    # 5. Get page 1 image
    res_img = client.get(f"/api/documents/{doc_id}/pages/1/image")
    assert res_img.status_code == 200
    assert "image" in res_img.headers.get("content-type", "")

    # 6. Search text
    res_search = client.get(f"/api/documents/{doc_id}/search?q=contrato")
    assert res_search.status_code == 200
    search_json = res_search.json()
    assert search_json["total_matches"] >= 1

    # 7. Ask AI question
    res_query = client.post(
        f"/api/documents/{doc_id}/query",
        json={"query": "¿En qué página aparece la palabra contrato?"},
    )
    assert res_query.status_code == 200
    query_json = res_query.json()
    assert query_json["found"] is True
    assert 1 in query_json["pages_found"]

    # 8. Get all results / detections
    res_results = client.get(f"/api/documents/{doc_id}/results")
    assert res_results.status_code == 200
    assert "detections" in res_results.json()

    # 9. Verify /status endpoint returns complete DocumentDetail fields
    res_status = client.get(f"/api/documents/{doc_id}/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert "filesize" in status_data and status_data["filesize"] > 0
    assert "created_at" in status_data and status_data["created_at"] is not None
    assert "updated_at" in status_data and status_data["updated_at"] is not None
    assert "summary_counts" in status_data


def test_upload_octet_stream_mime(client):
    """Test that PDF files uploaded with application/octet-stream are accepted."""
    pdf_path = TEST_DIR / "test1_digital_text.pdf"
    assert pdf_path.exists()

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    res = client.post(
        "/api/documents/upload",
        files={"file": ("test_stream.pdf", io.BytesIO(file_bytes), "application/octet-stream")},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["id"] is not None
    assert data["filename"] == "test_stream.pdf"
    assert data["filesize"] == len(file_bytes)
