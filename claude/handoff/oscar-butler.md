# Hand-over: Oscar Butler

## State
- `members/oscar-butler/dashboard testing/code/dashboard_v2.py` is the main fund-wide risk pull
  (v1 = single-portfolio prototype). First successful v2 run 2026-11-06 on the Bloomberg PC;
  outputs in `results/v2/20261106/` (OneDrive only).
- Open TODOs (see `members/oscar-butler/README.md`): BIF risk limits, NAV source (`--nav`),
  short borrow cost.
- GitHub repo set up 2026-11-06 from the Mac. Git login on the Bloomberg PC not yet working.

## Requests
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
- 2026-11-06 (mac) Created public repo Oscar339/BIF-risk-team, normalised line endings,
  added README setup steps, CLAUDE.md, this hand-over folder, protected `main`.
