"""Risk calculations for the dashboard (pandas/numpy only, no Bloomberg). Used by pull_data.py and the demo."""
from __future__ import annotations

import numpy as np
import pandas as pd

from design import config as C


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.sort_index().ffill().pct_change(fill_method=None).iloc[1:]


def weekly_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.sort_index().ffill().resample("W-FRI").last().pct_change(fill_method=None).iloc[1:]


def exposure(mv: pd.Series, nav: float) -> dict:
    long_, short = mv.clip(lower=0).sum(), mv.clip(upper=0).sum()
    return {"n_long": int((mv > 0).sum()), "n_short": int((mv < 0).sum()),
            "gross_pct_nav": 100 * (long_ - short) / nav, "net_pct_nav": 100 * (long_ + short) / nav}


def concentration(mv: pd.Series, nav: float) -> dict:
    return {"largest_position": str(mv.abs().idxmax()), "largest_position_pct_nav": float(100 * mv.abs().max() / nav)}


def risk_metrics(mv: pd.Series, rets: pd.DataFrame, nav: float, warnings: list[str]):
    """Ex-ante vol, risk contribution share per position, historical VaR/ES with today's holdings."""
    secs = list(mv.index)
    window = rets.reindex(columns=secs).tail(C.COV_WINDOW)
    coverage = window.notna().mean()
    for s in coverage[coverage < 0.9].index:
        warnings.append(f"{s}: only {coverage[s]:.0%} of the last {C.COV_WINDOW} daily returns available (missing = 0)")
    window = window.fillna(0.0)
    w = (mv / nav).to_numpy()
    cov = window.cov().to_numpy() * C.TRADING_DAYS
    port_vol = float(np.sqrt(w @ cov @ w))
    mcr = cov @ w / port_vol if port_vol else np.zeros_like(w)
    share = pd.Series(100 * w * mcr / port_vol if port_vol else np.zeros_like(w), index=mv.index, name="risk_share_pct")

    pos_pnl = rets.reindex(columns=secs).fillna(0.0) * mv  # today's book through every day of history
    hist = pos_pnl.sum(axis=1)
    out = {"ex_ante_vol_pct": 100 * port_vol, "var_history_days": int(len(hist))}
    for cl in (95, 99):
        q = hist.quantile(1 - cl / 100)
        out[f"var_{cl}_gbp"] = float(-q)
        out[f"es_{cl}_gbp"] = float(-hist[hist <= q].mean())
        out[f"var_{cl}_pct_nav"] = 100 * out[f"var_{cl}_gbp"] / nav
        out[f"es_{cl}_pct_nav"] = 100 * out[f"es_{cl}_gbp"] / nav
    hist_df = pd.DataFrame({"pnl_gbp": hist, "pnl_pct_nav": 100 * hist / nav})
    hist_df.index.name = "date"
    return out, share, pos_pnl, hist_df


def var_contributions(pos_pnl: pd.DataFrame) -> pd.DataFrame:
    """Component historical VaR: each position's average P&L over the scenarios around the VaR day,
    rescaled so contributions sum to fund VaR. Positive = adds to VaR."""
    if pos_pnl is None or pos_pnl.empty:
        return pd.DataFrame(columns=["security", "contrib_gbp", "pct"])
    port = pos_pnl.sum(axis=1)
    var = -port.quantile(1 - C.VAR_CONF)
    k = int(round((1 - C.VAR_CONF) * len(port)))
    tail = port.sort_values().index[max(0, k - C.VAR_WINDOW):k + C.VAR_WINDOW + 1]
    c = -pos_pnl.loc[tail].mean()
    c = c * var / c.sum() if c.sum() else c
    out = c.rename("contrib_gbp").reset_index().rename(columns={"index": "security"})
    out.columns = ["security", "contrib_gbp"]
    out["pct"] = 100 * out["contrib_gbp"] / var
    return out


def factor_exposures(mv: pd.Series, wk: pd.DataFrame, nav: float):
    """Weekly OLS on market + factor spreads. Returns (portfolio factor dict, per-stock market beta, portfolio weekly returns)."""
    wk = wk.tail(C.BETA_WEEKS)
    X = pd.DataFrame({"market": wk[C.BENCHMARK]})
    for name, tick in C.FACTORS.items():
        if tick in wk:
            X[name] = wk[tick] - wk[C.BENCHMARK]
    X = X.dropna()
    cols = list(X.columns)

    def ols(y: pd.Series, use):
        d = pd.concat([y, X[use]], axis=1).dropna()
        if len(d) < C.MIN_WEEKS:
            return None
        A = np.column_stack([np.ones(len(d)), d[use].to_numpy()])
        yv = d.iloc[:, 0].to_numpy()
        coef, *_ = np.linalg.lstsq(A, yv, rcond=None)
        resid = yv - A @ coef
        return coef, (1 - resid.var() / yv.var() if yv.var() else np.nan)

    beta = {}
    for s in mv.index:
        if s in wk:
            one = ols(wk[s], ["market"])
            if one:
                beta[s] = one[0][1]
    held = [s for s in mv.index if s in wk]
    port_rets = (wk[held].fillna(0.0) @ (mv / nav).reindex(held)).rename("portfolio")
    port, out = ols(port_rets, cols), {}
    if port:
        coef, r2 = port
        out = {**{f"factor_{c}": float(v) for c, v in zip(cols, coef[1:])}, "factor_r2_systematic_pct": 100 * float(r2)}
    return out, pd.Series(beta, name="beta", dtype=float), port_rets


