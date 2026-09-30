from __future__ import annotations

import base64
import math
import re
import stat
import xml.etree.ElementTree as ET
from collections import defaultdict
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
WUOLAH_RIGHTS_FOOTER_TEXT = (
    "Reservados todos los derechos",
    "No se permite la explotación económica",
    "Queda permitida la impresión en su totalidad",
)


@dataclass(frozen=True)
class CleanOptions:
    min_link_area: float = 0.004
    max_link_area: float = 0.80
    banner_tolerance: float = 0.025
    banner_top_min_width: float = 0.84
    banner_side_min_height: float = 0.70
    image_redaction: str = "pixels"
    graphics_redaction: str = "contained"
    fill_color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    remove_wuolah_branding: bool = True
    branding_repeat_ratio: float = 0.70
    branding_footer_top: float = 0.82
    branding_max_width: float = 0.40
    branding_max_height: float = 0.08
    black_mark_repeat_ratio: float = 0.25
    black_mark_right_min: float = 0.55
    black_mark_footer_top: float = 0.82
    black_mark_min_width: float = 0.06
    black_mark_max_width: float = 0.36
    black_mark_min_height: float = 0.005
    black_mark_max_height: float = 0.08
    remove_wuolah_cover: bool = True
    wuolah_cover_max_text: int = 500
    remove_full_page_ads: bool = True
    full_page_image_coverage: float = 0.90
    full_page_ad_max_text: int = 80
    full_page_neighbor_min_text: int = 500


@dataclass
class CleanResult:
    source: str
    output: str
    pages: int
    removed_pages: list[int]
    removed_regions: list[dict[str, str | int]] = field(default_factory=list)
    status: str = "cleaned"
    error: str | None = None
    removed_branding: list[dict[str, str | int]] = field(default_factory=list)
    removed_page_reasons: list[dict[str, str | int]] = field(default_factory=list)


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
            host = urlparse(link.get("uri", "")).hostname or ""
            if _is_wuolah_host(host):
                return True
    return False


def _is_wuolah_host(host: str) -> bool:
    host = host.casefold().rstrip(".")
    return host == TRACK_HOST or host == "wuolah.com" or host.endswith(".wuolah.com")


def _repeated_footer_brand_images(
    doc: pymupdf.Document, options: CleanOptions,
) -> dict[int, list[int]]:
    """Find small, shared images repeated in the footer across most pages."""
    uses: dict[int, list[tuple[int, int, int, float, float, float, float]]] = defaultdict(list)
    for page_index, page in enumerate(doc):
        width, height = page.rect.width, page.rect.height
        if not width or not height:
            continue
        for image in page.get_image_info(xrefs=True):
            xref = image.get("xref", 0)
            iw, ih = image.get("width", 0), image.get("height", 0)
            if xref <= 0 or iw <= 2 or ih <= 2:
                continue
            rect = pymupdf.Rect(image["bbox"]) & page.rect
            uses[xref].append((
                page_index + 1, iw, ih,
                rect.x0 / width, rect.y0 / height,
                rect.x1 / width, rect.y1 / height,
            ))

    threshold = max(3, math.ceil(doc.page_count * options.branding_repeat_ratio))
    matches: dict[int, list[int]] = {}
    for xref, instances in uses.items():
        # Repeated placements on one page alone do not establish a footer mark.
        page_instances: dict[int, tuple[int, int, float, float, float, float]] = {}
        for page_no, iw, ih, x0, y0, x1, y1 in instances:
            page_instances.setdefault(page_no, (iw, ih, x0, y0, x1, y1))
        if len(page_instances) < threshold:
            continue
        rows = list(page_instances.values())
        mid = len(rows) // 2
        med_x0 = sorted(row[2] for row in rows)[mid]
        med_y0 = sorted(row[3] for row in rows)[mid]
        med_width = sorted(row[4] - row[2] for row in rows)[mid]
        med_height = sorted(row[5] - row[3] for row in rows)[mid]
        if (
            med_x0 >= 0.60
            and med_y0 >= options.branding_footer_top
            and med_width <= options.branding_max_width
            and med_height <= options.branding_max_height
        ):
            matches[xref] = sorted(page_instances)
    return matches


