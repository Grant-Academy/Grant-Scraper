import httpx

from grantscrape.discover import discover, score_link

SITE = {
    "https://s.fi/robots.txt": ("text/plain", "User-agent: *\nDisallow: /wp-admin/\nDisallow: /salainen/\nSitemap: https://s.fi/wp-sitemap.xml\n"),
    "https://s.fi/": ("text/html", """<html><body><nav>
        <a href="/haku/">Hae apurahaa</a>
        <a href="/myonnetyt-apurahat/">Myönnetyt apurahat</a>
        <a href="/yhteystiedot/">Yhteystiedot</a>
        <a href="/salainen/myonnetyt/">Myönnetyt (salainen)</a>
        <a href="https://other.fi/myonnetyt/">External</a>
        <a href="/files/Myonnetyt-apurahat-2024.pdf">Vuoden 2024 saajat (PDF)</a>
        </nav></body></html>"""),
    "https://s.fi/wp-sitemap.xml": ("application/xml", """<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <sitemap><loc>https://s.fi/wp-sitemap-posts-page-1.xml</loc></sitemap></sitemapindex>"""),
    "https://s.fi/wp-sitemap-posts-page-1.xml": ("application/xml", """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://s.fi/arkisto/</loc></url><url><loc>https://s.fi/yhteystiedot/</loc></url></urlset>"""),
    "https://s.fi/myonnetyt-apurahat/": ("text/html", "<main><h1>2026</h1><p><b>A</b> – € 3.500</p><p><b>B</b> – € 2.000</p><p><b>C</b> – 1 000 €</p></main>"),
    "https://s.fi/arkisto/": ("text/html", "<main><h1>2025</h1>" + "".join(f"<p><b>P{i}</b> – € 1.000</p>" for i in range(30)) + "</main>"),
    "https://s.fi/haku/": ("text/html", "<main>Hakuaika päättyy.</main>"),
    "https://s.fi/yhteystiedot/": ("text/html", "<main>Puh 123</main>"),
}


def _transport():
    def handler(request: httpx.Request):
        url = str(request.url)
        if url in SITE:
            ctype, body = SITE[url]
            return httpx.Response(200, headers={"content-type": ctype}, content=body.encode())
        if url.endswith(".pdf"):
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.4")
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def test_score_link_rewards_award_words_and_penalises_application_pages():
    assert score_link("https://s.fi/myonnetyt-apurahat/", "Myönnetyt apurahat") > score_link("https://s.fi/apurahat/", "Apurahat")
    assert score_link("https://s.fi/haku/", "Hae apurahaa") < score_link("https://s.fi/apurahat/", "Apurahat")
    assert score_link("https://s.fi/yhteystiedot/", "Yhteystiedot") <= 0


def test_discover_ranks_award_pages_first_and_respects_robots():
    result = discover("https://s.fi/", transport=_transport(), probe=4)
    urls = [c["url"] for c in result["candidates"]]
    assert {"https://s.fi/arkisto/", "https://s.fi/myonnetyt-apurahat/"} <= set(urls[:3])
    assert urls.index("https://s.fi/arkisto/") < urls.index("https://s.fi/haku/") if "https://s.fi/haku/" in urls else True
    assert "https://s.fi/salainen/myonnetyt/" not in urls
    assert not any("other.fi" in u for u in urls)
    assert "https://s.fi/files/Myonnetyt-apurahat-2024.pdf" in urls


def test_discover_probe_counts_amounts_on_candidate_pages():
    result = discover("https://s.fi/", transport=_transport(), probe=4)
    by_url = {c["url"]: c for c in result["candidates"]}
    assert by_url["https://s.fi/arkisto/"]["amounts_on_page"] == 30
    assert by_url["https://s.fi/myonnetyt-apurahat/"]["amounts_on_page"] == 3
    assert by_url["https://s.fi/files/Myonnetyt-apurahat-2024.pdf"]["kind"] == "pdf"


def test_discover_uses_sitemap_urls():
    result = discover("https://s.fi/", transport=_transport(), probe=0)
    assert any(c["url"] == "https://s.fi/arkisto/" and "sitemap" in c["found_via"] for c in result["candidates"])
