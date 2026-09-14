import json
from pathlib import Path

from grantscrape.fetch import ingest_file
from grantscrape.llm_api import parse_extraction, extract_run, load_prompt, resolve_backend_config

FIX = Path(__file__).parent / "fixtures"
URL = "https://k.fi/Myonnetyt-apurahat-2024.pdf"

ROW = {"recipient_name": "Mikko Hänninen", "recipient_raw": "Hänninen Mikko", "recipient_type": "person",
       "amount": 14000, "amount_raw": "14 000 €", "currency": "EUR", "year": 2024,
       "project_title": "Haittaeläimestä suojelluksi lajiksi - Saimaannorppapolitiikka 1934-1955",
       "evidence": "| 2024010 | Hänninen Mikko |", "confidence": 0.95}


class FakeBackend:
    name = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.replies.pop(0)


def test_prompt_is_the_shared_extraction_rules():
    assert "Grant award extraction rules" in load_prompt()


def test_parse_extraction_strips_code_fences_and_sets_chunk_id():
    text = "```json\n" + json.dumps({"chunk_id": "wrong", "rows": [ROW]}, ensure_ascii=False) + "\n```"
    ex = parse_extraction(text, "007")
    assert ex.chunk_id == "007"
    assert ex.rows[0].amount == 14000


def test_extract_run_writes_rows_for_pending_chunks_only(tmp_path):
    run = tmp_path / "karjalan"
    ingest_file(run, URL, FIX / "karjalan.pdf")
    (run / "rows").mkdir()
    (run / "rows" / "002.json").write_text(json.dumps({"chunk_id": "002", "rows": []}))
    fake = FakeBackend([json.dumps({"rows": [ROW]}, ensure_ascii=False), json.dumps({"rows": []})])
    report = extract_run(run, fake, workers=1)
    assert sorted(report["written"]) == ["000", "001"]
    assert len(fake.calls) == 2
    assert "Grant award extraction rules" in fake.calls[0][0]
    assert "chunk_id: 000" in fake.calls[0][1] and "Hänninen Mikko" in fake.calls[0][1]
    saved = json.loads((run / "rows" / "000.json").read_text())
    assert saved["chunk_id"] == "000" and saved["rows"][0]["recipient_raw"] == "Hänninen Mikko"


def test_extract_run_retries_once_on_invalid_json_then_reports(tmp_path):
    run = tmp_path / "karjalan"
    ingest_file(run, URL, FIX / "karjalan.pdf")
    fake = FakeBackend(["not json", json.dumps({"rows": []}), "bad", "still bad", json.dumps({"rows": []})])
    report = extract_run(run, fake, workers=1)
    assert report["written"] == ["000", "002"]
    assert list(report["failed"]) == ["001"]
    assert "previous reply was not valid" in fake.calls[1][1]


def test_backend_presets_resolve_base_urls_and_env_keys(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    cfg = resolve_backend_config("openrouter", model="anthropic/claude-opus-5")
    assert cfg["base_url"] == "https://openrouter.ai/api/v1" and cfg["api_key"] == "or-key"
    assert resolve_backend_config("ollama", model="qwen3:14b")["base_url"] == "http://localhost:11434/v1"
    assert resolve_backend_config("anthropic")["model"] == "claude-opus-5"
