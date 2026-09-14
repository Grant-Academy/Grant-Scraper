"""Find candidate award-list pages on a foundation site: homepage links + sitemap, keyword-ranked, then probed."""

from __future__ import annotations

import os
import re
import unicodedata
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from .clean import html_to_markdown
from .normalize import find_amounts
from .robots import USER_AGENT, is_allowed

# Words that name the list of *awarded* grants (fi / sv / en), accent-folded.
_STRONG = ("myonnetyt", "myonnetty", "myonnettiin", "saajat", "saaneet", "tuensaajat", "apurahansaajat", "jaetut", "jaettu",
           "beviljade", "beviljats", "mottagare", "stipendiater", "awarded", "recipients", "grantees")
_MEDIUM = ("apuraha", "apurahat", "avustus", "avustukset", "stipendi", "stipendit", "stipendier", "palkinto", "tuki",
           "arkisto", "archive", "arkiv", "grants", "funding", "rahoitus")
_NEGATIVE = ("haku", "hae", "hakemus", "hakeminen", "hakuohje", "ohjeet", "apply", "application", "ansok", "login", "kirjaudu",
             "yhteystiedot", "contact", "kontakt", "tietosuoja", "privacy", "saavutettavuus", "feed", "wp-json", "wp-admin",
             "tag", "author", "cart", "shop")
_SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip", ".mp4", ".mp3", ".css", ".js", ".ico", ".docx", ".xlsx")
_YEAR = re.compile(r"(?<!\d)20[0-4]\d(?!\d)")


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def _tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _fold(s))


def score_link(url: str, text: str = "") -> float:
    """Keyword score for how likely a link leads to a list of awarded grants."""
    path = urlsplit(url).path
    toks = _tokens(path) + _tokens(text)
    joined = " ".join(toks)
    score = 0.0
    score += 3 * sum(1 for w in _STRONG if w in joined)
    score += 1 * sum(1 for w in _MEDIUM if w in toks or any(t.startswith(w) for t in toks))
    score -= 3 * sum(1 for w in _NEGATIVE if w in toks)
    if _YEAR.search(path) or _YEAR.search(text):
        score += 0.5
    if path.lower().endswith(".pdf"):
        score += 1
    return score


def _norm_url(u: str) -> str:
    p = urlsplit(u)
    return urlunsplit((p.scheme, p.netloc.lower(), p.path or "/", p.query, ""))


def _same_site(u: str, host: str) -> bool:
    return urlsplit(u).netloc.lower().removeprefix("www.") == host.removeprefix("www.")


def _sitemap_urls(client: httpx.Client, robots_txt: str | None, base: str, limit: int = 2000) -> list[str]:
    roots = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots_txt or "") or [urljoin(base, p) for p in ("/sitemap.xml", "/wp-sitemap.xml", "/sitemap_index.xml")]
    seen, out, queue = set(), [], list(roots)
    while queue and len(out) < limit and len(seen) < 40:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            r = client.get(sm)
        except httpx.HTTPError:
            continue
        if r.status_code != 200 or b"<" not in r.content[:200]:
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)
        if "<sitemapindex" in r.text:
            # Visit child sitemaps for pages/posts first; skip image/author/tag maps.
            kids = [l for l in locs if not re.search(r"(author|tag|category|image|user)", l)]
            queue.extend(sorted(kids, key=lambda l: 0 if re.search(r"page", l) else 1))
        else:
            out.extend(locs)
    return out[:limit]


def _tavily(host: str, name_hint: str | None) -> list[dict]:
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return []
    q = f"{name_hint or host} myönnetyt apurahat"
    try:
        r = httpx.post("https://api.tavily.com/search", json={"api_key": key, "query": q, "include_domains": [host], "max_results": 10}, timeout=30)
        r.raise_for_status()
        return [{"url": x["url"], "text": x.get("title", "")} for x in r.json().get("results", [])]
    except (httpx.HTTPError, ValueError, KeyError):
        return []


def discover(site_url: str, transport: httpx.BaseTransport | None = None, probe: int = 6, name_hint: str | None = None) -> dict:
    """Return {'site', 'candidates': [...]} ranked best-first. Each candidate: url, text, kind, score, found_via, amounts_on_page."""
    if not urlsplit(site_url).scheme:
        site_url = "https://" + site_url
    host = urlsplit(site_url).netloc.lower()
    client = httpx.Client(follow_redirects=True, timeout=20, headers={"User-Agent": USER_AGENT}, transport=transport)
    base = f"{urlsplit(site_url).scheme}://{host}/"

    robots_txt = None
    try:
        r = client.get(urljoin(base, "/robots.txt"))
        robots_txt = r.text if r.status_code == 200 else None
    except httpx.HTTPError:
        pass

    found: dict[str, dict] = {}

    def add(u: str, text: str, via: str) -> None:
        u = _norm_url(urljoin(site_url, u))
        if not u.startswith("http") or not _same_site(u, host):
            return
        if urlsplit(u).path.lower().endswith(_SKIP_EXT) or not is_allowed(u, robots_txt):
            return
        c = found.setdefault(u, {"url": u, "text": "", "found_via": [], "kind": "pdf" if u.lower().endswith(".pdf") else "html"})
        if text and len(text) > len(c["text"]):
            c["text"] = text.strip()[:120]
        if via not in c["found_via"]:
            c["found_via"].append(via)

    pages_to_scan = [site_url]
    try:
        home = client.get(site_url)
        if home.status_code == 200:
            soup = BeautifulSoup(home.content, "lxml")
            for a in soup.find_all("a", href=True):
                add(a["href"], a.get_text(" ", strip=True), "homepage")
    except httpx.HTTPError:
        pass
    for u in _sitemap_urls(client, robots_txt, base):
        add(u, "", "sitemap")
    for hit in _tavily(host, name_hint):
        add(hit["url"], hit["text"], "search")

    for c in found.values():
        c["score"] = round(score_link(c["url"], c["text"]), 2)
    ranked = sorted(found.values(), key=lambda c: -c["score"])
    ranked = [c for c in ranked if c["score"] > 0]

    # Second hop: award lists are often one level below an "apurahat" hub page. Scan links on the top hubs.
    for hub in [c for c in ranked[:3] if c["kind"] == "html"]:
        try:
            r = client.get(hub["url"])
            if r.status_code == 200:
                for a in BeautifulSoup(r.content, "lxml").find_all("a", href=True):
                    add(a["href"], a.get_text(" ", strip=True), f"linked from {urlsplit(hub['url']).path}")
        except httpx.HTTPError:
            continue
    for c in found.values():
        c["score"] = round(score_link(c["url"], c["text"]), 2)
    ranked = sorted((c for c in found.values() if c["score"] > 0), key=lambda c: -c["score"])

    # Probe: fetch top candidates and count euro amounts, the strongest deterministic signal of an award list.
    for c in ranked[:probe]:
        c["amounts_on_page"] = None
        if c["kind"] == "pdf":
            continue
        try:
            r = client.get(c["url"])
            if r.status_code == 200 and "html" in r.headers.get("content-type", "html"):
                c["amounts_on_page"] = len(find_amounts(html_to_markdown(r.content)))
                c["score"] = round(c["score"] + min(c["amounts_on_page"], 60) / 6, 2)
            else:
                c["http_status"] = r.status_code
        except httpx.HTTPError as e:
            c["error"] = str(e)[:100]
    ranked.sort(key=lambda c: -c["score"])
    return {"site": site_url, "robots_txt_found": robots_txt is not None, "candidates": ranked[:25]}
