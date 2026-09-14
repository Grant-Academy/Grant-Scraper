# Annex 1 — Target funders, with their award pages checked

Grant Academy / AI Campfire 14.9.2026

Every funder below is in our database with no award history at all. Before handing you this list we opened each site and looked at what is actually published. Verified 9 September 2026 by fetching the pages (no JavaScript execution — where that mattered, it is noted).

The tiers are what we found, not what we assumed.

## Tier 1 — Verified easy: start here to get something on screen

| Funder | Award page | What is there |
|---|---|---|
| Ida Aalberg -säätiö | <https://ida-aalberg-saatio.fi/apurahat/myonnetyt-apurahat/> | Spring 2019 – autumn 2025, ~24 grants, all on one page. Name, purpose, amount (uniformly €4,000). Server is flaky over https; http worked. |
| Greta ja William Lehtisen säätiö | <https://gretajawilliamlehtinen.fi/arkisto/> | 2016–2026, ~300 entries, HTML tables grouped by year and discipline. Name, profession, amount. No project titles. Watch the Finnish thousands separator ("3.000" = 3000). |

## Tier 2 — Verified medium: prose, not tables

Everything here is published and complete enough to be worth extracting, but it is free text or split across year sections, so entities have to be parsed out rather than read from columns. This is what most of our remaining ~700 funders look like.

| Funder | Award page | What is there |
|---|---|---|
| Samuel Huberin taidesäätiö | <https://www.hubersaatio.fi/myonnetyt-apurahat/> and /arkisto/ | 2006–2026, 500+ grants. Name, amount, discipline tags, project title, 2–3 sentence description — the richest data on this list. Note: huber.apurahat.fi is the application system and returns an empty page. |
| Olga ja Vilho Linnamon Säätiö | <https://linnamonsaatio.fi/arkisto/> | 2020–2025, ~16 per year. Name with credentials, full descriptive purpose, amount (€1,600–€26,000). One free-text line per grant. |
| Suomen Muinaismuistosäätiö | <https://muinaismuistosaatio.fi/avustukset/myonnetyt-avustukset/> | 2015–2025, ~70–80 entries on one page. Name, purpose, amount, field of study. |
| Music Finland | <https://musicfinland.fi/fi/kuulumisia/tag/tuensaajat> | 2020–2025, one article per round (33–74 recipients each). Name, amount, project description, nested under grant-type and genre headings. |
| Suomen valokuvataiteen museo | <https://www.valokuvataiteenmuseo.fi/fi/museoinfo/apurahat-ja-palkinnot/tutkimusapurahat> | 2011–2026, ~44 awards on one page, with amounts. Sentence wording drifts by year and names appear in inflected Finnish forms (Frigårdille, Zaitseville) that need normalising. |
| Sarjakuvantekijät ry | <https://www.sarjakuvantekijat.com/2025/03/patka-apurahat-2025.html> | One Blogger post per year, 2020–2025 verified. Name, purpose, amount (€2,000–3,000). Each year sits at a different, unpredictable URL, and the blog's label/search paths are robots-disallowed — go via the year archives. |
| Teaterstiftelsen Vivicas Vänner | <https://www.vivicasvanner.fi/apurahat/myonnetyt-apurahat> | 2006–2026, 200+ entries on one page in per-year collapsible sections. Name, project title, description — per-grant amounts are mostly missing, only yearly totals. |
| Teatterin tiedotuskeskus TINFO | <https://www.tinfo.fi/fi/Myonnetyt_TINFO-apurahat> | 2011–2025, one page per year, ~8–13 grants each. Author, play, target language, translator. No amounts at all. |
| Selim Eskelinin säätiö | <https://www.selimeskelin.fi/fi/apurahat/myonnetyt_apurahat/> | 2024–2025, ~86 names. Names only — no amounts, no purposes; recipients are told their sum by email. |

## Tier 3 — Verified hard: the data exists but the route to it does not

