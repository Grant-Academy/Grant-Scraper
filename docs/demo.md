# Demo runbook — 4 minutes, 7 beats

The brief's "What to show in the demo" ([challenge.md](challenge.md)), with the
exact commands, the numbers from the 14 Sep run, and what is on screen at each
beat. Everything shown here was produced by the run in
[`demo/run-log.txt`](../demo/run-log.txt); the outputs are in
[`demo/`](../demo/) so the demo survives a dead wifi.

**Before you start:** two browser tabs open on the raw pages (beat 1), a
terminal at the repo root with `grantscrape` installed and
`OPENROUTER_API_KEY` exported, and the demo page
([`demo/index.html`](../demo/index.html), or the published artifact) on a
third tab. If the network dies, every beat still works from `demo/`.

| # | Beat | Time | On screen |
|---|---|---|---|
| 1 | The raw problem | 0:30 | Two funder pages side by side |
| 2 | Untuned run | 1:00 | Terminal: discover → fetch → extract → validate |
| 3 | Click through | 0:30 | Table row → source page |
| 4 | The review pile | 0:40 | `needs_review.csv`, one row, its reason |
| 5 | The number | 0:30 | `eval/score.py` output: 113/113 |
| 6 | What the combined table shows | 0:30 | Two charts |
| 7 | Three → several hundred | 0:20 | One slide of next steps |

## 1. The raw problem (0:30)

Tabs: <https://www.hubersaatio.fi/myonnetyt-apurahat/> and
<https://www.karjalankulttuurirahasto.fi/wp-content/uploads/2024/12/Myonnetyt-apurahat-2024.pdf>.

Say: same information — who, how much, for what — in nothing like the same
shape. Huber: a bold name line, amount, discipline tags, then bullets with a
title, a description and a purpose. Karjalan: a PDF table with an application
number, surname first, a title column, a sum. And the photography museum
writes it as prose with inflected names: "5000 euroa Aura Saarikoskelle".
There are ~700 of these, each different.

## 2. Untuned run (1:00)

The photography museum was never seen by the person who built this; only the
skill file and the homepage URL.

```bash
grantscrape discover https://www.valokuvataiteenmuseo.fi/ --probe 8 --top 5
```

The awards page ranks first (score 9.83, 47 euro amounts found on it; the next
candidate has 1). Then:

```bash
grantscrape fetch https://www.valokuvataiteenmuseo.fi/fi/museoinfo/apurahat-ja-palkinnot/tutkimusapurahat \
  --run valokuvataiteen-museo --foundation "Suomen valokuvataiteen museo"
grantscrape extract --run valokuvataiteen-museo --backend openrouter --model anthropic/claude-sonnet-5
grantscrape validate --run valokuvataiteen-museo
grantscrape combine --out out
```

17 chunks, 45 awards 2011–2026, 0 in review. If the extract call is slow on
stage, say so and switch to the pre-run `demo/` outputs; the point is the
shape of the pipeline, not the wait. (Model calls took about a minute per
funder in the rehearsal.)

Say: no site-specific code. Python does robots.txt, fetch, HTML→markdown,
PDF tables, chunking between entries, and the checks. The model reads one
chunk at a time under one prompt file and must quote its evidence.

## 3. Click through (0:30)

Open `out/table.csv` (or the demo page's table). Pick any row; its
`source_url` carries a section anchor where the page has one
(`…/arkisto/#2025`) or the PDF page (`….pdf#page=2`). Open it. Show
`scan_metadata.source_quote`: the exact text the row was read from.

Say: every row is one click from its proof. That is the contract with the
applicant who will read this.

## 4. The review pile (0:40)

`out/needs_review.csv`: one row out of 251.

> Etelä-Karjalan arkeologian harrastajat J — €500 — Karjalan 2024
> reason: recipient name looks malformed in the source (ends in a lone letter,
> possibly cut off); agent confidence 0.60

Open the PDF: the name really is cut off in the source. The tool did not fix
it, did not guess, did not hide it.

Say how the score is decided: `confidence = min(model's own confidence, rule
score)`. The rule score starts at 1.0 and loses points when the source
disagrees: evidence not found verbatim −0.5 (always review), name or amount
text not found −0.3, year missing or off the section −0.3, amount outside
€50–€5 M −0.3, name malformed −0.3, amount missing though the chunk has sums
−0.2, type contradicts a legal-form marker −0.15, name rewritten −0.1. Below
0.70, or any serious rule, goes to review. Nothing is dropped or silently
corrected.

And the check that matters most: the funders' own totals. Karjalan's PDF says
"Yhteensä 52 kpl, 256 152 €": we have 51 rows + 1 in review = 52, and
255 652 + 500 = 256 152. Huber's page says 116 030 €: ours 116 030. Suomen
tietokirjailijat says "113 saajaa, 642 000 €": ours 113 and 642 000.

## 5. The number (0:30)

```bash
grep '"foundation_slug": "suomen-tietokirjailijat"' out/awards.jsonl > out/stk.jsonl
python3 eval/score.py --pred out/stk.jsonl --funder suomen-tietokirjailijat --year 2026
```

```
ground truth 113 rows, predicted 113, matched 113
precision 100.0%   recall 100.0%   F1 100.0%
amounts: 113/113 exact   project_title: 113/113
```

Against Grant Academy's own extraction of the same page, produced with a
hand-written per-funder instruction. Michael's earlier run on WSOY's 11-page
PDF: recall 100 % (265/265), and the 10 "extra" rows turned out to be second
awards to the same person that the ground truth had collapsed — the
prototype's total matched the PDF, the ground truth's did not.

Honest caveat: no row was wrong on either ground-truth funder, so the
calibration of the confidence number is untested on wrong rows. The review
pile is small because these pages are clean.

## 6. What the combined table shows (0:30)

Two things no single page shows:

- **Who gets funded differs by funder.** Huber gives 46 % of its 2026 grants
  to groups and collectives, Karjalan 76 % to organisations, the photography
  museum and Suomen tietokirjailijat almost only to individuals. A collective
  reading one page cannot see where it fits.
- **A change between years.** The photography museum's research-grant pool
  sat at €10 000 a year from 2019 to 2025 and jumped to €22 000 across four
  grants in 2026.

## 7. Three → several hundred (0:20)

- Run `discover` over the full funder list; `extract --backend …` in batch.
  Cost tonight: about a minute and a few cents per funder.
- Ground-truth funders become a regression suite on every prompt change.
- The review-reason counts decide which rule or prompt line to fix next.
- Known gaps: PDFs no index links (Karjalan needs Tavily), JS-rendered and 403
  sites need the browser fallback, `* ## Kuvataide 2026` list headings and
  bare `2.000` amounts (Lehtinen) are not yet parsed.
- Production import is one call: the rows already validate against the
  schema, and [production-pipeline.md](production-pipeline.md) says what the
  importer checks.