def rates_sensitivity(port_wk: pd.Series, yields: pd.DataFrame) -> dict:
    """Weekly portfolio return per +100bp in US / UK 10y yields (simple regression)."""
    dy = yields.ffill().resample("W-FRI").last().diff()
    out = {}
    for c in ("us_10y", "uk_10y"):
        if c not in dy:
            continue
        d = pd.concat([port_wk, dy[c]], axis=1, sort=True).dropna().tail(C.BETA_WEEKS)
        if len(d) >= C.MIN_WEEKS and d.iloc[:, 1].var() > 0:
            out[f"rates_sens_{c}_pct_per_100bp"] = 100 * float(d.iloc[:, 0].cov(d.iloc[:, 1]) / d.iloc[:, 1].var())
    return out


def drawdown(hist_pos: pd.DataFrame, prices: pd.DataFrame, nav_today: float | None, cash: pd.Series | None,
             warnings: list[str]) -> dict:
    """Fund drawdown since inception, rebuilt from end-of-day holdings (pos(t-1) x price change(t))."""
    if hist_pos.empty:
        warnings.append("No holdings history found: drawdown not available")
        return {}
    # absent on a date with holdings = not held that day
    pos = hist_pos.pivot_table(index="date", columns="security", values="position", aggfunc="sum").fillna(0.0)
    start = pos.index.min()
    P = prices.sort_index().ffill()
    P = P.loc[P.index >= start - pd.Timedelta(days=7)]
    pos = pos.reindex(pos.index.union(P.index)).sort_index().ffill().reindex(P.index).fillna(0.0)
    px = P.reindex(columns=pos.columns)
    pnl = (pos.shift(1) * px.diff()).fillna(0.0).sum(axis=1)
    mv = pos * px
    net, gross = mv.sum(axis=1), mv.abs().sum(axis=1)
    keep = pnl.index >= start
    pnl, net, gross = pnl[keep], net[keep], gross[keep]
    if cash is not None:
        c = cash.reindex(cash.index.union(pnl.index)).sort_index().ffill().bfill().reindex(pnl.index)
        denom = (net + c).shift(1)
    elif nav_today:
        denom = (nav_today - pnl[::-1].cumsum()[::-1].shift(-1).fillna(0.0)).shift(1)
    else:
        denom = gross.shift(1)
    r = (pnl / denom.replace(0, np.nan)).dropna()
    wealth = (1 + r).cumprod()
    dd = wealth / wealth.cummax() - 1
    if len(r) < C.MIN_DAYS_FOR_STATS:
        warnings.append(f"Only {len(r)} days of fund history: drawdown is indicative")
    return {"perf_start": str(start.date()), "perf_days": int(len(r)),
            "current_drawdown_pct": 100 * float(dd.iloc[-1]) if len(dd) else None,
            "max_drawdown_pct": 100 * float(dd.min()) if len(dd) else None}


def _worst(v: pd.Series, lo, hi):
    """The value furthest outside [lo, hi] and its label; if none is outside, the largest."""
    if v.empty:
        return None, None
    k = v.idxmin() if lo is not None and v.min() < lo else v.idxmax()
    return float(v[k]), k


def limit_values(summary: dict, positions: pd.DataFrame) -> dict[str, tuple]:
    """{limit metric: (value, where)}. Team checks cover sector teams that have a sleeve in PORT."""
    nav, out = summary.get("nav"), {}
    if not nav or positions.empty:
        return out
    out["short_pct_nav"] = (abs(float(100 * positions["mv"].clip(upper=0).sum() / nav)), None)
    cash = summary.get("cash")
    out["cash_pct_nav"] = (None if cash is None else 100 * cash / nav, None)
    teams = [t for t in C.REPORT_TEAMS if t in set(C.SLEEVE_TEAMS.values())]
    p = positions[positions["team"].isin(teams) & (positions["mv"].abs() > 0)]
    sizes = 100 * p["mv"].abs() / (nav * C.TEAM_NAV_SHARE)
    lo, hi = C.LIMITS.get("team_position_pct_team_nav", (None, None))
    v, i = _worst(sizes.reset_index(drop=True), lo, hi)
    out["team_position_pct_team_nav"] = (v, None if i is None else p["team"].iloc[i])
    names = p.groupby("team")["security"].nunique().reindex(teams, fill_value=0).astype(float)
    out["team_names"] = _worst(names, *C.LIMITS.get("team_names", (None, None)))
    return out


def check_limits(summary: dict, positions: pd.DataFrame) -> pd.DataFrame:
    vals, rows = limit_values(summary, positions), []
    for k, (lo, hi) in C.LIMITS.items():
        v, where = vals.get(k, (None, None))
        if v is None or (isinstance(v, float) and np.isnan(v)):
            status = "NO DATA"
        elif (lo is not None and v < lo) or (hi is not None and v > hi):
            status = "OUTSIDE" if k in C.GUIDES else "BREACH"
        else:
            status = "OK"
        rows.append({"metric": k, "value": v, "where": where, "min": lo, "max": hi, "status": status})
    return pd.DataFrame(rows, columns=["metric", "value", "where", "min", "max", "status"])
