import uuid
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
from pyzbar import pyzbar

from backend.app.models.schemas import BoundingBox, DetectionType, VisualDetection


class CodeDetector:
    def __init__(self):
        self.cv_qr_detector = cv2.QRCodeDetector()
        try:
            self.cv_barcode_detector = cv2.barcode.BarcodeDetector()
        except Exception:
            self.cv_barcode_detector = None

    def detect_codes(self, img_np: np.ndarray, page_num: int) -> Tuple[List[VisualDetection], List[VisualDetection]]:
        """Detects QR codes and 1D Barcodes, returning (qr_codes, barcodes)."""
        qr_detections: List[VisualDetection] = []
        barcode_detections: List[VisualDetection] = []
        h, w = img_np.shape[:2]

        # 1. Detect using PyZbar
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY) if len(img_np.shape) == 3 else img_np
        decoded_objects = pyzbar.decode(gray)

        # PyZbar can also benefit from contrast-enhanced image if first pass finds nothing
        if not decoded_objects:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            decoded_objects = pyzbar.decode(enhanced)

        detected_boxes: List[Tuple[int, int, int, int]] = []

        for obj in decoded_objects:
            code_type = obj.type
            data = obj.data.decode("utf-8", errors="replace")
            rect = obj.rect
            bbox = BoundingBox(
                x=rect.left / w,
                y=rect.top / h,
                width=rect.width / w,
                height=rect.height / h,
                page_width=float(w),
                page_height=float(h),
            )
            detected_boxes.append((rect.left, rect.top, rect.width, rect.height))

            if code_type == "QRCODE":
                qr_detections.append(
                    VisualDetection(
                        id=f"qr-{page_num}-{uuid.uuid4().hex[:8]}",
                        type=DetectionType.QR_CODE,
                        label="Código QR",
                        confidence=0.99,
                        bbox=bbox,
                        metadata={
                            "format": "QRCODE",
                            "decoded_text": data,
                            "is_url": data.startswith("http://") or data.startswith("https://"),
                            "decodable": True,
                        },
                    )
                )
            else:
                barcode_detections.append(
                    VisualDetection(
                        id=f"barcode-{page_num}-{uuid.uuid4().hex[:8]}",
                        type=DetectionType.BARCODE,
                        label=f"Código de Barras ({code_type})",
                        confidence=0.98,
                        bbox=bbox,
                        metadata={
                            "format": code_type,
                            "decoded_text": data,
                            "decodable": True,
                        },
                    )
                )

        # 2. OpenCV QR Detector fallback
        if not qr_detections:
            try:
                retval, decoded_info, points, _ = self.cv_qr_detector.detectAndDecodeMulti(gray)
                if retval and points is not None and len(points) > 0:
                    for i, pts in enumerate(points):
                        pts = pts.reshape(-1, 2)
                        x_min, y_min = np.min(pts, axis=0)
                        x_max, y_max = np.max(pts, axis=0)
                        box_w = max(10, x_max - x_min)
                        box_h = max(10, y_max - y_min)
                        info = decoded_info[i] if i < len(decoded_info) else ""
                        decodable = bool(info and len(info) > 0)
                        
                        bbox = BoundingBox(
                            x=float(x_min) / w,
                            y=float(y_min) / h,
                            width=float(box_w) / w,
                            height=float(box_h) / h,
                            page_width=float(w),
                            page_height=float(h),
                        )
                        qr_detections.append(
                            VisualDetection(
                                id=f"qr-cv-{page_num}-{uuid.uuid4().hex[:8]}",
                                type=DetectionType.QR_CODE,
                                label="Código QR",
                                confidence=0.90 if decodable else 0.75,
                                bbox=bbox,
                                metadata={
                                    "format": "QRCODE",
                                    "decoded_text": info if decodable else None,
                                    "is_url": info.startswith("http://") or info.startswith("https://") if info else False,
                                    "decodable": decodable,
                                },
                            )
                        )
            except Exception:
                pass

        # 3. OpenCV Barcode Detector fallback
        if not barcode_detections and self.cv_barcode_detector is not None:
            try:
                retval, decoded_info, decoded_type, points = self.cv_barcode_detector.detectAndDecode(gray)
                if retval and points is not None and len(points) > 0:
                    for i, pts in enumerate(points):
                        pts = pts.reshape(-1, 2)
                        x_min, y_min = np.min(pts, axis=0)
                        x_max, y_max = np.max(pts, axis=0)
                        box_w = max(10, x_max - x_min)
                        box_h = max(10, y_max - y_min)
                        info = decoded_info[i] if i < len(decoded_info) else ""
                        btype = decoded_type[i] if i < len(decoded_type) else "BARCODE"
                        decodable = bool(info and len(info) > 0)
                        
                        bbox = BoundingBox(
                            x=float(x_min) / w,
                            y=float(y_min) / h,
                            width=float(box_w) / w,
                            height=float(box_h) / h,
                            page_width=float(w),
                            page_height=float(h),
                        )
                        barcode_detections.append(
                            VisualDetection(
                                id=f"barcode-cv-{page_num}-{uuid.uuid4().hex[:8]}",
                                type=DetectionType.BARCODE,
                                label=f"Código de Barras ({btype})",
                                confidence=0.88 if decodable else 0.70,
                                bbox=bbox,
                                metadata={
                                    "format": str(btype),
                                    "decoded_text": info if decodable else None,
                                    "decodable": decodable,
                                },
                            )
                        )
            except Exception:
                pass

        # 4. Fallback for damaged / blurry QR codes that could not be decoded
        # Using nested contour hierarchy search (1:1:3:1:1 Finder Pattern detection)
        if not qr_detections:
            undecoded_qr = self._detect_undecodable_qr_patterns(gray, w, h, page_num)
            qr_detections.extend(undecoded_qr)

        # 5. Fallback for 1D Barcode pattern detection when decoding fails
        if not barcode_detections:
            undecoded_bc = self._detect_undecodable_barcode_patterns(gray, w, h, page_num)
            barcode_detections.extend(undecoded_bc)

        return qr_detections, barcode_detections

    def _detect_undecodable_qr_patterns(
        self, gray: np.ndarray, w: int, h: int, page_num: int
    ) -> List[VisualDetection]:
        """Detects QR finder pattern squares (outer-inner-center nested contours) when decoding fails."""
        results = []
        try:
            _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
            contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            if hierarchy is None or len(hierarchy) == 0:
                return results

            # QR codes have 3 position detection patterns with 3 nested squares
            hierarchy = hierarchy[0]
            finder_candidates = []
            for i in range(len(contours)):
                k = i
                count = 0
                while hierarchy[k][2] != -1:
                    k = hierarchy[k][2]
                    count += 1
                if count >= 2:
                    cnt = contours[i]
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    aspect = float(bw) / float(bh) if bh > 0 else 0
                    if 0.75 < aspect < 1.35 and bw > 15 and bh > 15:
                        finder_candidates.append((x, y, bw, bh))

            # If at least 3 finder candidates cluster together, we found an undecodable QR code!
            if len(finder_candidates) >= 3:
                all_x = [f[0] for f in finder_candidates]
                all_y = [f[1] for f in finder_candidates]
                all_r = [f[0] + f[2] for f in finder_candidates]
                all_b = [f[1] + f[3] for f in finder_candidates]
                min_x, min_y = min(all_x), min(all_y)
                max_r, max_b = max(all_r), max(all_b)
                box_w = max_r - min_x
                box_h = max_b - min_y
                
                # Check squareness of the cluster
                if 0.7 < (box_w / box_h) < 1.4 and box_w > 40:
                    bbox = BoundingBox(
                        x=min_x / w,
                        y=min_y / h,
                        width=box_w / w,
                        height=box_h / h,
                        page_width=float(w),
                        page_height=float(h),
                    )
                    results.append(
                        VisualDetection(
                            id=f"qr-damaged-{page_num}-{uuid.uuid4().hex[:8]}",
                            type=DetectionType.QR_CODE,
                            label="Código QR (No decodificable)",
                            confidence=0.72,
                            bbox=bbox,
                            metadata={
                                "format": "QRCODE",
                                "decoded_text": None,
                                "decodable": False,
                                "note": "Se detectó la estructura de un código QR pero no fue posible decodificar su contenido.",
                            },
                        )
                    )
        except Exception:
            pass
        return results

    def _detect_undecodable_barcode_patterns(
        self, gray: np.ndarray, w: int, h: int, page_num: int
    ) -> List[VisualDetection]:
        """Detects 1D barcode strips via Sobel-X gradient and morphological closing."""
        results = []
        try:
            grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=-1)
            grad_x = cv2.convertScaleAbs(grad_x)
            blurred = cv2.blur(grad_x, (9, 9))
            _, thresh = cv2.threshold(blurred, 190, 255, cv2.THRESH_BINARY)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
            closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            closed = cv2.erode(closed, None, iterations=2)
            closed = cv2.dilate(closed, None, iterations=2)

            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                x, y, bw, bh = cv2.boundingRect(cnt)
                aspect = float(bw) / float(bh) if bh > 0 else 0
                if aspect > 1.2 and bw > 50 and bh > 15 and (bw * bh) < (w * h * 0.45):
                    bbox = BoundingBox(
                        x=x / w,
                        y=y / h,
                        width=bw / w,
                        height=bh / h,
                        page_width=float(w),
                        page_height=float(h),
                    )
                    results.append(
                        VisualDetection(
                            id=f"barcode-morph-{page_num}-{uuid.uuid4().hex[:8]}",
                            type=DetectionType.BARCODE,
                            label="Código de Barras 1D",
                            confidence=0.85,
                            bbox=bbox,
                            metadata={
                                "format": "1D_BARCODE",
                                "decoded_text": None,
                                "decodable": False,
                                "note": "Se detectó el patrón visual de líneas paralelas de un código de barras 1D.",
                            },
                        )
                    )
                    break
        except Exception:
            pass
        return results


code_detector = CodeDetector()
