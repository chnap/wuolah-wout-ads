from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import fitz

# Strong page-level markers. Ordinary mentions of Wuolah are deliberately not enough.
PROMO_PATTERNS = (
    re.compile(r"elimina\s+la\s+publicidad", re.I),
    re.compile(r"descarga\s+sin\s+publicidad", re.I),
    re.compile(r"quitar\s+la\s+publicidad\s+de\s+wuolah", re.I),
    re.compile(r"anuncios?\s+(?:de|en)\s+wuolah", re.I),
    re.compile(r"publicidad\s+(?:de|en)\s+wuolah", re.I),
)

@dataclass
class CleanResult:
    source: str
    output: str
    pages: int
    removed_pages: list[int]
    status: str = "cleaned"
    error: str | None = None


def is_promotional_page(page: fitz.Page) -> bool:
    """Detect a dedicated Wuolah promo page using text only; never OCR or an LLM."""
    text = " ".join(page.get_text("text").split())
    if not text:
        return False
    matches = sum(bool(pattern.search(text)) for pattern in PROMO_PATTERNS)
    # Require the platform name alongside promo language: course material can
    # legitimately discuss advertising or downloading without being an ad page.
    has_brand = bool(re.search(r"\bwuolah\b", text, re.I))
    return matches >= 1 and has_brand and len(text) < 1800


def clean_pdf(source: Path, output: Path, *, force: bool = False) -> CleanResult:
    source = source.resolve()
    output = output.resolve()
    if source == output:
        raise ValueError("El archivo de salida no puede sobrescribir el original.")
    if output.exists() and not force:
        return CleanResult(str(source), str(output), 0, [], "skipped", "la salida ya existe")
    output.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(source) as doc:
        original_count = doc.page_count
        removed = [i for i, page in enumerate(doc) if is_promotional_page(page)]
        if removed:
            for i in reversed(removed):
                doc.delete_page(i)
            if doc.page_count == 0:
                return CleanResult(str(source), str(output), original_count, [i + 1 for i in removed], "skipped", "el documento solo contiene páginas promocionales")
        doc.save(output, garbage=3, deflate=True)
        return CleanResult(str(source), str(output), original_count, [i + 1 for i in removed])
