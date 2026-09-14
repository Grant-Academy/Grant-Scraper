import json

from grantscrape.ground_truth import load_truth, name_key, score_against_truth


def test_name_key_ignores_order_punctuation_case_and_titles():
    assert name_key("Fabritius, Noora") == name_key("Noora Fabritius")
    assert name_key("FM Hanna-Leena Puolakka") == name_key("Hanna-Leena Puolakka")
    assert name_key("VATANEN SANNA") == name_key("Sanna Vatanen")


def test_load_truth_csv_with_column_mapping(tmp_path):
    p = tmp_path / "truth.csv"
    p.write_text("saaja,vuosi,summa,url\nNoora Fabritius,2025,3700,https://x\nSaila Heinikoski,2025,\"10 000 €\",https://x\n")
    rows = load_truth(p, {"name": "saaja", "year": "vuosi", "amount": "summa"})
    assert rows == [{"name": "Noora Fabritius", "year": 2025, "amount": 3700},
                    {"name": "Saila Heinikoski", "year": 2025, "amount": 10000}]


def test_load_truth_json_guesses_common_columns(tmp_path):
    p = tmp_path / "truth.json"
    p.write_text(json.dumps([{"recipient_name": "A B", "year": 2024, "amount": 500}]))
    assert load_truth(p) == [{"name": "A B", "year": 2024, "amount": 500}]


def test_score_counts_exact_matches_amount_mismatches_misses_and_extras():
    extracted = [
        {"recipient_name": "Noora Fabritius", "year": 2025, "amount": 3700},   # exact
        {"recipient_name": "Saila Heinikoski", "year": 2025, "amount": 1000},  # name+year match, amount wrong
        {"recipient_name": "Keksitty Henkilö", "year": 2025, "amount": 999},   # extra
    ]
    truth = [
        {"name": "Fabritius, Noora", "year": 2025, "amount": 3700},
        {"name": "Heinikoski, Saila", "year": 2025, "amount": 10000},
        {"name": "Kasa, Tuija", "year": 2025, "amount": 26000},                # missed
        {"name": "Vanha Saaja", "year": 2010, "amount": 100},                   # out of scope year
    ]
    s = score_against_truth(extracted, truth)
    assert s["truth_in_scope"] == 3
    assert s["matched_recipient_year"] == 2
    assert s["matched_exact"] == 1
    assert s["amount_accuracy"] == 0.5
    assert s["recall"] == round(2 / 3, 3)
    assert s["precision"] == round(2 / 3, 3)
    assert [m["name"] for m in s["missed"]] == ["Kasa, Tuija"]
    assert [e["recipient_name"] for e in s["extra"]] == ["Keksitty Henkilö"]
