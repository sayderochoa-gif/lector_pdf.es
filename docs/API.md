# Especificación de la API REST - LectorPDF

Todos los endpoints se encuentran expuestos bajo el prefijo `/api`.

---

## 1. Estado y Salud del Sistema

### `GET /api/health`
Retorna el estado de operatividad de los servicios del backend (motor OCR Tesseract y modelo de visión ONNX).

**Respuesta Exitosa (200 OK):**
```json
{
  "status": "healthy",
  "app_name": "LectorPDF - AI Document Vision & OCR",
  "version": "1.0.0",
  "ocr_available": true,
  "tesseract_version": "5.5.3",
  "vision_model_loaded": true
}
```

---

## 2. Gestión de Documentos

### `POST /api/documents/upload`
Carga un documento PDF para análisis automático. Inicia una tarea asíncrona en segundo plano que procesa el archivo página a página.

**Parámetros:**
- `file` (Multipart/form-data): Archivo PDF binario. Límite máximo configurable (100 MB).

**Validaciones de Seguridad:**
- Extensión obligatoria `.pdf`.
- Tipo MIME validado (`application/pdf`).
- Validación de número mágico binario (`%PDF-`).
- Detección de contraseñas y archivos dañados sin páginas.

**Respuesta Exitosa (201 Created):**
```json
{
  "id": "c8a41dfa-45f8-4b71-92b0-91129b0a7012",
  "filename": "contrato_servicios.pdf",
  "filesize": 1450230,
  "page_count": 22,
  "status": "pending",
  "current_page": 0,
  "current_step": "En cola",
  "progress_percent": 0,
  "created_at": "2026-09-23T17:30:00Z",
  "updated_at": "2026-09-23T17:30:00Z",
  "error_message": null,
  "summary_counts": {
    "text_pages": 0,
    "ocr_pages": 0,
    "qr_codes": 0,
    "barcodes": 0,
    "signatures": 0,
    "stamps": 0,
    "images": 0,
    "tables": 0,
    "visual_objects": 0
  }
}
```

---

### `GET /api/documents`
Lista todos los documentos cargados en el sistema ordenados por fecha de creación descendente.

---

### `GET /api/documents/{id}`
Obtiene los detalles completos y métricas de análisis de un documento específico.

---

### `GET /api/documents/{id}/status`
Endpoint liviano optimizado para sondeo (polling) en tiempo real del progreso de procesamiento.

**Respuesta Exitosa (200 OK):**
```json
{
  "id": "c8a41dfa-45f8-4b71-92b0-91129b0a7012",
  "filename": "contrato_servicios.pdf",
  "status": "processing",
  "page_count": 22,
  "current_page": 7,
  "current_step": "Página 7 de 22: Analizando imágenes y elementos visuales",
  "progress_percent": 34,
  "error_message": null,
  "summary_counts": {
    "text_pages": 6,
    "ocr_pages": 1,
    "qr_codes": 1,
    "barcodes": 0,
    "signatures": 2,
    "stamps": 1,
    "images": 4,
    "tables": 2,
    "visual_objects": 3
  }
}
```

---

### `GET /api/documents/{id}/pages/{page}`
Obtiene el índice estructurado JSON de una página individual (elementos visuales, texto, tablas, códigos).

---

### `GET /api/documents/{id}/pages/{page}/image`
Retorna la renderización gráfica en alta resolución (WebP/PNG) de la página para el visor interactivo.

---

## 3. Consultas Inteligentes: Chatbot (RAG con IA) y Chat

### `POST /api/documents/{id}/chatbot`
**Proceso Chatbot**: Utiliza una arquitectura **RAG (Retrieval-Augmented Generation) con IA** para responder preguntas complejas y de razonamiento multimodal sobre el documento:
- **Detecciones complejas**: *"¿El documento tiene firmas?"*, *"¿Hay código QR en el documento?"*, *"¿Hay código de barras dentro del documento?"*, *"¿Existe algún sello o estampa?"*, *"¿Hay tablas estructuradas?"*.
- **Razonamiento multimodal y semántico**: *"¿De qué trata este documento?"*, *"¿Qué información extrajo Tesseract OCR?"*, *"¿Cuáles son las cláusulas de vigencia y valor?"*.
- Realiza **recuperación multimodal (Retrieval)** de pasajes y detecciones, **aumento de contexto (Augmentation)** y **generación con IA (Generation)**.

**Cuerpo de la Solicitud (JSON):**
```json
{
  "query": "¿El documento tiene firmas?"
}
```

**Respuesta Exitosa (200 OK):**
```json
{
  "found": true,
  "status": "found",
  "query": "¿El documento tiene firmas?",
  "intent": "chatbot_rag_signatures",
  "explanation": "🤖 **[Chatbot RAG - Análisis con IA]**\n\n✓ **Sí, el documento tiene firmas detectadas** (1 firma(s) encontrada(s)):\n\n• **Página 1**: Firma identificada con confianza del 95%\n\n*Detalles*: El análisis de densidad de trazos y visión computacional confirmó la presencia de signaturas manuscritas válidas.",
  "matches": [
    {
      "page": 1,
      "type": "signature",
      "confidence": 0.95,
      "label": "Firma manuscrita",
      "snippet": "Firma detectada en página 1 (manuscrita)",
      "bbox": { ... }
    }
  ],
  "total_matches": 1,
  "pages_found": [1]
}
```

---

### `POST /api/documents/{id}/chat`
**Proceso Chat**: Responde preguntas directas y no tan complejas mediante búsqueda léxica y reglas deterministas de alta velocidad:
- **Conteo de palabras**: *"¿Cuántas páginas contienen la palabra factura?"*.
- **Resumen básico de página**: *"¿Qué contiene la página 1?"*.
- **Identificadores exactos**: *"¿Existe el número de identificación 123456789?"*, *"NIT 900.123.456-7"*.
- **Búsqueda léxica directa**: *"Buscar Bogotá"*, *"factura"*.

**Cuerpo de la Solicitud (JSON):**
```json
{
  "query": "¿Cuántas páginas contienen la palabra factura?"
}
```

**Respuesta Exitosa (200 OK):**
```json
{
  "found": true,
  "status": "found",
  "query": "¿Cuántas páginas contienen la palabra factura?",
  "intent": "chat_count",
  "explanation": "✓ [Chat] La palabra \"factura\" aparece en 3 página(s):\nPágina 1, Página 3, Página 5.",
  "matches": [ ... ],
  "total_matches": 3,
  "pages_found": [1, 3, 5]
}
```

---

### `POST /api/documents/{id}/query`
Endpoint retrocompatible que enruta automáticamente la consulta según su complejidad hacia el servicio `Chat` o `Chatbot (RAG)`.

**Cuerpo de la Solicitud (JSON):**
```json
{
  "query": "¿Hay un árbol?"
}
```

---

### `GET /api/documents/{id}/search?q={termino}&exact={bool}&case_sensitive={bool}`
Búsqueda de texto completo insensible a acentos ortográficos (e.g. `Bogota` encuentra `Bogotá`), con extracción de contexto y fragmentos circundantes (*snippets*).