| Funder | Where the data is | Why it is hard |
|---|---|---|
| Suomen Kääntäjien ja Tulkkien Liitto (SKTL) | PDF lists per round, e.g. <https://www.sktl.fi/app/uploads/2026/04/Kopiosto-myonnetyt-kevat-2023.pdf> | The whole site returns HTTP 403 to automated fetchers, and archive.org is unavailable. Real browser session plus PDF table parsing. Contents unverified for that reason. |
| Karjalan Kulttuurirahasto | <https://www.karjalankulttuurirahasto.fi/wp-content/uploads/2024/12/Myonnetyt-apurahat-2024.pdf> | 52 rows with names, titles and amounts — but the PDF is findable only through a search engine. No index page links it, and no URL pattern for other years. |
| Suomen Arkkitehtiliitto SAFA | Sporadic news posts, e.g. <https://www.safa.fi/uutiset/safan-apurahat-2023-jaettu/> | Publishes names, purposes and amounts, but only sometimes: 2019 and 2023 found, nothing for 2020–2022 or 2024–2025. No index — the extractor has to crawl and classify a news feed. |
| Opetus- ja kulttuuriministeriö (OKM) | Per-call pages on okm.fi, each linking its own PDFs; central register at tutkihallintoa.fi (2026 onward) | Dozens of independent call pages, PDF decision lists with inconsistent filenames and table layouts — three different naming conventions on three consecutive years of one page. |
| Opetushallitus (OPH) | <https://www.oph.fi/fi/rahoitus/myonnetty> → per-call PDFs | The index renders client-side (returns an empty shell without JS), and each call's payload is a PDF with no fixed schema. |
| Creative Europe / Luova Eurooppa | <https://culture.ec.europa.eu/creative-europe/projects/search> | JS-rendered database; nothing rendered without a headless browser, and no bulk export is documented. Structure could not be verified. |

## Not scraping problems — bulk data already exists

Worth knowing so nobody wastes the evening on them:

- **Erasmus+**: the EU publishes complete project lists as Excel/CSV at <https://erasmus-plus.ec.europa.eu/projects/projects-lists>, with beneficiary, amount, dates and project summary, filterable by country. Download, don't scrape.
- **EU structural funds (rakennerahastot)**: <https://eura2021.fi/tiepa> has a first-party Excel export of funded projects, refreshed daily. The export's exact columns are unverified.
- **Interreg Central Baltic**: statutory List of Operations at <https://keep.eu/api/programme/331?response_type=lop> returns a binary file (an .xlsx by all appearances) with no API key. The project listing page itself is a JS filter app showing only project names.

## Checked and dropped

These five are in our database but publish nothing extractable, so they are not worth your time:

- **Sibelius-Akatemian tukisäätiö** and **Helsingin Kauppiaitten Säätiö** — siba.apurahat.net and helsinginkauppiaittensaatio.apurahat.net are Aspicore application portals behind a login. No recipient data anywhere; only aggregate sums in news prose.
- **K. Albin Johanssons stiftelse** — publishes one paragraph of yearly totals, overwritten each year. No recipients.
- **Lisi Wahls stiftelse** — states outright that decisions go to applicants by email only.
- **William Thurings stiftelse** — no recipient list on either its own site or its foundationweb mirror.

One we could not check: **Saastamoisen säätiö**. Its navigation contains a "Myönnetyt apurahat" item, but every subpage fetch failed on a broken robots.txt and archive.org was unavailable. If your team has a real browser, this one is unknown territory — and a fair target for exactly that reason. Recipient data for its university programmes is published by the partner university instead, e.g. <https://www.uef.fi/fi/artikkeli/vuoden-2025-saastamoisen-saation-apurahansaajat-valittu>.

## Ground rules

- Public pages only. No logins, no paywalls, respect robots.txt.
- "This funder publishes nothing" is a valid finding. Report it; do not invent rows.
- Most pages are in Finnish or Swedish. You do not need to read them yourself.

<https://github.com/Grant-Academy/Grant-Scraper/>
