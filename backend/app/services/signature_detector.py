import uuid
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
import pymupdf

from backend.app.models.schemas import BoundingBox, DetectionType, VisualDetection

SIGNATURE_KEYWORDS = [
    "firma", "firmas", "firmante", "firmantes", "firmado", "firmada",
    "rúbrica", "rubrica", "representante", "c.c.", "cedula", "cédula",
    "atentamente", "cordialmente", "aprobado", "recibido", "autorizado",
    "suscribe", "suscrito", "testigo", "interviniente", "contratista",
    "signature", "signed", "signer"
]


class SignatureAndStampDetector:
    def __init__(self):
        pass

    def detect_signatures_and_stamps(
        self,
        img_np: np.ndarray,
        page_num: int,
        page_text: str = "",
        pdf_page: Any = None,
    ) -> Tuple[List[VisualDetection], List[VisualDetection]]:
        """
        Detects handwritten signatures, digital signatures, vector signatures,
        and ink stamps/seals across all PDF document formats.
        Returns: (signatures, stamps)
        """
        signatures: List[VisualDetection] = []
        stamps: List[VisualDetection] = []
        h, w = img_np.shape[:2]

        # 1. Digital PDF Signature Fields & Annotations
        if pdf_page is not None:
            digital_sigs = self._detect_digital_pdf_signatures(pdf_page, page_num, w, h)
            signatures.extend(digital_sigs)

            # 2. Vector Path Signatures (Stylus, Apple Pencil, Acrobat Fill & Sign)
            vector_sigs = self._detect_vector_pdf_signatures(pdf_page, page_num, w, h)
            signatures.extend(vector_sigs)

            # 3. Embedded Signature Stamp Images
            image_sigs = self._detect_embedded_signature_images(pdf_page, page_num, w, h)
            signatures.extend(image_sigs)

        # 4. Computer Vision Detection (Handwritten ink, cursive strokes, stamps)
        cv_sigs, cv_stamps = self._detect_visual_signatures_and_stamps(img_np, page_num, page_text, pdf_page)
        signatures.extend(cv_sigs)
        stamps.extend(cv_stamps)

        # 5. Merge adjacent stroke fragments into unified signature bounding boxes
        signatures = self._merge_adjacent_signatures(signatures, w, h)

        # 6. Filter overlapping detections
        signatures = self._filter_overlaps(signatures)
        stamps = self._filter_overlaps(stamps)

        return signatures, stamps

    def _detect_digital_pdf_signatures(
        self, pdf_page: Any, page_num: int, page_w: int, page_h: int
    ) -> List[VisualDetection]:
        """Detects PDF Form Signature Fields (Acrobat/DocuSign ISO 32000 widgets) and Annotations."""
        results: List[VisualDetection] = []
        pw = float(pdf_page.rect.width) if hasattr(pdf_page, "rect") else float(page_w)
        ph = float(pdf_page.rect.height) if hasattr(pdf_page, "rect") else float(page_h)

        try:
            # Check Form Widgets
            if hasattr(pdf_page, "widgets"):
                for widget in pdf_page.widgets():
                    field_type = getattr(widget, "field_type", None)
                    name = (getattr(widget, "field_name", "") or "").lower()
                    val = str(getattr(widget, "field_value", "") or "").lower()
                    rect = getattr(widget, "rect", None)

                    is_sig_widget = (
                        field_type == getattr(pymupdf, "PDF_WIDGET_TYPE_SIGNATURE", 6)
                        or any(k in name for k in ["sig", "firma", "sign"])
                        or any(k in val for k in ["signed", "firmado", "signature"])
                    )

                    if is_sig_widget and rect and (rect.width > 0 and rect.height > 0):
                        bbox = BoundingBox(
                            x=rect.x0 / pw,
                            y=rect.y0 / ph,
                            width=(rect.x1 - rect.x0) / pw,
                            height=(rect.y1 - rect.y0) / ph,
                            page_width=float(page_w),
                            page_height=float(page_h),
                        )
                        results.append(
                            VisualDetection(
                                id=f"sig-widget-{page_num}-{uuid.uuid4().hex[:8]}",
                                type=DetectionType.SIGNATURE,
                                label="Firma Digital (Campo de Formulario)",
                                confidence=0.98,
                                bbox=bbox,
                                metadata={
                                    "kind": "digital_widget",
                                    "field_name": name,
                                    "verified": True,
                                },
                            )
                        )

            # Check Annotations
            if hasattr(pdf_page, "annots"):
                for annot in pdf_page.annots():
                    type_name = str(getattr(annot, "type", ["", ""])[1]).lower()
                    info = getattr(annot, "info", {}) or {}
                    content = (info.get("content") or "").lower()
                    subject = (info.get("subject") or "").lower()
                    title = (info.get("title") or "").lower()

                    is_sig_annot = (
                        "signature" in type_name
                        or "ink" in type_name
                        or any(k in subject for k in ["sign", "firma", "rúbrica"])
                        or any(k in content for k in ["firma", "firmado", "signature"])
                    )

                    if is_sig_annot:
                        rect = annot.rect
                        if rect and (rect.width > 0 and rect.height > 0):
                            bbox = BoundingBox(
                                x=rect.x0 / pw,
                                y=rect.y0 / ph,
                                width=(rect.x1 - rect.x0) / pw,
                                height=(rect.y1 - rect.y0) / ph,
                                page_width=float(page_w),
                                page_height=float(page_h),
                            )
                            results.append(
                                VisualDetection(
                                    id=f"sig-annot-{page_num}-{uuid.uuid4().hex[:8]}",
                                    type=DetectionType.SIGNATURE,
                                    label="Firma Digital / Electrónica",
                                    confidence=0.95,
                                    bbox=bbox,
                                    metadata={
                                        "kind": "digital_annotation",
                                        "annotation_type": type_name,
                                        "signer": title or subject or "Certificado Digital",
                                    },
                                )
                            )
        except Exception:
            pass
        return results

    def _detect_vector_pdf_signatures(
        self, pdf_page: Any, page_num: int, page_w: int, page_h: int
    ) -> List[VisualDetection]:
        """Detects vector signatures drawn with stylus, pen, or touchscreen."""
        results: List[VisualDetection] = []
        if not hasattr(pdf_page, "get_drawings"):
            return results

        pw = float(pdf_page.rect.width)
        ph = float(pdf_page.rect.height)

        try:
            drawings = pdf_page.get_drawings()
            candidate_clusters: List[Dict[str, Any]] = []

            for d in drawings:
                rect = d.get("rect")
                items = d.get("items", [])
                if not rect or rect.width < 25 or rect.height < 10:
                    continue

                # Count curves ('c') vs straight lines ('l')
                curve_count = sum(1 for it in items if it[0] in ("c", "qu"))
                total_items = len(items)

                # Signature vector criteria: contains curves or complex polyline in compact area
                if (curve_count >= 2 or total_items >= 5) and rect.width < pw * 0.7 and rect.height < ph * 0.35:
                    candidate_clusters.append({
                        "rect": rect,
                        "curve_count": curve_count,
                        "total_items": total_items,
                    })

            for cand in candidate_clusters:
                r = cand["rect"]
                bbox = BoundingBox(
                    x=r.x0 / pw,
                    y=r.y0 / ph,
                    width=(r.x1 - r.x0) / pw,
                    height=(r.y1 - r.y0) / ph,
                    page_width=float(page_w),
                    page_height=float(page_h),
                )
                results.append(
                    VisualDetection(
                        id=f"sig-vec-{page_num}-{uuid.uuid4().hex[:8]}",
                        type=DetectionType.SIGNATURE,
                        label="Firma Electrónica (Vectorial)",
                        confidence=0.92,
                        bbox=bbox,
                        metadata={
                            "kind": "vector_stylus",
                            "curves": cand["curve_count"],
                        },
                    )
                )
        except Exception:
            pass
        return results

    def _detect_embedded_signature_images(
        self, pdf_page: Any, page_num: int, page_w: int, page_h: int
    ) -> List[VisualDetection]:
        """Detects raster images of signatures pasted into the document."""
        results: List[VisualDetection] = []
        if not hasattr(pdf_page, "get_images") or not hasattr(pdf_page, "get_image_rects"):
            return results

        pw = float(pdf_page.rect.width)
        ph = float(pdf_page.rect.height)

        try:
            images = pdf_page.get_images(full=True)
            for img in images:
                xref = img[0]
                rects = pdf_page.get_image_rects(xref)
                for rect in rects:
                    rw, rh = rect.width, rect.height
                    aspect = rw / rh if rh > 0 else 0
                    # Signature stamp image proportions: typically 1.2 to 5.0 aspect ratio, not too huge
                    if 1.2 < aspect < 6.0 and 40 < rw < pw * 0.65 and 15 < rh < ph * 0.25:
                        # Check if located in lower half or near signature text
                        is_bottom = (rect.y0 / ph) > 0.35
                        bbox = BoundingBox(
                            x=rect.x0 / pw,
                            y=rect.y0 / ph,
                            width=rw / pw,
                            height=rh / ph,
                            page_width=float(page_w),
                            page_height=float(page_h),
                        )
                        results.append(
                            VisualDetection(
                                id=f"sig-img-{page_num}-{uuid.uuid4().hex[:8]}",
                                type=DetectionType.SIGNATURE,
                                label="Firma Manuscrita (Imagen)",
                                confidence=0.88 if is_bottom else 0.78,
                                bbox=bbox,
                                metadata={
                                    "kind": "embedded_image",
                                    "aspect_ratio": round(aspect, 2),
                                },
                            )
                        )
        except Exception:
            pass
        return results

    def _detect_visual_signatures_and_stamps(
        self,
        img_np: np.ndarray,
        page_num: int,
        page_text: str,
        pdf_page: Any = None,
    ) -> Tuple[List[VisualDetection], List[VisualDetection]]:
        sigs: List[VisualDetection] = []
        stamps: List[VisualDetection] = []
        h, w = img_np.shape[:2]

        hsv = cv2.cvtColor(img_np, cv2.COLOR_BGR2HSV) if len(img_np.shape) == 3 else None
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY) if len(img_np.shape) == 3 else img_np

        # ---------------------------------------------------------------------
        # A. Detect Stamps via Color (Red / Violet / Magenta ink) & Geometry
        # ---------------------------------------------------------------------
        if hsv is not None:
            mask_red1 = cv2.inRange(hsv, np.array([0, 60, 40]), np.array([12, 255, 255]))
            mask_red2 = cv2.inRange(hsv, np.array([165, 60, 40]), np.array([180, 255, 255]))
            mask_red = cv2.bitwise_or(mask_red1, mask_red2)
            mask_violet = cv2.inRange(hsv, np.array([130, 45, 40]), np.array([164, 255, 255]))

            stamp_mask = cv2.bitwise_or(mask_red, mask_violet)
            stamp_contours, _ = cv2.findContours(stamp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in stamp_contours:
                area = cv2.contourArea(cnt)
                if 500 < area < (w * h * 0.20):
                    bx, by, bw, bh = cv2.boundingRect(cnt)
                    aspect = float(bw) / float(bh) if bh > 0 else 0
                    hull = cv2.convexHull(cnt)
                    hull_area = cv2.contourArea(hull)
                    solidity = float(area) / float(hull_area) if hull_area > 0 else 0

                    is_circular = 0.70 < aspect < 1.40 and solidity > 0.35
                    is_oval = 0.45 < aspect < 2.2 and solidity > 0.30

                    if is_circular or is_oval:
                        confidence = min(0.95, 0.70 + (0.20 if is_circular else 0.10) + (0.05 if area > 1500 else 0.0))
                        color_name = "Rojo" if cv2.countNonZero(mask_red[by:by+bh, bx:bx+bw]) > cv2.countNonZero(mask_violet[by:by+bh, bx:bx+bw]) else "Violeta"
                        bbox = BoundingBox(
                            x=bx / w,
                            y=by / h,
                            width=bw / w,
                            height=bh / h,
                            page_width=float(w),
                            page_height=float(h),
                        )
                        stamps.append(
                            VisualDetection(
                                id=f"stamp-{page_num}-{uuid.uuid4().hex[:8]}",
                                type=DetectionType.STAMP,
                                label=f"Sello / Estampado ({color_name})",
                                confidence=round(confidence, 2),
                                bbox=bbox,
                                metadata={
                                    "shape": "Circular/Oval" if is_circular else "Sello rectangular",
                                    "ink_color": color_name,
                                    "area_pixels": int(area),
                                },
                            )
                        )

        # ---------------------------------------------------------------------
        # B. Robust Binarization for Handwritten Cursive Signatures
        # Combines Otsu + Adaptive Thresholding for off-white, scanned & normal pages
        # ---------------------------------------------------------------------
        _, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        binary_adapt = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 8
        )
        binary = cv2.bitwise_or(binary_otsu, binary_adapt)

        # Blue ink mask if color available
        mask_blue = None
        if hsv is not None:
            mask_blue = cv2.inRange(hsv, np.array([88, 35, 30]), np.array([138, 255, 255]))

        # Connect stroke segments with slight dilation/closing
        connect_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        connected = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, connect_kernel)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(connected)

        # Precompute signature anchor keyword locations from text
        p_text_lower = page_text.lower()
        has_page_sig_text = any(k in p_text_lower for k in SIGNATURE_KEYWORDS)

        anchor_rects = []
        if pdf_page is not None and hasattr(pdf_page, "get_text"):
            try:
                words = pdf_page.get_text("words")
                for w_item in words:
                    word_str = w_item[4].lower()
                    if any(k in word_str for k in ["firma", "c.c.", "cedula", "rúbrica"]):
                        anchor_rects.append((w_item[0], w_item[1], w_item[2], w_item[3]))
            except Exception:
                pass

        for i in range(1, num_labels):
            bx = stats[i, cv2.CC_STAT_LEFT]
            by = stats[i, cv2.CC_STAT_TOP]
            bw = stats[i, cv2.CC_STAT_WIDTH]
            bh = stats[i, cv2.CC_STAT_HEIGHT]
            area = stats[i, cv2.CC_STAT_AREA]

            # Ignore pure straight horizontal/vertical lines (underlines, table rules)
            aspect = float(bw) / float(bh) if bh > 0 else 0
            if (bh <= 3 and bw > 70) or (bw <= 3 and bh > 70):
                continue

            # Ignore standard single machine font characters
            if bw < 30 and bh < 22 and area < 90:
                continue

            # Signature dimensional criteria
            is_valid_size = (35 <= bw <= w * 0.75) and (14 <= bh <= h * 0.35) and (area >= 100)
            if not is_valid_size:
                continue

            density = float(area) / float(bw * bh)
            is_valid_density = 0.015 <= density <= 0.52
            is_valid_aspect = 0.65 <= aspect <= 7.5

            if not (is_valid_density and is_valid_aspect):
                continue

            # Analyze stroke complexity via edge gradients
            roi_gray = gray[by:by+bh, bx:bx+bw]
            edges = cv2.Canny(roi_gray, 40, 140)
            edge_count = cv2.countNonZero(edges)
            if edge_count < 25:
                continue

            # Check blue/colored ink
            has_colored_ink = False
            if mask_blue is not None:
                roi_blue = mask_blue[by:by+bh, bx:bx+bw]
                if cv2.countNonZero(roi_blue) > 20:
                    has_colored_ink = True

            # Check anchor word proximity
            is_near_anchor = has_page_sig_text
            if anchor_rects:
                # Convert component to page units
                comp_y0 = (by / h) * (pdf_page.rect.height if hasattr(pdf_page, "rect") else h)
                comp_x0 = (bx / w) * (pdf_page.rect.width if hasattr(pdf_page, "rect") else w)
                for ax0, ay0, ax1, ay1 in anchor_rects:
                    if abs(comp_y0 - ay0) < 160 and abs(comp_x0 - ax0) < 350:
                        is_near_anchor = True
                        break

            is_bottom_zone = (by / h) > 0.35

            # Calculate confidence
            confidence = 0.72  # Solid base confidence for qualified cursive components
            if has_colored_ink:
                confidence += 0.20  # Colored ink strongly indicates handwriting
            if is_near_anchor:
                confidence += 0.12  # Near signature text keywords
            if is_bottom_zone:
                confidence += 0.06  # Typical signature placement
            if 1.4 <= aspect <= 5.0:
                confidence += 0.04  # Elongated cursive shape

            confidence = min(0.97, round(confidence, 2))

            if confidence >= 0.60:
                bbox = BoundingBox(
                    x=bx / w,
                    y=by / h,
                    width=bw / w,
                    height=bh / h,
                    page_width=float(w),
                    page_height=float(h),
                )
                sigs.append(
                    VisualDetection(
                        id=f"sig-hw-{page_num}-{uuid.uuid4().hex[:8]}",
                        type=DetectionType.SIGNATURE,
                        label="Firma Manuscrita",
                        confidence=confidence,
                        bbox=bbox,
                        metadata={
                            "kind": "handwritten",
                            "has_colored_ink": has_colored_ink,
                            "aspect_ratio": round(aspect, 2),
                            "near_anchor": is_near_anchor,
                        },
                    )
                )

        return sigs, stamps

    def _merge_adjacent_signatures(
        self, sigs: List[VisualDetection], page_w: int, page_h: int
    ) -> List[VisualDetection]:
        """Merges adjacent signature stroke clusters (e.g. first name + last name + flourish)."""
        if len(sigs) <= 1:
            return sigs

        merged: List[VisualDetection] = []
        used = [False] * len(sigs)

        for i in range(len(sigs)):
            if used[i]:
                continue

            curr = sigs[i]
            if not curr.bbox:
                merged.append(curr)
                continue

            x0, y0 = curr.bbox.x, curr.bbox.y
            x1, y1 = curr.bbox.x + curr.bbox.width, curr.bbox.y + curr.bbox.height
            max_conf = curr.confidence
            best_label = curr.label
            metadata = dict(curr.metadata or {})

            for j in range(i + 1, len(sigs)):
                if used[j]:
                    continue
                cand = sigs[j]
                if not cand.bbox:
                    continue

                cx0, cy0 = cand.bbox.x, cand.bbox.y
                cx1, cy1 = cand.bbox.x + cand.bbox.width, cand.bbox.y + cand.bbox.height

                # Check horizontal & vertical proximity (within 10% page width and 6% page height)
                h_dist = max(0.0, max(x0, cx0) - min(x1, cx1))
                v_dist = max(0.0, max(y0, cy0) - min(y1, cy1))

                if h_dist < 0.08 and v_dist < 0.05:
                    x0 = min(x0, cx0)
                    y0 = min(y0, cy0)
                    x1 = max(x1, cx1)
                    y1 = max(y1, cy1)
                    max_conf = max(max_conf, cand.confidence)
                    used[j] = True

            used[i] = True
            merged.append(
                VisualDetection(
                    id=curr.id,
                    type=DetectionType.SIGNATURE,
                    label=best_label,
                    confidence=max_conf,
                    bbox=BoundingBox(
                        x=x0,
                        y=y0,
                        width=x1 - x0,
                        height=y1 - y0,
                        page_width=float(page_w),
                        page_height=float(page_h),
                    ),
                    metadata=metadata,
                )
            )

        return merged

    def _filter_overlaps(self, detections: List[VisualDetection]) -> List[VisualDetection]:
        """Removes duplicate detections that overlap significantly, keeping the highest confidence."""
        if len(detections) <= 1:
            return detections

        detections = sorted(detections, key=lambda d: d.confidence, reverse=True)
        kept: List[VisualDetection] = []

        for d in detections:
            if not d.bbox:
                kept.append(d)
                continue

            overlaps = False
            for k in kept:
                if not k.bbox:
                    continue
                x_left = max(d.bbox.x, k.bbox.x)
                y_top = max(d.bbox.y, k.bbox.y)
                x_right = min(d.bbox.x + d.bbox.width, k.bbox.x + k.bbox.width)
                y_bottom = min(d.bbox.y + d.bbox.height, k.bbox.y + k.bbox.height)

                if x_right > x_left and y_bottom > y_top:
                    intersection = (x_right - x_left) * (y_bottom - y_top)
                    d_area = d.bbox.width * d.bbox.height
                    if d_area > 0 and (intersection / d_area) > 0.40:
                        overlaps = True
                        break
            if not overlaps:
                kept.append(d)

        return kept


signature_stamp_detector = SignatureAndStampDetector()
