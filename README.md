# Grant Scraper

**Who actually got the money?** A hackathon build (AI Campfire, 14 September 2026,
Grant Academy): take a grant foundation's public website as input and turn its
published list of awarded grants into one clean, verifiable table — recipient,
type, amount, year, project title and description — with a source URL and an
honest confidence score on every row, and no site-specific code written by hand.

Read the brief first: **[docs/challenge.md](docs/challenge.md)**.

## What is in this repo

| Path | What |
|---|---|
| [`docs/challenge.md`](docs/challenge.md) | The challenge: why, the goal, constraints, what to show in the demo. |
| [`docs/production-pipeline.md`](docs/production-pipeline.md) | How Grant Academy stores award rows in production (table, identity key, upsert rules, provenance) and the validator that decides which extracted rows are written: name on the page, amount beside the name, year from the page, 5 % aggregate check. The reference behind the schema and the ground truth. |
| [`docs/annex-1-target-funders.md`](docs/annex-1-target-funders.md) | ~20 Finnish funders with no award history in our database, checked one by one and tiered by how awkward their publishing format is. Pick your difficulty here. |
| [`schema/award.schema.json`](schema/award.schema.json) | The row schema our production importer accepts, plus the challenge's `confidence` / `needs_review` / `discipline` fields. JSON Schema, with the traps written into the field descriptions (Finnish "3.000 €" is three thousand, never convert SEK to EUR, never guess a year). |
| [`schema/example-rows.json`](schema/example-rows.json) | Two rows in that shape: one clean, one flagged for review. |
| [`data/ground-truth/`](data/ground-truth/README.md) | 44 003 award rows across 187 funders we have already extracted, every one with its source URL. Both the rows and a per-funder coverage index are in the repo. |
| [`eval/score.py`](eval/score.py) | Scores your CSV / JSON / JSONL against the ground truth for one funder: precision, recall, amount accuracy, title/description retention, and whether your confidence scores were honest. Standard library only. |

## Quick start

```bash
git clone https://github.com/Grant-Academy/Grant-Scraper.git
cd Grant-Scraper
python3 eval/score.py --pred out/your-rows.csv --funder skr --year 2025
```

Your prototype can live in any language. Put it under `src/` (or a folder named
after your team if several teams share the repo), write its output to `out/`
(git-ignored), and keep API keys in `.env` (git-ignored, hand-written, never
committed). Firecrawl, Tavily and LLM keys are available at the table.

## Output contract

One row per award, in the schema above, as CSV or JSON. Required on every row:
`foundation_slug`, `program_slug`, `award_year`, `recipient_name`, `source_url`.
Everything else may be null — **a null is always better than a guess.** Rows the
extractor is unsure about carry `needs_review: true` and a one-line
`review_reason`, and are shown as a separate pile, not mixed into the table.

## Ground rules

- Public pages only. No logins, no paywalls, respect `robots.txt`.
- "This funder publishes nothing" is a valid finding. Report it; do not invent rows.
- Keep the funder's own wording for titles and descriptions. Do not summarise or translate.
- Store recipient names only as the funder published them. No enrichment about individuals from other sources.
- Most pages are in Finnish or Swedish. You do not need to read them; the model does.

## The demo (3–5 minutes)

Two funder pages side by side showing the same information in different shapes;
your prototype run on a funder it was not tuned for; one row clicked through to
its source; the needs-review pile and how it got there; the accuracy number if
you measured one; one pattern the combined table shows that no single page does;
and what you would do next to go from three funders to several hundred.
