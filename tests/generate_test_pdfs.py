import os
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import pymupdf
import qrcode

TEST_DIR = Path(__file__).resolve().parent / "sample_pdfs"
TEST_DIR.mkdir(parents=True, exist_ok=True)


def create_digital_text_pdf(path: Path) -> Path:
    """TEST 1: Digital text PDF with paragraphs and keywords."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4

    text = """CONTRATO DE PRESTACIÓN DE SERVICIOS PROFESIONALES

Entre los suscritos a saber: EMPRESA TECNOLÓGICA S.A.S., identificada con NIT 900.123.456-7,
y por la otra parte el contratista JUAN PÉREZ, con cédula de ciudadanía 123456789.

CLÁUSULA PRIMERA - OBJETO:
El contratista se compromete a realizar la consultoría de software y desarrollo de sistemas.
El valor acordado incluye la entrega de la hoja de vida y certificaciones laborales del equipo.

CLÁUSULA SEGUNDA - VIGENCIA:
El presente contrato tendrá una duración de seis meses a partir de la firma del acta de inicio.
"""
    page.insert_text(pymupdf.Point(50, 70), text, fontsize=12, fontname="helv")
    doc.save(str(path))
    doc.close()
    return path


def create_scanned_text_pdf(path: Path) -> Path:
    """TEST 2: Scanned text PDF (rendered as pure raster image without text layer)."""
    # Create image using PIL with readable font scale
    img = Image.new("RGB", (1240, 1754), color=(250, 250, 250))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=34)

    text_lines = [
        "DOCUMENTO ESCANEADO DE PRUEBA",
        "",
        "Este es un documento completamente escaneado sin capa de texto digital.",
        "El motor de OCR debe detectar estas líneas mediante Tesseract.",
        "Se menciona expresamente la palabra contrato y la palabra factura.",
        "Fecha de expedición: 23 de Septiembre de 2026.",
        "Identificación tributaria: NIT 800999111-2.",
    ]

    y = 140
    for line in text_lines:
        draw.text((100, y), line, fill=(20, 20, 20), font=font)
        y += 60

    # Add slight scan noise and minor rotation to simulate a real scanner
    img = img.rotate(1.2, fillcolor=(250, 250, 250), resample=Image.BICUBIC)

    # Save to PDF as an image-only page
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    img_bytes = img.tobytes("jpeg", "RGB")
    page.insert_image(page.rect, stream=img_bytes)
    doc.save(str(path))
    doc.close()
    return path


def create_20_pages_pdf(path: Path) -> Path:
    """TEST 3: 20+ pages PDF (22 pages) for stress and pagination testing."""
    doc = pymupdf.open()
    for i in range(1, 23):
        page = doc.new_page(width=595, height=842)
        if i == 15:
            content = f"MANUAL DE OPERACIONES - PÁGINA 15: Anexo de especificaciones técnicas del contrato.\n"
        elif i == 7:
            content = f"MANUAL DE OPERACIONES - PÁGINA 7: El cliente ha solicitado una revisión de términos.\n"
        elif i == 20:
            content = f"MANUAL DE OPERACIONES - PÁGINA 20: Resumen final de facturación y cierre contable.\n"
        else:
            content = f"MANUAL DE OPERACIONES Y PROCEDIMIENTOS - PÁGINA {i} DE 22\n"

        content += f"""
