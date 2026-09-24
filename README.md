# LectorPDF — Sistema de Análisis Documental, Visión Artificial & OCR

LectorPDF es una plataforma web profesional para la carga, análisis profundo, indexación página a página y consulta inteligente de documentos PDF (desde 1 hasta 100+ páginas). Integra procesamiento de texto digital, OCR inteligente con preprocesamiento avanzado de imágenes, visión por computador local para reconocimiento de objetos, detección geométrica y cromática de firmas y sellos, decodificación de códigos QR / códigos de barras 1D, y un visor PDF interactivo integrado.

---

## 1. Arquitectura y Justificación Tecnológica

| Componente | Tecnología | Justificación Técnica |
| :--- | :--- | :--- |
| **Backend Framework** | **Python 3 + FastAPI** | Asíncrono de alto rendimiento, validación nativa con Pydantic, generación automática de OpenAPI y concurrencia para procesamiento en segundo plano sin bloquear solicitudes HTTP. |
| **Motor de PDF** | **PyMuPDF (fitz)** | La librería de procesamiento de PDF más rápida del ecosistema open-source en C (MuPDF). Extrae texto vectorial de forma instantánea, detecta tablas vectoriales (`find_tables`), extrae imágenes incrustadas (`get_images`) y renderiza páginas con calidad configurable (DPI) en milisegundos. |
| **Preprocesamiento OCR** | **OpenCV (cv2) + NumPy** | Aplica filtros matemáticos rigurosos: conversión a escala de grises, reducción de ruido con filtro bilateral, realce de contraste adaptativo local (CLAHE), corrección de inclinación (*deskew*) mediante `minAreaRect`, y binarización Otsu adaptativa para legibilidad de textos borrosos. |
| **Motor OCR** | **Tesseract OCR 5 + PyTesseract** | Motor OCR estándar de la industria. Configurado con datos de entrenamiento en Español e Inglés (`spa+eng`). El sistema evalúa inteligentemente cuándo la página posee capa de texto válida y cuándo requiere ejecutar OCR. |
| **Visión Artificial Local** | **ONNX Runtime + MobileNetV2** | Inferencia ultraligera (14 MB) de redes neuronales convolucionales ejecutadas en CPU sin requerir dependencias pesadas como PyTorch (2GB). Mapea 1000 clases a conceptos semánticos (árboles, vehículos, personas, casas, animales, objetos). |
| **Códigos 1D / 2D** | **PyZbar + OpenCV Barcode/QR** | Detección híbrida redundante para códigos QR y códigos de barras (Code128, EAN13, Code39, UPCA), con fallback de contornos jerárquicos (1:1:3:1:1) para códigos dañados no decodificables. |
| **Detección de Firmas & Sellos**| **Heurísticas OpenCV + Análisis HSV** | Detección basada en densidad de trazos cursivos, componentes conexos, relación de aspecto y máscaras de color (tinta azul, tinta roja, tinta violeta) con cálculo realista de confianza. |
| **Base de Datos & Índice** | **SQLite en modo WAL** | Cero dependencias externas para desarrollo y despliegue local. El modo WAL (*Write-Ahead Logging*) permite lecturas concurrentes continuas mientras el trabajador en segundo plano actualiza el progreso página a página. |
| **Frontend** | **React 19 + TypeScript + Vite + Tailwind CSS** | Interfaz tipo SaaS moderna (estilo Linear/Stripe), ultra rápida, tipada rigurosamente de punta a punta, con visor interactivo de documentos y resaltado gráfico de detecciones. |

---

## 2. Diferenciación Crítica: Coincidencia Textual vs Coincidencia Visual

Una regla fundamental del sistema es **no alucinar ni confundir texto con elementos visuales**:
- Si un PDF contiene el texto: *"El árbol fue plantado en 2024"* pero **no** contiene una fotografía o imagen de un árbol:
  - Consulta: `"¿Hay una imagen de un árbol?"` ➔ **Responde NO ENCONTRADO** (especifica que no hay evidencia visual).
  - Consulta: `"¿Existe la palabra árbol?"` ➔ **Responde ENCONTRADO en la Página X (Texto)**.
  - Consulta: `"árbol"` (búsqueda general) ➔ **Diferencia ambos**, indicando si existe en texto, en imagen, o en ambos con tarjetas de tipo específico.

---

## 3. Funcionalidades Principales

