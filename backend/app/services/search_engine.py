import re
import unicodedata
from typing import Any, Dict, List, Optional
from backend.app.models.schemas import BoundingBox, QueryMatch


def normalize_text(text: str, remove_accents: bool = True) -> str:
    """Normalizes text for robust searching (lowercasing, accent removal)."""
    text = text.lower()
    if remove_accents:
        # Decompose unicode accents (e.g., 'á' -> 'a' + combining acute)
        nfkd = unicodedata.normalize("NFKD", text)
        text = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return text


def extract_context_snippet(full_text: str, match_start: int, match_end: int, context_chars: int = 45) -> str:
    """Extracts a neat snippet surrounding the match with word boundaries and ellipsis."""
    start = max(0, match_start - context_chars)
    end = min(len(full_text), match_end + context_chars)

    # Adjust to nearest space if possible
    if start > 0:
        prev_space = full_text.rfind(" ", 0, start)
        if prev_space != -1 and (start - prev_space) < 15:
            start = prev_space + 1

    if end < len(full_text):
        next_space = full_text.find(" ", end)
        if next_space != -1 and (next_space - end) < 15:
            end = next_space

    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(full_text) else ""

    snippet = full_text[start:end].replace("\n", " ").strip()
    return f"{prefix}{snippet}{suffix}"


class SearchEngine:
    def __init__(self):
        pass

    def search_text_in_pages(
        self,
        pages_data: List[Any],
        query: str,
        exact_match: bool = False,
        case_sensitive: bool = False,
    ) -> List[QueryMatch]:
        """
        Searches text across pages with accent insensitivity, partial matching, and snippet extraction.
        """
        results: List[QueryMatch] = []
        raw_query = query.strip()
        if not raw_query:
            return results

        # Normalize query
        norm_query = raw_query if case_sensitive else raw_query.lower()
        search_query_no_accents = normalize_text(norm_query, remove_accents=True)

        for page in pages_data:
            page_text = page.text or ""
            if not page_text.strip():
                continue

            # Original and normalized text
            target_text = page_text if case_sensitive else page_text.lower()
            target_text_no_accents = normalize_text(target_text, remove_accents=True)

            # Build regex pattern
            escaped_q = re.escape(search_query_no_accents)
            if exact_match:
                pattern = rf"\b{escaped_q}\b"
            else:
                pattern = rf"{escaped_q}"

            # Search in normalized text
            for m in re.finditer(pattern, target_text_no_accents):
                start_idx, end_idx = m.span()
                matched_snippet = extract_context_snippet(page_text, start_idx, end_idx)

                # Try to locate word bounding box if words coordinate data exists
                bbox = None
                words_list = getattr(page, "objects", [])  # or words if stored
                
                results.append(
                    QueryMatch(
                        page=page.page,
                        type="text",
                        confidence=1.0 if not exact_match else 1.0,
                        label=f'Texto: "{raw_query}"',
                        snippet=matched_snippet,
                        bbox=bbox,
                        metadata={
                            "match_position": [start_idx, end_idx],
                            "has_text_layer": page.has_text_layer,
                            "ocr_applied": page.ocr_applied,
                        },
                    )
                )

        return results


search_engine = SearchEngine()
