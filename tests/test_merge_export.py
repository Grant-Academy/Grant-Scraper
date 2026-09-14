import csv
import json
from pathlib import Path

from grantscrape.merge import validate_run
from grantscrape.export import combine

CHUNK = (
    "# 2026 {#2026}\n\n**Laura Rämä** – € 3.500 – esitystaide, musiikki, teatteri\n\n"
    "* Syntipukki\n* Syntipukki on seremoniallinen tapahtuma ja esitys\n\n"
    "**Oblivia & KlangLab** – € 4.000 – esitystaide\n\n* Dreaming Turtles\n"
)

GOOD = {
    "recipient_name": "Laura Rämä", "recipient_raw": "Laura Rämä", "recipient_type": "person",
    "amount": 3500, "amount_raw": "€ 3.500", "currency": "EUR", "year": 2026,
    "project_title": "Syntipukki", "project_description": "Syntipukki on seremoniallinen tapahtuma ja esitys",
    "purpose": None, "discipline": "esitystaide, musiikki, teatteri",
    "evidence": "**Laura Rämä** – € 3.500 – esitystaide, musiikki, teatteri", "confidence": 0.95,
}
SHAKY = {
    "recipient_name": "Oblivia & KlangLab", "recipient_raw": "Oblivia & KlangLab", "recipient_type": "group",
    "amount": 4000, "amount_raw": "€ 4.000", "currency": "EUR", "year": 2026,
    "project_title": "Dreaming Turtles", "project_description": None, "purpose": None, "discipline": "esitystaide",
    "evidence": "**Oblivia & KlangLab** – € 4.000 – esitystaide", "confidence": 0.5, "notes": "amount line ambiguous",
}


def _make_run(tmp_path, slug="huber", rows=(GOOD, SHAKY), chunk_text=CHUNK, extra_rows_file=None):
    run = tmp_path / slug
    (run / "chunks").mkdir(parents=True)
    (run / "rows").mkdir()
    (run / "chunks" / "000.md").write_text(chunk_text)
    manifest = [{"id": "000", "file": "000.md", "source_url": "https://h.fi/list", "anchor_url": "https://h.fi/list#2026",
                 "heading_path": ["2026"], "year_hint": 2026, "kind": "html", "page_no": None, "char_count": len(chunk_text), "source_idx": 0}]
    (run / "chunks" / "manifest.json").write_text(json.dumps(manifest))
    foundation = "Samuel Huberin taidesäätiö" if slug == "huber" else f"Foundation {slug}"
    (run / "run.json").write_text(json.dumps({"foundation": foundation, "foundation_url": "https://h.fi/"}))
    (run / "rows" / "000.json").write_text(json.dumps({"chunk_id": "000", "rows": list(rows), "chunk_notes": None}, ensure_ascii=False))
    if extra_rows_file:
        (run / "rows" / "001.json").write_text(extra_rows_file)
    return run


def test_validate_splits_rows_by_confidence(tmp_path):
    run = _make_run(tmp_path)
    result = validate_run(run)
    assert result.errors == []
    assert [r.recipient_name for r in result.rows] == ["Laura Rämä"]
    assert [r.recipient_name for r in result.needs_review] == ["Oblivia & KlangLab"]
    assert result.rows[0].confidence == 0.95
    assert result.rows[0].source_url == "https://h.fi/list#2026"
    assert result.rows[0].foundation == "Samuel Huberin taidesäätiö"
    assert result.rows[0].run_id == "huber"
    assert result.needs_review[0].review_reasons == ["agent confidence 0.50 below 0.70: amount line ambiguous"]


def test_validate_writes_output_files(tmp_path):
    run = _make_run(tmp_path)
    validate_run(run)
    rows = json.loads((run / "out" / "rows.json").read_text())
    review = json.loads((run / "out" / "needs_review.json").read_text())
    stats = json.loads((run / "out" / "run.json").read_text())
    assert len(rows) == 1 and len(review) == 1
    assert stats["rows"] == 1 and stats["needs_review"] == 1 and stats["chunks"] == 1 and stats["chunks_extracted"] == 1


def test_grounding_failure_goes_to_review_even_with_high_agent_confidence(tmp_path):
    bad = dict(GOOD, evidence="**Laura Rämä** – € 9.999", confidence=0.99)
    run = _make_run(tmp_path, rows=(bad,))
    result = validate_run(run)
    assert result.rows == []
    assert result.needs_review[0].confidence == 0.5
    assert any("evidence" in r for r in result.needs_review[0].review_reasons)


def test_final_confidence_is_min_of_agent_and_rules(tmp_path):
    row = dict(GOOD, year=2019, confidence=0.9)  # rule score 0.7 < agent 0.9
    result = validate_run(_make_run(tmp_path, rows=(row,)))
    assert result.needs_review[0].confidence == 0.7


def test_duplicates_within_run_are_collapsed(tmp_path):
    result = validate_run(_make_run(tmp_path, rows=(GOOD, dict(GOOD))))
    assert len(result.rows) == 1
    assert result.rows[0].review_reasons == []
    assert result.duplicates_dropped == 1


def test_malformed_rows_file_is_reported_not_fatal(tmp_path):
    run = _make_run(tmp_path, extra_rows_file="{not json")
    result = validate_run(run)
    assert len(result.errors) == 1
    assert "001.json" in result.errors[0]
    assert len(result.rows) == 1


def test_missing_rows_file_counts_as_unextracted_chunk(tmp_path):
    run = _make_run(tmp_path)
    (run / "rows" / "000.json").unlink()
    result = validate_run(run)
    assert result.chunks_missing == ["000"]


def test_combine_writes_csv_json_review_and_summary(tmp_path):
    run_a = _make_run(tmp_path, "huber")
    chunk_b = "# 2026\n\nFabritius, Noora (VTM) Matka-apuraha tutkijavierailuun 3 700 €\n"
    run_b = _make_run(tmp_path, "linnamo", chunk_text=chunk_b,
                      rows=(dict(GOOD, recipient_name="Noora Fabritius", recipient_raw="Fabritius, Noora", amount=3700, amount_raw="3 700 €",
                                 project_title=None, project_description=None, purpose="Matka-apuraha tutkijavierailuun",
                                 evidence="Fabritius, Noora (VTM) Matka-apuraha tutkijavierailuun 3 700 €", discipline="tiede"),))
    validate_run(run_a)
    validate_run(run_b)
    out = tmp_path / "out"
    summary = combine([run_a, run_b], out)
    with open(out / "combined.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert set(rows[0].keys()) >= {"foundation", "recipient_name", "recipient_type", "amount", "currency", "year",
                                   "project_title", "project_description", "discipline", "source_url", "confidence"}
    assert len(json.loads((out / "combined.json").read_text())) == 2
    with open(out / "needs_review.csv", newline="") as f:
        review = list(csv.DictReader(f))
    assert len(review) == 1 and review[0]["review_reasons"]
    s = json.loads((out / "summary.json").read_text())
    assert s["rows"] == 2 and s["needs_review"] == 1
    assert s["by_foundation"]["Samuel Huberin taidesäätiö"]["rows"] == 1
    assert s["by_year"]["2026"]["rows"] == 2
    assert "esitystaide" in s["discipline_by_year"]["2026"]
    assert summary == s