1. **Carga Segura de Archivos**: Drag & Drop y selector tradicional con validación de cabecera binaria `%PDF-`, tipo MIME, límite configurable (100 MB) y protección contra documentos encriptados o con path traversal.
2. **Monitoreo Real del Progreso**: Porcentaje real calculado con base en la página actual y etapa en curso (`Extrayendo texto`, `Ejecutando OCR`, `Analizando imágenes`, `Detectando códigos`, `Indexando contenido`).
3. **Visor PDF Integrado**:
   - Navegación anterior / siguiente / ir a página específica.
   - Zoom interactivo (50% a 250%) y restablecimiento a 100%.
   - **Capas interactivas de detección**: cajas delimitadoras (*bounding boxes*) sobre la página que identifican visualmente QR, códigos de barras, firmas, sellos, tablas y objetos detectados.
4. **Asistente Inteligente & Búsqueda NLP**:
   - Preguntas de existencia: *"¿Hay una firma?"*, *"¿Existe un sello?"*, *"¿Hay un código QR?"*, *"¿Hay un árbol?"*.
   - Resúmenes de página: *"¿Qué contiene la página 15?"*.
   - Conteo: *"¿Cuántas páginas contienen la palabra factura?"*.
   - Búsqueda exacta de identificadores: *"¿Existe el número de identificación 123456789?"*.
   - Búsqueda de texto insensible a acentos (*"Bogota"* localiza *"Bogotá"*) e insensible a mayúsculas.
   - Botón directo `[Ver página X]` que desplaza el visor automáticamente a la página de la coincidencia.

---

## 4. Requisitos del Sistema

- **Python**: 3.10 o superior (verificado y probado en Python 3.14).
- **Node.js**: v18 o superior (verificado en Node v26).
- **Librerías del Sistema**:
  - `tesseract-ocr` (con paquetes de idioma `tesseract-ocr-spa` o archivos `.traineddata`).
  - `libzbar0` / `libzbar-dev` (para decodificación de códigos de barras).
  - `libgl1` (para OpenCV).

---

## 5. Instalación y Ejecución

### Opción A: Ejecución Local Rápida (Sin Docker)

1. **Clonar el repositorio**:
   ```bash
   git clone <URL_DEL_REPOSITORIO>
   cd lector_pdf.es
   ```

2. **Crear y activar entorno virtual**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Instalar dependencias de Python**:
   ```bash
   pip install --upgrade pip
   pip install -r backend/requirements.txt
   ```

4. **Instalar dependencias de Frontend y compilar**:
   ```bash
   npm --prefix frontend install
   npm --prefix frontend run build
   ```

5. **Iniciar el aplicativo completo**:
   Puedes iniciar ambos servidores con el script proporcionado:
   ```bash
   ./scripts/run_dev.sh
   ```
   O manualmente en terminales separadas:
   - **Backend**:
     ```bash
     uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
     ```
   - **Frontend**:
     ```bash
     npm --prefix frontend run dev
     ```

