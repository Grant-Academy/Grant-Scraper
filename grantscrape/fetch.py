"""Download a page or PDF, save the raw source, and turn it into anchored chunks under a run dir."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import httpx

from .chunk import Chunk, chunk_markdown
from .clean import html_to_markdown
from .pdf import pdf_to_chunks
from .robots import USER_AGENT, fetch_robots, is_allowed

_BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
    "Accept-Language": "fi-FI,fi;q=0.9,sv;q=0.8,en;q=0.7",
}


@dataclass
class Fetched:
    url: str
    final_url: str
    status: int
    content_type: str
    body: bytes


def fetch_url(url: str, transport: httpx.BaseTransport | None = None, robots_txt: str | None = None, retries: int = 2) -> Fetched:
    """GET with a browser-like UA. Raises PermissionError when robots.txt disallows the path."""
    client = httpx.Client(follow_redirects=True, timeout=30, headers=_BROWSER_HEADERS, transport=transport)
    if robots_txt is None:
        robots_txt = fetch_robots(url, client)
    if not is_allowed(url, robots_txt):
        raise PermissionError(f"robots.txt disallows fetching {url}")
    last: Exception | None = None
    for _ in range(retries + 1):
        try:
            r = client.get(url)
            return Fetched(url=url, final_url=str(r.url), status=r.status_code, content_type=r.headers.get("content-type", ""), body=r.content)
        except httpx.HTTPError as e:  # pragma: no cover - network flakiness
            last = e
    raise RuntimeError(f"fetch failed for {url}: {last}")


def _load_manifest(run_dir: Path) -> list[dict]:
    p = run_dir / "chunks" / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else []


def _save_manifest(run_dir: Path, manifest: list[dict]) -> None:
    (run_dir / "chunks").mkdir(parents=True, exist_ok=True)
    (run_dir / "chunks" / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))


def _is_pdf(content_type: str, url: str, body: bytes) -> bool:
    return "pdf" in content_type.lower() or url.lower().endswith(".pdf") or body[:5] == b"%PDF-"


def _append_chunks(run_dir: Path, chunks: list[Chunk], source_idx: int) -> list[Chunk]:
    manifest = _load_manifest(run_dir)
    start = len(manifest)
    (run_dir / "chunks").mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(chunks):
        c.id = f"{start + i:03d}"
        c.file = f"{c.id}.md"
        (run_dir / "chunks" / c.file).write_text(c.text)
        entry = c.to_manifest()
        entry["source_idx"] = source_idx
        manifest.append(entry)
    _save_manifest(run_dir, manifest)
    return chunks


def _next_source_idx(run_dir: Path) -> int:
    src = run_dir / "source"
    src.mkdir(parents=True, exist_ok=True)
    return len({p.name.split(".")[0] for p in src.iterdir() if p.name[:3].isdigit()})


def ingest_bytes(run_dir: Path, source_url: str, body: bytes, content_type: str) -> list[Chunk]:
    """Save raw source and write chunks + manifest. Appends to an existing run."""
    run_dir = Path(run_dir)
    idx = _next_source_idx(run_dir)
    src = run_dir / "source"
    if _is_pdf(content_type, source_url, body):
        (src / f"{idx:03d}.raw.pdf").write_bytes(body)
        chunks = pdf_to_chunks(body, source_url=source_url)
    else:
        (src / f"{idx:03d}.raw.html").write_bytes(body)
        md = html_to_markdown(body)
        (src / f"{idx:03d}.cleaned.md").write_text(md)
        chunks = chunk_markdown(md, source_url=source_url, kind="html")
    (src / f"{idx:03d}.meta.json").write_text(json.dumps({"source_url": source_url, "content_type": content_type, "bytes": len(body)}, indent=1))
    return _append_chunks(run_dir, chunks, idx)


def ingest_file(run_dir: Path, source_url: str, path: Path) -> list[Chunk]:
    """Ingest a local file: .md/.txt are treated as pre-fetched cleaned text (browser fallback), else by sniffing."""
    path = Path(path)
    body = path.read_bytes()
    if path.suffix.lower() in (".md", ".txt"):
        run_dir = Path(run_dir)
        idx = _next_source_idx(run_dir)
        src = run_dir / "source"
        md = body.decode("utf-8")
        (src / f"{idx:03d}.cleaned.md").write_text(md)
        (src / f"{idx:03d}.meta.json").write_text(json.dumps({"source_url": source_url, "content_type": "text/markdown", "from_file": str(path)}, indent=1))
        return _append_chunks(run_dir, chunk_markdown(md, source_url=source_url, kind="html"), idx)
    content_type = "application/pdf" if path.suffix.lower() == ".pdf" else "text/html"
    return ingest_bytes(run_dir, source_url, body, content_type)


def ingest_url(run_dir: Path, url: str) -> tuple[Fetched, list[Chunk]]:
    f = fetch_url(url)
    if f.status != 200:
        raise RuntimeError(f"HTTP {f.status} for {url}. If this is a 403 or a JS shell, save the page text from a browser and use --from-file.")
    return f, ingest_bytes(run_dir, f.final_url, f.body, f.content_type)
