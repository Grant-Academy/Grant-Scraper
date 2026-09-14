# Who Actually Got the Money? (Teemu Laasanen — Grant Academy)

Build a scraper that reads a grant foundation's public website and turns its published list of awarded grants into clean, structured data — who got funded, for what kind of project, how much and when — with a source link and a confidence score for every row.

## Why this challenge matters

Artists and cultural organisations apply for grants almost blind. Foundations publish who they funded and how much, but every one of them does it differently: an HTML table on one site, a PDF annual report on another, a paginated search on a third, sometimes a press release in prose. That data is public, but in practice unusable — nobody can compare across foundations.

We run a grant database covering funders in 21 countries. Award history is the most valuable thing we can give an applicant, and the amounts are the smallest part of it. What an applicant actually needs to know is whether anything resembling their project has ever been funded here, what this foundation keeps funding in their field year after year, and which quieter signals should change how they write — a shift from individuals toward collectives, a discipline that has quietly dropped off the list, a foundation that funds first works but rarely second ones. None of that is visible one grant at a time. It only appears when the whole list is in one shape, across many foundations.

We have done this the hard way for close to two hundred funders, and it works: tens of thousands of awards, every row traceable to its source page. But each of those funders needed a human to look at the site and write an instruction for that site — which fields sit where, which page holds the list, what to ignore. Several hundred funders are still uncovered, and at one hand-written instruction each, we will never finish. That is the wall this challenge is aimed at.

## Your goal

By the end of the session, the prototype should:

- Take a foundation's website URL as input, with no site-specific code written by hand in advance.
- Find the page or document where awarded grants are published, including when it is a PDF or behind pagination.
- Extract each award into a common schema: recipient name, recipient type (person or organisation), amount, currency, year, project title, project description, discipline.
- Treat the project title and description as first-class data wherever the source publishes them, not as an afterthought next to the amount. They are what makes two grants comparable, and they are the part that gets dropped first. Keep the foundation's own wording rather than summarising it.
- Attach to every row the exact source URL it came from, so a human can verify it in one click.
- Give every row a confidence score, and put anything it is unsure about into a separate "needs review" list rather than silently guessing.
- Run against at least three different foundations with genuinely different page structures — and at least one the team has never looked at — and produce one combined table.
- Export the result as CSV or JSON.

Getting three foundations right with honest confidence scoring beats getting thirty rows out of one site.

## Resources

I will bring to the session:

- A list of about 20 Finnish foundation URLs, ranked by how awkward their publishing format is, so you can choose your difficulty. → [annex-1-target-funders.md](annex-1-target-funders.md)
- The target JSON schema we use in production. → [../schema/award.schema.json](../schema/award.schema.json)
- Ground truth: tens of thousands of award rows we have already extracted, across nearly two hundred funders, every one carrying the source URL it came from. Point your prototype at a funder we have already covered and you can measure your accuracy against real answers instead of guessing whether it worked. → [../data/ground-truth/README.md](../data/ground-truth/README.md) and [../eval/score.py](../eval/score.py)
- API keys for Firecrawl and Tavily, and an LLM key, if your team wants them — just ask me at the table.

You do not need access to any of our systems. Everything here is public data and the output is a file.

## Constraints

- Keep it realistic for a 3-hour build.
- One clear use case: URL in, verifiable table out.
- A working prototype beats a polished but unfinished concept.
- No login walls, no paywalled sources, and respect robots.txt — this is public data and it should stay that way.
- Finnish-language pages are the default. You do not need to speak Finnish; the model does.

## What to show in the demo

In 3 to 5 minutes:

1. Show the raw problem: two foundation pages side by side, publishing the same kind of information in completely different shapes.
2. Run your prototype on a foundation the team did not tune it for.
3. Show the resulting table, and click one row through to its source page to prove it is real.
4. Show the "needs review" pile and explain how the prototype decided what it was unsure about.
5. If you measured accuracy against the ground truth data, show the number.
6. Show one thing the combined table reveals that no single foundation's own page shows — what a field tends to get funded for, or something that changed between years.
7. Say what you would do next to take it from three foundations to several hundred.

## The objective is to…

…prove that a general extractor plus honest confidence scoring can replace the hand-written instruction we currently need for every single site, and turn scattered public funding data into something an applicant can read patterns from before they write a word.
