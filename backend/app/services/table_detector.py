import uuid
from typing import Any, Dict, List, Optional
import cv2
import numpy as np

from backend.app.models.schemas import BoundingBox, DetectionType, VisualDetection


class TableDetector:
    def __init__(self):
        pass

    def detect_tables(
        self,
        pdf_page: Any,
        img_np: np.ndarray,
        page_num: int,
    ) -> List[VisualDetection]:
        """Detects tables using PyMuPDF vector table finder and OpenCV morphological grid analysis."""
        tables: List[VisualDetection] = []
        h, w = img_np.shape[:2]

        # 1. Native PyMuPDF Table Finder (Vector tables)
        if pdf_page is not None and hasattr(pdf_page, "find_tables"):
            try:
                tabs = pdf_page.find_tables()
                for i, tab in enumerate(tabs):
                    bbox_rect = tab.bbox
                    pw = pdf_page.rect.width
                    ph = pdf_page.rect.height
                    bbox = BoundingBox(
                        x=bbox_rect[0] / pw,
                        y=bbox_rect[1] / ph,
                        width=(bbox_rect[2] - bbox_rect[0]) / pw,
                        height=(bbox_rect[3] - bbox_rect[1]) / ph,
                        page_width=float(w),
                        page_height=float(h),
                    )
                    row_count = tab.row_count
                    col_count = tab.col_count
                    
                    # Extract small text preview of headers or cells
                    extracted = tab.extract()
                    header_cells = [str(c) for c in (extracted[0] if extracted else []) if c]
                    preview_text = " | ".join(header_cells[:5]) if header_cells else ""

                    tables.append(
                        VisualDetection(
                            id=f"tab-vec-{page_num}-{i}-{uuid.uuid4().hex[:6]}",
                            type=DetectionType.TABLE,
                            label=f"Tabla ({row_count} filas × {col_count} columnas)",
                            confidence=0.96,
                            bbox=bbox,
                            metadata={
                                "rows": row_count,
                                "columns": col_count,
                                "method": "vector_mupdf",
                                "headers_preview": preview_text,
                            },
                        )
                    )
            except Exception:
                pass

        # 2. Scanned / Raster Grid Detection via OpenCV morphology
        # Only run if no vector tables were detected, or to complement scanned pages
        if len(tables) == 0:
            cv_tables = self._detect_raster_tables(img_np, page_num)
            tables.extend(cv_tables)

        return tables

    def _detect_raster_tables(self, img_np: np.ndarray, page_num: int) -> List[VisualDetection]:
        results: List[VisualDetection] = []
        try:
            h, w = img_np.shape[:2]
            gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY) if len(img_np.shape) == 3 else img_np

            # Adaptive threshold
            binary = cv2.adaptiveThreshold(
                ~gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, -2
            )

            # Horizontal lines
            h_size = max(20, w // 30)
            h_structure = cv2.getStructuringElement(cv2.MORPH_RECT, (h_size, 1))
            h_lines = cv2.erode(binary, h_structure)
            h_lines = cv2.dilate(h_lines, h_structure)

            # Vertical lines
            v_size = max(20, h // 30)
            v_structure = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_size))
            v_lines = cv2.erode(binary, v_structure)
            v_lines = cv2.dilate(v_lines, v_structure)

            # Table grid is the union of horizontal and vertical lines
            table_mask = cv2.add(h_lines, v_lines)
            contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for i, cnt in enumerate(contours):
                area = cv2.contourArea(cnt)
                # Ignore very small or whole-page contours
                if area > (w * h * 0.03) and area < (w * h * 0.85):
                    bx, by, bw, bh = cv2.boundingRect(cnt)
                    aspect = float(bw) / float(bh) if bh > 0 else 0
                    if 0.3 < aspect < 3.5:
                        # Count intersections (cells) inside this region
                        intersection = cv2.bitwise_and(h_lines[by:by+bh, bx:bx+bw], v_lines[by:by+bh, bx:bx+bw])
                        pts, _ = cv2.findContours(intersection, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
                        cells_count = max(4, len(pts))
                        
                        bbox = BoundingBox(
                            x=bx / w,
                            y=by / h,
                            width=bw / w,
                            height=bh / h,
                            page_width=float(w),
                            page_height=float(h),
                        )
                        results.append(
                            VisualDetection(
                                id=f"tab-cv-{page_num}-{i}-{uuid.uuid4().hex[:6]}",
                                type=DetectionType.TABLE,
                                label=f"Tabla detectada ({cells_count} celdas aprox.)",
                                confidence=0.88,
                                bbox=bbox,
                                metadata={
                                    "estimated_cells": cells_count,
                                    "method": "opencv_morphology",
                                },
                            )
                        )
        except Exception:
            pass
        return results


table_detector = TableDetector()
