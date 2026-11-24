# AI supply chain as a thematic risk

First thematic piece, published as the free Risk pages of **report 0** (November 2026 issue,
out Mon 7 Dec 2026). Final text goes in `reports/dashboard/report_00/pages.md`, charts in
`reports/dashboard/report_00/figures/`.

## Sections

| # | Section | Lead | Status |
|---|---|---|---|
| 1 | What AI thematic risk is: the layers, linked sectors (industrials, utilities, real estate), single points of failure, past and future moves | Team 1 | drafting |
| 2 | Correlation and shock analysis on the shared basket, with one shock definition | Team 1 (correlation), Team 2 (shocks) | drafting |
| 3 | Outlook and how BIF adapts its strategy | Risk team | written last |

Team 1: Baily, Johnny, Alex, Dom. Team 2: Guiseppe, Bea, Alexia.

## Agreed method (24 Nov 2026)

- **One basket** for everyone: [`basket.csv`](basket.csv), starting from Team 1's 19-name layered
  basket, split into a supply chain side and a hyperscaler (demand) side. Team 1 is extending it;
  update the file, don't keep private copies.
- **Benchmark:** S&P 500 ex-AI (from Bloomberg constituents). The 20-name hand-picked control
  basket (`basket.csv`, group `control`) is a secondary check only.
- **One shock definition** (Team 2 to confirm): basket daily return beyond ±2.5 sd of the previous
  250 trading days; shock days within 5 trading days form one episode; up and down counted separately.
- **Split date:** ChatGPT launch, 30 Nov 2022.
- **Data:** Bloomberg prices for the final numbers; Yahoo/CRSP only as a cross-check.

## Files

- **`draft.md`: the one working draft.** Both teams write sections 1 and 2 here; section 3 is
  added last. Analysts read and edit it on GitHub:
  https://github.com/Oscar339/BIF-risk-team/blob/main/reports/thematic/ai-supply-chain/draft.md
- `figures/`: charts for the draft, named `fig_<section>_<name>.png` (committed).
- `basket.csv`: ticker, name, layer, side (`supplier`, `hyperscaler`, `control`), notes.
- `benchmark.csv`: S&P 500 ex-AI tickers (Team 1 adds it; tickers only, no weights or prices).
- `code/`: shared analysis code. Name scripts by what they do (`correlation.py`, `shocks.py`).
- `code/team1_backing_calcs.py`: Team 1's backing calculations for their 23 Nov deck (Yahoo).
  Starting point for the shared analysis; move it to `basket.csv` and Bloomberg next.
- `drafts/team-1/`, `drafts/team-2/`: the teams' drafts (first versions 23 Nov).
- `planning/`: the 16 Nov briefing and the team to-do lists (`planning/team_todo_lists.md`).
- `results/`: outputs and tables (committed).
- `data/`: raw Bloomberg pulls (gitignored, Bloomberg licence). Share them through the shared OneDrive data folder.
