# Oscar Butler

Individual research space.

- `code/` scripts
- `notebooks/` Jupyter notebooks
- `data/` inputs (OneDrive only, not in git)
- `results/` outputs (OneDrive only, not in git)
- `dashboard testing/` risk dashboard data pulls (Bloomberg)

## Dashboard testing

Data pulls for a fund-wide risk report. Needs the Bloomberg Terminal open and logged in.

- `code/dashboard_v1.py`: holdings, reference data and price history for one PORT portfolio. Outputs to `results/v1/`.
- `code/dashboard_v2.py`: fund-wide risk data and metrics (exposure, concentration, liquidity, ex-ante vol, VaR/ES, risk contribution, correlation, betas, factor exposures, rates sensitivity, P&L, drawdown and attribution by book/sector/sleeve, fund vs MSCI World), plus market data: MSCI World (price, net/gross total return in USD and GBP, P/E, forward P/E, dividend yield, P/B) and UK/US government bonds (3m/2y/5y/10y/30y yields, SONIA, curve spreads, gilt and Treasury total return indices). 7 years of history by default. Outputs to `results/v2/<YYYYMMDD>/`, including one Excel workbook with every table. Stress tests are being built separately.

```
%LOCALAPPDATA%\envs\bif-risk-team\Scripts\python "members\oscar-butler\dashboard testing\code\dashboard_v2.py"
```

Results and `data/` sync through OneDrive (not git), so they can be opened from any machine; only the pull itself needs the Bloomberg Terminal.

**Fund cash** (`dashboard testing/data/fund_cash.csv`): PORT holds no cash, so NAV = holdings market value + cash from this file. Add a row whenever the cash balance changes (dates as YYYY-MM-DD, cash in GBP); each row applies until the next:

```
date,cash
2026-01-01,1000000
2026-02-01,500000
```

`--nav <NAV>` overrides today's NAV if needed.

### TODO: to be filled out

- [ ] **Risk limits.** BIF's limits are needed (e.g. gross/net exposure bands, max single position, sector caps, VaR limit). Fill them into `LIMITS` in `dashboard_v2.py`; the `limits` table then reports OK / BREACH for each.
- [ ] **Fund cash.** Fill in `data/fund_cash.csv` (above). Until then, % of NAV figures use gross market value.
- [ ] **Short borrow cost.** Not available through the Bloomberg API; needs another source (SECF or the prime broker) once the fund has shorts.