def _repeated_watermark_images(
    doc: pymupdf.Document, options: CleanOptions,
) -> dict[int, list[int]]:
    """Find a shared compact image stamp repeatedly placed at one page position."""
    placements: dict[int, dict[int, pymupdf.Rect]] = defaultdict(dict)
    for page_index, page in enumerate(doc):
        if not page.rect.width or not page.rect.height:
            continue
        for image in page.get_image_info(xrefs=True):
            xref = image.get("xref", 0)
            if xref <= 0 or image.get("width", 0) <= 2 or image.get("height", 0) <= 2:
                continue
            # Transparent image overlays are the common representation for a
            # reusable watermark. Opaque repeated study images are preserved.
            if not image.get("has-mask", False):
                continue
            rect = pymupdf.Rect(image["bbox"]) & page.rect
            area_ratio = _rect_area(rect) / (page.rect.width * page.rect.height)
            if 0 < area_ratio <= 0.12:
                placements[xref].setdefault(page_index, rect)
    threshold = max(2, math.ceil(doc.page_count * options.branding_repeat_ratio))
    matches: dict[int, list[int]] = {}
    for xref, by_page in placements.items():
        if len(by_page) < threshold:
            continue
        normalized = []
        for page_index, rect in by_page.items():
            page = doc.load_page(page_index)
            normalized.append((rect.x0 / page.rect.width, rect.y0 / page.rect.height,
                               rect.x1 / page.rect.width, rect.y1 / page.rect.height))
        reference = normalized[0]
        if all(max(abs(a - b) for a, b in zip(reference, coords)) <= 0.02 for coords in normalized[1:]):
            matches[xref] = sorted(index + 1 for index in by_page)
    return matches


def _black_footer_candidates(page: pymupdf.Page, options: CleanOptions) -> list[pymupdf.Rect]:
    """Find compact, solid black rectangles in the lower-right footer area.

    A low-resolution grayscale render catches rectangles embedded in scans as
    well as vector shapes. Candidates are only removed when repeated across
    pages at nearly the same normalized position.
    """
    pix = page.get_pixmap(matrix=pymupdf.Matrix(0.5, 0.5), colorspace=pymupdf.csGRAY, alpha=False)
    width, height = pix.width, pix.height
    if not width or not height:
        return []
    samples = memoryview(pix.samples)
    x_start = max(0, int(width * options.black_mark_right_min))
    y_start = max(0, int(height * options.black_mark_footer_top))
    row_runs: list[tuple[int, int, int]] = []
    components: list[dict[str, int]] = []
    # Merge dark horizontal runs across adjacent rows into connected blocks.
    for y in range(y_start, height):
        row = y * width
        x = x_start
        runs = []
        while x < width:
            if samples[row + x] >= 28:
                x += 1
                continue
            start = x
            while x < width and samples[row + x] < 28:
                x += 1
            if x - start >= max(3, int(width * options.black_mark_min_width * 0.8)):
                runs.append((start, x))
        next_active = []
        for start, end in runs:
            match = next((c for c in components if c["y1"] == y - 1 and start <= c["x1"] + 1 and end >= c["x0"] - 1), None)
            if match is None:
                components.append({"x0": start, "x1": end, "y0": y, "y1": y, "pixels": end - start})
            else:
                match["x0"] = min(match["x0"], start)
                match["x1"] = max(match["x1"], end)
                match["y1"] = y
                match["pixels"] += end - start
                next_active.append(match)
        # Components are kept in this list for final filtering; gaps break continuity.
        row_runs = [(start, end, y) for start, end in runs]
    del row_runs

    rects = []
    for comp in components:
        rw, rh = comp["x1"] - comp["x0"], comp["y1"] - comp["y0"] + 1
        nw, nh = rw / width, rh / height
        occupancy = comp["pixels"] / (rw * rh) if rw and rh else 0
        if (options.black_mark_min_width <= nw <= options.black_mark_max_width
                and options.black_mark_min_height <= nh <= options.black_mark_max_height
                and occupancy >= 0.88):
            sx, sy = page.rect.width / width, page.rect.height / height
            rects.append(pymupdf.Rect(comp["x0"] * sx, comp["y0"] * sy,
                                      comp["x1"] * sx, (comp["y1"] + 1) * sy))
    return rects