6. Abrir en el navegador:
   - Frontend en desarrollo: [http://localhost:3000](http://localhost:3000)
   - Servidor unificado: [http://localhost:8000](http://localhost:8000)
   - Documentación interactiva Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Opción B: Ejecución con Docker y Docker Compose

El proyecto incluye configuración completa de contenedores:

```bash

docker compose up --build
```

- El frontend estará disponible en: `http://localhost:3000`
- La API del backend estará disponible en: `http://localhost:8000`
- Los documentos e índices en SQLite se persisten en el volumen `./backend/storage`.

Para detener los contenedores:
```bash
docker compose down
```

---

## 6. Variables de Entorno

Copiar la plantilla de configuración:
```bash
cp .env.example .env
```

Parámetros disponibles:
- `DEBUG`: `true` o `false` (default: `false`).
- `MAX_UPLOAD_SIZE`: Tamaño máximo de subida en bytes (default: `104857600` = 100 MB).
- `RENDER_DPI`: Resolución de renderizado de páginas para el visor (default: `150`).
- `TESSERACT_CMD`: Ruta al ejecutable de Tesseract (default: `/usr/bin/tesseract`).
- `TESSERACT_LANG`: Idiomas para OCR (default: `spa+eng`).
- `ONNX_MODEL_URL`: URL del modelo de visión MobileNetV2 ONNX.
- `ENABLE_CLOUD_AI`: Opcional para modelos en la nube (default: `false`).
- `OPENAI_API_KEY`: Clave opcional si se habilita integración en la nube.

---

## 7. Pruebas Automatizadas (Testing Suite)

Se incluye un generador sintético de 13 documentos PDF reales para cubrir el 100% de los casos solicitados:

### Generar los 13 PDFs de prueba:
```bash
./scripts/generate_samples.sh
```

### Ejecutar todas las pruebas con pytest:
```bash
./scripts/run_tests.sh
```

### Matriz de Pruebas Ejecutadas:

| ID | Caso de Prueba | Archivo de Prueba | Validación |
| :--- | :--- | :--- | :--- |
| **TEST 1** | PDF de texto digital | `test1_digital_text.pdf` | Extracción nativa sin OCR innecesario. |
| **TEST 2** | PDF escaneado | `test2_scanned_text.pdf` | Ejecución de OCR Tesseract sobre imagen raster. |
| **TEST 3** | PDF con 20+ páginas | `test3_20_pages.pdf` | Procesamiento e indexación completa de 22 páginas. |
| **TEST 4** | PDF con imágenes | `test4_images.pdf` | Detección visual de árbol y vehículo con modelo ONNX. |
| **TEST 5** | PDF con imágenes borrosas | `test5_blurry.pdf` | Preprocesamiento con CLAHE, sharpen y OCR recuperado. |
| **TEST 6** | PDF con código QR | `test6_qr_code.pdf` | Decodificación de URL y coordenadas de bounding box. |
| **TEST 7** | PDF con código de barras | `test7_barcode.pdf` | Detección de código 1D y referencia numérica. |
| **TEST 8** | PDF con firmas | `test8_signatures.pdf` | Detección de trazo cursivo en tinta azul con confianza. |
| **TEST 9** | PDF con sellos | `test9_stamps.pdf` | Detección de sello circular en tinta roja. |
| **TEST 10** | PDF mixto texto + imágenes | `test10_mixed.pdf` | Análisis multimodal: texto + fotos + tablas + firmas. |
| **TEST 11** | Palabras repetidas en páginas | `test11_repeated_words.pdf` | Coincidencias de "factura" en págs 1, 3 y 5. |
| **TEST 12** | Palabras con tildes | `test12_accents.pdf` | Búsqueda insensible a tildes (Bogota vs Bogotá). |
| **TEST 13** | Páginas difíciles de leer | `test13_difficult.pdf` | Deskew de 3 grados, denoising y extracción OCR. |

---

## 8. Solución de Problemas (Troubleshooting)

1. **Error: `TesseractNotFoundError`**:
   - Verifique que `tesseract` esté instalado en su sistema (`which tesseract`).
   - En sistemas basados en Debian/Ubuntu: `sudo apt-get install tesseract-ocr tesseract-ocr-spa`.
   - En sistemas Arch/CachyOS: `sudo pacman -S tesseract tesseract-data-spa`.

2. **Error de carga de `libzbar.so`**:
   - Instale la librería dinámica: `sudo apt-get install libzbar0` o `sudo pacman -S zbar`.

3. **Puerto 8000 o 3000 ocupado**:
   - Inicie en puertos alternativos: `uvicorn backend.app.main:app --port 8080` y configure el proxy en `vite.config.ts`.

---

## 9. Limitaciones Técnicas Reales Conocidas

1. **Textos Caligráficos Extremos en Manuscritos**:
   - Tesseract está optimizado primariamente para fuentes tipográficas y documentos impresos. Documentos antiguos con caligrafía cursiva humana continua de baja legibilidad pueden presentar menor precisión en la transcripción OCR en comparación con texto mecanografiado.
2. **Firmas Superpuestas sobre Texto Denso**:
   - Cuando una firma manuscrita se realiza exactamente encima de un párrafo de texto impreso en tinta negra idéntica, el algoritmo de componentes conexos segmenta los trazos con una confianza moderada (60% - 75%), notificando la detección como `Posible firma` de acuerdo a los criterios de no-alucinación.
3. **Códigos QR severamente mutilados**:
   - Si más del 35% de los patrones de alineación de un código QR están destruidos físicamente, el sistema reportará: *"Se detectó un código QR en la página X, pero no fue posible decodificar su contenido"*, preservando la caja delimitadora en el visor.