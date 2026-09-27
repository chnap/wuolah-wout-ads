from __future__ import annotations

import base64
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import pymupdf


# A dedicated promo page needs both the platform name and promotional wording.
# Mentions of ads in study notes are not enough to remove a whole page.
PROMO_PATTERNS = (
    re.compile(r"elimina\s+la\s+publicidad", re.I),
    re.compile(r"descarga\s+sin\s+publicidad", re.I),
    re.compile(r"quitar\s+la\s+publicidad\s+de\s+wuolah", re.I),
    re.compile(r"anuncios?\s+(?:de|en)\s+wuolah", re.I),
    re.compile(r"publicidad\s+(?:de|en)\s+wuolah", re.I),
    re.compile(r"(?:hazte|pásate\s+a|consigue)\s+(?:wuolah\s+)?(?:plus|premium)", re.I),
)

TRACK_HOST = "track.wlh.es"
AD_DESTINATION_MARKERS = (
    "doubleclick.net",
    "adclick.",
    "googleadservices.com",
)


@dataclass
class CleanResult:
    source: str
    output: str
    pages: int
    removed_pages: list[int]
    removed_regions: list[dict[str, str | int]] = field(default_factory=list)
    status: str = "cleaned"
    error: str | None = None


def _page_promo_text(text: str) -> bool:
    text = " ".join(text.split())
    return (
        bool(text)
        and len(text) < 1800
        and bool(re.search(r"\bwuolah\b", text, re.I))
        and any(pattern.search(text) for pattern in PROMO_PATTERNS)
    )


def _is_wuolah_document(doc: pymupdf.Document, promo_pages: list[int], source: Path) -> bool:
    """Require a positive Wuolah signal before changing a PDF."""
    if source.name.casefold().startswith("wuolah-") or promo_pages:
        return True
    metadata = doc.metadata or {}
    if any("wuolah" in str(value).casefold() for value in metadata.values() if value):
        return True
    for page in doc:
        for link in page.get_links():
            host = (urlparse(link.get("uri", "")).hostname or "").casefold()
            if host == TRACK_HOST or host == "wuolah.com" or host.endswith(".wuolah.com"):
                return True
    return False


def _tracked_ad_destination(uri: str) -> bool:
    """Recognize Wuolah's base64-wrapped outbound ad-click links."""
    parsed = urlparse(uri)
    if parsed.hostname != TRACK_HOST:
        return False
    token = parsed.path.strip("/").split("/", 1)[0]
    if not token or token == "v2":
        return False
    try:
        padded = token + "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8", "ignore").lower()
    except (ValueError, base64.binascii.Error):
        return False
    return any(marker in decoded for marker in AD_DESTINATION_MARKERS)


def _rect_area(rect: pymupdf.Rect) -> float:
    return max(0.0, rect.width) * max(0.0, rect.height)


def _ad_link_rects(page: pymupdf.Page) -> list[pymupdf.Rect]:
    area = page.rect.width * page.rect.height
    found = []
    for link in page.get_links():
        uri = link.get("uri", "")
        rect = pymupdf.Rect(link.get("from", (0, 0, 0, 0))) & page.rect
        # Large click targets may enclose a whole scan. Preserve those pages;
        # the source PDF frequently links its original scanned test pages.
        ratio = _rect_area(rect) / area if area else 0
        if _tracked_ad_destination(uri) and 0.004 <= ratio < 0.80:
            found.append(rect)
    return found


