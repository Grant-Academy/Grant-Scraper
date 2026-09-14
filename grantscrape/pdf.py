"""PDF -> per-page markdown chunks (layout text plus any detected tables)."""

from __future__ import annotations

import io
import re

import pdfplumber

from .chunk import Chunk, chunk_markdown, MAX_CHARS
from .normalize import extract_year, squash_ws


def _cell(v: str | None) -> str:
    return "; ".join(squash_ws(part) for part in (v or "").split("\n") if part.strip())


def _table_to_markdown(table: list[list[str | None]]) -> str:
    rows = [[_cell(c) for c in row] for row in table if any((c or "").strip() for c in row)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header, body = rows[0], rows[1:]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def _title_row(row: list[str | None]) -> str | None:
    """A table row with exactly one non-empty cell is a title spanning the table (e.g. a category name)."""
    cells = [squash_ws(c) for c in row if c and squash_ws(c)]
    return cells[0] if len(cells) == 1 and not re.search(r"\d", cells[0]) else None


def continuation_titles(tables_per_page: list[list[list[list[str | None]]]]) -> list[str | None]:
    """For each page: the table title it continues from the previous page, or None if it starts its own."""
    out: list[str | None] = []
    carry: str | None = None
    for tables in tables_per_page:
        first_rows = [next((r for r in t if any(c and c.strip() for c in r)), None) for t in tables]
        starts_titled = bool(first_rows) and first_rows[0] is not None and _title_row(first_rows[0]) is not None
        out.append(None if (starts_titled or not tables) else carry)
        for t in tables:
            for r in t:
                title = _title_row(r)
                if title:
                    carry = title
    return out


def _page_markdown(page, page_no: int, doc_title: str = "", continues: str | None = None, tables=None) -> str:
    title = f"{doc_title} · page {page_no}" if doc_title else f"Page {page_no}"
    if continues:
        title += f" · continues: {continues}"
    parts = [f"# {title} {{#page={page_no}}}"]
    for table in (tables if tables is not None else page.extract_tables()) or []:
        md = _table_to_markdown(table)
        if md:
            parts.append(md)
    text = page.extract_text(layout=True) or ""
    lines = [re.sub(r"[ \t]{2,}", "  ", ln).strip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    if text:
        parts.append("## Page text\n\n" + text)
    return "\n\n".join(parts) + "\n"


def _doc_title(pdf) -> str:
    """First short text line of page 1 (e.g. 'MYÖNNETYT APURAHAT 2024'), carried onto every page's heading."""
    if not pdf.pages:
        return ""
    for line in (pdf.pages[0].extract_text() or "").splitlines():
        line = squash_ws(line)
        if line:
            return line if len(line) <= 100 else ""
    return ""


def pdf_to_markdown_pages(data: bytes) -> list[str]:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        title = _doc_title(pdf)
        tables = [p.extract_tables() or [] for p in pdf.pages]
        conts = continuation_titles(tables)
        return [_page_markdown(p, i + 1, title, conts[i], tables[i]) for i, p in enumerate(pdf.pages)]


def pdf_to_chunks(data: bytes, source_url: str, cap: int = MAX_CHARS) -> list[Chunk]:
    pages = pdf_to_markdown_pages(data)
    doc_year = None
    for md in pages:
        doc_year = extract_year(md.split("## Page text")[-1][:400]) if "## Page text" in md else None
        if doc_year:
            break
    doc_year = doc_year or extract_year(source_url)

    chunks: list[Chunk] = []
    for page_no, md in enumerate(pages, start=1):
        for c in chunk_markdown(md, source_url=source_url, kind="pdf", cap=cap, page_no=page_no):
            if c.year_hint is None:
                c.year_hint = doc_year
            c.id = f"{len(chunks):03d}"
            chunks.append(c)
    return chunks
