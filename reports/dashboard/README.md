# Risk dashboard and risk pages

The Risk team's pages in the BIF Monthly Research Review, published monthly (on the 7th, covering
the previous month). One PDF per report:

- **R1**: the one-page A4 risk dashboard ("Risk summary"), built from the Bloomberg pull.
- **R2, R3, ...**: free pages the Risk team fills each month (stress tests, modelling, advice to
  the teams, thematic pieces, a risk view of recent events), written in `pages.md`. Each
publication is a numbered report folder: `report_00`, `report_01`, …

## Making a report

All commands run from the repo folder (`BIF/`). Python is the team venv, see the
[root README](../../README.md) for setting it up. On Windows:
`%LOCALAPPDATA%\envs\bif-risk-team\Scripts\python`.

### 1. Pull the data (Bloomberg PC)

The Terminal must be open and logged in. Use the next unused report number:

```
python reports/dashboard/pull_data.py 1
```

This takes a few minutes. It pulls the holdings and prices, computes the risk numbers,
saves them in `report_01/data/`, and **builds the PDF automatically**:

```
reports/dashboard/report_01/risk_dashboard_report_01.pdf
```

The PDF already has every number and chart. Only the commentary box is a grey placeholder.

**NAV.** BIF is a simulated fund, so PORT holds no cash. Put the fund's start capital in
`members/oscar-butler/dashboard testing/data/fund_capital.csv` (OneDrive only, never git):

```
date,amount
2026-10-01,10000000
```

Add a row for any later top-up (+) or withdrawal (−). The pull then sets NAV = capital + P&L
since inception (rebuilt from end-of-day holdings, dividends ignored) and cash = NAV − holdings.
Without it, a cash file (`fund_cash.csv`, `date,cash`) is used if filled; otherwise the % NAV
figures use gross market value and the page says so. `--nav 3000000` overrides NAV for one pull.

### 2. Write the commentary (any machine)

Open **`reports/dashboard/report_01/commentary.md`**. It is the only file you edit. Type
under each heading:

| Heading | What goes there |
|---|---|
| `## authors` | Byline, e.g. `Risk team: A. Smith, B. Jones` |
| `## headline` | One line: the risk story this period |
| `## body` | About 100 words. Blank line = new paragraph; start a line with `- ` for a bullet |

The grey `<!-- ... -->` comments are hints and never appear on the PDF.

### 2b. Write the free pages (any machine)

Open **`reports/dashboard/report_01/pages.md`** (created on the first build). Every `# page`
heading is one A4 page; the file starts with two (R2, R3). Add or delete `# page` sections as
needed. Under each, set the header, then write anything:

```
# page
kicker: Stress test
title: If 2022 happened again
byline: Risk team: A. Smith
sources: S01 Bloomberg prices to 30 Nov 2026. Shocks are assumptions, not forecasts.

Plain paragraphs, **bold**, *italic*, ## sub-heading, ### small heading, - bullets, 1. numbers.
| Markdown | table |            numbers right-align automatically
![Title | subtitle | Source S01](my_chart.svg)      file in report_01/figures/; {height=60mm} after it to cap height
> **Box title**                  beige box (start with "> !" on its own line for a blue box)
> Box text
::: tiles                        number tiles, one per line: label | value | note
::: cols                         side by side; a line with ||| starts the next column ("::: cols 3:2" sets widths)
::: text2                        one text block flowing over two columns
:::                              closes any ::: block
Note: small grey footnote
```

The preview `design/preview/pages.md` is a full worked example (a stress test and a thematic page).

Figures: make them however you like (PNG or SVG). For the house style from Python, run from
`reports/dashboard/`:

```python
from design.page import save_figure, INK, BLUE, AMBER, LIGHT, MUTED   # also sets fonts
fig, ax = plt.subplots(figsize=(7.2, 2.4))   # 7.2in = full page width
...
save_figure(fig, "report_01/figures/my_chart.svg")
```