def _repeated_black_footer_marks(
    doc: pymupdf.Document, options: CleanOptions, excluded_pages: set[int],
) -> dict[int, list[pymupdf.Rect]]:
    occurrences: list[tuple[int, pymupdf.Rect, tuple[float, float, float, float]]] = []
    for index, page in enumerate(doc):
        if index in excluded_pages:
            continue
        for rect in _black_footer_candidates(page, options):
            norm = (rect.x0 / page.rect.width, rect.y0 / page.rect.height,
                    rect.x1 / page.rect.width, rect.y1 / page.rect.height)
            occurrences.append((index, rect, norm))
    # Cluster rectangles by normalized geometry; one hit on a single page is
    # deliberately insufficient to erase potentially legitimate study content.
    clusters: list[list[tuple[int, pymupdf.Rect, tuple[float, float, float, float]]]] = []
    for item in occurrences:
        cluster = next((group for group in clusters if
            max(abs(a - b) for a, b in zip(item[2], group[0][2])) <= 0.015), None)
        if cluster is None:
            clusters.append([item])
        else:
            cluster.append(item)
    threshold = max(2, math.ceil(doc.page_count * options.black_mark_repeat_ratio))
    found: dict[int, list[pymupdf.Rect]] = defaultdict(list)
    for cluster in clusters:
        by_page: dict[int, pymupdf.Rect] = {}
        for index, rect, _ in cluster:
            by_page.setdefault(index, rect)
        if len(by_page) >= threshold:
            for index, rect in by_page.items():
                found[index].append(rect)
    return found


def _largest_image_page_coverage(page: pymupdf.Page) -> float:
    page_area = page.rect.width * page.rect.height
    if not page_area:
        return 0.0
    return max(
        (
            _rect_area(pymupdf.Rect(info["bbox"]) & page.rect) / page_area
            for info in page.get_image_info()
        ),
        default=0.0,
    )


def _full_page_insert_pages(
    doc: pymupdf.Document, page_texts: list[str], options: CleanOptions,
) -> tuple[set[int], list[dict[str, str | int]]]:
    """Find a Wuolah front cover and sparse full-page ad inserts between notes."""
    removed: set[int] = set()
    reasons: list[dict[str, str | int]] = []
    if options.remove_wuolah_cover and doc.page_count:
        first = doc.load_page(0)
        if (
            _largest_image_page_coverage(first) >= options.full_page_image_coverage
            and len(page_texts[0].strip()) <= options.wuolah_cover_max_text
        ):
            removed.add(0)
            reasons.append({"page": 1, "kind": "wuolah_cover"})

    if options.remove_full_page_ads and doc.page_count >= 3:
        for index in range(1, doc.page_count - 1):
            if index in removed or len(page_texts[index].strip()) > options.full_page_ad_max_text:
                continue
            if _largest_image_page_coverage(doc.load_page(index)) < options.full_page_image_coverage:
                continue
            before = len(page_texts[index - 1].strip())
            after = len(page_texts[index + 1].strip())
            if before >= options.full_page_neighbor_min_text and after >= options.full_page_neighbor_min_text:
                removed.add(index)
                reasons.append({"page": index + 1, "kind": "full_page_advertisement"})
    return removed, reasons


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


def _ad_link_rects(page: pymupdf.Page, options: CleanOptions) -> list[pymupdf.Rect]:
    area = page.rect.width * page.rect.height
    found = []
    for link in page.get_links():
        uri = link.get("uri", "")
        rect = pymupdf.Rect(link.get("from", (0, 0, 0, 0))) & page.rect
        # Large click targets may enclose a whole scan. Preserve those pages;
        # the source PDF frequently links its original scanned test pages.
        ratio = _rect_area(rect) / area if area else 0
        if _tracked_ad_destination(uri) and options.min_link_area <= ratio < options.max_link_area:
            found.append(rect)
    return found


