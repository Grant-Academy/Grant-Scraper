"""Measure extracted rows against Grant Academy's ground truth: recipient+year recall/precision and amount accuracy."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path

from .normalize import parse_amount

_TITLES = {"fm", "ft", "fil", "yo", "tam", "tat", "dos", "ma", "mag", "ktm", "vtm", "vtt", "ytm", "ytt", "ttm", "tkt", "di",
           "fl", "fd", "fk", "phd", "dr", "prof", "tohtori", "maisteri", "kandidaatti", "taiteen", "filosofian"}

_GUESS = {
    "name": ("recipient_name", "name", "recipient", "saaja", "nimi", "hakija", "grantee", "mottagare"),
    "year": ("year", "vuosi", "år", "award_year"),
    "amount": ("amount", "summa", "euros", "eur", "amount_eur", "belopp", "myönnetty"),
}


def name_key(name: str) -> tuple[str, ...]:
    """Order-, case-, punctuation- and title-insensitive key: 'Fabritius, Noora' == 'Noora Fabritius'."""
    n = unicodedata.normalize("NFC", name or "").lower()
    n = re.sub(r"\([^)]*\)", " ", n)                 # drop '(Valtiotieteiden maisteri)'
    toks = re.findall(r"[\wåäöéü-]+", n)
    toks = [t for t in toks if t.strip("-") and t not in _TITLES and t != "ja"]
    return tuple(sorted(toks))


def _to_int_amount(v) -> int | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return int(v)
    amt, _ = parse_amount(str(v) if "€" in str(v) or "eur" in str(v).lower() else f"{v} €")
    return int(amt) if amt is not None else None


def _to_year(v) -> int | None:
    m = re.search(r"(19|20)\d{2}", str(v or ""))
    return int(m.group(0)) if m else None


def load_truth(path: Path, mapping: dict[str, str] | None = None, filters: dict[str, str] | None = None) -> list[dict]:
    """Load CSV or JSON ground truth into [{'name','year','amount'}]. `mapping` maps our field -> their column."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        records = data if isinstance(data, list) else data.get("rows") or data.get("awards") or []
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            records = list(csv.DictReader(f))
    if not records:
        return []
    cols = list(records[0].keys())
    lower = {c.lower(): c for c in cols}
    mapping = dict(mapping or {})
    for field, guesses in _GUESS.items():
        if field not in mapping:
            mapping[field] = next((lower[g] for g in guesses if g in lower), None)
    if not mapping.get("name"):
        raise ValueError(f"cannot find a recipient-name column in {cols}; pass --map name=<column>")
    out = []
    for r in records:
        if filters and any(str(r.get(k, "")).strip() != v for k, v in filters.items()):
            continue
        out.append({"name": str(r[mapping["name"]]).strip(),
                    "year": _to_year(r.get(mapping["year"])) if mapping.get("year") else None,
                    "amount": _to_int_amount(r.get(mapping["amount"])) if mapping.get("amount") else None})
    return out


def score_against_truth(extracted: list[dict], truth: list[dict], scope_years: bool = True) -> dict:
    """Greedy one-to-one matching on (name_key, year). Amount compared on matched pairs."""
    years = {e.get("year") for e in extracted if e.get("year")}
    in_scope = [t for t in truth if not scope_years or not years or t.get("year") in years]

    pool: dict[tuple, list[dict]] = {}
    for t in in_scope:
        pool.setdefault((name_key(t["name"]), t.get("year")), []).append(t)

    matched, exact, extra = 0, 0, []
    amount_pairs = 0
    for e in extracted:
        key = (name_key(e["recipient_name"]), e.get("year"))
        cands = pool.get(key) or []
        if not cands:
            extra.append(e)
            continue
        # prefer the candidate with the same amount
        amt = _to_int_amount(e.get("amount"))
        pick = next((c for c in cands if c.get("amount") == amt), cands[0])
        cands.remove(pick)
        matched += 1
        if pick.get("amount") is not None:
            amount_pairs += 1
            if pick["amount"] == amt:
                exact += 1
    missed = [t for lst in pool.values() for t in lst]
    n_ext, n_tru = len(extracted), len(in_scope)
    return {
        "extracted": n_ext,
        "truth_in_scope": n_tru,
        "matched_recipient_year": matched,
        "matched_exact": exact,
        "precision": round(matched / n_ext, 3) if n_ext else 0.0,
        "recall": round(matched / n_tru, 3) if n_tru else 0.0,
        "amount_accuracy": round(exact / amount_pairs, 3) if amount_pairs else None,
        "missed": missed,
        "extra": extra,
    }
