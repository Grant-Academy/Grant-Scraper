---
name: grant-extract
description: Extract a foundation's awarded grants from its public website into the common schema (recipient, type, amount, currency, year, project title, description, discipline) with a source URL and confidence score per row, plus a needs-review pile. Use when asked to "extract grants from <url>", "scrape awarded grants", "who got funded by <foundation>", or to add a foundation to the combined table.
---

# grant-extract: URL in, verifiable table out

You drive the deterministic `grantscrape` CLI and do the judgement work yourself: pick the awards page, read each chunk, write rows. Python does fetching, robots.txt, chunking, validation, confidence scoring and export. Never write site-specific code.

Run every command from the repo root. Work directory per foundation: `runs/<slug>/`.

## 1. Find the awards page

```bash
grantscrape discover <site-url>          # ranked candidate pages and PDFs -> runs/_discover/<host>.json
```

If `discover` is unavailable or finds nothing useful, look at the homepage links yourself (WebFetch) or use web search with the foundation name plus `myönnetyt apurahat`, `apurahansaajat`, `beviljade stipendier`.

The `€ amts` column counts euro amounts found on each probed page; a real award list usually has many. Choose the page(s) that list awarded grants. Prefer:
- an archive or all-years page over the current-year page (`/arkisto/` beats `/myonnetyt-apurahat/`), but take both if the archive lacks the current year;
- the page itself over a news post that links to it;
- PDFs when that is where the list lives;
- ONE language version. Sites often mirror the list under `/sv/` or `/en/`; fetching both duplicates every award. Take the Finnish one unless only another exists.

Skip application pages (`haku`, `hae`, `hakuohjeet`), application systems (`*.apurahat.fi`), and anything behind a login.

## 2. Fetch and chunk

```bash
grantscrape fetch <award-page-url> --run <slug> --foundation "<Foundation's name>"
```

Run once per chosen URL, same `--run` slug; chunks append. The command prints a chunk table: id, year hint, size, heading path.

- Exit code 3 means robots.txt disallows it. Stop and report; do not work around it.
- HTTP 403 or an empty JS shell: open the page with the Chrome tools (`get_page_text`), save the text to `runs/<slug>/source/manual.md`, then
  `grantscrape fetch --run <slug> --from-file runs/<slug>/source/manual.md --url <page-url> --foundation "<name>"`.

## 3. Extract, one rows file per chunk

Read `grantscrape/prompts/extraction.md` (the extraction rules) before reading any chunk. Then:

```bash
grantscrape status --run <slug> -v       # lists chunk files and which are still pending
```

For each pending chunk: read `runs/<slug>/chunks/<id>.md` and write `runs/<slug>/rows/<id>.json` exactly as the rules specify. A chunk with no awards still gets a rows file with `"rows": []` and a `chunk_notes` sentence.

**More than 6 chunks:** dispatch subagents in parallel, one per batch of about 5 chunk ids, all in a single message. Give each subagent this brief, filled in:

> Read /abs/path/grantscrape/prompts/extraction.md. Then for each chunk id in [<ids>]: read /abs/path/runs/<slug>/chunks/<id>.md and write /abs/path/runs/<slug>/rows/<id>.json following those rules exactly. Copy `evidence`, `recipient_raw` and `amount_raw` character for character from the chunk. Do not write any other files. Reply with the ids written and the row count per id.

## 4. Validate

```bash
grantscrape validate --run <slug>
```

- Exit 1 with ERRORS: those rows files are malformed. Re-read that chunk and rewrite its rows file.
- "chunks without rows file": extract those.
- The needs-review pile is expected. Do NOT edit rows to raise their confidence or to make evidence match. Only if a review reason is `evidence not found verbatim` may you re-read the chunk and fix a transcription slip in `evidence`, `recipient_raw` or `amount_raw`; never change the extracted values to do so.

## 5. Combine and report

```bash
grantscrape combine --out out
```

Report to the user, in this order:
1. Rows extracted and rows in needs-review, per foundation.
2. The top review reasons, and two or three example review rows with why they are there.
3. One or two cross-foundation observations from `out/summary.json` (for example which disciplines grow or shrink across years, or the person versus organisation share).
4. Paths: `out/combined.csv`, `out/combined.json`, `out/needs_review.csv`.

## Hard rules

- Never invent an amount, year or recipient. Missing is null.
- Keep the foundation's own wording for title, description and purpose. No summarising, no translating.
- `recipient_name` in base form and natural order; `recipient_raw` verbatim.
- Statistics, totals and instructions are not awards.
- Respect robots.txt. No login walls, no paywalls.
