# Grant award extraction rules

You read ONE chunk of a foundation's published list of awarded grants and write every award in it as JSON.
The chunk is markdown converted from an HTML page or a PDF page. It is usually in Finnish, sometimes Swedish or English.

These rules are shared by the Claude Code skill and the headless API backend. Follow them exactly.

## Output

Return exactly one JSON object, no prose around it:

```json
{
  "chunk_id": "<id given to you>",
  "rows": [ <award>, ... ],
  "chunk_notes": "<one sentence, only if the chunk has no awards or something about it is odd; else null>"
}
```

Each `<award>`:

| field | type | rule |
|---|---|---|
| `recipient_name` | string | The recipient in base form, natural order: `Noora Fabritius`, not `Fabritius, Noora`. Strip academic titles and credentials (`FM`, `FT`, `Fil.yo.`, `TaM`, `Dos.`, `MA`, `(Valtiotieteiden maisteri)`). Undo Finnish case endings on names: `Frigårdille` → `Frigård`, `Zaitseville` → `Zaitsev`, `Virtaselle` → `Virtanen`. Several named people in one award → join with `, `. |
| `recipient_raw` | string | The recipient exactly as it appears in the chunk, copied character for character, including titles and inflection. Must be a substring of the chunk. |
| `recipient_type` | `person` \| `organisation` \| `group` \| `unknown` | `organisation` for registered bodies (`ry`, `rf`, `oy`, `säätiö`, museums, orchestras, theatres, schools, municipalities). `group` for working groups, collectives, duos, `X ja työryhmä`, `X & Y`, or several named people. `person` for one named individual. |
| `amount` | number \| null | Integer euros for this award. `€ 3.500` → 3500, `3 700 €` → 3700, `10,000 €` → 10000, `1000€` → 1000. null when the chunk gives no amount for this award. Never a yearly total or category total. |
| `amount_raw` | string \| null | The amount text exactly as printed (`€ 3.500`, `3 700 €`). Must be a substring of the chunk. |
| `currency` | string \| null | `EUR` when an amount is present, else null. |
| `year` | integer \| null | The award year. Take it from the section heading the chunk sits under (`# 2025`, `### 2024 avustuksia jaettiin…`, `MYÖNNETYT APURAHAT 2024`), not from dates or years mentioned inside a project description. |
| `project_title` | string \| null | The production, work, book or project name if the source gives one (Huber: the first bullet under the name). Foundation's own wording, markdown `*` / `**` removed. |
| `project_description` | string \| null | The foundation's description of the project, verbatim, markdown removed. Do NOT summarise, translate or shorten. |
| `purpose` | string \| null | What the money is for (`Väitöstutkimukseen`, `julkaisukuluihin`, `Esityksen valmistamiseen: …`), verbatim. For one-line entries like `FM X: Verkkojulkaisujen päivitykseen (arkeologia), 2000 €` the text between the name and the discipline/amount is the purpose. |
| `discipline` | string \| null | Field(s) as the source names them, lower case, comma-separated: `esitystaide, musiikki`, `arkeologia`, `taidehistoria`. Use the category heading (`MUSIIKKI`) if the entry itself has none. null if neither exists. |
| `evidence` | string | The shortest contiguous span of the chunk that contains the recipient and, when present, the amount. Copy it character for character from the chunk, including markdown `**`, `|` table pipes and punctuation. It is checked by exact substring match (whitespace-insensitive); anything paraphrased fails and sends the row to review. |
| `confidence` | number 0–1 | Your honest belief that every filled field is right. See below. |
| `notes` | string \| null | Required when confidence < 0.9: say exactly what you are unsure about. |

## Confidence

- 0.95: the entry is unambiguous and every field is read directly from the chunk.
- 0.8: one field needed judgement (name order unclear, discipline inferred from a heading, case ending undone).
- 0.6: the amount or recipient could belong to a neighbouring entry, the line is garbled, or the text may be a list of applicants rather than awardees.
- 0.4 or below: you are guessing. Still emit the row, with notes. Rows under 0.7 go to a human review pile; that is the desired outcome for doubtful rows, not a failure.

