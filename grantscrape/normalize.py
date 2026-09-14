"""Deterministic normalisation helpers: amounts, years, recipient type, whitespace."""

from __future__ import annotations

import re
import unicodedata

_WS_RE = re.compile(r"[\s ]+")

# A euro amount as it appears in Finnish foundation pages:
#   "€ 3.500", "3 700 €", "10,000 €", "1000€", "26 000 euroa", "1 500,00 €"
_AMOUNT_RE = re.compile(
    r"(?:€\s*(\d[\d ., ]*\d|\d))"          # euro sign before number
    r"|(?:(\d[\d ., ]*\d|\d)\s*(?:€|euroa|euro\b|eur\b))",  # number before euro word/sign
    re.IGNORECASE,
)

_YEAR_RE = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")

_ORG_TOKENS = (
    "ry", "rf", "oy", "ab", "säätiö", "stiftelse", "yhdistys", "förening",
    "teatteri", "teater", "orkesteri", "orkester", "museo", "seura", "kuoro",
    "liitto", "keskus", "yliopisto", "koulu", "opisto", "kaupunki", "kunta",
    "osuuskunta", "kollektiivi", "festivaali", "festival", "ensemble",
)
_GROUP_TOKENS = ("työryhmä", "arbetsgrupp", "ryhmä", "kollektiivi", "duo", "trio", "kvartetti")


def squash_ws(text: str | None) -> str:
    """Collapse all whitespace (incl. NBSP) to single spaces and strip."""
    if not text:
        return ""
    return _WS_RE.sub(" ", unicodedata.normalize("NFC", text)).strip()


def _digits_to_int(num: str) -> int | None:
    """Turn '3.500', '3 700', '10,000', '1 500,00', '12.500,50' into an integer euro amount."""
    s = num.replace(" ", " ").strip()
    # decimal part: a trailing ',dd' or '.dd' (exactly 2 digits) after other separators or when
    # the value has a different separator earlier.
    m = re.match(r"^(.*?)[.,](\d{2})$", s)
    if m and (re.search(r"[ .,]", m.group(1)) or len(m.group(1)) > 3):
        s = m.group(1)
    s = re.sub(r"[ .,]", "", s)
    if not s.isdigit():
        return None
    return int(s)


def parse_amount(raw: str | None) -> tuple[int | None, str | None]:
    """Parse a euro amount string. Returns (amount_int, 'EUR') or (None, None)."""
    if not raw:
        return None, None
    m = _AMOUNT_RE.search(raw)
    if not m:
        return None, None
    num = m.group(1) or m.group(2)
    value = _digits_to_int(num)
    if value is None:
        return None, None
    return value, "EUR"


def find_amounts(text: str) -> list[str]:
    """Return every euro-amount substring found in text, in order."""
    return [m.group(0).strip() for m in _AMOUNT_RE.finditer(text or "")]


def extract_year(text: str | None) -> int | None:
    """First plausible 4-digit year (1950–2049) in text, or None."""
    if not text:
        return None
    m = _YEAR_RE.search(text)
    return int(m.group(1)) if m else None


def guess_recipient_type(name: str | None) -> str:
    """Heuristic: 'organisation', 'group' or 'person' from the recipient name."""
    if not name:
        return "unknown"
    n = squash_ws(name).lower()
    tokens = re.findall(r"[a-zåäö0-9]+", n)
    if "&" in n or " ja " in f" {n} " or " och " in f" {n} ":
        return "group"
    if any(t in tokens for t in _GROUP_TOKENS) or any(n.endswith(t) for t in _GROUP_TOKENS):
        return "group"
    for tok in _ORG_TOKENS:
        if tok in tokens or any(t.endswith(tok) and len(t) > len(tok) + 2 for t in tokens):
            return "organisation"
    return "person"