def _margin_ad_pair(page: pymupdf.Page, options: CleanOptions) -> list[pymupdf.Rect]:
    """Find Wuolah's distinctive top-banner + full-height side-banner layout."""
    width, height = page.rect.width, page.rect.height
    images = [pymupdf.Rect(info["bbox"]) & page.rect for info in page.get_image_info()]
    top_banners = [
        rect for rect in images
        if rect.x0 <= width * 0.025
        and rect.y0 <= height * 0.025
        and rect.width >= width * options.banner_top_min_width
        and height * 0.055 <= rect.height <= height * 0.19
    ]
    side_banners = [
        rect for rect in images
        if rect.x0 <= width * 0.025
        and width * 0.07 <= rect.width <= width * 0.19
        and rect.height >= height * options.banner_side_min_height
        and rect.y1 >= height * 0.94
    ]
    for top in top_banners:
        for side in side_banners:
            if abs(side.y0 - top.y1) <= height * options.banner_tolerance:
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


def _wuolah_brand_rects(page: pymupdf.Page) -> list[pymupdf.Rect]:
    found = []
    for term in ("wuolah", "wlh.es", *WUOLAH_RIGHTS_FOOTER_TEXT):
        found.extend(pymupdf.Rect(rect) for rect in page.search_for(term))
    return _unique_rects(found)


def _clean_page_ads(
    page: pymupdf.Page, page_number: int, options: CleanOptions,
    black_marks: list[pymupdf.Rect] | None = None,
) -> tuple[list[dict[str, str | int]], list[dict[str, str | int]]]:
    rects = _ad_link_rects(page, options) + _margin_ad_pair(page, options)
    rects = _unique_rects(rects)
    brand_rects = _wuolah_brand_rects(page) if options.remove_wuolah_branding else []
    regions: list[dict[str, str | int]] = []
    for rect in rects:
        page.add_redact_annot(rect, fill=options.fill_color, cross_out=False)
        regions.append({"page": page_number, "kind": "advertisement"})
    branding = []
    for rect in brand_rects:
        page.add_redact_annot(rect, fill=options.fill_color, cross_out=False)
        branding.append({"page": page_number, "kind": "footer_brand_text"})
    for rect in black_marks or []:
        padding = 0.6
        page.add_redact_annot(rect + (-padding, -padding, padding, padding), fill=options.fill_color, cross_out=False)
        branding.append({"page": page_number, "kind": "repeated_black_footer_mark"})

    if rects or brand_rects or black_marks:
        # Pixel mode clears the selected area without discarding nearby study
        # image content. The earlier images=0 setting left banners visible.
        image_modes = {"none": 0, "remove": 1, "pixels": 2}
        graphics_modes = {"none": 0, "covered": 1, "contained": 2}
        page.apply_redactions(
            images=image_modes[options.image_redaction],
            graphics=graphics_modes[options.graphics_redaction],
            text=0,
        )
    for link in page.get_links():
        host = urlparse(link.get("uri", "")).hostname or ""
        remove_link = (
            _is_wuolah_host(host) if options.remove_wuolah_branding else host.casefold() == TRACK_HOST
        )
        if remove_link:
            page.delete_link(link)
            branding.append({
                "page": page_number,
                "kind": "wuolah_link" if options.remove_wuolah_branding else "tracking_link",
            })
    return regions, branding


def _remove_wuolah_metadata(doc: pymupdf.Document) -> list[dict[str, str | int]]:
    removed = []
    metadata = doc.metadata or {}
    fields = [key for key, value in metadata.items() if value and "wuolah" in str(value).casefold()]
    if fields:
        sanitized = dict(metadata)
        for key in fields:
            sanitized[key] = ""
        doc.set_metadata(sanitized)
        removed.extend({"kind": "metadata", "field": key} for key in fields)

    xmp = doc.get_xml_metadata()
    if xmp and "wuolah" in xmp.casefold():
        root = ET.fromstring(xmp)
        count = 0
        for element in root.iter():
            if element.text and "wuolah" in element.text.casefold():
                element.text = ""
                count += 1
            if element.tail and "wuolah" in element.tail.casefold():
                element.tail = ""
                count += 1
            for key, value in list(element.attrib.items()):
                if "wuolah" in value.casefold():
                    del element.attrib[key]
                    count += 1
        doc.set_xml_metadata(ET.tostring(root, encoding="unicode"))
        if count:
            removed.append({"kind": "xmp_metadata", "fields": count})
    return removed


