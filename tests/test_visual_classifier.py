import pymupdf
import pytest
from backend.app.models.schemas import BoundingBox, PageData, VisualDetection
from backend.app.services.pdf_processor import pdf_processor
from backend.app.services.query_interpreter import query_interpreter
from tests.generate_test_pdfs import TEST_DIR


def test_visual_detection_on_images_pdf():
    """Verify visual elements (tree/vegetation, car/vehicle) detected in test4_images.pdf."""
    pdf_path = TEST_DIR / "test4_images.pdf"
    assert pdf_path.exists()

    with pymupdf.open(str(pdf_path)) as doc:
        page_data = pdf_processor.process_page(doc, 0, "test-doc-images")
        assert len(page_data.images) >= 1

        # Check visual objects
        categories = [o.metadata.get("category") for o in page_data.objects]
        assert "tree" in categories or "vehicle" in categories or len(page_data.images) >= 2


def test_critical_differentiation_text_vs_visual():
    """
    CRITICAL PROMPT TEST:
    A page contains ONLY the sentence: 'El árbol fue plantado en 2024'
    and NO visual images or detections of trees.
    A query for '¿Hay una imagen de un árbol?' MUST NOT match simply based on the word 'árbol'!
    """
    page_text_only = PageData(
        page=1,
        width=595,
        height=842,
        text="El árbol fue plantado en el año 2024 según el reporte forestal.",
        has_text_layer=True,
        ocr_applied=False,
        objects=[],  # NO VISUAL OBJECTS
        images=[],   # NO IMAGES
        qr_codes=[],
        barcodes=[],
        signatures=[],
        stamps=[],
        tables=[],
    )

    # 1. Ask for visual image
    resp_visual = query_interpreter.interpret_and_execute(
        "¿Hay una imagen de un árbol?", [page_text_only]
    )
    # MUST BE FALSE / NOT FOUND because there is NO visual image of a tree!
    assert resp_visual.found is False
    assert resp_visual.status == "not_found"
    assert "No encontré evidencia visual" in resp_visual.explanation

    # 2. Ask for the word / text
    resp_text = query_interpreter.interpret_and_execute(
        "¿Existe la palabra árbol?", [page_text_only]
    )
    # MUST BE TRUE / FOUND because the word exists in text!
    assert resp_text.found is True
    assert resp_text.status == "found"
    assert len(resp_text.matches) >= 1
    assert resp_text.matches[0].type == "text"


def test_ambiguous_keyword_returns_both_categories():
    """
    When user searches 'árbol' on a page that has BOTH text and an image of a tree,
    the system must return both clearly differentiated.
    """
    page_mixed = PageData(
        page=1,
        width=595,
        height=842,
        text="El árbol fue plantado en 2024.",
        has_text_layer=True,
        ocr_applied=False,
        objects=[
            VisualDetection(
                id="tree-1",
                type="visual",
                label="Árbol / Vegetación",
                confidence=0.91,
                bbox=BoundingBox(x=0.1, y=0.1, width=0.3, height=0.3),
                metadata={"category": "tree"},
            )
        ],
        images=[],
    )

    resp = query_interpreter.interpret_and_execute("árbol", [page_mixed])
    assert resp.found is True
    # Must report both visual and textual matches
    assert "Coincidencia Visual" in resp.explanation
    assert "Coincidencia Textual" in resp.explanation
    types = [m.type for m in resp.matches]
    assert "visual" in types
    assert "text" in types
