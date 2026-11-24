# AI thematic risk report: team to-do lists

Draft, 24 November 2026. When every box below is ticked, `draft.md` holds a full draft of Sections 1 and 2 (everything except our recommendations). Section 3 is written last by the risk team.

## Where everything lives

Repo: https://github.com/Oscar339/BIF-risk-team. Everything is in `reports/thematic/ai-supply-chain/`:

| What | Path | On GitHub? |
|---|---|---|
| **The one draft document** | `draft.md` | Yes |
| Shared basket (tickers, layers) | `basket.csv` | Yes (Team 1 owns it) |
| S&P 500 ex-AI ticker list | `benchmark.csv` | Yes (tickers only, no weights or prices) |
| Shared code | `code/` | Yes |
| Charts for the report | `figures/` (named `fig_<section>_<name>.png`) | Yes |
| Result tables from the shared code (e.g. correlation and shock-count CSVs) | `results/` | Yes |
| Analyst decks and PDFs | `drafts/team-1/`, `drafts/team-2/` | As set up by Oscar |
| This to-do list | `planning/team_todo_lists.md` | As set up by Oscar |
| **Raw Bloomberg pulls** (prices, index weights, SPLC exports) | OneDrive: `Documents/BIF-risk-team-shared-data/ai-supply-chain/bloomberg/` | **No, never commit these** |

**This repo is public: treat every commit as public.** Commit only public-company information, and never BIF holdings, NAV or position sizes. Raw Bloomberg exports (prices, weights, SPLC) stay in the shared OneDrive folder. Derived results go in `results/`, and the numbers you quote go into `draft.md`.

How to work: pull the repo, export from Bloomberg into the shared OneDrive `bloomberg/` folder, run the shared code (it reads from there), save tables to `results/` and charts to `figures/`, write your text into your subsections of `draft.md`, and update each subsection's "Lead / Status" line (Not started / Drafting / Ready for review).

## Order of work
1. Team 1 finishes `basket.csv` and `benchmark.csv`. **Team 2 waits for this before re-running.**
2. Both teams re-run their analysis on Bloomberg prices, in parallel.
3. Both teams write their `draft.md` subsections and Section 2.6 (methods).
4. The risk team reviews and writes Section 3.

## Team 1 (Baily, Johnny, Alex, Dom): Sections 1.1–1.5, 2.1–2.2

**A. Basket and benchmark (do first)**
- [ ] Update `basket.csv`: set `side` to `supplier` or `hyperscaler` so we get a 14-name supply chain basket and a 5-name demand basket.
- [ ] Add Amkor (packaging), Super Micro, Dell and Celestica (servers) to `basket.csv`. Add CoreWeave and GE Vernova with a `notes` entry giving the listing date ("short history").
- [ ] Keep SK Hynix, Samsung and Schneider marked "weekly only" in `notes`.
- [ ] Pull S&P 500 constituents on Bloomberg, remove the basket names, and commit the tickers as `benchmark.csv`. Keep the hand-picked 20 as `side = control`, used only as a secondary check.
- [ ] Tell Team 2 the basket is final.

**B. Correlation code**
- [ ] Turn `code/team1_backing_calcs.py` into `code/basket_correlations.py`: read tickers from `basket.csv` and `benchmark.csv` and take prices from the shared OneDrive `bloomberg/` folder, not yfinance.
- [ ] Output rolling 60- and 90-day average pairwise correlations, raw and market-adjusted, in equal-weighted and market-cap-weighted versions.
- [ ] Save the tables to `results/` and the charts to `figures/` (e.g. `fig_2_1_rolling_corr.png`, `fig_2_2_layers.png`).

**C. Single points of failure**
- [ ] Run Bloomberg SPLC on Nvidia, TSMC, Broadcom, Vertiv and Micron, and save the exports to the shared OneDrive `bloomberg/` folder.
- [ ] Find a source for every "reported" figure, or drop it: $720bn capex, Nvidia 54% from 3 customers, TSMC 68% HPC, Oracle $300bn backlog, OpenAI $1.15tn, HBM shares, TSMC 72% of foundry. Each source goes in the Sources section of `draft.md`.
- [ ] Recompute the average top-five customer share (43%) and the 17 vs 18 companies count on SPLC data.
- [ ] Recompute benchmark concentration (the basket's S&P weight, and Nvidia's) on Bloomberg index weights.

