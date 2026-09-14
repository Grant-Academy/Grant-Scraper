# How Grant Academy stores and validates award data in production

This is the reference the hackathon prototype is measured against: the schema
`schema/award.schema.json` is derived from, and the validator that decides
which extracted rows reach the database. It lives in the private repo
`Grant-Academy/apuraha-spark-hub`; the file paths below point there.

Two things to take from it. First, the production schema is deliberately
narrow: the row is what a funder published, plus the URL it was read from.
Second, production has no confidence *score*. It has a validator that either
accepts a row, drops it, clears a field, or holds the whole page. The
challenge's `confidence` and `needs_review` sit on top of that, not instead of
it: a row that the validator would drop has confidence 0 whatever the
extractor thought.

## 1. The table

`supabase/migrations/20260612100000_sprint3_award_fields.sql`

```sql
CREATE TABLE public.wt_grant_awards (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  foundation_slug     text NOT NULL,
  program_slug        text NOT NULL,
  program_id          uuid REFERENCES wt_grant_programs(id) ON DELETE SET NULL,
  award_year          smallint NOT NULL CHECK (award_year BETWEEN 1990 AND 2100),
  recipient_name      text,
  recipient_type      text CHECK (recipient_type IN ('individual','organization','group')),
  project_title       text,
  project_description text,
  amount              numeric,
  currency            text CHECK (currency ~ '^[A-Z]{3}$'),
  source_url          text NOT NULL,
  scan_metadata       jsonb NOT NULL DEFAULT '{}',
  created_at          timestamptz NOT NULL DEFAULT now(),
  project_search      tsvector GENERATED ...   -- added later, see §5
);
```

Design decisions that matter for an extractor:

- **Awards hang off a slug pair, not a foreign key.** `(foundation_slug,
  program_slug)` is the lineage. The grant catalogue archives a programme row
  every year and creates a new one, so a hard FK would orphan the history.
  `program_id` is only a convenience pointer to whichever programme row was
  current at scrape time.
- **No discipline column.** Discipline comes from the programme the award is
  attached to, not from the row. The challenge asks for it because it is what
  makes the combined table readable; production would store it in
  `scan_metadata` until there is a column.
- **`amount` without `currency` is refused.** A number nobody can name the
  unit of would be read as euros by everything downstream.
- **`source_url` is NOT NULL.** There is no row without a page.

### Identity

`supabase/migrations/20260903140000_grant_awards_idempotency.sql`

```sql
CREATE UNIQUE INDEX wt_grant_awards_identity_uniq
  ON wt_grant_awards (foundation_slug, program_slug, award_year,
                      recipient_name, coalesce(project_title, ''));
```

Same funder, programme, year, recipient and title = same award. This is why
`project_title` is not decoration: an invented title creates a second, false
award for a real person, and the validator (§3) drops titles the page does not
carry for exactly that reason. It is also why `eval/score.py` counts distinct
`(name, year)` pairs rather than rows.

### Write path: the upsert RPC

`wt_upsert_grant_awards(_rows jsonb, _dry_run boolean default false)` is the
only way rows get in. It is called by the admin importer Edge Function
(`supabase/functions/import-grant-data`, kind `awards`), which the `/admin`
page and `scripts/grants/import-awards-export.mjs` both talk to. Nobody writes
the table directly, and migrations never carry data.

Per row, in order:

| Check | Outcome |
|---|---|
| `foundation_slug`, `program_slug`, `recipient_name`, `source_url`, `award_year` present | otherwise row error `missing required field` |
| `award_year` in 1990–2100 | else `award_year out of range` |
| `recipient_type` ∈ individual / organization / group / null | else `invalid recipient_type` |
| `amount` set ⇒ `currency` set | else `currency required when amount present` |
| `amount` parses as `^\d+(\.\d+)?$` | otherwise silently null (a garbage amount is a row error, not a crash) |

Errors are per row: the rest of the batch still commits. The call returns
`{inserted, updated, skipped, errors:[{index, error}]}`.

