from grantscrape.schema import RawRow
from grantscrape.score import score_row

CHUNK = (
    "# 2026 {#2026}\n\n**Laura Rämä** – € 3.500 – esitystaide, musiikki, teatteri\n\n"
    "* Syntipukki\n* Syntipukki on seremoniallinen tapahtuma ja esitys\n* Esityksen valmistamiseen\n\n"
    "**Oblivia & KlangLab** – € 4.000 – esitystaide\n\n* Dreaming Turtles\n"
)


def _row(**kw):
    base = dict(
        recipient_name="Laura Rämä", recipient_raw="Laura Rämä", recipient_type="person",
        amount=3500, amount_raw="€ 3.500", currency="EUR", year=2026,
        project_title="Syntipukki", project_description="Syntipukki on seremoniallinen tapahtuma ja esitys",
        purpose="Esityksen valmistamiseen", discipline="esitystaide, musiikki, teatteri",
        evidence="**Laura Rämä** – € 3.500 – esitystaide, musiikki, teatteri", confidence=0.95,
    )
    base.update(kw)
    return RawRow(**base)


def test_fully_grounded_row_scores_one():
    s = score_row(_row(), CHUNK, year_hint=2026)
    assert s.rule_score == 1.0
    assert s.reasons == []
    assert s.grounding_failed is False


def test_evidence_not_in_chunk_is_grounding_failure():
    s = score_row(_row(evidence="**Laura Rämä** – € 9.999"), CHUNK, year_hint=2026)
    assert s.grounding_failed is True
    assert s.rule_score == 0.5
    assert any("evidence" in r for r in s.reasons)


def test_evidence_matching_ignores_whitespace_differences():
    s = score_row(_row(evidence="**Laura Rämä**  –\n€ 3.500 – esitystaide, musiikki, teatteri"), CHUNK, year_hint=2026)
    assert s.grounding_failed is False


def test_recipient_raw_missing_from_chunk():
    s = score_row(_row(recipient_raw="Laura Rämälä"), CHUNK, year_hint=2026)
    assert s.rule_score == 0.7
    assert any("recipient" in r for r in s.reasons)


def test_amount_raw_missing_from_chunk():
    s = score_row(_row(amount_raw="€ 3.600"), CHUNK, year_hint=2026)
    assert s.rule_score == 0.7


def test_amount_missing_while_chunk_has_amounts():
    s = score_row(_row(amount=None, amount_raw=None, currency=None), CHUNK, year_hint=2026)
    assert s.rule_score == 0.8
    assert any("amount" in r for r in s.reasons)


def test_amount_missing_when_chunk_has_no_amounts_is_fine():
    chunk = "# 2024\n\n**Anna** – kirjallisuus\n"
    s = score_row(_row(amount=None, amount_raw=None, currency=None, recipient_name="Anna", recipient_raw="Anna", evidence="**Anna** – kirjallisuus", year=2024), chunk, year_hint=2024)
    assert s.rule_score == 1.0


def test_year_outside_hint_is_penalised():
    s = score_row(_row(year=2019), CHUNK, year_hint=2026)
    assert s.rule_score == 0.7
    assert any("year" in r for r in s.reasons)


def test_year_missing_is_penalised():
    s = score_row(_row(year=None), CHUNK, year_hint=2026)
    assert s.rule_score == 0.7


def test_recipient_type_disagreement_with_heuristic():
    s = score_row(_row(recipient_name="Oblivia & KlangLab", recipient_raw="Oblivia & KlangLab", recipient_type="person",
                       amount=4000, amount_raw="€ 4.000", evidence="**Oblivia & KlangLab** – € 4.000 – esitystaide",
                       project_title="Dreaming Turtles", project_description=None, purpose=None, discipline="esitystaide"), CHUNK, year_hint=2026)
    assert s.rule_score == 0.85
    assert any("recipient_type" in r for r in s.reasons)


def test_implausible_amount_is_penalised():
    s = score_row(_row(amount=12, amount_raw="€ 3.500"), CHUNK, year_hint=2026)
    assert s.rule_score == 0.7


def test_penalties_accumulate_and_floor_at_zero():
    s = score_row(_row(evidence="nope", recipient_raw="nope", amount_raw="nope", year=None, amount=1), CHUNK, year_hint=2026)
    assert s.rule_score == 0.0
