from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .cleaner import CleanOptions, CleanResult, clean_pdf


def _one(args: tuple[str, str, bool, CleanOptions, bool, bool]) -> dict:
    src, dst, force, options, dry_run, assume_wuolah = args
    try:
        return clean_pdf(
            Path(src), Path(dst), force=force, options=options,
            dry_run=dry_run, assume_wuolah=assume_wuolah,
        ).__dict__
    except Exception as exc:
        return CleanResult(src, dst, 0, [], status="error", error=f"{type(exc).__name__}: {exc}").__dict__


def main() -> None:
    parser = argparse.ArgumentParser(prog="wuolah-wout-ads", description="Limpia PDFs de Wuolah localmente y omite otros documentos.")
    parser.add_argument("input", type=Path, help="PDF o carpeta de entrada")
    parser.add_argument("-o", "--output", type=Path, help="guarda copias limpias en esta ruta; por defecto reemplaza los PDFs Wuolah originales")
    parser.add_argument("-j", "--jobs", type=int, default=min(4, os.cpu_count() or 1), help="PDFs simultáneos (por defecto: hasta 4)")
    parser.add_argument("--force", action="store_true", help="con --output, reemplaza archivos de salida existentes")
    parser.add_argument("--json", action="store_true", help="imprime un resumen JSON compacto")
    parser.add_argument("--dry-run", action="store_true", help="informa qué limpiaría sin guardar cambios")
    parser.add_argument("--assume-wuolah", action="store_true", help="procesa un PDF aunque no tenga señales para reconocerlo como Wuolah")
    parser.add_argument("--min-link-area", type=float, default=0.004, metavar="FRACTION", help="área mínima del enlace publicitario respecto a la página (por defecto: 0.004)")
    parser.add_argument("--max-link-area", type=float, default=0.80, metavar="FRACTION", help="ignora enlaces que ocupan esta fracción o más de la página (por defecto: 0.80)")
    parser.add_argument("--banner-tolerance", type=float, default=0.025, metavar="FRACTION", help="tolerancia de separación entre banners, fracción de la altura (por defecto: 0.025)")
    parser.add_argument("--banner-top-min-width", type=float, default=0.84, metavar="FRACTION", help="ancho mínimo del banner superior (por defecto: 0.84)")
    parser.add_argument("--banner-side-min-height", type=float, default=0.70, metavar="FRACTION", help="alto mínimo del banner lateral (por defecto: 0.70)")
    parser.add_argument("--image-redaction", choices=("pixels", "remove", "none"), default="pixels", help="pixeles borra solo la zona; remove elimina imágenes que la tocan; none conserva imágenes (por defecto: pixels)")
    parser.add_argument("--graphics-redaction", choices=("contained", "covered", "none"), default="contained", help="manejo de gráficos vectoriales dentro de las zonas detectadas (por defecto: contained)")
    parser.add_argument("--redaction-color", default="#FFFFFF", metavar="#RRGGBB", help="color de relleno de las zonas borradas (por defecto: blanco)")
    ns = parser.parse_args()
    source = ns.input.resolve()
    if not source.exists():
        parser.error(f"No existe: {source}")
    if ns.jobs < 1:
        parser.error("--jobs debe ser al menos 1")
    if not 0 <= ns.min_link_area < ns.max_link_area <= 1:
        parser.error("--min-link-area y --max-link-area deben cumplir 0 <= mínimo < máximo <= 1")
    if not 0 <= ns.banner_tolerance <= 1 or not 0 < ns.banner_top_min_width <= 1 or not 0 < ns.banner_side_min_height <= 1:
        parser.error("los parámetros geométricos de banners deben ser fracciones válidas entre 0 y 1")
    color = ns.redaction_color.removeprefix("#")
    if len(color) != 6 or any(char not in "0123456789abcdefABCDEF" for char in color):
        parser.error("--redaction-color debe usar el formato #RRGGBB")
    fill_color = tuple(int(color[offset:offset + 2], 16) / 255 for offset in (0, 2, 4))
    if ns.assume_wuolah and not source.is_file():
        parser.error("--assume-wuolah solo se permite con un único PDF, nunca con carpetas mixtas")
    if source.is_file():
        if source.suffix.lower() != ".pdf":
            parser.error("La entrada debe ser un PDF")
        destination = ns.output.resolve() if ns.output else source
        pairs = [(source, destination)]
    else:
        destination = ns.output.resolve() if ns.output else source
        output_is_inside_input = destination != source and destination.is_relative_to(source)
        files = sorted(
            p for p in source.rglob("*")
            if p.is_file() and p.suffix.lower() == ".pdf"
            and not (output_is_inside_input and p.resolve().is_relative_to(destination))
        )
        pairs = [(p, p if destination == source else destination / p.relative_to(source)) for p in files]
    options = CleanOptions(
        min_link_area=ns.min_link_area,
        max_link_area=ns.max_link_area,
        banner_tolerance=ns.banner_tolerance,
        banner_top_min_width=ns.banner_top_min_width,
        banner_side_min_height=ns.banner_side_min_height,
        image_redaction=ns.image_redaction,
        graphics_redaction=ns.graphics_redaction,
        fill_color=fill_color,
    )
    tasks = [(str(src), str(dst), ns.force, options, ns.dry_run, ns.assume_wuolah) for src, dst in pairs]
    if not tasks:
        parser.error("No se encontraron archivos PDF")
    if len(tasks) == 1:
        rows = [_one(tasks[0])]
    else:
        rows = []
        with ProcessPoolExecutor(max_workers=min(ns.jobs, len(tasks))) as pool:
            futures = [pool.submit(_one, item) for item in tasks]
            for future in as_completed(futures):
                rows.append(future.result())
    rows.sort(key=lambda x: x["source"].casefold())
    if ns.json:
        print(json.dumps({
            "files": rows,
            "total": len(rows),
            "cleaned": sum(x["status"] == "cleaned" for x in rows),
            "unchanged": sum(x["status"] == "unchanged" for x in rows),
            "skipped": sum(x["status"] == "skipped" for x in rows),
            "would_clean": sum(x["status"] == "would_clean" for x in rows),
            "removed_pages": sum(len(x["removed_pages"]) for x in rows),
            "removed_regions": sum(len(x["removed_regions"]) for x in rows),
            "errors": sum(x["status"] == "error" for x in rows),
        }, ensure_ascii=False))
    else:
        for row in rows:
            removed = ",".join(map(str, row["removed_pages"])) or "ninguna"
            suffix = f" ({row['error']})" if row["error"] else ""
            print(f"{row['status']}: {row['source']} -> {row['output']} | páginas promocionales: {removed} | zonas publicitarias: {len(row['removed_regions'])}{suffix}")
        print(
            f"Limpiados: {sum(x['status'] == 'cleaned' for x in rows)}; "
            f"sin cambios: {sum(x['status'] == 'unchanged' for x in rows)}; "
            f"omitidos: {sum(x['status'] == 'skipped' for x in rows)}; "
            f"se limpiarían: {sum(x['status'] == 'would_clean' for x in rows)}; "
            f"errores: {sum(x['status'] == 'error' for x in rows)}"
        )


if __name__ == "__main__":
    main()
