import json
from pathlib import Path

from grantscrape.cli import main

FIX = Path(__file__).parent / "fixtures"
URL = "https://www.karjalankulttuurirahasto.fi/wp-content/uploads/2024/12/Myonnetyt-apurahat-2024.pdf"


def _fetch_pdf(tmp_path):
    return main(["--runs", str(tmp_path), "fetch", "--run", "karjalan", "--from-file", str(FIX / "karjalan.pdf"),
                 "--url", URL, "--foundation", "Karjalan Kulttuurirahasto"])


def test_fetch_records_foundation_in_run_json(tmp_path):
    assert _fetch_pdf(tmp_path) == 0
    meta = json.loads((tmp_path / "karjalan" / "run.json").read_text())
    assert meta["foundation"] == "Karjalan Kulttuurirahasto"
    assert meta["foundation_url"] == "https://www.karjalankulttuurirahasto.fi/"


def test_status_lists_pending_chunks(tmp_path, capsys):
    _fetch_pdf(tmp_path)
    capsys.readouterr()
    assert main(["--runs", str(tmp_path), "status", "--run", "karjalan"]) == 0
    out = capsys.readouterr().out
    assert "pending: 000 001 002" in out


def test_validate_exit_code_signals_problems(tmp_path, capsys):
    _fetch_pdf(tmp_path)
    run = tmp_path / "karjalan"
    (run / "rows").mkdir()
    (run / "rows" / "000.json").write_text("{broken")
    assert main(["--runs", str(tmp_path), "validate", "--run", "karjalan"]) == 1
    assert "000.json" in capsys.readouterr().out


def test_validate_and_combine_happy_path(tmp_path, capsys):
    _fetch_pdf(tmp_path)
    run = tmp_path / "karjalan"
    (run / "rows").mkdir()
    row = {"recipient_name": "Mikko Hänninen", "recipient_raw": "Hänninen Mikko", "recipient_type": "person",
           "amount": 14000, "amount_raw": "14 000 €", "currency": "EUR", "year": 2024,
           "project_title": "Haittaeläimestä suojelluksi lajiksi - Saimaannorppapolitiikka 1934-1955",
           "evidence": "| 2024010 | Hänninen Mikko | Haittaeläimestä suojelluksi lajiksi - Saimaannorppapolitiikka 1934-1955 | 14 000 € |",
           "confidence": 0.95}
    (run / "rows" / "000.json").write_text(json.dumps({"chunk_id": "000", "rows": [row]}, ensure_ascii=False))
    for cid in ("001", "002"):
        (run / "rows" / f"{cid}.json").write_text(json.dumps({"chunk_id": cid, "rows": []}))
    assert main(["--runs", str(tmp_path), "validate", "--run", "karjalan"]) == 0
    out_dir = tmp_path / "combined"
    assert main(["--runs", str(tmp_path), "combine", "--out", str(out_dir)]) == 0
    rows = json.loads((out_dir / "combined.json").read_text())
    assert rows[0]["source_url"] == URL + "#page=1"
    assert rows[0]["foundation"] == "Karjalan Kulttuurirahasto"


def test_discover_command_writes_candidates_file(tmp_path, monkeypatch, capsys):
    import grantscrape.discover as d
    monkeypatch.setattr(d, "discover", lambda url, **kw: {"site": url, "robots_txt_found": True,
        "candidates": [{"url": "https://s.fi/arkisto/", "score": 9.0, "kind": "html", "text": "Arkisto", "found_via": ["homepage"], "amounts_on_page": 30}]})
    assert main(["--runs", str(tmp_path), "discover", "https://s.fi/"]) == 0
    saved = json.loads((tmp_path / "_discover" / "s.fi.json").read_text())
    assert saved["candidates"][0]["url"] == "https://s.fi/arkisto/"
    assert "https://s.fi/arkisto/" in capsys.readouterr().out


def test_score_command_reports_recall_and_writes_score_json(tmp_path, capsys):
    run = tmp_path / "linnamo" / "out"
    run.mkdir(parents=True)
    (run / "rows.json").write_text(json.dumps([{"recipient_name": "Noora Fabritius", "year": 2025, "amount": 3700}]))
    (run / "needs_review.json").write_text(json.dumps([{"recipient_name": "Saila Heinikoski", "year": 2025, "amount": 10000}]))
    truth = tmp_path / "truth.csv"
    truth.write_text("funder,saaja,vuosi,summa\nLinnamo,\"Fabritius, Noora\",2025,3700\nLinnamo,\"Heinikoski, Saila\",2025,10000\nHuber,X Y,2025,1\n")
    args = ["--runs", str(tmp_path), "score", "--run", "linnamo", "--truth", str(truth),
            "--map", "name=saaja,year=vuosi,amount=summa", "--where", "funder=Linnamo"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "recall 0.5" in out
    assert main(args + ["--include-review"]) == 0
    s = json.loads((run / "score.json").read_text())
    assert s["recall"] == 1.0 and s["truth_in_scope"] == 2
