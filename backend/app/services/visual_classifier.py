import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
import onnxruntime as ort

from backend.app.config import BASE_DIR, settings
from backend.app.models.schemas import BoundingBox, DetectionType, VisualDetection


class VisualClassifier:
    def __init__(self):
        self.session = None
        self.input_name = None
        self.output_name = None
        self.labels: List[str] = []
        self._category_map: Dict[str, str] = {}
        self._spanish_label_map: Dict[str, str] = {}
        self._init_model()

    def _init_model(self):
        # 1. Load ONNX model if present
        model_path = settings.onnx_model_path
        if model_path.exists():
            try:
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 2
                self.session = ort.InferenceSession(str(model_path), sess_options=opts)
                self.input_name = self.session.get_inputs()[0].name
                self.output_name = self.session.get_outputs()[0].name
            except Exception as e:
                print(f"Warning: Could not initialize ONNX runtime session: {e}")
                self.session = None

        # 2. Load ImageNet labels
        labels_path = BASE_DIR / "models" / "imagenet_labels.json"
        if labels_path.exists():
            try:
                with open(labels_path, "r", encoding="utf-8") as f:
                    self.labels = json.load(f)
            except Exception:
                self.labels = []

        self._build_semantic_mappings()

    def _build_semantic_mappings(self):
        """Maps ImageNet classes to high-level Spanish semantic concepts required by user."""
        # Key categories required:
        # Árboles, Personas, Animales, Vehículos, Casas, Objetos, Fotografías, Diagramas, Logos
        self.tree_keywords = [
            "tree", "plant", "acorn", "willow", "palm", "forest", "leaf", "potted plant",
            "daisy", "sunflower", "wood", "grass", "flora", "flower", "rose", "mushroom",
            "pine", "cypress", "oak", "elm", "birch", "spruce", "fern", "bamboo", "jungle"
        ]
        self.person_keywords = [
            "person", "man", "woman", "scuba diver", "groom", "ballplayer", "suit", "academic gown",
            "trench coat", "wig", "mask", "face", "human", "pedestrian", "doctor", "soldier", "police",
            "girl", "boy", "child", "crowd"
        ]
        self.vehicle_keywords = [
            "car", "automobile", "sports car", "convertible", "minivan", "cab", "taxi", "bus",
            "school bus", "trolleybus", "truck", "fire truck", "garbage truck", "pickup", "trailer",
            "bicycle", "mountain bike", "motorcycle", "motor scooter", "moped", "airplane", "airliner",
            "helicopter", "boat", "speedboat", "canoe", "yacht", "submarine", "train", "locomotive"
        ]
        self.house_keywords = [
            "house", "home", "building", "church", "barn", "castle", "palace", "boathouse",
            "mobile home", "yurt", "monastery", "patio", "beacon", "dam", "dock", "pier", "greenhouse"
        ]
        self.animal_keywords = [
            "dog", "cat", "bird", "horse", "cow", "sheep", "elephant", "bear", "lion", "tiger",
            "wolf", "fox", "rabbit", "deer", "monkey", "chimpanzee", "fish", "shark", "whale",
            "frog", "snake", "eagle", "parrot", "penguin", "duck", "goose", "swan", "owl"
        ]

    def _classify_image_patch(self, img_rgb: np.ndarray) -> List[Tuple[str, str, float]]:
        """
        Runs MobileNet inference on RGB image patch.
        Returns list of (spanish_label, semantic_category, confidence)
        """
        if self.session is None or len(self.labels) == 0:
            return self._heuristic_image_classifier(img_rgb)

        try:
            # Resize to 224x224
            resized = cv2.resize(img_rgb, (224, 224), interpolation=cv2.INTER_LINEAR)
            # Normalize with ImageNet mean and std
            norm = resized.astype(np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            norm = (norm - mean) / std
            # Transpose HWC to CHW and add batch dimension: (1, 3, 224, 224)
            inp = np.transpose(norm, (2, 0, 1))[np.newaxis, ...]

            preds = self.session.run([self.output_name], {self.input_name: inp})[0][0]
            # Softmax
            exp_preds = np.exp(preds - np.max(preds))
            probs = exp_preds / np.sum(exp_preds)

            # Get top 5 predictions
            top_indices = np.argsort(probs)[::-1][:5]
            results = []

            for idx in top_indices:
                score = float(probs[idx])
                if score < 0.08:
                    continue
                label_en = self.labels[idx].lower() if idx < len(self.labels) else f"class_{idx}"
                cat, es_label = self._map_to_category(label_en)
                results.append((es_label, cat, score))

            return results if results else self._heuristic_image_classifier(img_rgb)
        except Exception:
            return self._heuristic_image_classifier(img_rgb)

    def _map_to_category(self, label_en: str) -> Tuple[str, str]:
        """Maps an English label to (category, spanish_label)."""
        label_lower = label_en.lower()
        if any(w in label_lower for w in self.tree_keywords):
            return "tree", f"Árbol / Vegetación ({label_en})"
        if any(w in label_lower for w in self.person_keywords):
            return "person", f"Persona / Humano ({label_en})"
        if any(w in label_lower for w in self.vehicle_keywords):
            return "vehicle", f"Vehículo ({label_en})"
        if any(w in label_lower for w in self.house_keywords):
            return "house", f"Casa / Estructura ({label_en})"
        if any(w in label_lower for w in self.animal_keywords):
            return "animal", f"Animal ({label_en})"
        return "object", f"Objeto ({label_en})"

    def _heuristic_image_classifier(self, img_rgb: np.ndarray) -> List[Tuple[str, str, float]]:
        """Fallback computer vision heuristic classifier using color and texture analysis."""
        hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
        h, s, v = cv2.split(hsv)

        # Green dominance (plants, trees, vegetation)
        green_mask = cv2.inRange(hsv, np.array([35, 40, 40]), np.array([85, 255, 255]))
        green_ratio = float(cv2.countNonZero(green_mask)) / (img_rgb.shape[0] * img_rgb.shape[1])
        if green_ratio > 0.25:
            return [("Árbol / Planta", "tree", round(min(0.92, 0.65 + green_ratio * 0.4), 2))]

        # Blue sky / outdoor dominance
        blue_mask = cv2.inRange(hsv, np.array([90, 40, 50]), np.array([130, 255, 255]))
        blue_ratio = float(cv2.countNonZero(blue_mask)) / (img_rgb.shape[0] * img_rgb.shape[1])
        if blue_ratio > 0.35 and green_ratio > 0.15:
            return [("Paisaje natural / Árboles", "tree", 0.75)]

        # Skin tone detection (People / Faces)
        skin_mask = cv2.inRange(hsv, np.array([0, 20, 70]), np.array([25, 170, 255]))
        skin_ratio = float(cv2.countNonZero(skin_mask)) / (img_rgb.shape[0] * img_rgb.shape[1])
        if 0.18 < skin_ratio < 0.75:
            return [("Persona / Rostro", "person", 0.78)]

        # General photograph
        return [("Fotografía / Imagen", "photo", 0.85)]

    def analyze_page_visual_elements(
        self,
        pdf_page: Any,
        page_img_bgr: np.ndarray,
        page_num: int,
    ) -> Tuple[List[VisualDetection], List[VisualDetection]]:
        """
        Analyzes embedded images, visual objects, diagrams, and logos on the page.
        Returns: (visual_objects, images)
        """
        objects: List[VisualDetection] = []
        images: List[VisualDetection] = []
        page_h, page_w = page_img_bgr.shape[:2]

        # ---------------------------------------------------------------------
        # 1. Embedded PDF Images (PyMuPDF XREFs)
        # ---------------------------------------------------------------------
        if pdf_page is not None:
            image_list = pdf_page.get_images(full=True)
            for img_info in image_list:
                xref = img_info[0]
                rects = pdf_page.get_image_rects(xref)
                for r in rects:
                    # Ignore tiny decorative icons or lines (< 20px)
                    if (r.x1 - r.x0) < 20 or (r.y1 - r.y0) < 20:
                        continue

                    pw = pdf_page.rect.width
                    ph = pdf_page.rect.height
                    bbox = BoundingBox(
                        x=r.x0 / pw,
                        y=r.y0 / ph,
                        width=(r.x1 - r.x0) / pw,
                        height=(r.y1 - r.y0) / ph,
                        page_width=float(page_w),
                        page_height=float(page_h),
                    )

                    # Crop image from rendered high-res page
                    px0 = max(0, int(bbox.x * page_w))
                    py0 = max(0, int(bbox.y * page_h))
                    px1 = min(page_w, int((bbox.x + bbox.width) * page_w))
                    py1 = min(page_h, int((bbox.y + bbox.height) * page_h))

                    if px1 > px0 + 10 and py1 > py0 + 10:
                        crop_bgr = page_img_bgr[py0:py1, px0:px1]
                        crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)

                        # Register image detection
                        img_id = f"img-{page_num}-{xref}-{uuid.uuid4().hex[:6]}"
                        images.append(
                            VisualDetection(
                                id=img_id,
                                type=DetectionType.PHOTO,
                                label="Fotografía / Imagen incrustada",
                                confidence=0.98,
                                bbox=bbox,
                                metadata={
                                    "xref": xref,
                                    "width_px": px1 - px0,
                                    "height_px": py1 - py0,
                                },
                            )
                        )

                        # Run classification on this image patch
                        classifications = self._classify_image_patch(crop_rgb)
                        for label_es, cat, conf in classifications:
                            # Avoid duplicate general "photo" object if already classified
                            if cat != "photo":
                                objects.append(
                                    VisualDetection(
                                        id=f"obj-{page_num}-{uuid.uuid4().hex[:6]}",
                                        type=DetectionType.VISUAL,
                                        label=label_es,
                                        confidence=round(conf, 2),
                                        bbox=bbox,
                                        metadata={
                                            "category": cat,
                                            "source_image_id": img_id,
                                        },
                                    )
                                )

        # ---------------------------------------------------------------------
        # 2. Diagrams and Charts (Vector drawings or color chart areas)
        # ---------------------------------------------------------------------
        if pdf_page is not None and hasattr(pdf_page, "get_drawings"):
            try:
                drawings = pdf_page.get_drawings()
                if len(drawings) >= 15:  # Many vector paths indicate a chart, diagram, or plot
                    all_rects = [d["rect"] for d in drawings if "rect" in d]
                    if all_rects:
                        dx0 = min(r.x0 for r in all_rects)
                        dy0 = min(r.y0 for r in all_rects)
                        dx1 = max(r.x1 for r in all_rects)
                        dy1 = max(r.y1 for r in all_rects)
                        dw = dx1 - dx0
                        dh = dy1 - dy0
                        pw = pdf_page.rect.width
                        ph = pdf_page.rect.height

                        # Diagrams usually take a significant portion of space
                        if (dw * dh) > (pw * ph * 0.05) and (dw * dh) < (pw * ph * 0.90):
                            bbox = BoundingBox(
                                x=dx0 / pw,
                                y=dy0 / ph,
                                width=dw / pw,
                                height=dh / ph,
                                page_width=float(page_w),
                                page_height=float(page_h),
                            )
                            objects.append(
                                VisualDetection(
                                    id=f"diag-{page_num}-{uuid.uuid4().hex[:6]}",
                                    type=DetectionType.DIAGRAM,
                                    label="Diagrama / Gráfico vectorial",
                                    confidence=0.92,
                                    bbox=bbox,
                                    metadata={
                                        "vector_paths_count": len(drawings),
                                    },
                                )
                            )
            except Exception:
                pass

        # ---------------------------------------------------------------------
        # 3. Logos (Prominent isolated emblems in header or corner)
        # ---------------------------------------------------------------------
        for img in images:
            if img.bbox:
                # If image is in the top 20% of page and of moderate size (< 25% page width)
                if img.bbox.y < 0.20 and img.bbox.width < 0.35 and img.bbox.height < 0.20:
                    objects.append(
                        VisualDetection(
                            id=f"logo-{page_num}-{uuid.uuid4().hex[:6]}",
                            type=DetectionType.LOGO,
                            label="Logo / Emblema institucional",
                            confidence=0.88,
                            bbox=img.bbox,
                            metadata={"position": "header"},
                        )
                    )

        # ---------------------------------------------------------------------
        # 4. Scanned page visual fallback: if no embedded images were detected
        # but page has photographic content (scanned document with a photo)
        # ---------------------------------------------------------------------
        if len(images) == 0:
            scanned_patches = self._find_scanned_image_patches(page_img_bgr, page_num)
            for p_bbox, p_rgb in scanned_patches:
                img_id = f"img-scan-{page_num}-{uuid.uuid4().hex[:6]}"
                images.append(
                    VisualDetection(
                        id=img_id,
                        type=DetectionType.PHOTO,
                        label="Fotografía en documento escaneado",
                        confidence=0.85,
                        bbox=p_bbox,
                        metadata={"origin": "scanned_patch"},
                    )
                )
                classifications = self._classify_image_patch(p_rgb)
                for label_es, cat, conf in classifications:
                    if cat != "photo":
                        objects.append(
                            VisualDetection(
                                id=f"obj-scan-{page_num}-{uuid.uuid4().hex[:6]}",
                                type=DetectionType.VISUAL,
                                label=label_es,
                                confidence=round(conf, 2),
                                bbox=p_bbox,
                                metadata={"category": cat, "source_image_id": img_id},
                            )
                        )

        return objects, images

    def _find_scanned_image_patches(
        self, img_bgr: np.ndarray, page_num: int
    ) -> List[Tuple[BoundingBox, np.ndarray]]:
        """Finds photo/image bounding boxes on scanned pages using color and edge density."""
        patches = []
        try:
            h, w = img_bgr.shape[:2]
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            # Blur and detect areas of high local variance/texture
            blur = cv2.GaussianBlur(gray, (11, 11), 0)
            diff = cv2.absdiff(gray, blur)
            _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
            closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if (w * h * 0.03) < area < (w * h * 0.60):
                    bx, by, bw, bh = cv2.boundingRect(cnt)
                    aspect = float(bw) / float(bh) if bh > 0 else 0
                    if 0.4 < aspect < 2.5:
                        crop = img_bgr[by:by+bh, bx:bx+bw]
                        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                        bbox = BoundingBox(
                            x=bx / w,
                            y=by / h,
                            width=bw / w,
                            height=bh / h,
                            page_width=float(w),
                            page_height=float(h),
                        )
                        patches.append((bbox, crop_rgb))
        except Exception:
            pass
        return patches


visual_classifier = VisualClassifier()