Capítulo {((i - 1) // 3) + 1} - Sección {i}
Este es el contenido detallado de la página {i} del documento de prueba de volumen.
Los sistemas de procesamiento deben indexar esta página de forma independiente.
"""
        page.insert_text(pymupdf.Point(50, 80), content, fontsize=12, fontname="helv")
    doc.save(str(path))
    doc.close()
    return path


def create_images_pdf(path: Path) -> Path:
    """TEST 4: PDF with visual embedded images (tree, vehicle, person)."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(pymupdf.Point(50, 50), "REPORTE CON ELEMENTOS VISUALES Y FOTOGRAFÍAS", fontsize=14, fontname="helv")

    # Generate a realistic synthetic image of a green tree / foliage
    tree_img = Image.new("RGB", (300, 300), color=(135, 206, 235))  # sky blue
    tree_draw = ImageDraw.Draw(tree_img)
    # Brown trunk
    tree_draw.rectangle([130, 180, 170, 280], fill=(101, 67, 33))
    # Green leaves cluster
    tree_draw.ellipse([60, 60, 240, 220], fill=(34, 139, 34))
    tree_draw.ellipse([100, 40, 200, 150], fill=(46, 175, 46))
    tree_draw.text((70, 260), "Árbol de Roble", fill=(10, 10, 10))

    # Save image to temp bytes and insert into PDF
    img_rect = pymupdf.Rect(50, 100, 300, 350)
    import io
    b = io.BytesIO()
    tree_img.save(b, format="PNG")
    page.insert_image(img_rect, stream=b.getvalue())

    # Generate image of a vehicle
    car_img = Image.new("RGB", (300, 200), color=(240, 240, 240))
    car_draw = ImageDraw.Draw(car_img)
    # Red car body
    car_draw.rectangle([40, 90, 260, 150], fill=(220, 20, 60))
    car_draw.polygon([(80, 90), (120, 40), (200, 40), (230, 90)], fill=(180, 20, 50))
    # Wheels
    car_draw.ellipse([70, 135, 110, 175], fill=(30, 30, 30))
    car_draw.ellipse([190, 135, 230, 175], fill=(30, 30, 30))

    car_b = io.BytesIO()
    car_img.save(car_b, format="PNG")
    page.insert_image(pymupdf.Rect(50, 400, 320, 580), stream=car_b.getvalue())

    doc.save(str(path))
    doc.close()
    return path


def create_blurry_pdf(path: Path) -> Path:
    """TEST 5: PDF with blurry degraded image and text."""
    img = Image.new("RGB", (1000, 800), color=(250, 250, 250))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=32)
    draw.text((80, 100), "TEXTO ORIGINAL CON DESENFOQUE", fill=(10, 10, 10), font=font)
    draw.text((80, 180), "Factura de compraventa y comprobante", fill=(10, 10, 10), font=font)
    draw.text((80, 260), "Numero de aprobacion: 98765", fill=(10, 10, 10), font=font)

    # Apply Gaussian blur
    blurred = img.filter(ImageFilter.GaussianBlur(radius=1.2))

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    import io
    b = io.BytesIO()
    blurred.save(b, format="JPEG", quality=85)
    page.insert_image(page.rect, stream=b.getvalue())
    doc.save(str(path))
    doc.close()
    return path


def create_qr_pdf(path: Path) -> Path:
    """TEST 6: PDF with a real QR code."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(pymupdf.Point(50, 60), "DOCUMENTO OFICIAL CON CÓDIGO QR", fontsize=14, fontname="helv")
    page.insert_text(pymupdf.Point(50, 90), "Escanee el código inferior para validar autenticidad.", fontsize=11, fontname="helv")

    # Generate QR Code
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data("https://github.com/google/antigravity")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    import io
    b = io.BytesIO()
    qr_img.save(b, format="PNG")
    page.insert_image(pymupdf.Rect(50, 130, 200, 280), stream=b.getvalue())

    doc.save(str(path))
    doc.close()
    return path


def create_barcode_pdf(path: Path) -> Path:
    """TEST 7: PDF with a real 1D barcode."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(pymupdf.Point(50, 60), "ORDEN DE DESPACHO CON CÓDIGO DE BARRAS", fontsize=14, fontname="helv")

    # Create synthetic Code128-like barcode image
    # alternating black & white bars with guard patterns
    bc_img = Image.new("RGB", (400, 120), color="white")
    bc_draw = ImageDraw.Draw(bc_img)
    import random
    random.seed(42)
    x = 30
    while x < 370:
        bar_w = random.choice([2, 3, 5])
        space_w = random.choice([2, 3, 4])
        bc_draw.rectangle([x, 15, x + bar_w, 90], fill="black")
        x += bar_w + space_w

    bc_draw.text((120, 95), "* DOC-987654321 *", fill="black")

    import io
    b = io.BytesIO()
    bc_img.save(b, format="PNG")
    page.insert_image(pymupdf.Rect(50, 120, 450, 240), stream=b.getvalue())
    page.insert_text(pymupdf.Point(50, 280), "Referencia de envío: DOC-987654321", fontsize=11, fontname="helv")

    doc.save(str(path))
    doc.close()
    return path


def create_signatures_pdf(path: Path) -> Path:
    """TEST 8: PDF with handwritten signature in blue ink."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(pymupdf.Point(50, 70), "ACTA DE ACEPTACIÓN FINAL", fontsize=14, fontname="helv")
    page.insert_text(
        pymupdf.Point(50, 120),
        "Por medio de la presente, las partes declaran su total conformidad con los entregables.\n"
        "Se firma el presente documento como constancia legal de recibido a satisfacción.",
        fontsize=11,
        fontname="helv",
    )

    # Signature section in bottom half
    page.insert_text(pymupdf.Point(80, 520), "Firma del Representante Legal:", fontsize=11, fontname="helv")
    page.draw_line(pymupdf.Point(80, 600), pymupdf.Point(320, 600))
    page.insert_text(pymupdf.Point(80, 620), "Carlos Mendoza - C.C. 79.456.123", fontsize=10, fontname="helv")

    # Generate handwritten cursive stroke signature in blue ink
    sig_img = Image.new("RGBA", (300, 100), (255, 255, 255, 0))
    sig_draw = ImageDraw.Draw(sig_img)
    # Draw cursive loops
    points = [
        (20, 60), (35, 25), (55, 75), (80, 30), (105, 65),
        (130, 20), (160, 70), (190, 45), (220, 80), (260, 40), (280, 60)
    ]
    blue_ink = (0, 35, 160, 255)
    for p in range(len(points) - 1):
        sig_draw.line([points[p], points[p+1]], fill=blue_ink, width=3)
    # Add signature flourish underline
    sig_draw.arc([15, 50, 270, 95], 0, 180, fill=blue_ink, width=2)

    import io
    b = io.BytesIO()
    sig_img.save(b, format="PNG")
    page.insert_image(pymupdf.Rect(80, 530, 300, 595), stream=b.getvalue())

    doc.save(str(path))
    doc.close()
    return path


def create_stamps_pdf(path: Path) -> Path:
    """TEST 9: PDF with circular red rubber stamp."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(pymupdf.Point(50, 70), "RESOLUCIÓN DE APROBACIÓN TÉCNICA", fontsize=14, fontname="helv")
    page.insert_text(
        pymupdf.Point(50, 110),
        "El comité certifica que la documentación aportada cumple con la totalidad de requisitos.",
        fontsize=11,
        fontname="helv",
    )

    # Generate a circular red ink stamp
    stamp_img = Image.new("RGBA", (250, 250), (255, 255, 255, 0))
    stamp_draw = ImageDraw.Draw(stamp_img)
    red_ink = (210, 25, 35, 240)
    # Outer circle
    stamp_draw.ellipse([10, 10, 240, 240], outline=red_ink, width=6)
    # Inner circle
    stamp_draw.ellipse([25, 25, 225, 225], outline=red_ink, width=3)
    # Stamp text
    stamp_draw.text((55, 105), "APROBADO", fill=red_ink)
    stamp_draw.text((70, 70), "DIRECCIÓN GENERAL", fill=red_ink)
    stamp_draw.text((80, 145), "2026 - VÁLIDO", fill=red_ink)

    import io
    b = io.BytesIO()
    stamp_img.save(b, format="PNG")
    page.insert_image(pymupdf.Rect(320, 200, 520, 400), stream=b.getvalue())

    doc.save(str(path))
    doc.close()
    return path


def create_mixed_pdf(path: Path) -> Path:
    """TEST 10: Mixed digital text + image + table + signature."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    page.insert_text(pymupdf.Point(50, 50), "INFORME INTEGRAL DE EVALUACIÓN", fontsize=14, fontname="helv")
    page.insert_text(
        pymupdf.Point(50, 80),
        "Se presenta el balance del proyecto forestal y de infraestructura sostenible.",
        fontsize=11,
        fontname="helv",
    )

    # Insert photo of tree
    tree_img = Image.new("RGB", (200, 200), (34, 139, 34))
    import io
    b = io.BytesIO()
    tree_img.save(b, format="PNG")
    page.insert_image(pymupdf.Rect(50, 110, 200, 240), stream=b.getvalue())

    # Insert table grid
    # Header
    page.draw_rect(pymupdf.Rect(50, 270, 545, 300), color=(0.2, 0.2, 0.2), fill=(0.9, 0.9, 0.9))
    page.insert_text(pymupdf.Point(60, 290), "Ítem | Descripción del Proyecto | Estado | Presupuesto", fontsize=10, fontname="helv")
    # Rows
    for r in range(1, 4):
        y0 = 300 + (r - 1) * 30
        y1 = y0 + 30
        page.draw_rect(pymupdf.Rect(50, y0, 545, y1), color=(0.7, 0.7, 0.7))
        page.insert_text(pymupdf.Point(60, y0 + 20), f"00{r} | Fase de implementación {r} | Aprobado | $15.000.000", fontsize=9, fontname="helv")

    # Signature line
    page.insert_text(pymupdf.Point(50, 500), "Firma del Auditor Ambiental:", fontsize=10, fontname="helv")
    page.draw_line(pymupdf.Point(50, 560), pymupdf.Point(280, 560))

    doc.save(str(path))
    doc.close()
    return path


def create_repeated_words_pdf(path: Path) -> Path:
    """TEST 11: PDF with repeated word 'factura' on page 1, 3, and 5."""
    doc = pymupdf.open()
    for p in range(1, 6):
        page = doc.new_page(width=595, height=842)
        if p == 1:
            page.insert_text(pymupdf.Point(50, 80), "Página 1: Se adjunta la factura correspondiente al mes de enero.", fontsize=12, fontname="helv")
        elif p == 3:
            page.insert_text(pymupdf.Point(50, 80), "Página 3: La factura de servicios públicos fue cancelada oportunamente.", fontsize=12, fontname="helv")
        elif p == 5:
            page.insert_text(pymupdf.Point(50, 80), "Página 5: Copia de la factura final del proveedor de cómputo.", fontsize=12, fontname="helv")
        else:
            page.insert_text(pymupdf.Point(50, 80), f"Página {p}: Información general de inventario de equipos.", fontsize=12, fontname="helv")
    doc.save(str(path))
    doc.close()
    return path


def create_accents_pdf(path: Path) -> Path:
    """TEST 12: PDF with accented Spanish words: Bogotá, facturación, vehículo, análisis, código."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    text = """INFORME DE GESTIÓN REGIONAL - BOGOTÁ D.C.

En la ciudad de Bogotá se realizó la facturación correspondiente al último trimestre.
El vehículo de inspección técnica completó el análisis de emisiones.
El código de verificación del proceso es BOG-2026-XYZ.
"""
    page.insert_text(pymupdf.Point(50, 80), text, fontsize=12, fontname="helv")
    doc.save(str(path))
    doc.close()
    return path


def create_difficult_pdf(path: Path) -> Path:
    """TEST 13: PDF with noisy, tilted, low contrast page to test image enhancement."""
    img = Image.new("RGB", (1000, 1400), color=(235, 235, 235))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=32)
    # Low contrast gray text
    draw.text((100, 150), "TEXTO EN CONDICIONES DIFICILES", fill=(60, 60, 60), font=font)
    draw.text((100, 230), "Referencia catastral: 44556677", fill=(55, 55, 55), font=font)
    draw.text((100, 310), "Direccion del predio: Calle 45", fill=(65, 65, 65), font=font)

    # Add moderate noise
    np_img = np.array(img)
    noise = np.random.randint(0, 25, np_img.shape, dtype=np.uint8)
    noisy = cv2.add(np_img, noise)

    # Slight tilt (skew of 3 degrees)
    h, w = noisy.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), 3.0, 1.0)
    rotated = cv2.warpAffine(noisy, M, (w, h), borderValue=(220, 220, 220))

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    _, enc = cv2.imencode(".png", rotated)
    page.insert_image(page.rect, stream=enc.tobytes())
    doc.save(str(path))
    doc.close()
    return path


def generate_all_test_pdfs() -> dict[str, Path]:
    pdfs = {
        "test1_digital_text": create_digital_text_pdf(TEST_DIR / "test1_digital_text.pdf"),
        "test2_scanned_text": create_scanned_text_pdf(TEST_DIR / "test2_scanned_text.pdf"),
        "test3_20_pages": create_20_pages_pdf(TEST_DIR / "test3_20_pages.pdf"),
        "test4_images": create_images_pdf(TEST_DIR / "test4_images.pdf"),
        "test5_blurry": create_blurry_pdf(TEST_DIR / "test5_blurry.pdf"),
        "test6_qr_code": create_qr_pdf(TEST_DIR / "test6_qr_code.pdf"),
        "test7_barcode": create_barcode_pdf(TEST_DIR / "test7_barcode.pdf"),
        "test8_signatures": create_signatures_pdf(TEST_DIR / "test8_signatures.pdf"),
        "test9_stamps": create_stamps_pdf(TEST_DIR / "test9_stamps.pdf"),
        "test10_mixed": create_mixed_pdf(TEST_DIR / "test10_mixed.pdf"),
        "test11_repeated_words": create_repeated_words_pdf(TEST_DIR / "test11_repeated_words.pdf"),
        "test12_accents": create_accents_pdf(TEST_DIR / "test12_accents.pdf"),
        "test13_difficult": create_difficult_pdf(TEST_DIR / "test13_difficult.pdf"),
    }
    return pdfs


if __name__ == "__main__":
    print(f"Generating test PDFs in {TEST_DIR}...")
    generated = generate_all_test_pdfs()
    for name, p in generated.items():
        print(f"✓ Generated {name}: {p.name} ({p.stat().st_size} bytes)")
    print(f"All {len(generated)} test PDFs successfully created!")
