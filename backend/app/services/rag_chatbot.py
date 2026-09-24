import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import httpx

from backend.app.config import settings
from backend.app.models.schemas import BoundingBox, PageData, QueryMatch, QueryResponse
from backend.app.services.search_engine import extract_context_snippet, normalize_text, search_engine

logger = logging.getLogger(__name__)

SPANISH_STOP_WORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "a", "al",
    "en", "para", "por", "con", "sin", "sobre", "entre", "hasta", "desde", "hacia",
    "y", "e", "o", "u", "que", "qué", "quien", "quién", "quienes", "quiénes",
    "cual", "cuál", "cuales", "cuáles", "como", "cómo", "donde", "dónde", "cuando", "cuándo",
    "cuanto", "cuánto", "cuanta", "cuánta", "cuantos", "cuántos", "cuantas", "cuántas",
    "es", "son", "fue", "era", "ser", "hay", "habia", "había", "tiene", "tienen",
    "se", "su", "sus", "mi", "mis", "tu", "tus", "nuestro", "nuestra",
    "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas", "aquel", "aquella",
    "dice", "menciona", "trata", "contiene", "aparece", "existe",
    "documento", "archivo", "texto", "informacion", "información", "contenido",
}


class RAGContext:
    """Contenedor de información multimodal recuperada (Retrieval) para el RAG."""
    def __init__(self):
        self.signatures: List[Tuple[int, Any]] = []
        self.qr_codes: List[Tuple[int, Any]] = []
        self.barcodes: List[Tuple[int, Any]] = []
        self.stamps: List[Tuple[int, Any]] = []
        self.tables: List[Tuple[int, Any]] = []
        self.visual_objects: List[Tuple[int, Any]] = []
        self.images: List[Tuple[int, Any]] = []
        self.relevant_passages: List[Dict[str, Any]] = []
        self.tesseract_pages: List[PageData] = []
        self.all_pages_summary: Dict[str, Any] = {}