def _margin_ad_pair(page: pymupdf.Page) -> list[pymupdf.Rect]:
    """Find Wuolah's distinctive top-banner + full-height side-banner layout."""
    width, height = page.rect.width, page.rect.height
    images = [pymupdf.Rect(info["bbox"]) & page.rect for info in page.get_image_info()]
    top_banners = [
        rect for rect in images
        if rect.x0 <= width * 0.025
        and rect.y0 <= height * 0.025
        and rect.width >= width * 0.84
        and height * 0.055 <= rect.height <= height * 0.19
    ]
    side_banners = [
        rect for rect in images
        if rect.x0 <= width * 0.025
        and width * 0.07 <= rect.width <= width * 0.19
        and rect.height >= height * 0.70
        and rect.y1 >= height * 0.94
    ]
    for top in top_banners:
        for side in side_banners:
            if abs(side.y0 - top.y1) <= height * 0.025:
                return [top, side]
    return []


def _unique_rects(rects: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    out: list[pymupdf.Rect] = []
    for rect in rects:
        rect = pymupdf.Rect(rect)
        if rect.is_empty or rect.is_infinite:
            continue
        if any(rect == old or old.contains(rect) for old in out):
            continue
        out = [old for old in out if not rect.contains(old)]
        out.append(rect)
    return out


def _clean_page_ads(page: pymupdf.Page, page_number: int) -> list[dict[str, str | int]]:
    rects = _ad_link_rects(page) + _margin_ad_pair(page)
    rects = _unique_rects(rects)
    if not rects:
        # Remove Wuolah's tracking hotspots, including tiny invisible pixels,
        # while leaving normal outbound links (e.g. the source-document link).
        removed_tracking = []
        for link in page.get_links():
            if urlparse(link.get("uri", "")).hostname == TRACK_HOST:
                page.delete_link(link)
                removed_tracking.append({"page": page_number, "kind": "tracking_link"})
        return removed_tracking

    regions: list[dict[str, str | int]] = []
    for rect in rects:
        page.add_redact_annot(rect, fill=(1, 1, 1), cross_out=False)
        regions.append({"page": page_number, "kind": "advertisement"})

    # Keep background/image objects and nearby diagrams intact. The white
    # redaction fill visually clears only each detected ad rectangle; text
    # inside it and overlapping links are physically removed by MuPDF.
    page.apply_redactions(images=0, graphics=0, text=0)
    for link in page.get_links():
        if urlparse(link.get("uri", "")).hostname == TRACK_HOST:
            page.delete_link(link)
    return regions


def clean_pdf(source: Path, output: Path | None = None, *, force: bool = False) -> CleanResult:
    source = source.resolve()
    output = (output or source).resolve()
    in_place = source == output
    if output.exists() and not in_place and not force:
        return CleanResult(str(source), str(output), 0, [], status="skipped", error="la salida ya existe")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output.with_name(f".{output.stem}.{uuid4().hex}.tmp{output.suffix or '.pdf'}")
    try:
        with pymupdf.open(source) as doc:
            original_count = doc.page_count
            removed = []
            promo_pages = []
            for i, page in enumerate(doc):
                text = page.get_text("text")
                if _page_promo_text(text):
                    removed.append(i)
                    promo_pages.append(i)
            if not _is_wuolah_document(doc, promo_pages, source):
                return CleanResult(
                    str(source), str(output), original_count, [],
                    status="skipped", error="no parece un PDF de Wuolah",
                )
            regions: list[dict[str, str | int]] = []
            removed_set = set(removed)
            for i, page in enumerate(doc):
                if i not in removed_set:
                    regions.extend(_clean_page_ads(page, i + 1))
            for i in reversed(removed):
                doc.delete_page(i)
            if doc.page_count == 0:
                return CleanResult(
                    str(source), str(output), original_count, [i + 1 for i in removed],
                    regions, "skipped", "el documento solo contiene páginas promocionales",
                )
            if not removed and not regions:
                return CleanResult(str(source), str(output), original_count, [], status="unchanged")
            doc.save(temp_output, garbage=3, deflate=True)
        if in_place:
            temp_output.chmod(stat.S_IMODE(source.stat().st_mode))
        temp_output.replace(output)
        return CleanResult(str(source), str(output), original_count, [i + 1 for i in removed], regions)
    finally:
        temp_output.unlink(missing_ok=True)
