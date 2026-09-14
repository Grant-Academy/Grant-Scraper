import json
from pathlib import Path

import httpx
import pytest

from grantscrape.robots import is_allowed
from grantscrape.fetch import fetch_url, ingest_bytes, ingest_file, Fetched

FIX = Path(__file__).parent / "fixtures"


def test_robots_disallow_blocks_path():
    robots = "User-agent: *\nDisallow: /search\n"
    assert is_allowed("https://x.fi/search/2020", robots_txt=robots) is False
    assert is_allowed("https://x.fi/2020/03/post.html", robots_txt=robots) is True


def test_robots_missing_means_allowed():
    assert is_allowed("https://x.fi/anything", robots_txt=None) is True


def test_fetch_url_returns_body_and_content_type():
    def handler(request):
        assert "Mozilla" in request.headers["user-agent"]
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, content=b"<html><main>hi</main></html>")

    f = fetch_url("https://example.fi/page", transport=httpx.MockTransport(handler), robots_txt="")
    assert isinstance(f, Fetched)
    assert f.status == 200
    assert f.content_type.startswith("text/html")
    assert f.body.startswith(b"<html>")


def test_fetch_url_refuses_when_robots_disallows():
    with pytest.raises(PermissionError):
        fetch_url("https://example.fi/private/x", transport=httpx.MockTransport(lambda r: httpx.Response(200)), robots_txt="User-agent: *\nDisallow: /private")


def test_ingest_html_writes_chunks_and_manifest(tmp_path):
    run = tmp_path / "huber"
    chunks = ingest_bytes(run, "https://www.hubersaatio.fi/myonnetyt-apurahat/", (FIX / "huber.html").read_bytes(), "text/html")
    manifest = json.loads((run / "chunks" / "manifest.json").read_text())
    assert len(manifest) == len(chunks) > 3
    assert (run / "chunks" / "000.md").exists()
    assert manifest[0]["file"] == "000.md"
    assert manifest[1]["source_url"] == "https://www.hubersaatio.fi/myonnetyt-apurahat/"
    assert (run / "source" / "000.raw.html").exists()
    assert (run / "source" / "000.cleaned.md").exists()


def test_ingest_pdf_by_content_type(tmp_path):
    run = tmp_path / "karjalan"
    chunks = ingest_bytes(run, "https://k.fi/a.pdf", (FIX / "karjalan.pdf").read_bytes(), "application/pdf")
    assert len(chunks) == 3
    assert chunks[0].kind == "pdf"
    assert (run / "source" / "000.raw.pdf").exists()


def test_second_ingest_appends_with_continued_ids(tmp_path):
    run = tmp_path / "huber"
    first = ingest_bytes(run, "https://h.fi/a", (FIX / "huber.html").read_bytes(), "text/html")
    second = ingest_bytes(run, "https://h.fi/b", (FIX / "linnamo.html").read_bytes(), "text/html")
    manifest = json.loads((run / "chunks" / "manifest.json").read_text())
    assert len(manifest) == len(first) + len(second)
    assert second[0].id == f"{len(first):03d}"
    assert manifest[-1]["source_url"] == "https://h.fi/b"
    assert (run / "source" / "001.raw.html").exists()


def test_ingest_file_treats_markdown_as_prefetched_text(tmp_path):
    src = tmp_path / "manual.md"
    src.write_text("# 2023\n\n**Anna Virtanen** – 1 000 €\n")
    chunks = ingest_file(tmp_path / "run", "https://blocked.fi/list", src)
    assert len(chunks) == 1
    assert chunks[0].year_hint == 2023
    assert chunks[0].source_url == "https://blocked.fi/list"
