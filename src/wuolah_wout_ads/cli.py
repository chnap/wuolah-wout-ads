from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .cleaner import CleanResult, clean_pdf


def _one(args: tuple[str, str, bool]) -> dict:
    src, dst, force = args
    try:
        return clean_pdf(Path(src), Path(dst), force=force).__dict__
    except Exception as exc:
        return CleanResult(src, dst, 0, [], status="error", error=f"{type(exc).__name__}: {exc}").__dict__


def main() -> None:
    parser = argparse.ArgumentParser(prog="wuolah-wout-ads", description="Limpia PDFs de Wuolah localmente y omite otros documentos.")
    parser.add_argument("input", type=Path, help="PDF o carpeta de entrada")
    parser.add_argument("-o", "--output", type=Path, help="guarda copias limpias en esta ruta; por defecto reemplaza los PDFs Wuolah originales")
    parser.add_argument("-j", "--jobs", type=int, default=min(4, os.cpu_count() or 1), help="PDFs simultáneos (por defecto: hasta 4)")
    parser.add_argument("--force", action="store_true", help="con --output, reemplaza archivos de salida existentes")
    parser.add_argument("--json", action="store_true", help="imprime un resumen JSON compacto")
    ns = parser.parse_args()
    source = ns.input.resolve()
    if not source.exists():
        parser.error(f"No existe: {source}")
    if ns.jobs < 1:
        parser.error("--jobs debe ser al menos 1")
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
    tasks = [(str(src), str(dst), ns.force) for src, dst in pairs]
    if not tasks:
        parser.error("No se encontraron archivos PDF")
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
            f"errores: {sum(x['status'] == 'error' for x in rows)}"
        )


if __name__ == "__main__":
    main()
