"""Collect rows/*.json for a run, validate, score, dedupe and split into rows / needs_review."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import ValidationError

from .normalize import squash_ws
from .schema import Award, RawExtraction
from .score import REVIEW_THRESHOLD, SERIOUS_RULE_FLOOR, score_row


@dataclass
class ValidationResult:
    rows: list[Award] = field(default_factory=list)
    needs_review: list[Award] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    chunks_missing: list[str] = field(default_factory=list)
    duplicates_dropped: int = 0
    chunk_notes: dict[str, str] = field(default_factory=dict)


def load_run_meta(run_dir: Path) -> dict:
    p = run_dir / "run.json"
    meta = json.loads(p.read_text()) if p.exists() else {}
    if not meta.get("foundation"):
        manifest = load_manifest(run_dir)
        host = urlsplit(manifest[0]["source_url"]).netloc if manifest else run_dir.name
        meta.setdefault("foundation", host.removeprefix("www."))
        meta.setdefault("foundation_url", f"https://{host}/" if host else None)
    return meta


def load_manifest(run_dir: Path) -> list[dict]:
    p = run_dir / "chunks" / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else []


def _dedupe_key(a: Award) -> tuple:
    """Same recipient, year, amount, title, discipline and programme = the same award extracted twice.
    Discipline and programme matter: one person can get equal grants in two categories of the same list."""
    return (squash_ws(a.recipient_name).lower(), a.year, a.amount, squash_ws(a.project_title or "").lower(),
            squash_ws(a.discipline or "").lower(), squash_ws(a.program or "").lower())


def validate_run(run_dir: Path) -> ValidationResult:
    run_dir = Path(run_dir)
    meta = load_run_meta(run_dir)
    manifest = {m["id"]: m for m in load_manifest(run_dir)}
    result = ValidationResult()
    seen: set[tuple] = set()
    rows_dir = run_dir / "rows"

    # Parse every rows file first so malformed or stray files are always reported.
    parsed: dict[str, RawExtraction] = {}
    for rows_file in sorted(rows_dir.glob("*.json")) if rows_dir.exists() else []:
        try:
            parsed[rows_file.stem] = RawExtraction.model_validate_json(rows_file.read_text())
        except (ValidationError, ValueError) as e:
            result.errors.append(f"{rows_file.name}: {str(e).splitlines()[0]}")
            continue
        if rows_file.stem not in manifest:
            result.errors.append(f"{rows_file.name}: no chunk with this id in manifest")

    for chunk_id, m in manifest.items():
        extraction = parsed.get(chunk_id)
        if extraction is None:
            if not (rows_dir / f"{chunk_id}.json").exists():
                result.chunks_missing.append(chunk_id)
            continue
        if extraction.chunk_notes:
            result.chunk_notes[chunk_id] = extraction.chunk_notes
        chunk_text = (run_dir / "chunks" / m["file"]).read_text()

        for raw in extraction.rows:
            s = score_row(raw, chunk_text, m.get("year_hint"))
            reasons = list(s.reasons)
            if raw.confidence < REVIEW_THRESHOLD:
                reasons.append(f"agent confidence {raw.confidence:.2f} below {REVIEW_THRESHOLD:.2f}" + (f": {raw.notes}" if raw.notes else ""))
            award = Award(
                foundation=meta["foundation"],
                foundation_url=meta.get("foundation_url"),
                **raw.model_dump(exclude={"confidence"}),
                source_url=m.get("anchor_url") or m["source_url"],
                confidence=round(min(raw.confidence, s.rule_score), 2),
                agent_confidence=raw.confidence,
                rule_score=s.rule_score,
                review_reasons=reasons,
                chunk_id=chunk_id,
                run_id=run_dir.name,
            )
            key = _dedupe_key(award)
            if key in seen:
                result.duplicates_dropped += 1
                continue
            seen.add(key)
            # Review when: grounding failed, the extractor was unsure, or any single serious rule fired (0.3 penalty).
            if s.grounding_failed or award.confidence < REVIEW_THRESHOLD or s.rule_score < SERIOUS_RULE_FLOOR:
                result.needs_review.append(award)
            else:
                result.rows.append(award)

    out = run_dir / "out"
    out.mkdir(exist_ok=True)
    (out / "rows.json").write_text(json.dumps([a.model_dump() for a in result.rows], ensure_ascii=False, indent=1))
    (out / "needs_review.json").write_text(json.dumps([a.model_dump() for a in result.needs_review], ensure_ascii=False, indent=1))
    stats = {
        "run_id": run_dir.name,
        "foundation": meta["foundation"],
        "chunks": len(manifest),
        "chunks_extracted": len(manifest) - len(result.chunks_missing),
        "chunks_missing": result.chunks_missing,
        "rows": len(result.rows),
        "needs_review": len(result.needs_review),
        "duplicates_dropped": result.duplicates_dropped,
        "errors": result.errors,
        "chunk_notes": result.chunk_notes,
    }
    (out / "run.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    return result
