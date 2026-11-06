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
- `code/dashboard_v2.py`: fund-wide risk data and metrics (exposure, concentration, liquidity, ex-ante vol, VaR/ES, risk contribution, correlation, betas, factor exposures, P&L, drawdown and attribution by book/sector/sleeve). Outputs to `results/v2/<YYYYMMDD>/`, including one Excel workbook with every table. Stress tests are being built separately.

```
%LOCALAPPDATA%\envs\bif-risk-team\Scripts\python "members\oscar-butler\dashboard testing\code\dashboard_v2.py" --nav <fund NAV in GBP>
```

### TODO: to be filled out

- [ ] **Risk limits.** BIF's limits are needed (e.g. gross/net exposure bands, max single position, sector caps, VaR limit). Fill them into `LIMITS` in `dashboard_v2.py`; the `limits` table then reports OK / BREACH for each.
- [ ] **NAV source.** PORT has no cash, so the fund NAV (including cash) must be passed with `--nav`. Without it, % of NAV figures use gross market value.
- [ ] **Short borrow cost.** Not available through the Bloomberg API; needs another source (SECF or the prime broker) once the fund has shorts.
