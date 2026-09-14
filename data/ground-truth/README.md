# Ground truth

Award rows Grant Academy has already extracted, so a prototype can be scored
against real answers instead of eyeballed. Exported from our database on
2026-09-14: **44,003 rows across 187 funders**
(fi: 144, no: 15, dk: 13, se: 8, None: 6, mt: 1).

## Two files

| File | In git | What |
|---|---|---|
| `coverage.json` | yes | Per-funder summary: row count, years, how many rows carry an amount / title / description, how many distinct source pages. No names. Use it to pick a funder to evaluate against. |
| `awards.jsonl` | yes | The rows themselves, one JSON object per line (25 MB). Every row is public information from the funder's own page, with that page's URL on the row. |

## Columns of `awards.jsonl`

Same names as [`../../schema/award.schema.json`](../../schema/award.schema.json):
`foundation_slug`, `program_slug`, `award_year`, `recipient_name`, `recipient_type`,
`project_title`, `project_description`, `amount`, `currency`, `source_url`, plus
three joined for convenience: `foundation_name`, `foundation_website`, `foundation_country`.

`source_url` is the page or PDF the row was read from. That is the URL to point
your prototype at when you want a like-for-like comparison — the funder's front
page is often several clicks away from the list.

## How to score

```bash
python3 eval/score.py --pred out/my-rows.csv --funder skr --year 2025
```

Rows match on normalised recipient name + award year. The scorer reports
precision, recall, amount accuracy, whether you kept the title and description
where the funder publishes them, and — if your rows carry `confidence` and
`needs_review` — whether the confidence was honest (mean confidence on correct
vs. wrong rows, precision of the rows you did **not** flag).

## Good funders to evaluate against

Finnish, at least 50 rows, amounts on nearly every row, and the whole list on a
dozen pages or fewer, so one run covers it:

| foundation_slug | Funder | Rows | Years | Source pages | Amount | Title | Description | Website |
|---|---|---|---|---|---|---|---|---|
| `mes` | Musiikin edistämissäätiö | 2389 | 2023–2025 | 3 | 100% | 0% | 98% | https://hakemus.musiikinedistamissaatio.fi/ |
| `skr` | Suomen Kulttuurirahasto | 2319 | 2024–2026 | 4 | 100% | 0% | 100% | https://apurahat.skr.fi |
| `ses` | Suomen elokuvasäätiö | 1702 | 2024–2026 | 1 | 100% | 100% | 33% | https://www.ses.fi/ |
| `otavan-kirjasaatio` | Otavan Kirjasäätiö | 1358 | 2023–2026 | 7 | 100% | 7% | 100% | https://otavankirjasaatio.fi/ |
| `nordisk-kulturkontakt` | Pohjoismainen kulttuuripiste (Nordisk Kulturkontakt) | 1349 | 2023–2026 | 1 | 100% | 17% | 100% | https://www.nkk.org/ |
| `fili` | FILI – Suomen kirjallisuuden tiedotuskeskus | 1082 | 2023–2026 | 11 | 100% | 100% | 100% | https://fili.fi/ |
| `wsoy-kirjallisuussaatio` | WSOY:n kirjallisuussäätiö | 1078 | 2023–2026 | 4 | 100% | 0% | 100% | https://www.wsoy-kirjallisuussaatio.fi/ |
| `otto-a-malm` | Kauppaneuvos Otto A. Malmin lahjoitusrahasto | 802 | 2023–2026 | 4 | 100% | 0% | 100% | https://fi.ottomalm.fi/ |
| `aktiasaatio-porvoo` | Aktiasäätiö Porvoo | 743 | 2024–2026 | 1 | 100% | 0% | 0% | https://aktiastiftelsen.fi/ |
| `oskar-oflund` | Oskar Öflunds Stiftelse | 564 | 2023–2025 | 4 | 100% | 0% | 100% | https://www.oskaroflund.fi/ |
| `sjunde-mars` | Stiftelsen 7:nde Mars Fonden | 552 | 2023–2026 | 4 | 100% | 0% | 100% | https://www.sjundemars.fi/ |
| `musiikintekijoiden-rahasto` | Musiikintekijöiden rahasto | 533 | 2023–2026 | 7 | 100% | 0% | 100% | https://musiikintekijat.fi/ |
| `suomen-tietokirjailijat` | Suomen tietokirjailijat ry | 503 | 2025–2026 | 2 | 100% | 100% | 100% | https://www.suomentietokirjailijat.fi/ |
| `helsingin-kaupunki` | Helsingin kaupunki | 485 | 2023–2025 | 3 | 100% | 0% | 100% | https://avustukset.hel.fi/ |
| `finska-lakaresallskapet` | Finska Läkaresällskapet | 465 | 2023–2026 | 4 | 100% | 0% | 100% | https://fls.fi/ |

The full list is in `coverage.json`. Big multi-page ones (Taike: 86 pages,
Statens Kunstfond: 102) are fair game but a run takes correspondingly longer.

## What the ground truth is, and is not

- **How it was made.** A language model read each page (or PDF) under a
  hand-written per-funder instruction; every row was then machine-checked
  against the page text: the recipient name had to occur on the page, an amount
  that could not be found on the page was cleared to null, and the year had to
  come from the page or its URL. Rows that failed were dropped. So the rows that
  are here are well grounded; the rows that are *missing* were never extracted
  or failed that check.
- **Recall is not 100 %.** For some funders only the last years, one programme,
  or a sample of a very long list was taken. A predicted row the scorer reports
  as "not in ground truth" may be a real award we lack. Click its source URL
  before calling it a hallucination — and tell us, that is a finding.
- **Identity.** Two awards to the same name in the same year with no
  distinguishing title collapse into one row on both sides. The count the
  scorer prints is distinct (name, year) pairs.
- **Names are as published.** Mostly nominative, sometimes with titles
  ("Kauppatieteiden maisteri Mikko Aro"), occasionally a joint row ("X ja Y").
  The scorer ignores case, diacritics, punctuation and word order but not extra
  words, so strip academic titles if your extractor keeps them and the funder's
  list does not — or vice versa. Look at the missed examples it prints.
- **Descriptions.** Where `project_description` is filled it is the funder's
  own wording, sometimes fetched from a per-project page behind the list
  (Koneen Säätiö, Lundbeckfonden). Where it is empty for a whole funder, the
  funder publishes none — check `coverage.json` before spending time on it.
