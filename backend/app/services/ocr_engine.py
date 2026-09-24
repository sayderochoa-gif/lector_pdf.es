import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
import pytesseract
from PIL import Image

from backend.app.config import BASE_DIR, settings

# Ensure TESSDATA_PREFIX is set to local tessdata if available
LOCAL_TESSDATA = BASE_DIR / "tessdata"
if LOCAL_TESSDATA.exists():
    os.environ["TESSDATA_PREFIX"] = str(LOCAL_TESSDATA)

if settings.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


class OCREngine:
    def __init__(self, lang: Optional[str] = None):
        self.lang = lang or self._detect_best_language()

    def _detect_best_language(self) -> str:
        try:
            available = pytesseract.get_languages(config="")
            langs = []
            if "spa" in available:
                langs.append("spa")
            if "eng" in available:
                langs.append("eng")
            return "+".join(langs) if langs else "eng"
        except Exception:
            return "eng"

    @staticmethod
    def review_image(img_np: np.ndarray) -> Dict[str, Any]:
        """
        Reviews and diagnoses image quality with OpenCV.
        Checks dimensions, sharpness/blur (Laplacian variance), contrast, brightness,
        tilt/skew angle, and high-frequency noise.
        """
        if len(img_np.shape) == 3:
            gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_np.copy()

        h, w = gray.shape[:2]

        # 1. Blur and Sharpness with Laplacian variance
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_var = float(laplacian.var())
        is_blurry = laplacian_var < 100.0

        # 2. Brightness and Contrast with meanStdDev
        mean_val, std_val = cv2.meanStdDev(gray)
        brightness = float(mean_val[0][0])
        contrast = float(std_val[0][0])
        is_low_contrast = contrast < 38.0
        is_dark = brightness < 80.0
        is_overexposed = brightness > 225.0

        # 3. Skew Angle Detection (Optimized with downscaled geometry for speed)
        skew_angle = 0.0
        has_skew = False
        try:
            max_dim = max(h, w)
            if max_dim > 800:
                scale = 800.0 / max_dim
                small_gray = cv2.resize(gray, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            else:
                small_gray = gray
            _, thresh = cv2.threshold(small_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            coords = np.column_stack(np.where(thresh > 0))
            if len(coords) >= 50:
                min_rect_angle = cv2.minAreaRect(coords)[-1]
                if min_rect_angle < -45:
                    angle = -(90 + min_rect_angle)
                elif min_rect_angle > 45:
                    angle = 90 - min_rect_angle
                else:
                    angle = min_rect_angle

                if 0.5 < abs(angle) < 40.0:
                    skew_angle = float(angle)
                    has_skew = True
        except Exception:
            pass

        # 4. Noise estimation
        median_blur = cv2.medianBlur(gray, 3)
        noise_diff = cv2.absdiff(gray, median_blur)
        noise_level = float(np.mean(noise_diff))
        has_noise = noise_level > 7.0

        # 5. Formulate OpenCV review diagnosis
        diagnostics = []
        if is_blurry:
            diagnostics.append(f"Desenfoque detectado (nitidez: {laplacian_var:.1f})")
        else:
            diagnostics.append(f"Nitidez óptima (score: {laplacian_var:.1f})")

        if is_low_contrast:
            diagnostics.append(f"Bajo contraste ({contrast:.1f})")
        if is_dark:
            diagnostics.append(f"Imagen oscura (brillo: {brightness:.1f})")
        elif is_overexposed:
            diagnostics.append(f"Sobreexposición (brillo: {brightness:.1f})")
        if has_skew:
            diagnostics.append(f"Inclinación de {skew_angle:.1f}°")
        if has_noise:
            diagnostics.append(f"Ruido detectado ({noise_level:.1f})")

        diagnosis_summary = " | ".join(diagnostics)

        return {
            "dimensions": f"{w}x{h}",
            "sharpness_score": round(laplacian_var, 2),
            "is_blurry": is_blurry,
            "brightness": round(brightness, 2),
            "contrast": round(contrast, 2),
            "is_low_contrast": is_low_contrast,
            "skew_angle": round(skew_angle, 2),
            "has_skew": has_skew,
            "noise_level": round(noise_level, 2),
            "has_noise": has_noise,
            "diagnosis": diagnosis_summary,
        }

    def review_and_preprocess(
        self, img_np: np.ndarray, is_digital_text: bool = False
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Runs OpenCV image review and applies targeted corrections for maximum Tesseract OCR precision.
        When is_digital_text is True, heavy raster filtering is safely bypassed since native text exists.
        """
        review = self.review_image(img_np)

        if is_digital_text:
            review["corrections_applied"] = ["Texto digital nativo (procesamiento de imagen acelerado)"]
            return img_np, review

        preprocessed = self.preprocess_image(
            img_np,
            deskew=True,
            denoise=True,
            enhance_contrast=True,
            sharpen=True,
            binarize=False,
        )

        corrections = ["Conversión a escala de grises"]
        if review["has_skew"]:
            corrections.append(f"Enderezado OpenCV ({review['skew_angle']}°)")
        if review["is_low_contrast"] or review["brightness"] < 100:
            corrections.append("Realce de contraste adaptativo CLAHE")
        if review["is_blurry"]:
            corrections.append("Filtro de enfoque convolucional")
        if review["has_noise"]:
            corrections.append("Filtro bilateral de eliminación de ruido")

        review["corrections_applied"] = corrections
        return preprocessed, review

    @staticmethod
    def preprocess_image(
        img_np: np.ndarray,
        deskew: bool = True,
        denoise: bool = True,
        enhance_contrast: bool = True,
        sharpen: bool = True,
        binarize: bool = False,
    ) -> np.ndarray:
        """Applies comprehensive image preprocessing for maximum OCR accuracy."""
        # 1. Grayscale
        if len(img_np.shape) == 3:
            gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_np.copy()

        # 2. Upscaling if resolution is low
        h, w = gray.shape[:2]
        if w < 1200 or h < 1200:
            scale = min(2.0, 1800.0 / max(w, h))
            if scale > 1.1:
                gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        # 3. Denoising
        if denoise:
            # Bilateral filter preserves sharp text edges while smoothing background noise
            gray = cv2.bilateralFilter(gray, 7, 50, 50)

        # 4. Contrast Enhancement via CLAHE (Contrast Limited Adaptive Histogram Equalization)
        if enhance_contrast:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)

        # 5. Deskewing
        if deskew:
            gray = OCREngine._correct_skew(gray)

        # 6. Sharpening
        if sharpen:
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]], dtype=np.float32)
            gray = cv2.filter2D(gray, -1, kernel)

        # 7. Optional Binarization (Otsu thresholding)
        if binarize:
            _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return gray

    @staticmethod
    def _correct_skew(image: np.ndarray) -> np.ndarray:
        """Detects tilt angle and rotates image to be upright."""
        try:
            # Invert image (text becomes white on black background)
            _, thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            # Find all non-zero points
            coords = np.column_stack(np.where(thresh > 0))
            if len(coords) < 50:
                return image

            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            elif angle > 45:
                angle = 90 - angle

            # Only correct if angle is significant (> 0.5 deg) and not extreme (> 40 deg, which might be vertical text)
            if 0.5 < abs(angle) < 40.0:
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(
                    image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
                )
                return rotated
        except Exception:
            pass
        return image

    def extract_text_and_data(
        self, img_np: np.ndarray, preprocess: bool = True
    ) -> Dict[str, Any]:
        """Runs OCR and returns cleaned text, average confidence, and word bounding boxes."""
        processed = self.preprocess_image(img_np) if preprocess else img_np
        pil_img = Image.fromarray(processed)

        # Configure Tesseract
        custom_config = r"--oem 3 --psm 3"
        try:
            ocr_data = pytesseract.image_to_data(
                pil_img, lang=self.lang, config=custom_config, output_type=pytesseract.Output.DICT
            )
            raw_text = pytesseract.image_to_string(pil_img, lang=self.lang, config=custom_config)
        except Exception as e:
            # Fallback to default language
            ocr_data = pytesseract.image_to_data(
                pil_img, lang="eng", config=custom_config, output_type=pytesseract.Output.DICT
            )
            raw_text = pytesseract.image_to_string(pil_img, lang="eng", config=custom_config)

        # Parse word-level bounding boxes and confidence scores
        words: List[Dict[str, Any]] = []
        confidences: List[float] = []
        n_boxes = len(ocr_data["text"])
        img_h, img_w = processed.shape[:2]

        for i in range(n_boxes):
            word = ocr_data["text"][i].strip()
            conf = float(ocr_data["conf"][i])
            if conf > 20.0 and len(word) > 0:
                confidences.append(conf / 100.0)
                words.append({
                    "word": word,
                    "confidence": conf / 100.0,
                    "x": ocr_data["left"][i] / img_w,
                    "y": ocr_data["top"][i] / img_h,
                    "width": ocr_data["width"][i] / img_w,
                    "height": ocr_data["height"][i] / img_h,
                })

        mean_confidence = float(np.mean(confidences)) if confidences else 0.0
        cleaned_text = re.sub(r"\n{3,}", "\n\n", raw_text).strip()

        # Multi-pass recovery for blurry, noisy, or sparse pages
        if len(cleaned_text) < 5 and preprocess:
            try:
                bin_img = self.preprocess_image(img_np, binarize=True, deskew=True, sharpen=True)
                bin_pil = Image.fromarray(bin_img)
                fallback_text = pytesseract.image_to_string(bin_pil, lang=self.lang, config=r"--oem 3 --psm 6")
                fallback_cleaned = re.sub(r"\n{3,}", "\n\n", fallback_text).strip()
                if len(fallback_cleaned) > len(cleaned_text):
                    cleaned_text = fallback_cleaned
                    mean_confidence = 0.70
            except Exception:
                pass

        return {
            "text": cleaned_text,
            "confidence": round(mean_confidence, 4),
            "word_count": len(words),
            "words": words,
        }


ocr_engine = OCREngine()
