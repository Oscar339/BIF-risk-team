# Hand-over: Oscar Butler

## State
- `members/oscar-butler/dashboard testing/code/dashboard_v2.py` is the main fund-wide risk pull
  (v1 = single-portfolio prototype). First successful v2 run 2026-11-06 on the Bloomberg PC;
  outputs in `results/v2/20261106/` (OneDrive only).
- Open TODOs (see `members/oscar-butler/README.md`): BIF risk limits, NAV source (`--nav`),
  short borrow cost.
- GitHub repo set up 2026-11-06 from the Mac. Git login on the Bloomberg PC not yet working.

- 2026-11-07 (bloomberg) Published dashboard pipeline now lives in `reports/dashboard/` (onebox layout
  chosen). `pull_data.py <n>` (Bloomberg) -> `report_XX/data/` + PDF; `build_report.py [n]` rebuilds from
  `report_XX/commentary.md` (any machine); design shared in `reports/dashboard/design/`. Arrows on tiles
  compare with the previous report (red = more risk). See `reports/dashboard/README.md`.
  report_00 pulled 2026-11-07 (10 holdings, all long; NAV = gross proxy, so net shows 100% and breaches
  the 80% limit until cash is filled).
- 2026-11-07 (mac) LIMITS now follow *BIF Fund & Investment Strategy 2026/27* (short ≤20% NAV, cash 5–10%
  guide, position 5–20% of team NAV with team NAV = NAV/8, 5–10 names per team); old gross/net/VaR/10%
  placeholders removed. Limits are computed at build time (page.load_report), so no re-pull needed.
  Report 0: Special Situations position ~200% of team NAV and teams with 0 names breach (NAV still a proxy).
  Oscar confirmed: "5–10 active names" is per team; team weights equal (1/8) for now, may change later. Demo book (preview) is far outside the new limits and
  its commentary mentions the old 200% gross limit: tidy when next changing the design.
- Bloomberg PC venv recreated 2026-11-07 with uv + Python 3.13 (`%LOCALAPPDATA%\envs\bif-risk-team`).
  No git installed on this PC.

## Requests
- [ ] 2026-11-07 for: bloomberg (from: mac) Once Oscar has the fund's start capital (from fund leadership) in
  `members/oscar-butler/dashboard testing/data/fund_capital.csv` (`date,amount`): re-pull report 0 with
  `python reports/dashboard/pull_data.py 0 --force`. The log should say "Capital from ..." and NAV source
  "start capital + P&L since inception". Check cash looks sensible (it is printed as % NAV on the page).
- [ ] 2026-11-07 for: either (from: bloomberg) Write report_00 commentary in
  `reports/dashboard/report_00/commentary.md`, then `python reports/dashboard/build_report.py 0`.
- [ ] 2026-11-06 for: bloomberg (from: mac) Once GitHub works on this PC: `git pull`, check
  `git status` is clean and `git log` shows "Add Claude hand-over setup", then do a test
  `git push` (e.g. tick this request off). Note here if anything failed.

- [ ] 2026-11-06 for: either (from: mac) Fill `dashboard testing/data/fund_cash.csv` with real cash
  balances, then rerun v2 so % NAV figures stop using gross MV as a proxy.
- [ ] 2026-11-06 for: either (from: mac) Financials sleeve (J. Heyworth) not in PORT yet. When it
  exists, add its ID to SLEEVES and SLEEVE_TEAMS in dashboard_v2.py. Other sleeves mapped
  (C. Hook = CIO, S. Dominguez = Chairman).

## Notes
- 2026-11-06 (mac) Bloomberg-PC commits 955a43b/00b7bb9 were never pushed; rebuilt on the Mac
  with dummy cash figures in the README example (originals possibly real) and pushed. Never put
  real cash/NAV figures in tracked files: the repo is public. Oscar to confirm whether the
  original figures were real (only matters for knowing what the PC session wrote).
- Mac Python env: ~/envs/bif-risk-team (Homebrew Python 3.13, requirements.txt installed).
- Risk dashboard renderer: `dashboard testing/code/build_dashboard.py` (+ `dashboard_style.css`).
  Reads `results/v2/<date>/`, writes the one-page A4 risk dashboard in two candidate layouts (onebox preferred; nofactors kept for now)
  to `results/v2/<date>/dashboard/risk_dashboard_<layout>.html/.pdf` (gitignored: contains holdings). Commentary (headline + body) in
  `results/v2/<date>/commentary.md`. `--demo` renders an invented 8-team book to
  `mockups/demo/` (safe to commit). Runs on the Mac with ~/envs/bif-risk-team; no Bloomberg.
  Old static mockups: `dashboard testing/mockups/risk_dashboard_mockup.html`.

## Done
- 2026-11-07 (mac) NAV from start capital: `fund_capital.csv` (date,amount) -> NAV = capital + daily P&L from
  end-of-day holdings, cash = NAV - holdings (`risk.fund_pnl`, `risk.nav_from_capital`). Tested on synthetic
  data only; first real run is the report 0 re-pull above. Empty template created in OneDrive (gitignored).
- 2026-11-07 (mac) Committed + pushed `reports/dashboard/` (code, README, design/preview, report_00/commentary.md),
  `reports/README.md`, `.gitignore` and the static mockup PDF. Checked: no report data/PDF/HTML or
  `metrics_history.csv` tracked; preview and mockup PDFs contain invented data only.
- 2026-11-06 (mac) Created public repo Oscar339/BIF-risk-team, normalised line endings,
  added README setup steps, CLAUDE.md, this hand-over folder, protected `main`.
