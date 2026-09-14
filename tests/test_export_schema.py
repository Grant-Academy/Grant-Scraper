"""The exported rows must validate against the organiser's production schema (schema/award.schema.json)."""
import json
from pathlib import Path

import jsonschema

from grantscrape.export import combine
from grantscrape.merge import validate_run
from tests.test_merge_export import _make_run, GOOD, SHAKY

SCHEMA = json.loads((Path(__file__).parent.parent / "schema" / "award.schema.json").read_text())


def test_every_exported_row_validates_against_award_schema(tmp_path):
    run = _make_run(tmp_path, "huber")
    validate_run(run)
    combine([run], tmp_path / "out")
    rows = [json.loads(l) for l in (tmp_path / "out" / "awards.jsonl").read_text().splitlines()]
    assert len(rows) == 2
    for r in rows:
        jsonschema.validate(r, SCHEMA)


def test_export_maps_types_flags_and_provenance(tmp_path):
    run = _make_run(tmp_path, "huber")
    validate_run(run)
    combine([run], tmp_path / "out")
    rows = {r["recipient_name"]: r for r in map(json.loads, (tmp_path / "out" / "awards.jsonl").read_text().splitlines())}
    laura, group = rows["Laura Rämä"], rows["Oblivia & KlangLab"]
    assert laura["recipient_type"] == "individual" and laura["needs_review"] is False and laura["review_reason"] is None
    assert laura["foundation_slug"] == "huber" and laura["program_slug"] == "general" and laura["award_year"] == 2026
    assert laura["scan_metadata"]["source_quote"] == GOOD["evidence"]
    assert laura["source_url"] == "https://h.fi/list#2026"
    assert group["needs_review"] is True and "0.50" in group["review_reason"]


def test_purpose_fills_description_when_the_funder_gives_no_description(tmp_path):
    row = dict(GOOD, project_description=None, purpose="Esityksen valmistamiseen")
    run = _make_run(tmp_path, "huber", rows=(row,))
    validate_run(run)
    combine([run], tmp_path / "out")
    r = json.loads((tmp_path / "out" / "awards.jsonl").read_text().splitlines()[0])
    assert r["project_description"] == "Esityksen valmistamiseen"


def test_program_is_slugified(tmp_path):
    row = dict(GOOD, program="Teemahaku 2025: Oikeus ja politiikka")
    run = _make_run(tmp_path, "huber", rows=(row,))
    validate_run(run)
    combine([run], tmp_path / "out")
    r = json.loads((tmp_path / "out" / "awards.jsonl").read_text().splitlines()[0])
    assert r["program_slug"] == "teemahaku-2025-oikeus-ja-politiikka"


def test_production_type_values_are_accepted_from_the_extractor(tmp_path):
    row = dict(GOOD, recipient_type="individual")
    run = _make_run(tmp_path, "huber", rows=(row,))
    res = validate_run(run)
    assert res.rows[0].recipient_type == "person"
