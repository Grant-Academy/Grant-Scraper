from pathlib import Path

from grantscrape.clean import html_to_markdown

FIX = Path(__file__).parent / "fixtures"


def test_heading_ids_become_markdown_anchors():
    md = html_to_markdown((FIX / "huber_arkisto.html").read_bytes())
    assert "# 2025 {#2025}" in md
    assert "### ESITYSTAIDE {#esitystaide}" in md


def test_headings_without_id_have_no_anchor_suffix():
    md = html_to_markdown((FIX / "linnamo.html").read_bytes())
    assert "## Vuoden 2025 teemahaku: oikeus ja politiikka" in md
    assert "{#" not in md.split("Vuoden 2025 teemahaku")[1].split("\n")[0]


def test_navigation_and_scripts_are_dropped():
    md = html_to_markdown((FIX / "huber.html").read_bytes())
    assert "<script" not in md
    assert "wp-block" not in md


def test_grant_entry_structure_is_preserved():
    md = html_to_markdown((FIX / "huber.html").read_bytes())
    i = md.index("**Laura Rämä**")
    block = md[i : i + 400]
    assert "€ 3.500" in block
    assert "* Syntipukki" in block or "- Syntipukki" in block


def test_prose_lines_are_preserved_as_separate_paragraphs():
    md = html_to_markdown((FIX / "linnamo.html").read_bytes())
    assert "Fabritius, Noora" in md
    assert "Heinikoski, Saila" in md


def test_decomposed_unicode_is_normalised_to_nfc():
    decomposed = "<main><p>" + "Häkkinen " * 40 + "</p></main>"
    md = html_to_markdown(decomposed.encode())
    assert "Häkkinen" in md
    assert "ä" not in md
