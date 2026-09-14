"""Deterministic confidence rules. The extractor says how sure it is; these rules check it against the source."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .normalize import find_amounts, guess_recipient_type, squash_ws
from .schema import RawRow

REVIEW_THRESHOLD = 0.7        # final confidence below this -> needs_review
SERIOUS_RULE_FLOOR = 0.8      # any single 0.3 rule penalty (missing year, ungrounded amount...) -> needs_review
MIN_AMOUNT, MAX_AMOUNT = 50, 5_000_000


@dataclass
class Score:
    rule_score: float = 1.0
    reasons: list[str] = field(default_factory=list)
    grounding_failed: bool = False

    def penalise(self, amount: float, reason: str) -> None:
        self.rule_score = max(0.0, round(self.rule_score - amount, 2))
        self.reasons.append(reason)


def _in(needle: str | None, haystack_norm: str) -> bool:
    if not needle:
        return False
    return squash_ws(needle) in haystack_norm


def score_row(row: RawRow, chunk_text: str, year_hint: int | None) -> Score:
    s = Score()
    hay = squash_ws(chunk_text)

    if not _in(row.evidence, hay):
        s.grounding_failed = True
        s.penalise(0.5, "evidence not found verbatim in source chunk")

    if row.recipient_raw and not _in(row.recipient_raw, hay):
        s.penalise(0.3, "recipient_raw not found in source chunk")
    elif not row.recipient_raw and not _in(row.recipient_name, hay):
        s.penalise(0.3, "recipient_name not found in source chunk")

    if row.amount_raw and not _in(row.amount_raw, hay):
        s.penalise(0.3, "amount_raw not found in source chunk")

    if row.amount is None and find_amounts(chunk_text):
        s.penalise(0.2, "amount missing although the chunk contains euro amounts")

    if row.year is None:
        s.penalise(0.3, "year missing")
    elif year_hint is not None and row.year != year_hint:
        s.penalise(0.3, f"year {row.year} differs from section year {year_hint}")

    if row.recipient_raw:
        raw_toks = set(re.findall(r"[\w-]+", squash_ws(row.recipient_raw).lower()))
        new = [t for t in re.findall(r"[\w-]+", squash_ws(row.recipient_name).lower()) if t not in raw_toks]
        if new:
            s.penalise(0.1, f"recipient_name rewritten from source ({', '.join(new)} not in '{row.recipient_raw}'): check spelling")

    guessed = guess_recipient_type(row.recipient_name)
    if row.recipient_type != "unknown" and guessed != row.recipient_type and not (guessed == "group" and row.recipient_type == "organisation"):
        s.penalise(0.15, f"recipient_type '{row.recipient_type}' disagrees with name heuristic '{guessed}'")

    if row.amount is not None and not (MIN_AMOUNT <= row.amount <= MAX_AMOUNT):
        s.penalise(0.3, f"amount {row.amount} outside plausible range")

    return s
