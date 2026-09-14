"""Split markdown into heading-anchored chunks that fit an LLM read, without cutting entries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

from .normalize import extract_year

MAX_CHARS = 6000
BREADCRUMB_RESERVE = 200  # room for the "[section: ...]" line at the top of each chunk
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+\{#([^}]+)\})?\s*$")


@dataclass
class Chunk:
    id: str
    text: str
    source_url: str
    anchor_url: str
    heading_path: list[str]
    year_hint: int | None
    kind: str
    page_no: int | None = None
    file: str = ""

    @property
    def char_count(self) -> int:
        return len(self.text)

    def to_manifest(self) -> dict:
        d = asdict(self)
        d.pop("text")
        d["char_count"] = self.char_count
        return d


@dataclass
class _Section:
    level: int
    title: str
    anchor: str | None
    body_lines: list[str] = field(default_factory=list)
    children: list["_Section"] = field(default_factory=list)

    def own_text(self) -> str:
        head = f"{'#' * self.level} {self.title}\n\n" if self.level else ""
        return head + "\n".join(self.body_lines).strip() + "\n"

    def full_text(self) -> str:
        return self.own_text() + "".join("\n" + c.full_text() for c in self.children)


def _parse_sections(md: str) -> _Section:
    root = _Section(level=0, title="", anchor=None)
    stack = [root]
    for line in md.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            level, title, anchor = len(m.group(1)), m.group(2).strip(), m.group(3)
            sec = _Section(level=level, title=title, anchor=anchor)
            while stack[-1].level >= level:
                stack.pop()
            stack[-1].children.append(sec)
            stack.append(sec)
        else:
            stack[-1].body_lines.append(line)
    return root


def _is_entry_start(para: str) -> bool:
    """A paragraph that opens a new award entry: bold name, table row, or heading."""
    p = para.lstrip()
    return p.startswith(("**", "__", "|", "#"))


def _units(text: str) -> list[str]:
    """Group paragraphs into entries so a name line is never separated from its bullets/amount lines.

    If the text has bold/table entry starters, a unit runs from one starter to the next.
    Otherwise (plain one-liner lists) every paragraph is its own unit."""
    paras = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if sum(_is_entry_start(p) for p in paras[1:]) == 0:
        return paras
    units: list[str] = []
    for p in paras:
        if not units or _is_entry_start(p):
            units.append(p)
        else:
            units[-1] += "\n\n" + p
    return units


def _split_at_blank_lines(text: str, cap: int) -> list[str]:
    out, cur = [], ""
    for unit in _units(text):
        pieces = [unit] if len(unit) <= cap else re.split(r"\n\s*\n", unit)  # oversized entry: fall back to paragraphs
        for p in pieces:
            cand = f"{cur}\n\n{p}" if cur else p
            if len(cand) <= cap or not cur:
                cur = cand
            else:
                out.append(cur)
                cur = p
    if cur:
        out.append(cur)
    return out


def _walk(sec: _Section, path: list[tuple[str, str | None]], cap: int, out: list[dict]) -> None:
    """Emit leaf pieces: (text, heading_path_with_anchors). Descend only when a section is over cap."""
    my_path = path + ([(sec.title, sec.anchor)] if sec.level else [])
    full = sec.full_text()
    if sec.level and len(full) <= cap and not _children_carry_other_years(sec, _year_from_path(my_path)):
        if full.strip():
            out.append({"text": full, "path": my_path})
        return
    own = sec.own_text()
    if own.strip():
        for piece in _split_at_blank_lines(own, cap):
            out.append({"text": piece, "path": my_path})
    for child in sec.children:
        _walk(child, my_path, cap, out)


def _children_carry_other_years(sec: _Section, year: int | None) -> bool:
    """True if any descendant heading names a year different from `year` (so we must descend)."""
    for child in sec.children:
        y = extract_year(child.title)
        if y and y != year:
            return True
        if _children_carry_other_years(child, y or year):
            return True
    return False


def _year_from_path(path: list[tuple[str, str | None]]) -> int | None:
    for title, _ in reversed(path):
        y = extract_year(title)
        if y:
            return y
    return None


def _anchor_from_path(path: list[tuple[str, str | None]]) -> str | None:
    for _, anchor in reversed(path):
        if anchor:
            return anchor
    return None


def chunk_markdown(md: str, source_url: str, kind: str = "html", cap: int = MAX_CHARS, page_no: int | None = None) -> list[Chunk]:
    root = _parse_sections(md)
    pieces: list[dict] = []
    body_cap = cap - BREADCRUMB_RESERVE
    _walk(root, [], body_cap, pieces)

    # Greedy merge of consecutive pieces that share a year hint, to keep chunk count sane.
    merged: list[dict] = []
    for p in pieces:
        p["year"] = _year_from_path(p["path"])
        prev = merged[-1] if merged else None
        fits = prev is not None and len(prev["text"]) + len(p["text"]) + 2 <= body_cap
        if fits and prev["year"] == p["year"]:
            prev["text"] += "\n" + p["text"]
        elif fits and prev["year"] is None:
            # A year-less preamble (page title, intro) joins the first real section after it.
            prev["text"] += "\n" + p["text"]
            prev["year"] = p["year"]
            prev["path"] = p["path"]
        else:
            merged.append(p)

    chunks: list[Chunk] = []
    for i, p in enumerate(merged):
        anchor = _anchor_from_path(p["path"])
        crumb = " > ".join(t for t, _ in p["path"] if t)
        text = (f"[section: {crumb}]\n" if crumb else "") + p["text"].strip() + "\n"
        anchor_url = f"{source_url}#{anchor}" if anchor else (f"{source_url}#page={page_no}" if page_no else source_url)
        chunks.append(
            Chunk(
                id=f"{i:03d}",
                text=text,
                source_url=source_url,
                anchor_url=anchor_url,
                heading_path=[t for t, _ in p["path"]],
                year_hint=p["year"],
                kind=kind,
                page_no=page_no,
            )
        )
    return chunks
