"""Combine validated runs into one CSV/JSON table, a needs_review CSV, and a summary."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from .schema import Award

EXPORT_COLUMNS = [
    "foundation", "foundation_url", "recipient_name", "recipient_type", "amount", "currency", "year",
    "project_title", "project_description", "purpose", "discipline", "source_url", "evidence",
    "confidence", "review_reasons", "recipient_raw", "amount_raw", "notes", "chunk_id", "run_id",
]


def to_export_row(a: Award) -> dict:
    """The ONE mapping from our Award to the output schema. Adapt here when the production schema differs."""
    d = a.model_dump()
    d["review_reasons"] = "; ".join(a.review_reasons)
    d["amount"] = int(a.amount) if a.amount is not None and float(a.amount).is_integer() else a.amount
    return {k: d.get(k) for k in EXPORT_COLUMNS}


def _load(run_dir: Path, name: str) -> list[Award]:
    p = Path(run_dir) / "out" / name
    if not p.exists():
        return []
    return [Award.model_validate(x) for x in json.loads(p.read_text())]


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS)
        w.writeheader()
        w.writerows(rows)


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

    _write_csv(out_dir / "combined.csv", [to_export_row(a) for a in rows])
    (out_dir / "combined.json").write_text(json.dumps([to_export_row(a) for a in rows], ensure_ascii=False, indent=1))
    _write_csv(out_dir / "needs_review.csv", [to_export_row(a) for a in review])
    (out_dir / "needs_review.json").write_text(json.dumps([to_export_row(a) for a in review], ensure_ascii=False, indent=1))
    summary = summarise(rows, review)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    return json.loads((out_dir / "summary.json").read_text())