def clean_pdf(
    source: Path,
    output: Path | None = None,
    *,
    force: bool = False,
    options: CleanOptions = CleanOptions(),
    dry_run: bool = False,
    assume_wuolah: bool = False,
) -> CleanResult:
    source = source.resolve()
    output = (output or source).resolve()
    in_place = source == output
    if output.exists() and not in_place and not force:
        return CleanResult(str(source), str(output), 0, [], status="skipped", error="la salida ya existe")
    temp_output = output.with_name(f".{output.stem}.{uuid4().hex}.tmp{output.suffix or '.pdf'}")
    try:
        with pymupdf.open(source) as doc:
            original_count = doc.page_count
            removed = []
            promo_pages = []
            page_texts = []
            for i, page in enumerate(doc):
                text = page.get_text("text")
                page_texts.append(text)
                if _page_promo_text(text):
                    removed.append(i)
                    promo_pages.append(i)
            if not assume_wuolah and not _is_wuolah_document(doc, promo_pages, source):
                return CleanResult(
                    str(source), str(output), original_count, [],
                    status="skipped", error="no parece un PDF de Wuolah",
                )
            whole_page_removals, page_reasons = _full_page_insert_pages(doc, page_texts, options)
            for page_index in whole_page_removals:
                if page_index not in removed:
                    removed.append(page_index)
            removed.sort()

            regions: list[dict[str, str | int]] = []
            branding: list[dict[str, str | int]] = []
            black_marks = (
                _repeated_black_footer_marks(doc, options, set(removed))
                if options.remove_wuolah_branding else {}
            )
            if options.remove_wuolah_branding:
                repeated_images = _repeated_footer_brand_images(doc, options)
                repeated_images.update({
                    xref: pages for xref, pages in _repeated_watermark_images(doc, options).items()
                    if xref not in repeated_images
                })
                for xref, page_numbers in repeated_images.items():
                    # PyMuPDF replaces this image xref globally, including its
                    # uses on every page, with a transparent 1x1 image.
                    doc.load_page(page_numbers[0] - 1).delete_image(xref)
                    branding.extend(
                        {"page": page_no, "kind": "repeated_transparent_image_mark"}
                        for page_no in page_numbers
                    )
                branding.extend(_remove_wuolah_metadata(doc))
            removed_set = set(removed)
            for i, page in enumerate(doc):
                if i not in removed_set:
                    page_regions, page_branding = _clean_page_ads(
                        page, i + 1, options, black_marks.get(i),
                    )
                    regions.extend(page_regions)
                    branding.extend(page_branding)
            for i in reversed(removed):
                doc.delete_page(i)
            if doc.page_count == 0:
                return CleanResult(
                    str(source), str(output), original_count, [i + 1 for i in removed],
                    regions, "skipped", "el documento solo contiene páginas promocionales",
                    removed_page_reasons=page_reasons,
                )
            if not removed and not regions and not branding:
                return CleanResult(str(source), str(output), original_count, [], status="unchanged")
            if dry_run:
                return CleanResult(
                    str(source), str(output), original_count,
                    [i + 1 for i in removed], regions, "would_clean",
                    removed_branding=branding,
                    removed_page_reasons=page_reasons,
                )
            output.parent.mkdir(parents=True, exist_ok=True)
            doc.save(temp_output, garbage=4, deflate=True, deflate_images=True, clean=True)
        if in_place:
            temp_output.chmod(stat.S_IMODE(source.stat().st_mode))
        temp_output.replace(output)
        return CleanResult(
            str(source), str(output), original_count, [i + 1 for i in removed],
            regions, removed_branding=branding,
            removed_page_reasons=page_reasons,
        )
    finally:
        temp_output.unlink(missing_ok=True)
