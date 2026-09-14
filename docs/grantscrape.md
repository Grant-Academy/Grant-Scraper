# grantscrape — how it works, how to run it, what it measured

A foundation's URL goes in; a verifiable table of awarded grants comes out, in
[`schema/award.schema.json`](../schema/award.schema.json), with the exact source
section and a confidence score on every row, and a separate needs-review pile.
No site-specific code.

## The split: deterministic Python + Claude Code skills

| Step | Who | What |
|---|---|---|
| `grantscrape discover <site>` | Python | robots.txt, sitemap, homepage and hub links, fi/sv/en keyword ranking, then probes the top pages and counts euro amounts on each. |
| pick the page | Claude (skill) | Reads the ranked list; prefers archive pages, PDFs where the list lives, one language version. |
| `grantscrape fetch <url> --run <slug>` | Python | Respects robots.txt. HTML → markdown with heading anchors; PDF → per-page tables + text. Splits into chunks of ≤ 6 000 chars **between entries, never inside one**, each prefixed with `[section: …]` so the year and category travel with it. |
| extract | Claude (skill, parallel subagents) | One JSON file per chunk under [`grantscrape/prompts/extraction.md`](../grantscrape/prompts/extraction.md). Every row carries `evidence`: a verbatim span of the chunk. |
| `grantscrape validate --run <slug>` | Python | Schema check, rule scoring, dedupe, needs-review split. |
| `grantscrape combine` | Python | `out/awards.jsonl` / `.csv` (every row, production schema, `needs_review` flag), `out/table.csv`, `out/needs_review.csv`, `out/summary.json`. |
| `eval/score.py` | Organiser | Precision / recall against ground truth. |

Headless alternative to the skill for batch runs:
`grantscrape extract --run <slug> --backend anthropic|openrouter|ollama|lmstudio|openai [--model …]`
(same prompt file; `pip install -e '.[api]'`). Not live-tested in this session: no API keys were available and the local Ollama had no models.

## How confidence is decided

`confidence = min(extractor's own confidence, rule score)`. The rule score starts at 1.0 and loses points when the source disagrees:

| Check against the source chunk | Penalty |
|---|---|
| `evidence` not found verbatim (whitespace- and Unicode-normalised) | −0.50, always review |
| recipient text / amount text not found | −0.30 each |
| year missing, or different from the section's year | −0.30 |
| amount outside €50 – €5 000 000 | −0.30 |
| amount missing although the chunk lists euro amounts | −0.20 |
| name looks malformed in the source: ends in a lone letter (cut off), or a comma with no space inside it | −0.30 |
| recipient type contradicts a legal-form marker in the name (`ry`, `oy`, `säätiö`, `työryhmä`, `&`) | −0.15 |
| name contains words not in the source (inflection undone, spelling repaired) | −0.10, a visible flag |

A row goes to **needs review** when grounding fails, confidence is below 0.70, or rule penalties exceed 0.20. Nothing is dropped or silently corrected; every reason travels with the row in `review_reason` / `scan_metadata.review_reasons`.

Why both halves: two independent extractions of the same garbled Linnamo name (`Al,Busultan, Bilal ja työryhmä`) self-reported 0.65 and 0.80. Model confidence alone is noisy; the deterministic checks anchor it to the page.

## Results (14 Sep 2026)