**D. Write in `draft.md`**
- [ ] 1.1 What we mean by AI thematic risk: "one theme, not seven sectors"; the linked sectors (tech, industrials, utilities, real estate).
- [ ] 1.2 The ecosystem: the layers, plus a table of the basket generated from `basket.csv`.
- [ ] 1.3 Single points of failure: customer concentration, supplier bottlenecks, the funding loop (from C).
- [ ] 1.4 Hidden benchmark exposure: the basket's weight in the S&P and Nvidia's weight (from C).
- [ ] 1.5 Past and future moves: performance since 2020, the November 2026 drawdowns, capex guidance and what to watch next.
- [ ] 2.1 Do the stocks move together? Rolling correlations of AI vs benchmark, raw and market-adjusted, split at 30 Nov 2022, and hyperscalers vs suppliers.
- [ ] 2.2 Does spreading across layers diversify? Layer vs chip-design correlations, plus the portfolio comparison from the 7-page piece re-run on the new layers.
- [ ] Fold in the useful parts of the two other supply chain drafts. Drop the S&P weekly −2% sell-off rule and the duplicated slide.
- [ ] Your part of 2.6 (methods): data, dates, windows, weights, market adjustment.

## Team 2 (Guiseppe, Bea, Alexia): Sections 2.3–2.5

**A. Shock code (start once Team 1 says the basket is final)**
- [ ] Write `code/shocks.py`, reading tickers from `basket.csv` (supply chain side) and `benchmark.csv`, with Bloomberg prices from the shared OneDrive `bloomberg/` folder. Port your existing rule from your midterm code.
- [ ] Headline rule: the basket's daily return is beyond ±2.5 standard deviations of its previous 250 trading days (today excluded). Shock days within 5 trading days form one episode. Up and down shocks are counted separately.
- [ ] Label each shock with your gap rule: AI-led if the basket also trails or beats the S&P ex-AI by more than 2.5 sd, broad otherwise.
- [ ] Sensitivity at 2 and 3 sd.

**B. Frequency**
- [ ] Shocks per quarter since 2020, split at 30 Nov 2022. Keep 2010–24 vs 2025–26 as a secondary view where the history allows.
- [ ] Run the same rule on the benchmark basket.
- [ ] Re-run the binomial test and the random-day simulation.
- [ ] Event list: the briefing's 12 events plus DeepSeek (27 Jan 2025) and Nvidia earnings days. Report how many events the rule catches, and which flagged days have no event.

**C. Correlation in shocks**
- [ ] Shock vs calm correlation between the basket and the benchmark, and the AI-led vs broad sell-off table, re-run.
- [ ] Correct for the volatility bias (the Forbes–Rigobon adjustment or market-adjusted returns) and show both.
- [ ] Re-run the midterm supplier case study, keeping the check that leaves out 5 November.
- [ ] Save the tables to `results/` and the charts to `figures/` (e.g. `fig_2_3_shock_counts.png`, `fig_2_4_shock_corr.png`).

**D. Write in `draft.md`**
- [ ] 2.3 What a shock is and how often they happen: the definition, the quarterly counts, the benchmark comparison and the event hit rate.
- [ ] 2.4 What shocks do to diversification: AI-led vs broad, the volatility correction, the midterm case study.
- [ ] 2.5 Why it happens (hypotheses): one paragraph and one piece of evidence each for index concentration, crowded positioning, dependence on capex announcements and passive flows.
- [ ] Your part of 2.6 (methods): the shock rule, episodes, tests and data. Include a worked example (e.g. 5 November 2026).

## Done when
- [ ] Every subsection of 1.1–2.6 in `draft.md` reads "Ready for review".
- [ ] Every chart in `draft.md` is in `figures/` and every number has a source in Sources.
- [ ] No raw Bloomberg export has been committed. They are all in the shared OneDrive folder.
