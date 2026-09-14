#!/usr/bin/env python3
"""Score a prototype's output against Grant Academy ground truth.

Usage:
    python3 eval/score.py --pred out/skr.csv --funder skr [--year 2025] [--json]
    python3 eval/score.py --pred out/rows.jsonl --funder taike --gt data/ground-truth/awards.jsonl

--pred      CSV, JSON array, or JSONL. Needs at least recipient_name and
            award_year; amount, project_title, project_description,
            confidence and needs_review are scored when present.
--funder    foundation_slug in the ground truth (see data/ground-truth/coverage.json).
--year      restrict both sides to one award year.
--gt        path to awards.jsonl (default data/ground-truth/awards.jsonl).

A ground-truth row and a predicted row match when their normalised recipient
names are equal (case, diacritics, punctuation and word order ignored) and
the award year is the same. Standard library only.
"""
import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


def normalise(value):
    if value is None:
        return ""
    s = unicodedata.normalize("NFKD", str(value))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(sorted(s.split()))


def load_rows(path):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".csv":
        return list(csv.DictReader(text.splitlines()))
    stripped = text.strip()
    if stripped.startswith("["):
        return json.loads(stripped)
    return [json.loads(line) for line in stripped.splitlines() if line.strip()]


def to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def to_amount(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("€", "").replace("euroa", "").strip()
    s = re.sub(r"[\s.](?=\d{3}\b)", "", s).replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y", "t")


def key(row):
    return (normalise(row.get("recipient_name")), to_int(row.get("award_year")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--funder", required=True)
    ap.add_argument("--year", type=int)
    ap.add_argument("--gt", default="data/ground-truth/awards.jsonl")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    a = ap.parse_args()

    gt = [r for r in load_rows(a.gt) if r.get("foundation_slug") == a.funder]
    if a.year:
        gt = [r for r in gt if to_int(r.get("award_year")) == a.year]
    if not gt:
        sys.exit(f"no ground truth for funder {a.funder!r}; see data/ground-truth/coverage.json")

    pred = load_rows(a.pred)
    if a.year:
        pred = [r for r in pred if to_int(r.get("award_year")) == a.year]

    gt_by = defaultdict(list)
    for r in gt:
        gt_by[key(r)].append(r)

    matched, unmatched_pred = [], []
    seen = set()
    for p in pred:
        k = key(p)
        if k in gt_by and k not in seen:
            seen.add(k)
            matched.append((p, gt_by[k][0]))
        elif k in gt_by:
            matched.append((p, gt_by[k][0]))  # duplicate prediction of a real row
        else:
            unmatched_pred.append(p)
    missed = [r for k, rows in gt_by.items() if k not in seen for r in rows]

    tp = len(seen)
    precision = tp / len(pred) if pred else 0.0
    recall = tp / len(gt_by) if gt_by else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    amount_pairs = [(to_amount(p.get("amount")), to_amount(g.get("amount"))) for p, g in matched if g.get("amount") is not None]
    amount_exact = sum(1 for pa, ga in amount_pairs if pa is not None and abs(pa - ga) < 1)
    amount_missing = sum(1 for pa, _ in amount_pairs if pa is None)

    def text_recall(field):
        have = [(p, g) for p, g in matched if g.get(field)]
        got = sum(1 for p, _ in have if p.get(field))
        return got, len(have)

    title_got, title_have = text_recall("project_title")
    desc_got, desc_have = text_recall("project_description")

    conf_tp = [float(p["confidence"]) for p, _ in matched if p.get("confidence") not in (None, "")]
    conf_fp = [float(p["confidence"]) for p in unmatched_pred if p.get("confidence") not in (None, "")]
    has_review = any("needs_review" in p for p in pred)
    clean = [p for p in pred if has_review and not truthy(p.get("needs_review"))]
    clean_tp = sum(1 for p in clean if key(p) in gt_by)

    summary = {
        "funder": a.funder,
        "year": a.year,
        "ground_truth_rows": len(gt_by),
        "predicted_rows": len(pred),
        "matched": tp,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "amount": {
            "scored": len(amount_pairs),
            "exact": amount_exact,
            "missing_in_prediction": amount_missing,
            "wrong": len(amount_pairs) - amount_exact - amount_missing,
        },
        "project_title": {"ground_truth_has": title_have, "prediction_has": title_got},
        "project_description": {"ground_truth_has": desc_have, "prediction_has": desc_got},
        "confidence": {
            "mean_on_correct_rows": round(sum(conf_tp) / len(conf_tp), 3) if conf_tp else None,
            "mean_on_wrong_rows": round(sum(conf_fp) / len(conf_fp), 3) if conf_fp else None,
        },
        "needs_review": {
            "flagged": len(pred) - len(clean) if has_review else None,
            "precision_of_unflagged": round(clean_tp / len(clean), 3) if clean else None,
        },
        "examples": {
            "missed": [{"recipient_name": r.get("recipient_name"), "award_year": r.get("award_year"), "source_url": r.get("source_url")} for r in missed[:5]],
            "not_in_ground_truth": [{"recipient_name": r.get("recipient_name"), "award_year": r.get("award_year")} for r in unmatched_pred[:5]],
        },
    }

    if a.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    print(f"{a.funder}{f' / {a.year}' if a.year else ''}: ground truth {len(gt_by)} rows, predicted {len(pred)}, matched {tp}")
    print(f"  precision {precision:.1%}   recall {recall:.1%}   F1 {f1:.1%}")
    if amount_pairs:
        print(f"  amounts: {amount_exact}/{len(amount_pairs)} exact, {amount_missing} missing, {summary['amount']['wrong']} wrong")
    if title_have:
        print(f"  project_title present: {title_got}/{title_have} of the rows where the funder publishes one")
    if desc_have:
        print(f"  project_description present: {desc_got}/{desc_have}")
    if conf_tp or conf_fp:
        print(f"  confidence: mean {summary['confidence']['mean_on_correct_rows']} on correct rows, {summary['confidence']['mean_on_wrong_rows']} on wrong rows")
    if has_review:
        print(f"  needs_review: {summary['needs_review']['flagged']} flagged; precision of the unflagged rows {summary['needs_review']['precision_of_unflagged']}")
    if missed:
        print("  missed (first 5):")
        for r in missed[:5]:
            print(f"    - {r.get('recipient_name')} ({r.get('award_year')})  {r.get('source_url')}")
    if unmatched_pred:
        print("  not in ground truth (first 5) — either a real find we lack, or an invented row:")
        for r in unmatched_pred[:5]:
            print(f"    - {r.get('recipient_name')} ({r.get('award_year')})")


if __name__ == "__main__":
    main()
