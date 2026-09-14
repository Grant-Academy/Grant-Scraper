"""robots.txt checks. Public data should stay public: we refuse disallowed paths."""

from __future__ import annotations

from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "Mozilla/5.0 (compatible; grantscrape/0.1; +https://github.com/grant-academy) research bot"
_cache: dict[str, str | None] = {}


def robots_url(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}/robots.txt"


def fetch_robots(url: str, client: httpx.Client | None = None) -> str | None:
    """Return robots.txt text for the host of `url`, or None if unavailable. Cached per host."""
    key = urlsplit(url).netloc
    if key in _cache:
        return _cache[key]
    text: str | None = None
    try:
        c = client or httpx.Client(follow_redirects=True, timeout=15, headers={"User-Agent": USER_AGENT})
        r = c.get(robots_url(url))
        if r.status_code == 200:
            text = r.text
    except httpx.HTTPError:
        text = None
    _cache[key] = text
    return text


def is_allowed(url: str, robots_txt: str | None, agent: str = "*") -> bool:
    if not robots_txt:
        return True
    rp = RobotFileParser()
    rp.parse(robots_txt.splitlines())
    return rp.can_fetch(agent, url)
