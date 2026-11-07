"""Step 1: pull the data for one risk dashboard report from Bloomberg, then build its PDF.

Run on a Bloomberg PC with the Terminal open and logged in.

Usage (from the repo folder):
    python reports/dashboard/pull_data.py 0              # report_00
    python reports/dashboard/pull_data.py 1 --nav 3000000
    python reports/dashboard/pull_data.py 1 --force      # re-pull a report that already has data

Pulls only what the dashboard page uses: current fund and sleeve holdings, daily holdings since
inception (for drawdown), GBP prices for the holdings, MSCI World and its factor indices, and
US/UK 10y yields. Writes report_XX/data/ (gitignored, contains holdings), creates
report_XX/commentary.md if needed and builds the PDF.

NAV: PORT holds no cash, so NAV = holdings + cash from data/fund_cash.csv (see design/config.py),
or --nav. With neither, % of NAV figures use gross market value (flagged on the page).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from design import config as C  # noqa: E402
from design import page as P  # noqa: E402
from design import risk as R  # noqa: E402


def load_cash(warnings: list[str]) -> pd.Series | None:
    """Fund cash by date (date,cash). Each row holds until the next."""
    f = next((p for p in C.CASH_FILES if p.exists()), None)
    if f is None:
        warnings.append("No fund_cash.csv found: NAV excludes cash")
        return None
    df = pd.read_csv(f)
    if df.empty:
        warnings.append(f"{f} is empty: NAV excludes cash")
        return None
    df["date"] = pd.to_datetime(df["date"], dayfirst=True)
    df["cash"] = pd.to_numeric(df["cash"].astype(str).str.replace(",", ""), errors="coerce")
    print(f"Cash from {f}")
    return df.dropna().groupby("date")["cash"].last().sort_index()


def team_split(current: pd.DataFrame, fund: pd.DataFrame) -> pd.DataFrame:
    """Each fund position split across the teams whose sleeves hold it (by share of position).
    Anything not in a sleeve is 'Unallocated'. Returns security, team, share."""
    sl = current[current["port_id"].isin(C.SLEEVES)].copy()
    sl["team"] = sl["port_id"].map(lambda p: C.SLEEVE_TEAMS.get(p) or "Unassigned")
    sl = sl.groupby(["security", "team"], as_index=False)["position"].sum()
    sl["share"] = sl["position"] / sl["security"].map(fund["position"])
    sl = sl[sl["security"].isin(fund.index)]
    rest = 1 - sl.groupby("security")["share"].sum().reindex(fund.index).fillna(0.0)
    rest = rest[rest.abs() > 1e-6]
    un = pd.DataFrame({"security": rest.index, "team": "Unallocated", "share": rest.to_numpy()})
    return pd.concat([sl[["security", "team", "share"]], un], ignore_index=True)


def clean(v):
    if isinstance(v, (np.floating, float)):
        return None if math.isnan(v) or math.isinf(v) else float(v)
    if isinstance(v, np.integer):
        return int(v)
    return v


def pull(n: int, nav: float | None = None, force: bool = False) -> Path:
    from design.bloomberg import Bloomberg  # only needed here, so build_report.py works without blpapi

    data = P.report_dir(n) / "data"
    if (data / "summary.json").exists() and not force:
        raise SystemExit(f"{data} already has data. Use the next report number, or --force to re-pull this one.")
    today = dt.date.today()
    start = today - dt.timedelta(days=round(365.25 * C.HISTORY_YEARS))
    ccy = C.BASE_CCY

    with Bloomberg() as bbg:
        print("Pulling current holdings...")
        current = bbg.portfolio([C.FUND, *C.SLEEVES], "PORTFOLIO_DATA")
        print(f"Pulling daily holdings since {C.INCEPTION} (for drawdown)...")
        hist, _ = bbg.holdings_history([C.FUND], C.INCEPTION, today)
        universe = sorted(set(current.loc[current["port_id"] == C.FUND, "security"]) | set(hist["security"]))
        if not universe:
            raise SystemExit(f"No holdings found for {C.FUND}. Bloomberg warnings: {bbg.warnings}")
        print(f"Pulling {C.HISTORY_YEARS}y {ccy} prices for {len(universe)} securities, MSCI World and factors...")
        px = bbg.history(universe + [C.BENCHMARK, C.BENCHMARK_TR, *C.FACTORS.values()], ["PX_LAST"], start, today, currency=ccy)
        prices = px.pivot(index="date", columns="security", values="PX_LAST").sort_index()
        print("Pulling US/UK 10y yields...")
        y = bbg.history(list(C.YIELDS), ["PX_LAST"], start, today)
        yields = y.pivot(index="date", columns="security", values="PX_LAST").rename(columns=C.YIELDS).sort_index()
        warnings = bbg.warnings

    # Current fund positions (signed market value in base currency) and NAV
    fund = current[current["port_id"] == C.FUND].groupby("security")[["position", "market_value"]].sum()
    mv = (np.sign(fund["position"]) * fund["market_value"].abs()).rename("mv")
    cash = load_cash(warnings)
    cash_today = None
    if cash is not None and len(cash.loc[:pd.Timestamp(today)]):
        cash_today = float(cash.loc[:pd.Timestamp(today)].iloc[-1])
    if nav:
        nav_source = "user (--nav)"
    elif cash_today is not None:
        nav, nav_source = float(mv.sum() + cash_today), "holdings + cash"
    else:
        nav, nav_source = float(mv.abs().sum()), "proxy: gross market value (no cash; fill fund_cash.csv or pass --nav)"
        warnings.append("NAV not available: all % of NAV figures use gross market value")

    rets, wk = R.daily_returns(prices), R.weekly_returns(prices)
    factors, beta, port_wk = R.factor_exposures(mv, wk, nav)
    risk, share, pos_pnl, hist_pnl = R.risk_metrics(mv, rets, nav, warnings)
    summary = {
        "report": n, "as_of": str(today), "fund": C.FUND, "base_ccy": ccy, "nav": nav, "nav_source": nav_source,
        "cash": cash_today, **R.exposure(mv, nav), **R.concentration(mv, nav),
        "beta": float((mv * beta.reindex(mv.index)).sum() / nav),  # NAV-weighted stock betas to MSCI World
        **risk, **factors, **R.rates_sensitivity(port_wk, yields),
        **R.drawdown(hist[hist["port_id"] == C.FUND], prices, nav if nav_source.startswith("user") else None, cash, warnings),
    }
    summary = {k: clean(v) for k, v in summary.items()}

    split = team_split(current, fund)
    positions = split.assign(mv=split["security"].map(mv) * split["share"],
                             risk_share_pct=split["security"].map(share) * split["share"])

    data.mkdir(parents=True, exist_ok=True)
    (data / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    positions[["security", "team", "mv", "risk_share_pct"]].to_csv(data / "positions.csv", index=False)
    R.var_contributions(pos_pnl).to_csv(data / "var_contribution.csv", index=False)
    hist_pnl.to_csv(data / "var_hist_pnl.csv")
    R.check_limits(summary).to_csv(data / "limits.csv", index=False)
    (data / "warnings.txt").write_text("\n".join(warnings), encoding="utf-8")

    print(f"\nReport {n}, as of {today}. NAV £{nav:,.0f} ({nav_source})")
    print(f"Gross {summary['gross_pct_nav']:.1f}% | Net {summary['net_pct_nav']:+.1f}% | Beta {summary['beta']:.2f} | "
          f"Ex-ante vol {summary['ex_ante_vol_pct']:.1f}% | VaR99 {summary['var_99_pct_nav']:.2f}%")
    if warnings:
        print(f"{len(warnings)} warnings -> {data / 'warnings.txt'}")
    print(f"Data: {data}")
    return data


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", type=int, help="Report number, e.g. 0 for report_00 (use the next unused number)")
    ap.add_argument("--nav", type=float, help="Fund NAV in GBP including cash (overrides fund_cash.csv)")
    ap.add_argument("--force", action="store_true", help="Overwrite this report's existing data")
    a = ap.parse_args()
    pull(a.report, a.nav, a.force)
    P.ensure_commentary(a.report)
    from build_report import build  # noqa: E402

    build(a.report)
