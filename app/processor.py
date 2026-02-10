from __future__ import annotations
import zipfile
from pathlib import Path
from typing import Iterable
from .pdf_utils import load_all_pages, extract_pages_as_docs, tile_pages, merge_pdfs, save_single_per_page
from .config import A4_WIDTH_PT, A4_HEIGHT_PT, THERMAL_75x120, THERMAL_100x150, ORDER_ID_REGEX

def collect_input_files(paths: Iterable[Path], workdir: Path) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        if p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p, "r") as z:
                for n in z.namelist():
                    if n.lower().endswith(".pdf"):
                        z.extract(n, path=workdir)
                        out.append(workdir / n)
        elif p.suffix.lower() == ".pdf":
            out.append(p)
    return out

def group_by_invoice_id(pdf_paths: list[Path]) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {}
    for p in pdf_paths:
        m = ORDER_ID_REGEX.search(p.stem)
        key = m.group(1) if m else p.stem
        groups.setdefault(key, []).append(p)
    for k in groups:
        groups[k].sort()
    return groups

def process_layout(mode: str, input_paths: list[Path], out_path: Path) -> Path:
    if mode == "MERGE":
        merge_pdfs(input_paths, out_path)
        return out_path

    groups = group_by_invoice_id(input_paths)
    group_pages = []
    for _, files in groups.items():
        docs = load_all_pages(files)
        pages = extract_pages_as_docs(docs)
        group_pages.extend(pages)

    if mode == "THERMAL_75x120":
        save_single_per_page(group_pages, out_path, THERMAL_75x120)
    elif mode == "THERMAL_100x150":
        save_single_per_page(group_pages, out_path, THERMAL_100x150)
    elif mode == "A4_SINGLE":
        save_single_per_page(group_pages, out_path, (A4_WIDTH_PT, A4_HEIGHT_PT))
    elif mode == "A4_2x2":
        tile_pages(group_pages, out_path, (A4_WIDTH_PT, A4_HEIGHT_PT), (2,2))
    elif mode == "A4_2x4":
        tile_pages(group_pages, out_path, (A4_WIDTH_PT, A4_HEIGHT_PT), (2,4))
    elif mode == "A4_3x3":
        tile_pages(group_pages, out_path, (A4_WIDTH_PT, A4_HEIGHT_PT), (3,3))
    else:
        raise ValueError(f"Unknown mode: {mode}")
    return out_path
