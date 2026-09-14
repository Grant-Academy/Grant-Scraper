from pathlib import Path

from grantscrape.pdf import pdf_to_chunks

FIX = Path(__file__).parent / "fixtures"
URL = "https://www.karjalankulttuurirahasto.fi/wp-content/uploads/2024/12/Myonnetyt-apurahat-2024.pdf"


def _chunks():
    return pdf_to_chunks((FIX / "karjalan.pdf").read_bytes(), source_url=URL)


def test_one_chunk_per_page_with_page_anchor():
    chunks = _chunks()
    assert len(chunks) == 3
    assert [c.anchor_url for c in chunks] == [f"{URL}#page={n}" for n in (1, 2, 3)]
    assert [c.page_no for c in chunks] == [1, 2, 3]
    assert all(c.kind == "pdf" for c in chunks)


def test_table_rows_are_rendered_as_markdown_table():
    page1 = _chunks()[0].text
    assert "| 2024010 | Hänninen Mikko |" in page1
    assert "14 000 €" in page1


def test_multiline_cells_are_joined_with_semicolon():
    page2 = _chunks()[1].text
    assert "Kangaskosken-Ritakosken kyläyhdistys; ry" in page2


def test_year_hint_comes_from_document_when_page_has_no_year_heading():
    chunks = _chunks()
    assert all(c.year_hint == 2024 for c in chunks)


def test_chunk_ids_sequential_across_pages():
    assert [c.id for c in _chunks()] == ["000", "001", "002"]


def test_pdf_pages_carry_document_title_so_later_pages_know_the_year():
    chunks = _chunks()
    assert "MYÖNNETYT APURAHAT 2024" in chunks[2].text.splitlines()[0]
