from pathlib import Path

from grantscrape.clean import html_to_markdown
from grantscrape.chunk import chunk_markdown, MAX_CHARS

FIX = Path(__file__).parent / "fixtures"
HUBER_URL = "https://www.hubersaatio.fi/arkisto/"


def _chunks(name, url):
    md = html_to_markdown((FIX / name).read_bytes())
    return chunk_markdown(md, source_url=url, kind="html")


def test_huber_archive_splits_into_many_year_chunks_under_cap():
    chunks = _chunks("huber_arkisto.html", HUBER_URL)
    assert len(chunks) >= 20
    assert all(c.char_count <= MAX_CHARS for c in chunks)
    assert all(c.year_hint is not None for c in chunks if "**" in c.text)


def test_huber_chunk_anchor_points_to_year_heading():
    chunks = _chunks("huber_arkisto.html", HUBER_URL)
    c2025 = [c for c in chunks if c.year_hint == 2025]
    assert c2025
    assert all(c.anchor_url == HUBER_URL + "#2025" for c in c2025)
    assert all("2025" in c.heading_path for c in c2025)


def test_chunk_ids_are_sequential_zero_padded():
    chunks = _chunks("linnamo.html", "https://linnamonsaatio.fi/arkisto/")
    assert [c.id for c in chunks] == [f"{i:03d}" for i in range(len(chunks))]


def test_linnamo_year_hints_cover_all_years():
    chunks = _chunks("linnamo.html", "https://linnamonsaatio.fi/arkisto/")
    years = {c.year_hint for c in chunks}
    assert {2020, 2021, 2022, 2023, 2024, 2025} <= years


def test_no_grant_line_is_lost_by_chunking():
    md = html_to_markdown((FIX / "linnamo.html").read_bytes())
    chunks = chunk_markdown(md, source_url="u", kind="html")
    joined = "\n".join(c.text for c in chunks)
    for needle in ("Fabritius, Noora", "Heinikoski, Saila", "Airo, Henri"):
        assert needle in joined


def test_tiny_yearless_preamble_merges_into_following_chunk():
    md = "# ARKISTO\n\nIntro line.\n\n# 2021 {#2021}\n\n**A** – € 1.000\n\n**B** – € 2.000\n"
    chunks = chunk_markdown(md, source_url="u", kind="html")
    assert len(chunks) == 1
    assert chunks[0].year_hint == 2021
    assert chunks[0].anchor_url == "u#2021"
    assert "Intro line." in chunks[0].text


def test_oversized_section_is_split_only_at_blank_lines():
    body = "\n\n".join(f"**Person {i}** – € 1.000 – musiikki\n* Title {i}\n* Desc {i}" for i in range(400))
    md = f"# 2021 {{#2021}}\n\n{body}\n"
    chunks = chunk_markdown(md, source_url="u", kind="html")
    assert len(chunks) > 1
    assert all(c.char_count <= MAX_CHARS for c in chunks)
    for c in chunks:
        assert c.text.splitlines()[1].startswith(("**Person", "# 2021"))
        assert c.year_hint == 2021
        assert c.anchor_url == "u#2021"


def test_every_chunk_starts_with_section_breadcrumb():
    body = "\n\n".join(f"**Person {i}** – € 1.000 – musiikki\n* Title {i}" for i in range(300))
    md = f"# 2021 {{#2021}}\n\n## Myönnetyt apurahat\n\n### MUSIIKKI\n\n{body}\n"
    chunks = chunk_markdown(md, source_url="u", kind="html")
    assert len(chunks) > 1
    assert chunks[0].text.startswith("[section: 2021")
    for c in chunks[1:]:
        assert c.text.startswith("[section: 2021 > Myönnetyt apurahat > MUSIIKKI]\n")


def test_split_never_separates_bold_name_line_from_its_bullets():
    entries = [f"**Person {i}** – € 1.000 – musiikki\n\n* Title {i}\n* " + ("Kuvaus " * 40) for i in range(60)]
    md = "# 2026\n\n" + "\n\n".join(entries) + "\n"
    chunks = chunk_markdown(md, source_url="u", kind="html")
    assert len(chunks) > 1
    for c in chunks:
        body = c.text.split("\n", 1)[1].strip()          # drop breadcrumb line
        body = body.removeprefix("# 2026").strip()
        assert body.startswith("**Person"), body[:60]
        assert c.text.rstrip().endswith("Kuvaus")


def test_one_liner_lists_without_bold_still_split_under_cap():
    md = "# 2020\n\n" + "\n\n".join(f"FM Henkilö {i}: julkaisukuluihin (arkeologia), 700 €" for i in range(400)) + "\n"
    chunks = chunk_markdown(md, source_url="u", kind="html")
    assert len(chunks) > 1
    assert all(c.char_count <= MAX_CHARS for c in chunks)
