# Thematic risk pieces

Longer risk pieces on one theme, run by the Risk team over a few weeks and published as the
free Risk pages (R2+) of a monthly report (see [../dashboard/README.md](../dashboard/README.md)).

One folder per piece:

```
thematic/<piece>/
  README.md        scope, sections, owners, status, agreed method (basket, windows, shock rule)
  basket.csv       the tickers the piece uses
  draft.md         the one working draft every team writes into (committed)
  figures/         charts for the draft (committed)
  code/            shared analysis code (committed)
  drafts/          analysts' decks, PDFs and working notes, one folder per team (committed)
  planning/        to-do lists, briefings, meeting notes (committed)
  results/         outputs: tables, workbooks, numbers behind the charts (committed)
  data/            raw Bloomberg pulls (gitignored, OneDrive only: Bloomberg licence)
```

The finished pages and charts go into the report they are published in:
`reports/dashboard/report_XX/pages.md` and `report_XX/figures/`.

Everything is committed to GitHub (private repo) except `data/`. Raw Bloomberg pulls that
the other team needs go in the shared OneDrive data folder (see the root README).

## Pieces

| Piece | Published in | Status |
|---|---|---|
| [ai-supply-chain/](ai-supply-chain/README.md): AI supply chain as a thematic risk | report 0 (Nov 2026, out 7 Dec) | drafting |
