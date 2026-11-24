# T1-B: Correlation (Team 1)

If this list and [the team to-do lists](../../planning/team_todo_lists.md) ever differ, the to-do lists win.

**Feeds:** `report.md` sections 2.1 and 2.2. **Needs:** T1-A done.
**Code:** `../../code/basket_correlations.py` (from `team1_backing_calcs.py`).
**Outputs:** tables (CSV) in this folder; charts in `../../figures/` (`fig_2_1_*.png`, `fig_2_2_*.png`).

- [ ] Turn `team1_backing_calcs.py` into `basket_correlations.py`: tickers from `basket.csv` and
      `benchmark.csv`, Bloomberg prices from the shared OneDrive `bloomberg/` folder (not yfinance).
- [ ] Rolling 60- and 90-day average pairwise correlation, raw and market-adjusted, equal-weighted
      and market-cap-weighted. Split at 30 Nov 2022. Supply chain vs hyperscalers vs benchmark.
- [ ] Layer vs chip-design correlations; re-run the portfolio comparison from the 7-page piece
      (`../../drafts/team-1/2026-11-23_supply_chain_diversification_7p.pdf`) on the new layers.
- [ ] Re-check the deck's headline numbers (0.44 vs 0.23; 0.31 vs 0.08; hyperscalers 0.80 to 0.54).
- [ ] Write 2.1, 2.2 and your part of 2.6 (methods) in `report.md`.
