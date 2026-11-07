# Risk dashboard

The one-page A4 risk dashboard ("Risk at a glance"), published roughly monthly. Each
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

### 3. Rebuild the PDF (any machine, no Bloomberg needed)

```
python reports/dashboard/build_report.py 1
```

Repeat steps 2 and 3 until it reads well. If the text overflows the box, shorten it.
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
    page.py             charts and page layout
    risk.py             risk calculations
    bloomberg.py        Bloomberg API client
    preview/            demo page with invented data
  report_00/            one folder per publication
    commentary.md       <- you write here (committed)
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