On conflict with the identity index the row is **filled in, never
overwritten**: `amount`, `currency`, `project_description` and
`recipient_type` are updated only where the stored value is NULL. A funder
that publishes names in spring and sums in autumn can be imported twice. A
`force: true` on the row flips that to "incoming wins". When an amount is
filled in from a different page than the one the row was first read from,
`source_url` moves to the page that carries the amount, so the link still
proves the number.

`_dry_run = true` runs the same validation and returns the same error list
without writing. Use it before every real import.

### Provenance

`scan_metadata` is free-form JSON. The keys production writes:

```json
{
  "method": "firecrawl+llm",
  "fetched_at": "2026-09-03T08:12:00Z",
  "validation": {
    "aggregate":   {"stated": 457000, "extracted": 436250, "deviation": 0.045},
    "count_check": {"stated": 72, "extracted": 69, "matches": false},
    "amounts_cleared": 0,
    "rejected": 1
  },
  "source_quote": "Päähakija: … | Myöntösumma: 7600 € | …"
}
```

`source_quote` is what the challenge schema asks for on every row. Production
does not require it on the awards table (the programme catalogue does, via a
trigger), but every audit we have done started from it.

## 2. The rest of the schema around the table

| Object | Migration | What it does |
|---|---|---|
| `wt_grant_award_stats` view | 20260612100000 | Per programme and currency: count, first/last year, min/max/median amount. Feeds `funding.typical_awarded` on the programme card and the agent's budget advice. |
| `project_search` tsvector + `wt_search_funded_projects(query)` | 20260615150000 | Full-text search over title + description, `simple` dictionary so Finnish, Swedish and English all work. The agent tool that answers "has anything like my project been funded here". |
| `wt_award_import_runs` | 20260903150000 | One row per collector run: pages fetched, rows inserted / rejected, pages held, tokens, per-programme report. Exists because the collector stalled for two months in summer 2026 and nothing said so. |
| `wt_repoint_grant_awards(old, new)` | 20260903160000 | Moves history when a funder renames a programme (Taike merged two into one). History is keyed on slugs, so a rename would otherwise hide three years of awards. |
| `wt_purge_expired_grant_awards()` | 20260903120000 | Deletes rows older than award year + 5. Implements the retention period the privacy notice promises. |
| RLS | 20260821150000 | `SELECT` only for admins; `anon` has nothing. The agent reads through service role. Awards are public data, but a bulk-readable table of named recipients is not something we expose. |

## 3. The validator (`functions/src/awards/validate.ts`)

This is the production equivalent of the challenge's confidence score. It
runs on every page after the model has extracted rows and before anything is
written. The premise: a model that invents a name or an amount produces
something that looks exactly like a real row, so nothing is trusted until
code that cannot be persuaded has checked it against the page text.

Rules, in the order they bite:

1. **Recipient name must occur in the page text**, or the row is dropped
   (`name_not_in_source`). The comparison folds case, diacritics and
   whitespace. A plain substring match is not enough: `ry` matches every
   Finnish association and `Anna` matches `Annastiina`. So the match must fall
   on word boundaries, and must either *start* a published row (where a
   recipient name actually sits) or be substantial (two words, eight
   characters) so an accidental hit is not a realistic risk. A single token
   under four characters never matches.
2. **The year must be printed on the page or in its URL**, or the row is
   dropped (`year_not_from_source`). The model may report a year only on
   archive pages that print a heading per year; on a single-year list the
   page's publication line or URL decides (`extract.ts` `resolveAwardYear`).
   A plausible wrong year is worse than none, so a page whose year cannot be
   read is held rather than guessed.
3. **The amount must sit in the same segment as the recipient.** Page-wide
   presence is not accepted: if the model swaps two recipients' sums, both
   numbers are still on the page and the total still balances. Segments are
   lines and semicolon-separated pieces, the shape funders publish one award
   per. Thousands separators (space, dot, NBSP) and `,50` decimals are
   normalised. A miss **clears the amount to null and keeps the row**: a named
   recipient without a sum is still true.
4. **Title and description must be on the page verbatim** (under
   normalisation), or they are cleared. Paraphrase is exactly what this
   guards against, and title is part of the identity key.
