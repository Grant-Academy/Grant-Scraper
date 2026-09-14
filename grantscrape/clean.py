"""HTML -> main-content markdown, keeping heading ids as `{#id}` anchors."""

from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup, Comment
from markdownify import MarkdownConverter

_DROP_TAGS = ("script", "style", "noscript", "nav", "header", "footer", "aside", "form", "iframe", "svg", "button")
_DROP_ROLES = ("navigation", "banner", "contentinfo", "search", "menu")


class _Converter(MarkdownConverter):
    """markdownify with ATX headings, '*' bullets and anchor suffixes on headings that carry an id."""

    def convert_hN(self, n, el, text, parent_tags):  # type: ignore[override]
        text = re.sub(r"(\*\*|__|\*|_)(.+?)\1", r"\2", text).strip()
        if not text:
            return ""
        hid = el.get("id")
        if hid:
            text = f"{text} {{#{hid}}}"
        return f"\n\n{'#' * n} {text}\n\n"

    def convert_h1(self, el, text, parent_tags):
        return self.convert_hN(1, el, text, parent_tags)

    def convert_h2(self, el, text, parent_tags):
        return self.convert_hN(2, el, text, parent_tags)

    def convert_h3(self, el, text, parent_tags):
        return self.convert_hN(3, el, text, parent_tags)

    def convert_h4(self, el, text, parent_tags):
        return self.convert_hN(4, el, text, parent_tags)

    def convert_h5(self, el, text, parent_tags):
        return self.convert_hN(5, el, text, parent_tags)

    def convert_h6(self, el, text, parent_tags):
        return self.convert_hN(6, el, text, parent_tags)


def select_main(soup: BeautifulSoup):
    """Pick the main content container: <main>, else <article>, else the body."""
    for selector in ("main", "article", "[role=main]", "#content", "#main", ".entry-content", ".content"):
        node = soup.select_one(selector)
        if node and len(node.get_text(strip=True)) > 200:
            return node
    return soup.body or soup


def html_to_markdown(raw: bytes | str) -> str:
    soup = BeautifulSoup(raw, "lxml")
    for tag in soup.find_all(_DROP_TAGS):
        tag.decompose()
    for tag in soup.find_all(attrs={"role": _DROP_ROLES}):
        tag.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    main = select_main(soup)
    md = _Converter(heading_style="ATX", bullets="*", strip=["img"]).convert_soup(main)
    md = unicodedata.normalize("NFC", md)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"
