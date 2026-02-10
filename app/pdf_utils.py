from __future__ import annotations
import fitz  # PyMuPDF
from pathlib import Path
from typing import Iterable, Tuple, List

Rect = fitz.Rect

# точки в мм, чтобы задать margin автокропа в мм
PT_PER_MM = 72 / 25.4

def autotrim_bbox(page: fitz.Page, margin_mm: float = 3) -> fitz.Rect:
    """
    Находит минимальный bbox всех блоков (текст, изображения, вектор)
    и расширяет его на margin_mm миллиметров.
    """
    info = page.get_text("dict")
    boxes: list[fitz.Rect] = []
    for b in info["blocks"]:
        if b["type"] in (0, 1, 2):  # 0=text, 1=image, 2=drawing
            boxes.append(fitz.Rect(*b["bbox"]))
    if not boxes:
        # пустая страница
        return page.rect

    # объединяем все боксы
    bbox = boxes[0]
    for r in boxes[1:]:
        bbox |= r

    # добавляем margin и не выходим за пределы страницы
    m = margin_mm * PT_PER_MM
    bbox.x0 = max(0, bbox.x0 - m)
    bbox.y0 = max(0, bbox.y0 - m)
    bbox.x1 = min(page.rect.x1, bbox.x1 + m)
    bbox.y1 = min(page.rect.y1, bbox.y1 + m)
    return bbox

def load_all_pages(paths: Iterable[Path]) -> list[tuple[Path, fitz.Document]]:
    docs = []
    for p in paths:
        if p.suffix.lower() == ".pdf":
            docs.append((p, fitz.open(p)))
    return docs

def extract_pages_as_docs(docs: list[tuple[Path, fitz.Document]]) -> list[fitz.Page]:
    pages: list[fitz.Page] = []
    for _, d in docs:
        for page in d:
            pages.append(page)
    return pages

def tile_pages(
    pages: List[fitz.Page],
    out_pdf: Path,
    page_size_pt: Tuple[float, float],
    grid: Tuple[int, int]
) -> None:
    """
    Размещает страницы по сетке grid на листе page_size_pt,
    сначала обрезая поля, затем масштабируя и центрируя.
    """
    cols, rows = grid
    W, H = page_size_pt
    cell_w, cell_h = W / cols, H / rows

    out = fitz.open()
    col = row = 0
    outpage: fitz.Page | None = None

    for page in pages:
        if col == 0 and row == 0:
            outpage = out.new_page(width=W, height=H)

        src_rect = page.rect
        clip = autotrim_bbox(page)
        ratio_w = cell_w / clip.width
        ratio_h = cell_h / clip.height
        scale = min(ratio_w, ratio_h)
        new_w = clip.width * scale
        new_h = clip.height * scale

        x0 = col * cell_w + (cell_w - new_w) / 2
        y0 = row * cell_h + (cell_h - new_h) / 2
        dest = fitz.Rect(x0, y0, x0 + new_w, y0 + new_h)

        outpage.show_pdf_page(dest, page.parent, page.number, clip=clip)

        col += 1
        if col >= cols:
            col = 0
            row += 1
        if row >= rows:
            row = 0

    out.save(out_pdf)
    out.close()

def merge_pdfs(paths: Iterable[Path], out_pdf: Path) -> None:
    out = fitz.open()
    for p in paths:
        with fitz.open(p) as doc:
            out.insert_pdf(doc)
    out.save(out_pdf)
    out.close()

def save_single_per_page(
    pages: List[fitz.Page],
    out_pdf: Path,
    page_size_pt: Tuple[float, float]
) -> None:
    """
    Помещает по одному автокропнутому PDF-клипу на каждую страницу заданного размера.
    """
    out = fitz.open()
    W, H = page_size_pt

    for page in pages:
        outpage = out.new_page(width=W, height=H)
        clip = autotrim_bbox(page)
        ratio_w = W / clip.width
        ratio_h = H / clip.height
        scale = min(ratio_w, ratio_h)
        new_w, new_h = clip.width * scale, clip.height * scale

        x0 = (W - new_w) / 2
        y0 = (H - new_h) / 2
        dest = fitz.Rect(x0, y0, x0 + new_w, y0 + new_h)

        outpage.show_pdf_page(dest, page.parent, page.number, clip=clip)

    out.save(out_pdf)
    out.close()