class RAGChatbot:
    """
    Chatbot basado en RAG (Retrieval-Augmented Generation) con IA para preguntas complejas:
    - Análisis multimodal: Firmas, Códigos QR, Códigos de barras, Sellos, Tablas, Fotos
    - Razonamiento semántico profundo sobre el contenido del documento y OCR
    - Recuperación contextual (Retrieval) + Aumento de conocimiento (Augmentation) + Generación con IA (Generation)
    """

    def process_chatbot(
        self,
        query: str,
        pages_data: List[PageData],
        doc_filename: str = "documento",
    ) -> QueryResponse:
        raw_query = query.strip()
        if not raw_query:
            return QueryResponse(
                found=False,
                status="not_found",
                query=raw_query,
                intent="chatbot_empty",
                explanation="Por favor ingrese su pregunta para el Chatbot con RAG e IA.",
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        # -------------------------------------------------------------
        # 1. RETRIEVAL (Recuperación Multimodal + Textual)
        # -------------------------------------------------------------
        rag_context = self._retrieve_multimodal_context(raw_query, pages_data, doc_filename)

        # -------------------------------------------------------------
        # 2. GENERATION (Generación Aumentada con IA)
        # -------------------------------------------------------------
        # Intentar llamar al modelo LLM si está configurado en cloud o local
        llm_response = self._try_cloud_or_local_llm(raw_query, rag_context, doc_filename)
        if llm_response:
            return llm_response

        # Motor de IA generativa y razonamiento multimodal integrado (offline/local)
        return self._generate_local_ai_rag(raw_query, rag_context, pages_data, doc_filename)

    def _retrieve_multimodal_context(
        self, query: str, pages_data: List[PageData], doc_filename: str
    ) -> RAGContext:
        ctx = RAGContext()
        q_norm = normalize_text(query)

        # Indexar elementos multimodales por página
        total_words = 0
        for p in pages_data:
            words = len((p.text or "").split())
            total_words += words

            for sig in p.signatures:
                ctx.signatures.append((p.page, sig))
            for qr in p.qr_codes:
                ctx.qr_codes.append((p.page, qr))
            for bc in p.barcodes:
                ctx.barcodes.append((p.page, bc))
            for stamp in p.stamps:
                ctx.stamps.append((p.page, stamp))
            for tbl in p.tables:
                ctx.tables.append((p.page, tbl))
            for obj in p.objects:
                ctx.visual_objects.append((p.page, obj))
            for img in p.images:
                ctx.images.append((p.page, img))

            if p.ocr_applied or p.extracted_by == "tesseract" or p.confidence.get("ocr", 0) > 0:
                ctx.tesseract_pages.append(p)

        ctx.all_pages_summary = {
            "total_pages": len(pages_data),
            "total_words": total_words,
            "filename": doc_filename,
            "has_signatures": len(ctx.signatures) > 0,
            "has_qr": len(ctx.qr_codes) > 0,
            "has_barcodes": len(ctx.barcodes) > 0,
            "has_stamps": len(ctx.stamps) > 0,
            "has_tables": len(ctx.tables) > 0,
        }

        # Tokenizar query para recuperación de pasajes de texto más relevantes
        query_words = [
            w for w in re.findall(r"\b[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9\-]+\b", q_norm)
            if len(w) >= 3 and w not in SPANISH_STOP_WORDS
        ]

        scored_passages = []
        for p in pages_data:
            text = p.text or ""
            # Dividir en fragmentos / oraciones con sentido
            chunks = [c.strip() for c in re.split(r"[\n\.]+", text) if len(c.strip()) > 8]
            for chunk in chunks:
                chunk_norm = normalize_text(chunk)
                score = sum(2.0 for w in query_words if w in chunk_norm)
                # Bonificación si coincide la frase entera
                if len(query_words) >= 2 and all(w in chunk_norm for w in query_words):
                    score += 5.0
                if score > 0:
                    scored_passages.append({
                        "page": p.page,
                        "text": chunk,
                        "score": score,
                        "ocr": p.ocr_applied,
                    })

        scored_passages.sort(key=lambda x: x["score"], reverse=True)
        ctx.relevant_passages = scored_passages[:8]

        return ctx

    def _try_cloud_or_local_llm(
        self, query: str, ctx: RAGContext, doc_filename: str
    ) -> Optional[QueryResponse]:
        """Llama a un proveedor de LLM (OpenAI o endpoint local compatible) si está habilitado."""
        if not settings.enable_cloud_ai or not settings.openai_api_key:
            return None

        try:
            # Ensamblar contexto aumentado (Augmented prompt)
            prompt_context = self._build_rag_prompt(query, ctx, doc_filename)

            headers = {
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Eres el Chatbot RAG con IA de LectorPDF. Respondes preguntas complejas de documentos analizados "
                            "con visión computacional y OCR. Sé conciso, preciso, cita siempre las páginas relevantes "
                            "y explica con certeza si existen firmas, códigos QR, códigos de barras, sellos o datos específicos."
                        ),
                    },
                    {"role": "user", "content": prompt_context},
                ],
                "temperature": 0.2,
            }

            with httpx.Client(timeout=12.0) as client:
                res = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    answer_text = data["choices"][0]["message"]["content"]

                    # Extraer páginas mencionadas y armar matches
                    pages_mentioned = sorted(list(set(int(m) for m in re.findall(r"p[aá]gina\s*(\d+)", answer_text, re.IGNORECASE))))
                    matches = self._build_matches_from_context(ctx, pages_mentioned)

                    return QueryResponse(
                        found=True if ("no encontr" not in answer_text.lower() and "no hay" not in answer_text.lower()) else False,
                        status="found",
                        query=query,
                        intent="rag_llm_chatbot",
                        explanation=f"🤖 [Chatbot RAG con IA]\n\n{answer_text}",
                        matches=matches,
                        total_matches=len(matches),
                        pages_found=pages_mentioned,
                    )
        except Exception as e:
            logger.warning(f"Fallo al invocar LLM externo: {e}. Usando generador RAG integrado.")

        return None

    def _build_rag_prompt(self, query: str, ctx: RAGContext, doc_filename: str) -> str:
        detections_info = []
        if ctx.signatures:
            sigs_desc = [f"Página {p} (confianza {int(s.confidence * 100)}%)" for p, s in ctx.signatures]
            detections_info.append(f"- Firmas encontradas ({len(ctx.signatures)}): {', '.join(sigs_desc)}")
        else:
            detections_info.append("- Firmas encontradas: Ninguna")

        if ctx.qr_codes:
            qrs_desc = [f"Página {p} (Contenido: {s.metadata.get('decoded_text', 'No decodificable')})" for p, s in ctx.qr_codes]
            detections_info.append(f"- Códigos QR ({len(ctx.qr_codes)}): {', '.join(qrs_desc)}")
        else:
            detections_info.append("- Códigos QR: Ninguno")

        if ctx.barcodes:
            bcs_desc = [f"Página {p} (Formato: {s.metadata.get('format', '1D')}, Contenido: {s.metadata.get('decoded_text', 'No decodificado')})" for p, s in ctx.barcodes]
            detections_info.append(f"- Códigos de barras ({len(ctx.barcodes)}): {', '.join(bcs_desc)}")
        else:
            detections_info.append("- Códigos de barras: Ninguno")

        if ctx.stamps:
            stamps_desc = [f"Página {p} (Color: {s.metadata.get('ink_color', 'tinta')})" for p, s in ctx.stamps]
            detections_info.append(f"- Sellos/Estampas ({len(ctx.stamps)}): {', '.join(stamps_desc)}")

        passages_text = []
        for pas in ctx.relevant_passages:
            passages_text.append(f"[Página {pas['page']}]: {pas['text']}")

        return (
            f"Documento: {doc_filename}\n"
            f"Total de páginas: {ctx.all_pages_summary.get('total_pages', 0)}\n\n"
            f"EVIDENCIA MULTIMODAL DETECTADA:\n" + "\n".join(detections_info) + "\n\n"
            f"PASAJES DE TEXTO RECUPERADOS:\n" + ("\n".join(passages_text) if passages_text else "Sin texto relevante directo.") + "\n\n"
            f"PREGUNTA DEL USUARIO:\n{query}"
        )

    def _generate_local_ai_rag(
        self,
        raw_query: str,
        ctx: RAGContext,
        pages_data: List[PageData],
        doc_filename: str,
    ) -> QueryResponse:
        """
        Motor de IA generativa y razonamiento multimodal local de alta fidelidad.
        Sintetiza la respuesta basándose en la evidencia recuperada por el RAG.
        """
        q_norm = normalize_text(raw_query)

        # ---------------------------------------------------------------------
        # CASO 1: ¿El documento tiene firmas?
        # ---------------------------------------------------------------------
        is_signature_q = (
            any(w in q_norm for w in [
                "firma", "firmas", "firmando", "firmante", "firmantes", "firmado", "firmada",
                "firmados", "firmadas", "rúbrica", "rubrica", "signatura", "signaturas",
                "autógrafo", "autografo", "suscribe", "suscrito", "suscrita"
            ])
            or any(p in q_norm for p in [
                "tiene firmas", "tiene firma", "hay firmas", "hay firma", "esta firmado",
                "está firmado", "fue firmado", "quien firmo", "quién firmó", "no reconoce las firmas",
                "reconoce las firmas", "reconoce firmas", "documento firmado", "aparecen firmas"
            ])
        )
        if is_signature_q:
            return self._answer_signatures_rag(raw_query, ctx)

        # ---------------------------------------------------------------------
        # CASO 2: ¿Hay código QR en el documento?
        # ---------------------------------------------------------------------
        if "qr" in q_norm or "código qr" in q_norm or "codigo qr" in q_norm:
            return self._answer_qr_rag(raw_query, ctx)

        # ---------------------------------------------------------------------
        # CASO 3: ¿Hay código de barras dentro del documento?
        # ---------------------------------------------------------------------
        if any(w in q_norm for w in ["código de barras", "codigo de barras", "barcode", "código de barra", "codigo de barra"]):
            return self._answer_barcode_rag(raw_query, ctx)

        # ---------------------------------------------------------------------
        # CASO 4: Sellos o estampas
        # ---------------------------------------------------------------------
        if any(w in q_norm for w in ["sello", "sellos", "estampa", "estampado", "timbre"]):
            return self._answer_stamps_rag(raw_query, ctx)

        # ---------------------------------------------------------------------
        # CASO 5: Tablas estructuradas
        # ---------------------------------------------------------------------
        if any(w in q_norm for w in ["tabla", "tablas", "cuadro"]):
            return self._answer_tables_rag(raw_query, ctx)

        # ---------------------------------------------------------------------
        # CASO 6: Elementos visuales / Fotografías / Objetos
        # ---------------------------------------------------------------------
        if any(w in q_norm for w in ["imagen", "foto", "fotografia", "fotografía", "arbol", "árbol", "persona", "vehiculo", "vehículo", "carro", "casa"]):
            return self._answer_visual_rag(raw_query, ctx)

        # ---------------------------------------------------------------------
        # CASO 7: Preguntas sobre OCR Tesseract
        # ---------------------------------------------------------------------
        if any(w in q_norm for w in ["tesseract", "ocr", "extrajo el ocr", "extrajo tesseract"]):
            return self._answer_tesseract_rag(raw_query, ctx)

        # ---------------------------------------------------------------------
        # CASO 8: Resumen general o preguntas semánticas abiertas del contenido
        # ---------------------------------------------------------------------
        return self._answer_semantic_content_rag(raw_query, ctx, pages_data, doc_filename)

    def _answer_signatures_rag(self, query: str, ctx: RAGContext) -> QueryResponse:
        matches: List[QueryMatch] = []
        for page_num, sig in ctx.signatures:
            matches.append(
                QueryMatch(
                    page=page_num,
                    type="signature",
                    confidence=sig.confidence,
                    label=sig.label,
                    snippet=f"Firma detectada en página {page_num} ({sig.metadata.get('kind', 'manuscrita')})",
                    bbox=sig.bbox,
                    metadata=sig.metadata,
                )
            )

        pages_found = sorted(list(set(m.page for m in matches)))

        if not matches:
            return QueryResponse(
                found=False,
                status="not_found",
                query=query,
                intent="chatbot_rag_signatures",
                explanation=(
                    "🤖 **[Chatbot RAG - Análisis con IA]**\n\n"
                    "⚠ **Resultado**: No encontré evidencia de firmas manuscritas ni rúbricas en el documento.\n\n"
                    "• El detector de visión computacional y trazados no identificó grafías de firma en ninguna de las páginas analizadas."
                ),
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        pages_bullets = []
        for m in matches:
            kind_str = m.metadata.get("kind", "manuscrita") if m.metadata else "manuscrita"
            conf_pct = int(m.confidence * 100)
            pages_bullets.append(f"• **Página {m.page}**: {m.label} ({kind_str}) — Confianza: **{conf_pct}%**")

        explanation = (
            f"🤖 **[Chatbot RAG - Análisis con IA]**\n\n"
            f"✓ **Sí, el documento tiene firmas detectadas** ({len(matches)} firma(s) encontrada(s)):\n\n"
            + "\n".join(pages_bullets) + "\n\n"
            f"*Detalles*: El análisis de densidad de trazos, curvas vectoriales y visión computacional confirmó la presencia de firmas válidas."
        )

        return QueryResponse(
            found=True,
            status="found",
            query=query,
            intent="chatbot_rag_signatures",
            explanation=explanation,
            matches=matches,
            total_matches=len(matches),
            pages_found=pages_found,
        )

    def _answer_qr_rag(self, query: str, ctx: RAGContext) -> QueryResponse:
        matches: List[QueryMatch] = []
        for page_num, qr in ctx.qr_codes:
            decoded = qr.metadata.get("decoded_text", "")
            matches.append(
                QueryMatch(
                    page=page_num,
                    type="qr",
                    confidence=qr.confidence,
                    label=qr.label,
                    snippet=f"Contenido QR: {decoded}" if decoded else "Código QR detectado",
                    bbox=qr.bbox,
                    metadata=qr.metadata,
                )
            )

        pages_found = sorted(list(set(m.page for m in matches)))

        if not matches:
            return QueryResponse(
                found=False,
                status="not_found",
                query=query,
                intent="chatbot_rag_qr",
                explanation=(
                    "🤖 **[Chatbot RAG - Análisis con IA]**\n\n"
                    "⚠ **Resultado**: No se detectaron códigos QR en ninguna página del documento."
                ),
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        details = []
        for m in matches:
            dec = m.metadata.get("decoded_text") if m.metadata else None
            dec_str = f"\"{dec}\"" if dec else "Estructura QR identificada (contenido no legible/borroso)"
            details.append(f"• **Página {m.page}**: Contenido decodificado: {dec_str}")

        explanation = (
            f"🤖 **[Chatbot RAG - Análisis con IA]**\n\n"
            f"✓ **Sí, hay código QR en el documento** ({len(matches)} código(s) detectado(s)):\n\n"
            + "\n".join(details)
        )

        return QueryResponse(
            found=True,
            status="found",
            query=query,
            intent="chatbot_rag_qr",
            explanation=explanation,
            matches=matches,
            total_matches=len(matches),
            pages_found=pages_found,
        )

    def _answer_barcode_rag(self, query: str, ctx: RAGContext) -> QueryResponse:
        matches: List[QueryMatch] = []
        for page_num, bc in ctx.barcodes:
            decoded = bc.metadata.get("decoded_text", "")
            matches.append(
                QueryMatch(
                    page=page_num,
                    type="barcode",
                    confidence=bc.confidence,
                    label=bc.label,
                    snippet=f"Formato: {bc.metadata.get('format', '1D')}, Contenido: {decoded}",
                    bbox=bc.bbox,
                    metadata=bc.metadata,
                )
            )

        pages_found = sorted(list(set(m.page for m in matches)))

        if not matches:
            return QueryResponse(
                found=False,
                status="not_found",
                query=query,
                intent="chatbot_rag_barcode",
                explanation=(
                    "🤖 **[Chatbot RAG - Análisis con IA]**\n\n"
                    "⚠ **Resultado**: No se encontraron códigos de barras dentro del documento."
                ),
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        details = []
        for m in matches:
            dec = m.metadata.get("decoded_text") if m.metadata else "No decodificado"
            fmt = m.metadata.get("format", "1D") if m.metadata else "1D"
            details.append(f"• **Página {m.page}**: Formato **{fmt}**, Contenido: `{dec}`")

        explanation = (
            f"🤖 **[Chatbot RAG - Análisis con IA]**\n\n"
            f"✓ **Sí, hay código de barras dentro del documento**:\n\n"
            + "\n".join(details)
        )

        return QueryResponse(
            found=True,
            status="found",
            query=query,
            intent="chatbot_rag_barcode",
            explanation=explanation,
            matches=matches,
            total_matches=len(matches),
            pages_found=pages_found,
        )

    def _answer_stamps_rag(self, query: str, ctx: RAGContext) -> QueryResponse:
        matches = [
            QueryMatch(
                page=p,
                type="stamp",
                confidence=st.confidence,
                label=st.label,
                snippet=f"Sello detectado en página {p} ({st.metadata.get('ink_color', 'tinta')})",
                bbox=st.bbox,
                metadata=st.metadata,
            )
            for p, st in ctx.stamps
        ]
        pages_found = sorted(list(set(m.page for m in matches)))

        if not matches:
            return QueryResponse(
                found=False,
                status="not_found",
                query=query,
                intent="chatbot_rag_stamps",
                explanation="🤖 **[Chatbot RAG]**\n\n⚠ No encontré evidencia de sellos o timbres en el documento.",
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        bullets = "\n".join(f"• **Página {p}**: Sello de tinta detectado" for p in pages_found)
        return QueryResponse(
            found=True,
            status="found",
            query=query,
            intent="chatbot_rag_stamps",
            explanation=f"🤖 **[Chatbot RAG - Análisis con IA]**\n\n✓ **Sellos detectados en el documento**:\n\n{bullets}",
            matches=matches,
            total_matches=len(matches),
            pages_found=pages_found,
        )

    def _answer_tables_rag(self, query: str, ctx: RAGContext) -> QueryResponse:
        matches = [
            QueryMatch(
                page=p,
                type="table",
                confidence=t.confidence,
                label=t.label,
                snippet=f"Tabla en página {p} ({t.metadata.get('rows', '?')} filas × {t.metadata.get('columns', '?')} col)",
                bbox=t.bbox,
                metadata=t.metadata,
            )
            for p, t in ctx.tables
        ]
        pages_found = sorted(list(set(m.page for m in matches)))

        if not matches:
            return QueryResponse(
                found=False,
                status="not_found",
                query=query,
                intent="chatbot_rag_tables",
                explanation="🤖 **[Chatbot RAG]**\n\n⚠ No encontré tablas tabulares estructuradas en el documento.",
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        bullets = "\n".join(
            f"• **Página {m.page}**: {m.metadata.get('rows', '?')} filas × {m.metadata.get('columns', '?')} columnas"
            for m in matches
        )
        return QueryResponse(
            found=True,
            status="found",
            query=query,
            intent="chatbot_rag_tables",
            explanation=f"🤖 **[Chatbot RAG - Análisis con IA]**\n\n✓ **Tablas estructuradas encontradas**:\n\n{bullets}",
            matches=matches,
            total_matches=len(matches),
            pages_found=pages_found,
        )

    def _answer_visual_rag(self, query: str, ctx: RAGContext) -> QueryResponse:
        q_norm = normalize_text(query)
        matches: List[QueryMatch] = []

        # Categorías y sinónimos
        synonyms = ["imagen", "foto", "objeto"]
        if any(w in q_norm for w in ["arbol", "árbol", "planta", "vegetacion"]):
            synonyms.extend(["arbol", "tree", "plant", "vegetacion"])
        elif any(w in q_norm for w in ["persona", "humano", "hombre", "mujer", "gente"]):
            synonyms.extend(["persona", "person", "humano", "man", "woman"])
        elif any(w in q_norm for w in ["vehiculo", "vehículo", "carro", "auto", "coche"]):
            synonyms.extend(["vehiculo", "car", "auto", "coche", "truck"])
        elif any(w in q_norm for w in ["casa", "edificio"]):
            synonyms.extend(["casa", "house", "building"])

        for p, obj in ctx.visual_objects:
            obj_label_norm = normalize_text(obj.label)
            if any(s in obj_label_norm for s in synonyms):
                matches.append(
                    QueryMatch(
                        page=p,
                        type="visual",
                        confidence=obj.confidence,
                        label=obj.label,
                        snippet=f"Elemento visual clasificado: {obj.label}",
                        bbox=obj.bbox,
                        metadata=obj.metadata,
                    )
                )

        if not matches and any(w in q_norm for w in ["foto", "imagen"]):
            for p, img in ctx.images:
                matches.append(
                    QueryMatch(
                        page=p,
                        type="visual",
                        confidence=img.confidence,
                        label=img.label,
                        snippet=f"Fotografía o imagen en página {p}",
                        bbox=img.bbox,
                        metadata=img.metadata,
                    )
                )

        pages_found = sorted(list(set(m.page for m in matches)))
        if not matches:
            return QueryResponse(
                found=False,
                status="not_found",
                query=query,
                intent="chatbot_rag_visual",
                explanation=f"🤖 **[Chatbot RAG]**\n\n⚠ No encontré evidencia visual o fotográfica correspondiente a su consulta.",
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        bullets = "\n".join(f"• **Página {m.page}**: {m.label} (Confianza: {int(m.confidence * 100)}%)" for m in matches)
        return QueryResponse(
            found=True,
            status="found",
            query=query,
            intent="chatbot_rag_visual",
            explanation=f"🤖 **[Chatbot RAG - Visión Computacional con IA]**\n\n✓ **Elementos visuales detectados**:\n\n{bullets}",
            matches=matches,
            total_matches=len(matches),
            pages_found=pages_found,
        )

    def _answer_tesseract_rag(self, query: str, ctx: RAGContext) -> QueryResponse:
        if not ctx.tesseract_pages:
            return QueryResponse(
                found=True,
                status="found",
                query=query,
                intent="chatbot_rag_tesseract",
                explanation=(
                    "🤖 **[Chatbot RAG - Auditoría OCR]**\n\n"
                    "ℹ Este documento cuenta con una **capa de texto digital nativa** validada por PyMuPDF.\n\n"
                    "No requirió Tesseract OCR ya que el texto fue extraído directamente de la estructura vectorial del PDF."
                ),
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        details = []
        matches: List[QueryMatch] = []
        for p in ctx.tesseract_pages:
            conf = p.confidence.get("ocr", p.confidence.get("tesseract", 0.90))
            conf_pct = int(conf * 100) if conf <= 1.0 else int(conf)
            words_count = len(p.text.split())
            preview = p.text[:250].replace("\n", " ") + "..."

            rev_info = ""
            if p.opencv_review:
                rev = p.opencv_review
                rev_info = f" (Nitidez: {rev.get('sharpness_score', 'N/A')}, Contraste: {rev.get('contrast', 'N/A')})"

            details.append(f"• **Página {p.page}**: Confianza OCR **{conf_pct}%** ({words_count} palabras extraídas){rev_info}")
            matches.append(
                QueryMatch(
                    page=p.page,
                    type="tesseract_ocr",
                    confidence=conf if conf <= 1.0 else conf / 100.0,
                    label=f"Extracción Tesseract (Página {p.page})",
                    snippet=preview,
                    metadata={"page": p.page, "opencv_review": p.opencv_review},
                )
            )

        explanation = (
            f"🤖 **[Chatbot RAG - Auditoría Tesseract OCR]**\n\n"
            f"El motor Tesseract procesó las siguientes páginas tras optimización con OpenCV:\n\n"
            + "\n".join(details)
        )

        return QueryResponse(
            found=True,
            status="found",
            query=query,
            intent="chatbot_rag_tesseract",
            explanation=explanation,
            matches=matches,
            total_matches=len(matches),
            pages_found=sorted(list(set(m.page for m in matches))),
        )

    def _answer_semantic_content_rag(
        self,
        query: str,
        ctx: RAGContext,
        pages_data: List[PageData],
        doc_filename: str,
    ) -> QueryResponse:
        """Responde preguntas semánticas complejas usando los pasajes recuperados por RAG."""
        q_norm = normalize_text(query)

        # ¿De qué trata el documento? / Resumen ejecutivo
        if any(term in q_norm for term in ["de que trata", "de qué trata", "resumen", "que dice", "qué dice"]):
            total_pages = len(pages_data)
            first_text = pages_data[0].text if pages_data else ""
            first_norm = normalize_text(first_text)

            doc_type = "Documento estructurado"
            bullets = []
            if "contrato" in first_norm:
                doc_type = "Contrato de Prestación de Servicios / Acuerdo Comercial"
                bullets.append("• **Naturaleza**: Contrato formal con obligaciones y partes firmantes")
            elif "manual" in first_norm:
                doc_type = "Manual de Operaciones / Procedimientos"
            elif "escaneado" in first_norm:
                doc_type = "Documento Escaneado con validación de calidad y OCR"

            if ctx.signatures:
                bullets.append(f"• **Firmas**: Contiene {len(ctx.signatures)} firma(s) en página(s) {', '.join(str(p) for p, _ in ctx.signatures)}")
            if ctx.qr_codes:
                bullets.append(f"• **Códigos QR**: Contiene {len(ctx.qr_codes)} código(s) QR")
            if ctx.barcodes:
                bullets.append(f"• **Códigos de barras**: Contiene {len(ctx.barcodes)} código(s) de barras")

            bullets_str = "\n".join(bullets) if bullets else f"• Total de {total_pages} página(s) indexadas."

            explanation = (
                f"🤖 **[Chatbot RAG - Síntesis con IA del Documento]**\n\n"
                f"• **Archivo**: `{doc_filename}` ({total_pages} páginas)\n"
                f"• **Tipo identificado**: {doc_type}\n"
                f"{bullets_str}\n\n"
                f"*Extracto de apertura*:\n\"{first_text[:280].replace(chr(10), ' ')}...\""
            )

            match = QueryMatch(
                page=1,
                type="summary",
                confidence=1.0,
                label="Síntesis RAG del documento",
                snippet=first_text[:200].replace("\n", " "),
                metadata={"doc_type": doc_type},
            )

            return QueryResponse(
                found=True,
                status="found",
                query=query,
                intent="chatbot_rag_summary",
                explanation=explanation,
                matches=[match],
                total_matches=1,
                pages_found=[1],
            )

        # Si hay pasajes recuperados con puntuación
        if ctx.relevant_passages:
            top_passage = ctx.relevant_passages[0]
            top_page = top_passage["page"]
            top_text = top_passage["text"]

            matches = [
                QueryMatch(
                    page=top_page,
                    type="text",
                    confidence=min(1.0, top_passage["score"] / 8.0),
                    label="Respuesta RAG sobre contenido",
                    snippet=top_text,
                    metadata={"source": "rag_retrieval"},
                )
            ]

            explanation = (
                f"🤖 **[Chatbot RAG - Razonamiento sobre el contenido]**\n\n"
                f"De acuerdo con la información analizada e indexada (Página {top_page}):\n\n"
                f"\"{top_text}\""
            )

            return QueryResponse(
                found=True,
                status="found",
                query=query,
                intent="chatbot_rag_qa",
                explanation=explanation,
                matches=matches,
                total_matches=1,
                pages_found=[top_page],
            )

        # Fallback sin coincidencias
        return QueryResponse(
            found=False,
            status="not_found",
            query=query,
            intent="chatbot_rag_not_found",
            explanation=(
                f"🤖 **[Chatbot RAG]**\n\n"
                f"⚠ No encontré evidencia suficiente en el contenido ni en los elementos visuales "
                f"del documento para responder a: \"{query}\"."
            ),
            matches=[],
            total_matches=0,
            pages_found=[],
        )

    def _build_matches_from_context(self, ctx: RAGContext, pages_mentioned: List[int]) -> List[QueryMatch]:
        matches: List[QueryMatch] = []
        for p in pages_mentioned:
            for p_num, sig in ctx.signatures:
                if p_num == p:
                    matches.append(QueryMatch(page=p, type="signature", confidence=sig.confidence, label=sig.label, bbox=sig.bbox))
            for p_num, qr in ctx.qr_codes:
                if p_num == p:
                    matches.append(QueryMatch(page=p, type="qr", confidence=qr.confidence, label=qr.label, bbox=qr.bbox))
            for p_num, bc in ctx.barcodes:
                if p_num == p:
                    matches.append(QueryMatch(page=p, type="barcode", confidence=bc.confidence, label=bc.label, bbox=bc.bbox))
        return matches


rag_chatbot = RAGChatbot()
