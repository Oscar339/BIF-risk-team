# AI supply chain as a thematic risk: method and files

The work behind sections 1 and 2 of [report 0](../README.md). The text itself goes in
[`../report.md`](../report.md). Each task has a folder under [`work/`](work/) with its own README.

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

- `basket.csv`: ticker, name, layer, side (`supplier`, `hyperscaler`, `control`), notes. Team 1 owns it;
  update this file, don't keep private copies.
- `benchmark.csv`: S&P 500 ex-AI tickers (Team 1 adds it; tickers only, no weights or prices).
- `code/`: shared code. Name scripts by what they do (`basket_correlations.py`, `shocks.py`).
  `code/team1_backing_calcs.py` is Team 1's script behind their 23 Nov deck (Yahoo): the starting point.
  Scripts read raw prices from the shared OneDrive folder and write tables to the task's `work/` folder.
- `figures/`: charts used in `report.md`, named `fig_<section>_<name>.png`.
- `work/<task>/`: one folder per task: its README (what to do, inputs, outputs, which section it
  feeds), result tables (CSV) and working notes.
- `drafts/team-1/`, `drafts/team-2/`: the teams' 23 Nov drafts (reference only).
- `planning/`: the 16 Nov briefing and the team to-do lists (`planning/team_todo_lists.md`).
- Raw Bloomberg exports: shared OneDrive folder `BIF-risk-team-shared-data/ai-supply-chain/bloomberg/`,
  never in the repo (Bloomberg licence, and the repo is public).
