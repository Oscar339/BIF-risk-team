# AI supply chain as a thematic risk: method and code

The code and the shared basket behind sections 1 and 2 of [report 0](../README.md). Everything
else (the report itself, to-do lists, results, charts, Bloomberg data) is in the shared OneDrive
folder `BIF-risk-team-shared-data/report0/`. Start with `START HERE.docx` there.

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

## Where code reads and writes

Scripts read raw Bloomberg exports from, and write results to, the shared OneDrive folder, never
the repo. Its path differs per person, so scripts take it from the `BIF_SHARED` environment
variable (the path to your `BIF-risk-team-shared-data` folder or shortcut), for example:

```python
import os
from pathlib import Path
SHARED = Path(os.environ["BIF_SHARED"]) / "report0"
prices = SHARED / "bloomberg" / "basket_prices_20261125.csv"   # input
out = SHARED / "work" / "t1-b-correlation"                       # tables
figs = SHARED / "figures"                                        # charts, fig_<section>_<name>.png
```

The repo is public: never commit BIF holdings, NAV, position sizes or raw Bloomberg data.
