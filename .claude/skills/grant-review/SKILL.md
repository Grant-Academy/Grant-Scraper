---
name: grant-review
description: Triage the needs-review pile produced by grant-extract. For each uncertain grant row, check it against its source chunk and either confirm it into the main table or leave it in review with a note. Use when asked to "review the needs-review rows", "triage uncertain grants", or "check the flagged rows".
---

# grant-review: work the needs-review pile honestly

Input: `runs/<slug>/out/needs_review.json` after `grantscrape validate --run <slug>`.

For each row:

1. Read its `review_reasons` and `notes`.
2. Open the source chunk `runs/<slug>/chunks/<chunk_id>.md`. If the chunk is ambiguous, open the row's `source_url` too (WebFetch or the Chrome tools).
3. Decide:
   - **Confirm**: the values are right as extracted. Quote the exact source text that proves each field in your decision.
   - **Correct**: one value is wrong. Quote the source text that proves the new value.
   - **Keep in review**: the source itself is ambiguous (for example an amount that could belong to two entries). Say what a human would need to check.

Record decisions in `runs/<slug>/review_decisions.json` as a list:

```json
[{"chunk_id": "004", "recipient_raw": "FT Maija Esimerkki", "decision": "confirm|correct|keep",
  "field": "amount", "new_value": 700, "quote": "…exact source text…", "note": "why"}]
```

Rules:
- Never change a value without a verbatim quote from the chunk that supports it.
- Never confirm a row whose evidence you could not find in the chunk.
- Do not edit `rows/*.json` or `out/*.json` directly; decisions live in `review_decisions.json` so the audit trail stays separate from the extraction.

Finish by reporting counts per decision and the rows kept in review with their reasons.
