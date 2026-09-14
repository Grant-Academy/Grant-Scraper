"""Combine validated runs into one CSV/JSON table, a needs_review CSV, and a summary."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from .schema import Award

# Columns of schema/award.schema.json (Grant Academy production importer + challenge fields).
EXPORT_COLUMNS = [
    "foundation_slug", "program_slug", "award_year", "recipient_name", "recipient_type", "project_title",
    "project_description", "amount", "currency", "source_url", "discipline", "confidence", "needs_review",
    "review_reason", "scan_metadata",
]
_TYPE_OUT = {"person": "individual", "organisation": "organization", "group": "group", "unknown": None}
EXTRACTOR = "grantscrape/0.1"


def slugify(text: str | None) -> str:
    s = unicodedata.normalize("NFKD", (text or "").lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "general"


def to_export_row(a: Award, needs_review: bool) -> dict:
    """The ONE mapping from our Award to schema/award.schema.json. Audit fields live in scan_metadata."""
    description = a.project_description or a.purpose
    meta = {
        "source_quote": a.evidence,
        "extractor": f"{EXTRACTOR} ({a.extractor})" if getattr(a, "extractor", None) else EXTRACTOR,
        "foundation": a.foundation,
        "recipient_raw": a.recipient_raw,
        "amount_raw": a.amount_raw,
        "agent_confidence": a.agent_confidence,
        "rule_score": a.rule_score,
        "review_reasons": a.review_reasons,
        "notes": a.notes,
        "chunk_id": a.chunk_id,
        "run_id": a.run_id,
    }
    if a.project_description and a.purpose:
        meta["purpose"] = a.purpose
    return {
        "foundation_slug": slugify(a.run_id),
        "program_slug": slugify(a.program) if a.program else "general",
        "award_year": a.year,
        "recipient_name": a.recipient_name,
        "recipient_type": _TYPE_OUT.get(a.recipient_type),
        "project_title": a.project_title,
        "project_description": description,
        "amount": (int(a.amount) if float(a.amount).is_integer() else a.amount) if a.amount is not None else None,
        "currency": a.currency if a.amount is not None else None,
        "source_url": a.source_url,
        "discipline": a.discipline,
        "confidence": a.confidence,
        "needs_review": needs_review,
        "review_reason": "; ".join(a.review_reasons) if needs_review and a.review_reasons else None,
        "scan_metadata": {k: v for k, v in meta.items() if v not in (None, [], "")},
    }


def _flat(row: dict) -> dict:
    out = dict(row)
    out["scan_metadata"] = json.dumps(row["scan_metadata"], ensure_ascii=False)
    return out


def _load(run_dir: Path, name: str) -> list[Award]:
    p = Path(run_dir) / "out" / name
    if not p.exists():
        return []
    return [Award.model_validate(x) for x in json.loads(p.read_text())]


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS)
        w.writeheader()
        w.writerows(_flat(r) for r in rows)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def _disciplines(a: Award) -> list[str]:
    return [d.strip().lower() for d in (a.discipline or "").replace("/", ",").split(",") if d.strip()]


def summarise(rows: list[Award], review: list[Award]) -> dict:
    by_foundation: dict[str, dict] = defaultdict(lambda: {"rows": 0, "needs_review": 0, "total_amount": 0, "years": set()})
    by_year: dict[str, dict] = defaultdict(lambda: {"rows": 0, "total_amount": 0, "person": 0, "organisation": 0, "group": 0, "unknown": 0})
    disc_by_year: dict[str, Counter] = defaultdict(Counter)
    for a in rows:
        f = by_foundation[a.foundation]
        f["rows"] += 1
        f["total_amount"] += a.amount or 0
        if a.year:
            f["years"].add(a.year)
            y = by_year[str(a.year)]
            y["rows"] += 1
            y["total_amount"] += a.amount or 0
            y[a.recipient_type] += 1
            for d in _disciplines(a):
                disc_by_year[str(a.year)][d] += 1
    for a in review:
        by_foundation[a.foundation]["needs_review"] += 1
    for f in by_foundation.values():
        f["years"] = sorted(f["years"])
    return {
        "rows": len(rows),
        "needs_review": len(review),
        "by_foundation": dict(by_foundation),
        "by_year": dict(sorted(by_year.items())),
        "discipline_by_year": {y: dict(c.most_common()) for y, c in sorted(disc_by_year.items())},
    }


def combine(run_dirs: list[Path], out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[Award] = []
    review: list[Award] = []
    for rd in run_dirs:
        rows += _load(rd, "rows.json")
        review += _load(rd, "needs_review.json")
    rows.sort(key=lambda a: (a.foundation, -(a.year or 0), a.recipient_name))
    review.sort(key=lambda a: (a.foundation, -(a.year or 0), a.recipient_name))

    clean = [to_export_row(a, False) for a in rows]
    flagged = [to_export_row(a, True) for a in review]
    # awards.*: every row with its needs_review flag (the deliverable, and what eval/score.py reads).
    _write_jsonl(out_dir / "awards.jsonl", clean + flagged)
    _write_csv(out_dir / "awards.csv", clean + flagged)
    (out_dir / "awards.json").write_text(json.dumps(clean + flagged, ensure_ascii=False, indent=1))
    # table.csv: the confident rows only; needs_review.csv: the separate pile for a human.
    _write_csv(out_dir / "table.csv", clean)
    _write_csv(out_dir / "needs_review.csv", flagged)
    summary = summarise(rows, review)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    return json.loads((out_dir / "summary.json").read_text())
