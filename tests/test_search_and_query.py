import pymupdf
import pytest
from backend.app.models.schemas import PageData
from backend.app.services.pdf_processor import pdf_processor
from backend.app.services.query_interpreter import query_interpreter
from backend.app.services.search_engine import search_engine
from tests.generate_test_pdfs import TEST_DIR


def test_accent_insensitive_search():
    """Verify that searching without accents finds accented words in test12_accents.pdf."""
    pdf_path = TEST_DIR / "test12_accents.pdf"
    assert pdf_path.exists()

    with pymupdf.open(str(pdf_path)) as doc:
        page_data = pdf_processor.process_page(doc, 0, "test-doc-accents")
        pages = [page_data]

        # 1. Search 'bogota' (no accent) against 'Bogotá'
        matches_bogota = search_engine.search_text_in_pages(pages, "bogota")
        assert len(matches_bogota) >= 1
        assert "Bogotá" in matches_bogota[0].snippet

        # 2. Search 'facturacion' (no accent) against 'facturación'
        matches_fac = search_engine.search_text_in_pages(pages, "facturacion")
        assert len(matches_fac) >= 1
        assert "facturación" in matches_fac[0].snippet

        # 3. Search 'vehiculo' against 'vehículo'
        matches_veh = search_engine.search_text_in_pages(pages, "vehiculo")
        assert len(matches_veh) >= 1


def test_repeated_words_multiple_pages():
    """Verify finding the word 'factura' across multiple pages in test11_repeated_words.pdf."""
    pdf_path = TEST_DIR / "test11_repeated_words.pdf"
    assert pdf_path.exists()

    pages = []
    with pymupdf.open(str(pdf_path)) as doc:
        for i in range(len(doc)):
            pages.append(pdf_processor.process_page(doc, i, "test-doc-repeated"))

    # Search 'factura'
    matches = search_engine.search_text_in_pages(pages, "factura")
    matched_pages = sorted(list(set(m.page for m in matches)))
    assert matched_pages == [1, 3, 5]

    # Query interpretation for count
    count_resp = query_interpreter.interpret_and_execute(
        "¿Cuántas páginas contienen la palabra factura?", pages
    )
    assert count_resp.found is True
    assert "3 página(s)" in count_resp.explanation
    assert count_resp.pages_found == [1, 3, 5]


def test_page_summary_query():
    """Verify page summary query format."""
    dummy_page = PageData(
        page=15,
        width=595,
        height=842,
        text="En esta página 15 se encuentra el anexo de especificaciones técnicas del contrato.",
        has_text_layer=True,
        ocr_applied=False,
        tables=[],
        signatures=[],
        qr_codes=[],
    )

    resp = query_interpreter.interpret_and_execute("¿Qué contiene la página 15?", [dummy_page])
    assert resp.found is True
    assert "Página 15" in resp.explanation
    assert "especificaciones técnicas" in resp.explanation


def test_identification_number_query():
    """Verify search for identification number."""
    dummy_page = PageData(
        page=1,
        width=595,
        height=842,
        text="El contratista JUAN PÉREZ identificado con cédula de ciudadanía 123456789 presentó su oferta.",
        has_text_layer=True,
        ocr_applied=False,
    )

    resp = query_interpreter.interpret_and_execute(
        "¿Existe el número de identificación 123456789?", [dummy_page]
    )
    assert resp.found is True
    assert resp.pages_found == [1]
    assert "123456789" in resp.explanation
