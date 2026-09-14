"""Headless extraction backend: same prompt as the Claude Code skill, sent to an LLM per chunk.

Backends:
  anthropic   Claude via the official Anthropic SDK (default model claude-opus-5, server-side refusal fallback on).
  openrouter  OpenAI-compatible, https://openrouter.ai/api/v1, key from OPENROUTER_API_KEY.
  ollama      OpenAI-compatible, http://localhost:11434/v1 (local models).
  lmstudio    OpenAI-compatible, http://localhost:1234/v1 (local models).
  openai      Any OpenAI-compatible endpoint: --base-url or GRANTSCRAPE_API_BASE, key GRANTSCRAPE_API_KEY.
"""

from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib import resources
from pathlib import Path

from pydantic import ValidationError

from .merge import load_manifest
from .schema import RawExtraction

PRESETS = {
    "anthropic": {"base_url": None, "key_env": "ANTHROPIC_API_KEY", "model": "claude-opus-5"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY", "model": "anthropic/claude-opus-5"},
    "ollama": {"base_url": "http://localhost:11434/v1", "key_env": None, "model": None},
    "lmstudio": {"base_url": "http://localhost:1234/v1", "key_env": None, "model": None},
    "openai": {"base_url": None, "key_env": "GRANTSCRAPE_API_KEY", "model": None},
}


def load_prompt() -> str:
    return resources.files("grantscrape").joinpath("prompts/extraction.md").read_text(encoding="utf-8")


def resolve_backend_config(backend: str, model: str | None = None, base_url: str | None = None, api_key: str | None = None) -> dict:
    if backend not in PRESETS:
        raise ValueError(f"unknown backend {backend!r}; choose one of {', '.join(PRESETS)}")
    p = PRESETS[backend]
    return {
        "backend": backend,
        "base_url": base_url or os.environ.get("GRANTSCRAPE_API_BASE") if backend == "openai" else (base_url or p["base_url"]),
        "api_key": api_key or (os.environ.get(p["key_env"]) if p["key_env"] else None) or os.environ.get("GRANTSCRAPE_API_KEY"),
        "model": model or os.environ.get("GRANTSCRAPE_MODEL") or p["model"],
    }


class AnthropicBackend:
    """Claude through the official SDK. Opus 5 thinks adaptively by default; a refusal falls back to Opus 4.8 server-side."""

    name = "anthropic"

    def __init__(self, model: str = "claude-opus-5", api_key: str | None = None):
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model

    def complete(self, system: str, user: str) -> str:
        kwargs = dict(
            model=self.model,
            max_tokens=16000,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],  # same rules every chunk -> cached
            messages=[{"role": "user", "content": user}],
        )
        if self.model in ("claude-opus-5", "claude-fable-5-1"):
            kwargs.update(betas=["server-side-fallback-2026-06-01"], fallbacks=[{"model": "claude-opus-4-8"}])
            response = self.client.beta.messages.create(**kwargs)
        else:
            response = self.client.messages.create(**kwargs)
        if response.stop_reason == "refusal":
            raise RuntimeError(f"model declined this chunk (request {response._request_id})")
        return "".join(b.text for b in response.content if b.type == "text")


class OpenAICompatBackend:
    """OpenRouter, Ollama, LM Studio, vLLM... anything speaking the OpenAI chat-completions API."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None, name: str = "openai"):
        from openai import OpenAI

        if not base_url:
            raise ValueError("an OpenAI-compatible backend needs --base-url or GRANTSCRAPE_API_BASE")
        if not model:
            raise ValueError("pass --model (e.g. qwen3:14b for Ollama) or set GRANTSCRAPE_MODEL")
        self.client = OpenAI(base_url=base_url, api_key=api_key or "not-needed")
        self.model = model
        self.name = name
        self._json_mode = True

    def complete(self, system: str, user: str) -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        if self._json_mode:
            try:
                r = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0,
                                                        response_format={"type": "json_object"})
                return r.choices[0].message.content or ""
            except Exception as e:  # some local servers reject response_format; retry without it once
                if "response_format" not in str(e) and "json" not in str(e).lower():
                    raise
                self._json_mode = False
        r = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0)
        return r.choices[0].message.content or ""


def make_backend(cfg: dict):
    if cfg["backend"] == "anthropic":
        return AnthropicBackend(model=cfg["model"], api_key=cfg["api_key"])
    return OpenAICompatBackend(base_url=cfg["base_url"], model=cfg["model"], api_key=cfg["api_key"], name=cfg["backend"])


def _user_message(chunk_id: str, chunk_text: str) -> str:
    return (f"chunk_id: {chunk_id}\n\nExtract every award in this chunk following the rules. "
            f"Reply with the JSON object only.\n\n<chunk>\n{chunk_text}\n</chunk>")


def parse_extraction(text: str, chunk_id: str) -> RawExtraction:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in reply")
    data = json.loads(t[start : end + 1])
    data["chunk_id"] = chunk_id
    return RawExtraction.model_validate(data)


def _extract_one(backend, system: str, chunk_id: str, chunk_text: str) -> RawExtraction:
    user = _user_message(chunk_id, chunk_text)
    reply = backend.complete(system, user)
    try:
        return parse_extraction(reply, chunk_id)
    except (ValueError, ValidationError) as e:
        retry = user + f"\n\nYour previous reply was not valid ({str(e).splitlines()[0]}). Reply with one JSON object matching the schema."
        return parse_extraction(backend.complete(system, retry), chunk_id)


def extract_run(run_dir: Path, backend, workers: int = 4, redo: bool = False) -> dict:
    run_dir = Path(run_dir)
    system = load_prompt()
    rows_dir = run_dir / "rows"
    rows_dir.mkdir(parents=True, exist_ok=True)
    todo = [m for m in load_manifest(run_dir) if redo or not (rows_dir / f"{m['id']}.json").exists()]
    written, failed = [], {}

    def job(m):
        text = (run_dir / "chunks" / m["file"]).read_text()
        return m["id"], _extract_one(backend, system, m["id"], text)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(job, m): m["id"] for m in todo}
        for fut in as_completed(futures):
            cid = futures[fut]
            try:
                _, ex = fut.result()
            except Exception as e:  # keep going; the failed chunk stays pending for a rerun or the skill
                failed[cid] = str(e).splitlines()[0][:200]
                continue
            (rows_dir / f"{cid}.json").write_text(ex.model_dump_json(indent=1))
            written.append(cid)
    return {"backend": getattr(backend, "name", "?"), "written": sorted(written), "failed": dict(sorted(failed.items()))}
