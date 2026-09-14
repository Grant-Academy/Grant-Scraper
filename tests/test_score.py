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
    s = score_row(_row(recipient_name="Laura Rämälä", recipient_raw="Laura Rämälä"), CHUNK, year_hint=2026)
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


def test_reordered_name_is_not_flagged():
    chunk = "# 2025\n\n**Fabritius, Noora** (VTM)\n\n3 700 €\n"
    s = score_row(_row(recipient_name="Noora Fabritius", recipient_raw="Fabritius, Noora", amount=3700, amount_raw="3 700 €",
                       evidence="**Fabritius, Noora** (VTM)", year=2025), chunk, year_hint=2025)
    assert not any("rewritten" in r for r in s.reasons)


def test_name_with_tokens_absent_from_source_is_flagged_softly():
    chunk = "# 2024\n\n**Yli, Annala, Kari**\n\n5 000 €\n"
    s = score_row(_row(recipient_name="Kari Yli-Annala", recipient_raw="Yli, Annala, Kari", amount=5000, amount_raw="5 000 €",
                       evidence="**Yli, Annala, Kari**", year=2024), chunk, year_hint=2024)
    assert any("rewritten" in r for r in s.reasons)
    assert s.rule_score == 0.9


def test_type_heuristic_without_markers_does_not_penalise():
    chunk = "# 2024\n\n| 2024124 | Etelä-Karjalan arkeologian harrastajat J | Kaivaus | 500 € |\n"
    s = score_row(_row(recipient_name="Etelä-Karjalan arkeologian harrastajat J", recipient_raw="Etelä-Karjalan arkeologian harrastajat J",
                       recipient_type="organisation", amount=500, amount_raw="500 €", year=2024,
                       evidence="| 2024124 | Etelä-Karjalan arkeologian harrastajat J | Kaivaus | 500 € |"), chunk, year_hint=2024)
    assert not any("heuristic" in r for r in s.reasons)


def test_type_heuristic_with_marker_still_penalises():
    chunk = "# 2024\n\n**Teatteri Metamorfoosi ry** – € 3.000\n"
    s = score_row(_row(recipient_name="Teatteri Metamorfoosi ry", recipient_raw="Teatteri Metamorfoosi ry", recipient_type="person",
                       amount=3000, amount_raw="€ 3.000", year=2024, evidence="**Teatteri Metamorfoosi ry** – € 3.000"), chunk, year_hint=2024)
    assert any("heuristic" in r for r in s.reasons)


def _named(raw, chunk_line):
    chunk = f"# 2024\n\n{chunk_line}\n"
    return score_row(_row(recipient_name=raw, recipient_raw=raw, recipient_type="unknown", amount=500, amount_raw="500 €",
                          year=2024, evidence=chunk_line), chunk, year_hint=2024)


def test_truncated_name_ending_in_lone_letter_goes_to_review():
    s = _named("Etelä-Karjalan arkeologian harrastajat J", "| 2024124 | Etelä-Karjalan arkeologian harrastajat J | Kaivaus | 500 € |")
    assert any("malformed" in r for r in s.reasons) and s.rule_score <= 0.7


def test_comma_without_space_inside_name_is_malformed():
    s = _named("Al,Busultan, Bilal ja työryhmä", "**Al,Busultan, Bilal ja työryhmä** 500 €")
    assert any("malformed" in r for r in s.reasons)


def test_ordinary_names_are_not_malformed():
    for raw in ("Fabritius, Noora", "Hänninen Mikko", "Huuska (Snow) Tapio (Cristal)", "Oblivia & KlangLab", "J. K. Virtanen", "Yli, Annala, Kari", "2nd Generation Lynx Larynx"):
        s = _named(raw, f"**{raw}** 500 €")
        assert not any("malformed" in r for r in s.reasons), raw