5. **Aggregate check.** If the page states its own total ("yhteensä 500 000
   euroa", "jakoi … 2,1 miljoonaa euroa") and every accepted row has an
   amount, the extracted sum must be within 5 % of it, or **the whole page is
   held** and nothing is written. A partial list would fail this for the wrong
   reason, which is why it only runs when every row carries an amount.
6. **Count check.** If the page states how many recipients it has ("Apurahan
   sai 72 taiteilijaa"), the number is compared with rows kept. A mismatch
   is recorded in provenance, never a hold on its own: funders routinely count
   people where they list working groups. It exists because the 5 % sum
   tolerance hides a three-row gap (Taike Uusimaa 2026: 457 000 € stated,
   436 250 € listed, 72 stated, 69 listed).

Outcomes per row are therefore only four: accepted, dropped, amount cleared,
text cleared. Per page: written or held. The challenge's `needs_review` pile
corresponds to "held" plus "cleared"; the challenge's confidence number has no
production counterpart yet, which is one reason the challenge exists.

What the validator deliberately does *not* do: it never fixes anything. A
wrong amount is nulled, not corrected; a name that is inflected on the page
(`Virtaselle`) fails the name check unless the extractor already put it in
nominative form and the nominative also appears somewhere on the page. That
is a known weakness for prose sources (Valokuvataiteen museo), and a place
where a prototype can do better.

## 4. The collector around it (`functions/src/awards/`)

The validator is one step of a pipeline that has run monthly since summer
2026. It is the "hand-written instruction per funder" the challenge wants to
replace, except that it is not per funder: it is one generic vocabulary and
one generic prompt, and the gap it leaves is coverage, not correctness.

```
buildQueue        wt_grant_programs × wt_grant_awards → programmes missing any of the last 3 years, worst first
discover.ts       Firecrawl /search restricted to the funder's host, one query per language
                  ("myönnetyt apurahat", "beviljade stipendier", "tildelinger", "awarded grants"…),
                  biased by the programme's name and URL; result cached on the funder row
collect.ts        ≤ 4 candidate pages per programme, one request at a time per host;
                  a page must NAME the programme (text, title or URL) when the funder has several,
                  or it is left unbound — Taike has eight programmes and one decision list would
                  otherwise be written eight times
extract.ts        google/gemini-2.5-flash reads the whole page markdown; system prompt forbids
                  inferring anything, forbids inventing a year, and asks for an aggregate_note on
                  summary-only pages; currency aliases (€, euroa, kr…) normalised to ISO or null
validate.ts       §3
writer            wt_upsert_grant_awards, scan_metadata carries the validation result
wt_award_import_runs   the run report; DRY_RUN is the default at every level
```

Budget caps: max programmes, max pages per programme, max model calls per
run. A single bad page (a PDF too big for the context, a malformed reply)
is caught per page and the programme continues.

Where it stops short, and where the ~700 uncovered funders are:

- Discovery is search-engine based. A PDF that no index page links (Karjalan
  Kulttuurirahasto), a news feed with sporadic posts (SAFA) or a
  client-rendered index (OPH) never becomes a candidate.
- One page, one model call. No chunking, so a 58-year archive page (Huber) or
  a 300-entry table (Lehtinen) either fits the context or is lost.
- Prose sources fail the name check on inflection.
- No per-row confidence, so everything that is not dropped looks equally
  good downstream.

## 5. What this means for a prototype's output

A row is importable into production when it satisfies the RPC (§1): five
required fields, ISO currency whenever there is an amount, a year the page
actually prints. It survives an audit when it carries `source_quote`. It is
*correct* when it would pass §3: name on the page, amount beside the name,
title and description verbatim.

`eval/score.py` in this repo scores against rows that already passed §3, so
"not in ground truth" can mean either an invented row or an award the
collector never reached. The scorer prints the source URL of every missed row
for that reason: open it before deciding which.

Mapping from the challenge schema to the table is one to one except for the
three challenge-only fields (`discipline`, `confidence`, `needs_review` /
`review_reason`), which production would keep in `scan_metadata` until the
challenge shows they earn columns.
