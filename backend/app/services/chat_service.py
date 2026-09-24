import re
from typing import List, Optional
from backend.app.models.schemas import PageData, QueryMatch, QueryResponse
from backend.app.services.search_engine import normalize_text, search_engine


class ChatService:
    """
    Servicio 'Chat' para preguntas directas y no tan complejas:
    - Búsqueda textual directa (palabras o frases exactas/parciales)
    - Conteo de ocurrencias de palabras en páginas ("¿Cuántas páginas contienen la palabra X?")
    - Búsqueda de identificadores específicos (NIT, Cédula, ID numérico)
    - Resumen básico de una página específica ("¿Qué contiene la página X?")
    - Búsquedas léxicas rápidas sin sobrecarga de IA generativa
    """

    def process_chat(
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
                intent="chat_empty",
                explanation="Por favor ingrese un término de búsqueda o pregunta directa.",
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        q_lower = raw_query.lower()
        q_norm = normalize_text(q_lower)

        # 1. Resumen básico de una página: "¿Qué contiene la página 15?" o "página 1"
        page_summary_match = re.search(r"(?:que|qué)\s+contiene\s+(?:la\s+)?p[aá]gina\s+(\d+)", q_norm)
        if not page_summary_match and re.match(r"^p[aá]gina\s+(\d+)$", q_norm):
            page_summary_match = re.search(r"p[aá]gina\s+(\d+)", q_norm)

        if page_summary_match:
            target_page_num = int(page_summary_match.group(1))
            return self._handle_page_summary(target_page_num, pages_data, raw_query)

        # 2. Conteo de páginas con una palabra: "¿Cuántas páginas contienen la palabra X?"
        count_match = re.search(
            r"cu[aá]ntas\s+p[aá]ginas\s+contienen\s+(?:la\s+palabra\s+)?['\"]?([^'\"?]+)['\"]?",
            q_norm,
        )
        if count_match:
            term = count_match.group(1).strip()
            return self._handle_count_query(term, pages_data, raw_query)

        # 3. Pregunta directa de existencia de texto: "¿En qué página aparece la palabra X?", "¿Existe la palabra X?"
        text_explicit_match = re.search(
            r"(?:existe|aparece|menciona|en\s+qu[eé]\s+p[aá]gina[s]?\s+aparece|en\s+qu[eé]\s+p[aá]gina[s]?\s+se\s+menciona)?\s*(?:la\s+palabra|el\s+texto|la\s+frase)\s+['\"]?([^'\"?]+)['\"]?",
            q_norm,
        )
        if text_explicit_match and text_explicit_match.group(1):
            term = text_explicit_match.group(1).strip()
            return self._handle_text_query(term, pages_data, raw_query)

        # 4. Búsqueda de identificador o número específico (NIT, Cédula, ID)
        id_match = re.search(
            r"(?:n[uú]mero\s+de\s+identificaci[oó]n|c[eé]dula|nit|id|n[uú]mero)\s+([a-zA-Z0-9\-\.]+)",
            q_norm,
        )
        if id_match:
            term = id_match.group(1).strip()
            return self._handle_text_query(term, pages_data, raw_query, is_identifier=True)

        # 5. Detección y consulta sobre firmas en Chat
        is_signature_query = (
            any(w in q_norm for w in [
                "firma", "firmas", "firmando", "firmante", "firmantes", "firmado", "firmada",
                "firmados", "firmadas", "rúbrica", "rubrica", "signatura", "signaturas"
            ])
            or any(p in q_norm for p in [
                "tiene firmas", "tiene firma", "hay firmas", "hay firma", "esta firmado",
                "está firmado", "fue firmado", "no reconoce las firmas", "reconoce las firmas"
            ])
        )
        if is_signature_query:
            return self._handle_signatures_query(pages_data, raw_query)

        # 6. Detección de códigos QR en Chat
        if "qr" in q_norm or "código qr" in q_norm or "codigo qr" in q_norm:
            return self._handle_qr_query(pages_data, raw_query)

        # 7. Detección de códigos de barras en Chat
        if any(w in q_norm for w in ["código de barras", "codigo de barras", "barcode", "código de barra", "codigo de barra"]):
            return self._handle_barcode_query(pages_data, raw_query)

        # 8. Búsqueda directa por término general (ej: "factura", "Bogotá", "contrato")
        return self._handle_direct_search(raw_query, pages_data)

    def _handle_page_summary(
        self, target_page: int, pages_data: List[PageData], raw_query: str
    ) -> QueryResponse:
        matching_page = next((p for p in pages_data if p.page == target_page), None)
        if not matching_page:
            return QueryResponse(
                found=False,
                status="not_found",
                query=raw_query,
                intent="chat_page_summary",
                explanation=f"⚠ La página {target_page} no existe en este documento (total: {len(pages_data)} páginas).",
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        elements_summary = []
        if matching_page.has_text_layer or matching_page.ocr_applied:
            words_count = len(matching_page.text.split())
            method = "Tesseract OCR" if matching_page.ocr_applied else "Texto digital nativo"
            elements_summary.append(f"Texto ({words_count} palabras vía {method})")

        if matching_page.qr_codes:
            elements_summary.append(f"{len(matching_page.qr_codes)} código(s) QR")
        if matching_page.barcodes:
            elements_summary.append(f"{len(matching_page.barcodes)} código(s) de barras")
        if matching_page.signatures:
            elements_summary.append(f"{len(matching_page.signatures)} firma(s)")
        if matching_page.stamps:
            elements_summary.append(f"{len(matching_page.stamps)} sello(s)")
        if matching_page.tables:
            elements_summary.append(f"{len(matching_page.tables)} tabla(s)")

        summary_str = " • " + "\n • ".join(elements_summary) if elements_summary else "Página sin elementos detectados."
        text_preview = matching_page.text[:220].replace("\n", " ") + "..." if len(matching_page.text) > 220 else matching_page.text

        explanation = (
            f"✓ [Chat - Resumen Directo] Página {target_page}:\n\n"
            f"{summary_str}\n\n"
            f"Extracto de texto inicial:\n\"{text_preview}\""
        )

        match = QueryMatch(
            page=target_page,
            type="summary",
            confidence=1.0,
            label=f"Resumen de Página {target_page}",
            snippet=text_preview,
            metadata={"elements": elements_summary},
        )

        return QueryResponse(
            found=True,
            status="found",
            query=raw_query,
            intent="chat_page_summary",
            explanation=explanation,
            matches=[match],
            total_matches=1,
            pages_found=[target_page],
        )

    def _handle_count_query(
        self, term: str, pages_data: List[PageData], raw_query: str
    ) -> QueryResponse:
        text_matches = search_engine.search_text_in_pages(pages_data, term)
        pages_set = sorted(list(set(m.page for m in text_matches)))
        count = len(pages_set)

        if count > 0:
            pages_list_str = ", ".join(f"Página {p}" for p in pages_set)
            explanation = f"✓ [Chat] La palabra \"{term}\" aparece en {count} página(s):\n{pages_list_str}."
            return QueryResponse(
                found=True,
                status="found",
                query=raw_query,
                intent="chat_count",
                explanation=explanation,
                matches=text_matches,
                total_matches=len(text_matches),
                pages_found=pages_set,
            )
        else:
            return QueryResponse(
                found=False,
                status="not_found",
                query=raw_query,
                intent="chat_count",
                explanation=f"⚠ [Chat] La palabra \"{term}\" no aparece en ninguna página del documento.",
                matches=[],
                total_matches=0,
                pages_found=[],
            )

    def _handle_text_query(
        self,
        term: str,
        pages_data: List[PageData],
        raw_query: str,
        is_identifier: bool = False,
    ) -> QueryResponse:
        text_matches = search_engine.search_text_in_pages(pages_data, term, exact_match=is_identifier)
        pages_set = sorted(list(set(m.page for m in text_matches)))

        if not text_matches:
            return QueryResponse(
                found=False,
                status="not_found",
                query=raw_query,
                intent="chat_text_search",
                explanation=f"⚠ [Chat] No encontré \"{term}\" en el texto del documento.",
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        if len(pages_set) == 1:
            explanation = f"✓ Sí, encontré \"{term}\".\n\nPágina:\n{pages_set[0]}"
        else:
            pages_list = "\n".join(f"• Página {p}" for p in pages_set)
            explanation = f"✓ Sí, encontré \"{term}\" en el documento.\n\nEncontrado en:\n{pages_list}"

        return QueryResponse(
            found=True,
            status="found",
            query=raw_query,
            intent="chat_text_search",
            explanation=explanation,
            matches=text_matches,
            total_matches=len(text_matches),
            pages_found=pages_set,
        )

    def _handle_direct_search(self, raw_query: str, pages_data: List[PageData]) -> QueryResponse:
        term = raw_query.strip()
        text_matches = search_engine.search_text_in_pages(pages_data, term)

        if not text_matches:
            return QueryResponse(
                found=False,
                status="not_found",
                query=raw_query,
                intent="chat_direct_search",
                explanation=f"⚠ [Chat] No encontré coincidencias para \"{term}\" en el texto del documento.",
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        pages_set = sorted(list(set(m.page for m in text_matches)))
        if len(pages_set) == 1:
            explanation = f"✓ [Chat] Coincidencia encontrada para \"{term}\":\n\nPágina:\n{pages_set[0]}"
        else:
            pages_list = "\n".join(f"• Página {p}" for p in pages_set)
            explanation = f"✓ [Chat] Coincidencias encontradas para \"{term}\":\n\n{pages_list}"

        return QueryResponse(
            found=True,
            status="found",
            query=raw_query,
            intent="chat_direct_search",
            explanation=explanation,
            matches=text_matches,
            total_matches=len(text_matches),
            pages_found=pages_set,
        )

    def _handle_signatures_query(
        self, pages_data: List[PageData], raw_query: str
    ) -> QueryResponse:
        matches: List[QueryMatch] = []
        for p in pages_data:
            for sig in p.signatures:
                matches.append(
                    QueryMatch(
                        page=p.page,
                        type="signature",
                        confidence=sig.confidence,
                        label=sig.label,
                        snippet=f"Firma detectada en la página {p.page} ({sig.metadata.get('kind', 'manuscrita')})",
                        bbox=sig.bbox,
                        metadata=sig.metadata,
                    )
                )

        if not matches:
            return QueryResponse(
                found=False,
                status="not_found",
                query=raw_query,
                intent="chat_signatures",
                explanation="⚠ [Chat] No se encontraron firmas en el documento.",
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        pages_set = sorted(list(set(m.page for m in matches)))
        if len(pages_set) == 1:
            explanation = f"✓ [Chat] Sí, encontré una firma en el documento.\n\nPágina:\n{pages_set[0]}"
        else:
            bullets = "\n".join(f"• Página {p}" for p in pages_set)
            explanation = f"✓ [Chat] Sí, encontré {len(matches)} firma(s) en el documento.\n\nEncontrado en:\n{bullets}"

        return QueryResponse(
            found=True,
            status="found",
            query=raw_query,
            intent="chat_signatures",
            explanation=explanation,
            matches=matches,
            total_matches=len(matches),
            pages_found=pages_set,
        )

    def _handle_qr_query(self, pages_data: List[PageData], raw_query: str) -> QueryResponse:
        matches: List[QueryMatch] = []
        for p in pages_data:
            for qr in p.qr_codes:
                decoded = qr.metadata.get("decoded_text")
                matches.append(
                    QueryMatch(
                        page=p.page,
                        type="qr",
                        confidence=qr.confidence,
                        label=qr.label,
                        snippet=f"Contenido QR: {decoded}" if decoded else "Código QR detectado",
                        bbox=qr.bbox,
                        metadata=qr.metadata,
                    )
                )

        if not matches:
            return QueryResponse(
                found=False,
                status="not_found",
                query=raw_query,
                intent="chat_qr",
                explanation="⚠ [Chat] No se encontraron códigos QR en el documento.",
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        pages_set = sorted(list(set(m.page for m in matches)))
        first_match = matches[0]
        decoded = first_match.metadata.get("decoded_text") if first_match.metadata else None
        explanation = (
            f"✓ [Chat] Código QR encontrado en la Página {first_match.page}.\n"
            f"Contenido: {decoded or 'Estructura detectada'}"
        )

        return QueryResponse(
            found=True,
            status="found",
            query=raw_query,
            intent="chat_qr",
            explanation=explanation,
            matches=matches,
            total_matches=len(matches),
            pages_found=pages_set,
        )

    def _handle_barcode_query(self, pages_data: List[PageData], raw_query: str) -> QueryResponse:
        matches: List[QueryMatch] = []
        for p in pages_data:
            for bc in p.barcodes:
                decoded = bc.metadata.get("decoded_text")
                matches.append(
                    QueryMatch(
                        page=p.page,
                        type="barcode",
                        confidence=bc.confidence,
                        label=bc.label,
                        snippet=f"Formato: {bc.metadata.get('format', '1D')}, Contenido: {decoded}",
                        bbox=bc.bbox,
                        metadata=bc.metadata,
                    )
                )

        if not matches:
            return QueryResponse(
                found=False,
                status="not_found",
                query=raw_query,
                intent="chat_barcode",
                explanation="⚠ [Chat] No se encontraron códigos de barras en el documento.",
                matches=[],
                total_matches=0,
                pages_found=[],
            )

        pages_set = sorted(list(set(m.page for m in matches)))
        first_match = matches[0]
        decoded = first_match.metadata.get("decoded_text") if first_match.metadata else "No decodificado"
        explanation = (
            f"✓ [Chat] Código de barras encontrado en la Página {first_match.page}.\n"
            f"Contenido: {decoded}"
        )

        return QueryResponse(
            found=True,
            status="found",
            query=raw_query,
            intent="chat_barcode",
            explanation=explanation,
            matches=matches,
            total_matches=len(matches),
            pages_found=pages_set,
        )


chat_service = ChatService()