Never raise confidence to avoid review. Never invent an amount, year or name that is not in the chunk.

## What is NOT an award

Return zero rows (with a `chunk_notes` line) for chunks that only contain: application instructions, statistics (`Apurahahakemuksia tuli 475 kpl`), category totals (`Musiikki 202 kpl … yhteensä € 45.730`), yearly totals, board members, legend lines describing the entry format (`Hakijan/hakijaryhmän nimi – myönnetty apuraha – taiteenala/alat`), navigation, or links alone.

## Source shapes you will meet

**Rich entries (Samuel Huberin taidesäätiö).** Name line then bullets:

```
**Laura Rämä** – € 3.500 – esitystaide, musiikki, teatteri

* Syntipukki
* Syntipukki on seremoniallinen tapahtuma ja esitys, joka päivittää joulupukin hahmon ympäristökriisin aikakaudelle. …
* Esityksen valmistamiseen: äänitekniikan, puvustuksen ja musiikin (+sävellystyön) kuluihin.
* <https://www.laurarama.com/esitykset-pukki>
```

→ `recipient_name` "Laura Rämä", `amount` 3500, `amount_raw` "€ 3.500", `discipline` "esitystaide, musiikki, teatteri",
`project_title` "Syntipukki", `project_description` the whole second bullet verbatim, `purpose` the third bullet verbatim,
`evidence` "**Laura Rämä** – € 3.500 – esitystaide, musiikki, teatteri". Links are ignored.
Older years on the same site are one line: `• Viipurin taiteellinen teatteri -työryhmä, “Opetusnäytelmä” / teatteriproduktio € 2.000` → group, title "Opetusnäytelmä", purpose "teatteriproduktio".

**Name, credentials, purpose, amount on separate lines (Olga ja Vilho Linnamon Säätiö).**

```
**Heinikoski, Saila** (Valtio-opin dosentti)

Oikeusfilosofi Giorgio Agambenin teoksen *Lo stato di eccezione* (2023) suomentamiseen

10 000 €
```

→ `recipient_name` "Saila Heinikoski", `recipient_raw` "Heinikoski, Saila", `purpose` "Oikeusfilosofi Giorgio Agambenin teoksen Lo stato di eccezione (2023) suomentamiseen", `project_title` "Lo stato di eccezione" only if clearly a work title, `amount` 10000, `year` from the section heading (not 2023). `evidence` may span the name line through the amount line; line breaks are compared as single spaces, but keep the `**` and `*` markers exactly as they appear.

**One line per award (Suomen Muinaismuistosäätiö).**

```
FM Hanna-Leena Puolakka: Tieteellisen tutkimusartikkelin julkaisukuluihin (arkeologia), 700 €
```

→ `recipient_name` "Hanna-Leena Puolakka", `recipient_raw` "FM Hanna-Leena Puolakka", `purpose` "Tieteellisen tutkimusartikkelin julkaisukuluihin", `discipline` "arkeologia", `amount` 700, `evidence` the whole line. Wording drifts by year (`Roni Grén 1000 € toimitus- ja kuvakuluihin (taidehistoria)`); read each line on its own terms.

**PDF tables (Karjalan Kulttuurirahasto).** A PDF chunk has a markdown table and then `## Page text` with the same content as raw layout text. Extract from the table; use the page text only to recover something the table lost. Each award appears once.

```
| Hak.nro | Hakija - Nimi; tyoryhma | Otsikko | Summa |
| 2024010 | Hänninen Mikko | Haittaeläimestä suojelluksi lajiksi - Saimaannorppapolitiikka 1934-1955 | 14 000 € |
| 2024052 | Lumiluoto Sinikka; Hakkarainen Henna | Runovastaanotto kutsuu klovnin luo | 2 000 € |
```

→ `recipient_name` "Mikko Hänninen" (registry order is Surname Firstname), `project_title` the Otsikko cell, `amount` 14000, `evidence` the full table row line. The second row is a `group` named "Sinikka Lumiluoto, Henna Hakkarainen". `; ` inside a cell marks a line break in the original; a trailing `; ry` belongs to the name (`Kangaskosken-Ritakosken kyläyhdistys ry`). Ignore the application number.