If a page has too much content, the build prints a warning and the PDF shows a red bar on that
page: cut text or shrink a figure. `pages.md` and `figures/` are gitignored (OneDrive only), so
naming holdings there is fine.

Leave market narrative to Investment Reporting: write about events only as they affect the
fund's risk.

### 3. Rebuild the PDF (any machine, no Bloomberg needed)

```
python reports/dashboard/build_report.py 1
```

Repeat steps 2 and 3 until it reads well. If the text overflows its box or page, the build warns
and the PDF shows a red bar: shorten it.
If the PDF doesn't update, close it in your PDF viewer first.

### 4. Save the record

Commit `commentary.md` (it is public on GitHub, so **no holdings, position sizes, NAV or £
figures** in it). The data and PDF stay in OneDrive only and are gitignored.

## Arrows on the headline tiles

Each tile compares with the previous report folder that has data:

- **▲ / ▼** shows whether the number went up or down.
- **Red** means risk rose, **green** means risk fell, and grey means unchanged.
  - VaR, ES, volatility, gross and largest position: higher is more risk.
  - Beta and net: further from zero is more risk.
  - Drawdown: more negative is more risk.
- Report 0 has nothing to compare against, so it shows "first report".

`metrics_history.csv` lists the headline numbers of every report. It is rebuilt from the
report folders on each build, so the report folders are the record. Never delete an old
report's `data/`.

## Folder layout

```
reports/dashboard/
  pull_data.py          step 1, Bloomberg pull (then builds the PDF)
  build_report.py       step 3, rebuild the PDF from data + commentary
  design/               shared by every report: change the look here, once
    config.py           fund and sleeve IDs, sleeve -> team map, limits, tile list, method settings
    style.css           page styling
    page.py             charts and page layout (dashboard, page shell, PDF)
    pages.py            free pages: reads pages.md
    risk.py             risk calculations
    bloomberg.py        Bloomberg API client
    preview/            demo pages with invented data (pages.md = worked example)
  report_00/            one folder per publication
    commentary.md       <- you write here: dashboard text (committed)
    pages.md            <- you write here: free pages R2+ (OneDrive only)
    figures/            charts for pages.md (OneDrive only)
    data/               pulled data (OneDrive only)
    risk_dashboard_report_00.pdf
```

## Changing the design

Edit files in `design/`. Then preview with invented data (no Bloomberg, safe to commit):

```
python reports/dashboard/build_report.py --demo
```

The preview goes to `design/preview/risk_dashboard_preview.pdf`. Rebuilding an old report
uses the current design, so old PDFs change if you rebuild them.

## Settings to keep up to date (`design/config.py`)

- `LIMITS`: mandate limits, taken from *BIF Fund & Investment Strategy 2026/27*: short ≤ 20% NAV,
  cash 5–10% NAV (a guide, so shown as "Outside" rather than "Breach"), each position 5–20% of its
  team's NAV, 5–10 names per team. Team NAV = fund NAV × `TEAM_NAV_SHARE` (1/8, equal weighting).
  Team rows show the team furthest outside the range. Limits are checked when the PDF is built, so
  changing them and rebuilding updates old reports too. Not checked automatically: market cap, the
  30% subsector/theme cap and the Sharpe target.
- `SLEEVES` / `SLEEVE_TEAMS`: add new sleeves when they appear in PORT (Financials is still missing).
- `INCEPTION`: start of the fund year (drawdown is measured from here).

## Method notes

- VaR/ES: historical simulation running today's holdings through 5 years of daily GBP
  prices. Dividends are ignored.
- Ex-ante vol and risk share: 252-day covariance. Beta, factors and rates: 104-week regressions.
- Drawdown: daily P&L rebuilt from end-of-day PORT holdings since `INCEPTION`.
- A position held by several sleeves is split across their teams in proportion to the
  position. Anything not in a sleeve shows as "Unallocated".