Tuned on (the prompt's worked examples come from these):

| Funder | Shape | Rows | Review | Check against the funder's own numbers |
|---|---|---|---|---|
| Samuel Huberin taidesäätiö 2026 | rich HTML: name, amount, tags, title, description | 41 | 0 | €116,030 = page's "kokonaissumma"; every discipline's count and sum match |
| Olga ja Vilho Linnamon Säätiö 2020–2025 | one prose entry per grant, per-year theme calls | 130 | 2 | no published totals; each year's call captured as `program_slug` |
| Karjalan Kulttuurirahasto 2024 | 3-page PDF table | 51 | 1 | €256,152 = PDF's "Yhteensä 52 kpl" |

Never seen by the builder (fresh agent, only the skill file and a URL, no code changes allowed):

| Funder | Shape | Result |
|---|---|---|
| Suomen valokuvataiteen museo, from the **homepage URL** | prose sentences per year, inflected names | discover ranked the right page first. 45 awards 2011–2026, every yearly block's announced count reconciles. As run: 42 rows + 3 review. After four harness fixes the run's friction report prompted: 44 + 1. The remaining review row is a genuine conflict (2022 heading, 2021 board-meeting date in the sentence). |
| WSOY:n kirjallisuussäätiö 2025 PDF (ground truth) | 11-page PDF, one table per category | **recall 100 % (265/265), precision of unflagged rows 1.0**. Scorer precision 96.4 % and 9 "wrong" amounts are all the same thing: 10 people with two awards (e.g. €400 residency + €6,000 grant). The ground truth keeps one row per name and year and lacks the second award; our €1,310,000 equals the PDF's own total, the ground truth's €1,266,800 does not. |
| Suomen tietokirjailijat, spring 2026 (ground truth) | HTML list, three sub-programmes, bare amounts | **precision 100 %, recall 100 % (113/113), amounts 113/113, titles 113/113**. Sum €642,000 equals the page's "113 saajaa, 642 000 €". |

`project_description` scores 0 on both ground-truth funders because the ground truth stores a section heading there (WSOY: "Tietokirjallisuus ja oppikirjat"; tietokirjailijat: "Apurahat tieto- ja oppikirjojen kirjoittamiseen (euroina)"). We store those in `discipline` / `program_slug`, as the schema describes. A mapping choice, not missing data.

**Combined table:** 6 funders, 658 rows (654 in the table, 4 in needs review), 0 violations of `schema/award.schema.json`. Three random rows re-checked against the live pages: all present.

**The review pile, and why each row is in it:**

| Row | Reason |
|---|---|
| Etelä-Karjalan arkeologian harrastajat J (Karjalan 2024, €500) | name ends in a lone letter: cut off in the source PDF itself |
| Al,Busultan, Bilal ja työryhmä (Linnamo 2024) | comma inside the surname: garbled on the page |
| Jalonen,Vappu (Linnamo) | comma with no space: sloppy on the page, worth a look |
| Johanna Frigård ja työryhmä (photography museum 2022, €10,000) | the extractor's own doubt (2022 heading, 2021 date in the sentence) plus a name put back into nominative from "Frigårdille" |

The first two were in the pile only on some extraction runs, because the model's self-reported confidence for them varied between 0.60 and 0.80; the malformed-name rule (added last, after all runs) now catches them deterministically.

**Honest caveat on calibration:** across both ground-truth funders no extracted row was wrong, so the scorer has no wrong rows to test calibration on (`mean_on_wrong_rows: None`). The review pile is small because these pages are clean, not because the thresholds are loose; the untuned photography-museum run shows what gets flagged when a page is ambiguous.

## One thing the combined table shows that no single page does

- **Who gets funded differs sharply by funder.** Huber gives 46 % of its grants to working groups and collectives; WSOY 10 %, the photography museum 7 %. Karjalan funds organisations 75 % of the time. A collective reading only one page cannot see where it fits.
- **A change between years.** The photography museum's research-grant pool sat at €10,000 a year from 2019 to 2025 and jumped to €22,000 across four grants in 2026.

## Demo script (4 minutes)

1. **The raw problem.** Huber's page (name – € – tags, then bullets) next to the Karjalan PDF table. Same information, nothing in common.
2. **Untuned run.** `grantscrape discover https://www.valokuvataiteenmuseo.fi/` → the awards page ranks first → `fetch` → skill extracts → `validate`.
3. **Click through.** Open any row's `source_url`: it carries the section anchor where the page has one (`…#2025` on Huber's archive, `….pdf#page=2`), else the exact page. `scan_metadata.source_quote` is the exact text.
4. **The review pile.** `out/needs_review.csv`: four rows, each with its reason (table above). Show the penalty table and the point that model confidence alone varied 0.60–0.80 on the same garbled name.
5. **Accuracy.** WSOY: 100 % recall, unflagged precision 1.0, and a finding for Grant Academy: the ground truth drops second awards to the same person.
6. **The pattern.** Collectives vs individuals by funder; the museum's 2026 jump.
7. **Next, three → several hundred.** Run `discover` over the full funder list; `grantscrape extract --backend …` for batch; use the ground-truth funders as a regression suite on every prompt change; let the review-reason counts decide which rule or prompt line to fix next; add a headless browser only for the ~5 % of sites that need JS.

## Known limits

- Discover cannot find search-engine-only PDFs (Karjalan) without Tavily (`TAVILY_API_KEY`).
- JS-rendered or 403 sites need the browser fallback in the skill (`fetch --from-file`).
- A multi-page PDF table that repeats only its column header now inherits the category from the previous page (fixed after the WSOY run; the WSOY numbers above are from before the fix).
- Programme vs discipline is a judgement call the prompt only partly settles.
