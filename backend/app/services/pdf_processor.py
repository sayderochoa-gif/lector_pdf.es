import os
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import cv2
import numpy as np
import pymupdf  # PyMuPDF

from backend.app.config import PAGE_IMAGES_DIR, settings
from backend.app.models.schemas import (
    DocumentSummaryCounts,
    PageData,
    VisualDetection,
)
from backend.app.services.code_detector import code_detector
from backend.app.services.ocr_engine import ocr_engine
from backend.app.services.signature_detector import signature_stamp_detector
from backend.app.services.table_detector import table_detector
from backend.app.services.visual_classifier import visual_classifier


class PDFProcessor:
    def __init__(self):
        pass

    def get_document_page_count(self, file_path: str) -> int:
        """Quickly opens PDF to retrieve page count without loading entire document."""
        with pymupdf.open(file_path) as doc:
            return len(doc)

    def validate_pdf_document(self, file_path: str) -> Dict[str, Any]:
        """
        Validates with PyMuPDF whether the PDF is primarily 'imagen', 'texto', or 'mixto'.
        Inspects text layer existence, character density, and embedded raster images.
        """
        with pymupdf.open(file_path) as doc:
            total_pages = len(doc)
            text_pages = 0
            image_pages = 0
            page_details = []

            for idx, page in enumerate(doc):
                page_num = idx + 1
                raw_text = page.get_text("text").strip()
                meaningful_chars = len([c for c in raw_text if c.isalnum()])
                images = page.get_images()

                # Classification based on PyMuPDF inspection
                if meaningful_chars >= 25:
                    p_type = "texto"
                    text_pages += 1
                else:
                    p_type = "imagen"
                    image_pages += 1

                page_details.append({
                    "page": page_num,
                    "type": p_type,
                    "chars": meaningful_chars,
                    "images_count": len(images),
                })

            if text_pages == total_pages:
                doc_type = "texto"
                verdict = "Documento de texto digital nativo (validado con PyMuPDF)"
            elif image_pages == total_pages:
                doc_type = "imagen"
                verdict = "Documento tipo imagen / escaneado (validado con PyMuPDF; requiere revisión OpenCV y OCR Tesseract)"
            else:
                doc_type = "mixto"
                verdict = f"Documento mixto ({text_pages} páginas de texto digital, {image_pages} de imagen)"

            return {
                "document_type": doc_type,
                "total_pages": total_pages,
                "text_pages": text_pages,
                "image_pages": image_pages,
                "verdict": verdict,
                "pages": page_details,
            }

    def process_page(
        self,
        doc: pymupdf.Document,
        page_index: int,
        doc_id: str,
        step_callback: Optional[Callable[[str], None]] = None,
    ) -> PageData:
        """
        Processes a single PDF page:
        1. PyMuPDF renders high-resolution image.
        2. PyMuPDF validates whether page is image or text.
        3. OpenCV reviews image quality (blur, contrast, brightness, skew, noise) and optimizes it.
        4. Tesseract extracts information when page is an image.
        5. Detects QR/barcodes, signatures/stamps, and tables.
        """
        page_num = page_index + 1
        page = doc[page_index]
        page_rect = page.rect
        width = float(page_rect.width)
        height = float(page_rect.height)

        # ---------------------------------------------------------------------
        # 1. High-Resolution Rendering for Vision & Web Viewer
        # ---------------------------------------------------------------------
        zoom = settings.render_dpi / 72.0
        matrix = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        # Convert pixmap to numpy BGR image for OpenCV
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 3:
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        else:
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)

        # Save web-optimized image for PDF viewer
        page_image_filename = f"{doc_id}_page_{page_num}.webp"
        page_image_path = PAGE_IMAGES_DIR / page_image_filename
        cv2.imwrite(str(page_image_path), img_bgr, [cv2.IMWRITE_WEBP_QUALITY, 85])
        image_url = f"/api/documents/{doc_id}/pages/{page_num}/image"

        # ---------------------------------------------------------------------
        # 2. PyMuPDF Validation: Is the page Image or Text?
        # ---------------------------------------------------------------------
        if step_callback:
            step_callback("Validando tipo de archivo con PyMuPDF")

        raw_digital_text = page.get_text("text").strip()
        meaningful_chars = len([c for c in raw_digital_text if c.isalnum()])
        has_text_layer = meaningful_chars >= 25
        page_type = "texto" if has_text_layer else "imagen"

        # ---------------------------------------------------------------------
        # 3. OpenCV Image Review & Preprocessing
        # ---------------------------------------------------------------------
        if step_callback:
            step_callback(f"Revisando calidad de imagen con OpenCV ({page_type})")

        preprocessed_img, opencv_review = ocr_engine.review_and_preprocess(
            img_bgr, is_digital_text=has_text_layer
        )

        # ---------------------------------------------------------------------
        # 4. Text Extraction (Tesseract OCR for images, PyMuPDF for digital text)
        # ---------------------------------------------------------------------
        ocr_applied = False
        final_text = raw_digital_text
        confidence_map: Dict[str, float] = {}
        extracted_by = "pymupdf"

        if not has_text_layer:
            # PyMuPDF validated page as image/scanned; extract with Tesseract
            if step_callback:
                step_callback("Extrayendo información con Tesseract OCR")
            ocr_res = ocr_engine.extract_text_and_data(preprocessed_img, preprocess=False)
            final_text = ocr_res["text"]
            ocr_applied = True
            extracted_by = "tesseract"
            confidence_map["ocr"] = ocr_res["confidence"]
            confidence_map["tesseract"] = ocr_res["confidence"]
        else:
            confidence_map["text_layer"] = 1.0

        # ---------------------------------------------------------------------
        # 5. Code Detection (QR and Barcodes)
        # ---------------------------------------------------------------------
        if step_callback:
            step_callback("Detectando códigos")
        qr_codes, barcodes = code_detector.detect_codes(img_bgr, page_num)

        # ---------------------------------------------------------------------
        # 6. Signature & Stamp Detection
        # ---------------------------------------------------------------------
        if step_callback:
            step_callback("Detectando firmas y sellos")
        signatures, stamps = signature_stamp_detector.detect_signatures_and_stamps(
            img_bgr, page_num, page_text=final_text, pdf_page=page
        )

        # ---------------------------------------------------------------------
        # 7. Table Detection
        # ---------------------------------------------------------------------
        if step_callback:
            step_callback("Detectando tablas")
        tables = table_detector.detect_tables(page, img_bgr, page_num)

        # ---------------------------------------------------------------------
        # 8. Visual Objects, Photos, Diagrams, Logos
        # ---------------------------------------------------------------------
        if step_callback:
            step_callback("Analizando elementos visuales")
        objects, images = visual_classifier.analyze_page_visual_elements(page, img_bgr, page_num)

        # ---------------------------------------------------------------------
        # 9. Construct and Return PageData
        # ---------------------------------------------------------------------
        return PageData(
            page=page_num,
            width=width,
            height=height,
            text=final_text,
            has_text_layer=has_text_layer,
            ocr_applied=ocr_applied,
            page_type=page_type,
            extracted_by=extracted_by,
            opencv_review=opencv_review,
            objects=objects,
            qr_codes=qr_codes,
            barcodes=barcodes,
            signatures=signatures,
            stamps=stamps,
            images=images,
            tables=tables,
            confidence=confidence_map,
            image_url=image_url,
        )


pdf_processor = PDFProcessor()
