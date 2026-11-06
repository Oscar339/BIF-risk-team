"""Dashboard v2: pull BIF fund-wide risk data from Bloomberg and compute risk metrics.

Covers exposure, concentration, liquidity, risk (vol, VaR/ES, risk contribution,
correlation, betas, factor exposures) and performance (P&L, drawdown, attribution).
Stress tests are out of scope (built separately).

Needs the Bloomberg Terminal open and logged in on this machine.

Usage:
    python dashboard_v2.py [--nav 3000000] [--ccy GBP] [--years 3]

--nav is fund NAV in base currency (including cash). PORT holds no cash, so without
it every "% of NAV" figure uses gross market value as a stand-in (flagged in output).

Outputs go to members/oscar-butler/dashboard testing/results/v2/<YYYYMMDD>/:
one CSV per table, risk_data_<date>.xlsx with every table as a sheet, summary.json
with headline numbers, and warnings.txt.

Known approximations:
- Prices are PX_LAST converted to base currency; dividends are ignored.
- Realised P&L is rebuilt from end-of-day holdings: pos(t-1) * price change(t).
  Intraday trading P&L and costs are not captured.
- Without --nav, returns are P&L / previous day's gross market value.
- Short borrow cost is not available through the API (use SECF / prime broker).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import blpapi
import numpy as np
import pandas as pd

HOST, PORT = "localhost", 8194
REFDATA = "//blp/refdata"
RESULTS_DIR = Path(__file__).resolve().parents[1] / "results" / "v2"

# ---------------------------------------------------------------- configuration
FUND = "U15794802-9231"  # BIF Portfolio 2026/27:All
SLEEVES = {  # member sleeves, from PRTU
    "U15794802-9236": "A. Jeffery",
    "U15794802-9232": "C. Hook",
    "U15794802-9237": "F. Howe",
    "U15794802-9307": "G. Smith",
    "U15794802-9233": "J. Wilczewski",
    "U15794802-9235": "L. Folwer",
    "U15794802-9234": "M. Yadukha",
    "U15794802-9238": "S. Dominguez",
    "U15794802-9308": "Y. Atasay",
}
INCEPTION = dt.date(2026, 10, 1)  # earliest date to search for holdings

BENCHMARK = "MXWO Index"  # MSCI World
FACTORS = {  # MSCI World factor indices; exposure is to (factor index - MSCI World)
    "value": "M1WO000V Index",
    "momentum": "M1WOMOM Index",
    "quality": "M1WOQU Index",
    "min_vol": "M1WOMVOL Index",
    "small_cap": "M1WOSC Index",
}

# Risk limits: {summary metric: (min, max)}, None = no bound. Metric names are the
# keys of summary.json. TODO: fill in from BIF risk policy (see README), e.g.
#   "gross_pct_nav": (None, 200), "net_pct_nav": (-20, 80),
#   "largest_position_pct_nav": (None, 10), "var_99_pct_nav": (None, 3),
LIMITS: dict[str, tuple[float | None, float | None]] = {}

ADV_PARTICIPATION = 0.20  # share of 20-day average volume we could trade per day
LIQUIDITY_BUCKETS = [0, 1, 5, 20, np.inf]
LIQUIDITY_LABELS = ["<1 day", "1-5 days", "5-20 days", ">20 days"]
TRADING_DAYS = 252
COV_WINDOW = 252  # daily returns used for ex-ante vol, risk contribution, correlation
BETA_WEEKS = 104  # weekly returns used for betas / factor regressions
MIN_WEEKS = 26  # minimum weekly observations for a regression
RISK_FREE_RATE = 0.0  # annual, for Sharpe

REF_FIELDS = {
    "NAME": "name",
    "SECURITY_TYP": "security_type",
    "CRNCY": "currency",
    "GICS_SECTOR_NAME": "sector",
    "GICS_INDUSTRY_NAME": "industry",
    "CNTRY_OF_RISK": "country",
    "PX_LAST": "price_local",
    "CRNCY_ADJ_PX_LAST": "price_base",
    "CRNCY_ADJ_MKT_CAP": "mkt_cap_base",
    "EQY_BETA": "beta_bbg",
    "VOLATILITY_90D": "vol_90d",
    "VOLUME_AVG_20D": "adv_20d",
    "EQY_FLOAT": "float_mn",
    "SHORT_INT": "short_interest",
    "SHORT_INT_RATIO": "days_to_cover",
    "PE_RATIO": "pe_ratio",
    "EQY_DVD_YLD_IND": "div_yield",
}
NUMERIC = ["price_local", "price_base", "mkt_cap_base", "beta_bbg", "vol_90d", "adv_20d",
           "float_mn", "short_interest", "days_to_cover", "pe_ratio", "div_yield"]


# ---------------------------------------------------------------- Bloomberg client
def _to_py(el: blpapi.Element):
    """Convert a blpapi Element into plain Python (dicts, lists, values)."""
    if el.isArray():
        return [_to_py(v) if isinstance(v, blpapi.Element) else v for v in el.values()]
    if el.isComplexType():
        return {str(e.name()): _to_py(e) for e in el.elements()}
    return el.getValue()


class Bloomberg:
    """Minimal Bloomberg reference/historical/portfolio data client."""

    def __init__(self, host: str = HOST, port: int = PORT, timeout_ms: int = 30000):
        opts = blpapi.SessionOptions()
        opts.setServerHost(host)
        opts.setServerPort(port)
        self.session = blpapi.Session(opts)
        self.timeout_ms = timeout_ms
        self.warnings: list[str] = []
        if not self.session.start():
            raise ConnectionError("Could not start Bloomberg session. Is the Terminal open and logged in?")
        if not self.session.openService(REFDATA):
            raise ConnectionError(f"Could not open {REFDATA}")
        self.service = self.session.getService(REFDATA)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.session.stop()

    def _send(self, request) -> list[blpapi.Message]:
        self.session.sendRequest(request)
        msgs = []
        while True:
            ev = self.session.nextEvent(self.timeout_ms)
            etype = ev.eventType()
            if etype == blpapi.Event.TIMEOUT:
                raise TimeoutError("Bloomberg request timed out")
            for msg in ev:
                if etype in (blpapi.Event.PARTIAL_RESPONSE, blpapi.Event.RESPONSE):
                    if msg.hasElement("responseError"):
                        raise RuntimeError(str(msg.getElement("responseError")))
                    msgs.append(msg)
            if etype == blpapi.Event.RESPONSE:
                return msgs

    def _collect_errors(self, sd: blpapi.Element, sec: str) -> bool:
        """Record security/field errors as warnings. Returns False if the whole security failed."""
        if sd.hasElement("securityError"):
            err = sd.getElement("securityError").getElementAsString("message")
            self.warnings.append(f"{sec}: {err}")
            return False
        if sd.hasElement("fieldExceptions"):
            for fe in sd.getElement("fieldExceptions").values():
                field = fe.getElementAsString("fieldId")
                msg = fe.getElement("errorInfo").getElementAsString("message")
                self.warnings.append(f"{sec} / {field}: {msg}")
        return True

    def reference(self, securities, fields, overrides: dict | None = None,
                  request_type: str = "ReferenceDataRequest") -> pd.DataFrame:
        """Current values: one row per security, one column per field."""
        req = self.service.createRequest(request_type)
        for s in securities:
            req.getElement("securities").appendValue(s)
        for f in fields:
            req.getElement("fields").appendValue(f)
        for k, v in (overrides or {}).items():
            o = req.getElement("overrides").appendElement()
            o.setElement("fieldId", k)
            o.setElement("value", v)

        rows = {}
        for msg in self._send(req):
            for sd in msg.getElement("securityData").values():
                sec = sd.getElementAsString("security")
                if self._collect_errors(sd, sec):
                    rows[sec] = _to_py(sd.getElement("fieldData"))
        df = pd.DataFrame.from_dict(rows, orient="index")
        df.index.name = "security"
        return df.reindex(columns=list(fields))

    def history(self, securities, fields, start: dt.date, end: dt.date,
                currency: str | None = None) -> pd.DataFrame:
        """Daily history in long format: date, security, <fields>."""
        req = self.service.createRequest("HistoricalDataRequest")
        for s in securities:
            req.getElement("securities").appendValue(s)
        for f in fields:
            req.getElement("fields").appendValue(f)
        req.set("startDate", start.strftime("%Y%m%d"))
        req.set("endDate", end.strftime("%Y%m%d"))
        req.set("periodicitySelection", "DAILY")
        if currency:
            req.set("currency", currency)

        frames = []
        for msg in self._send(req):
            sd = msg.getElement("securityData")
            sec = sd.getElementAsString("security")
            if not self._collect_errors(sd, sec):
                continue
            data = _to_py(sd.getElement("fieldData"))
            if data:
                frame = pd.DataFrame(data)
                frame["security"] = sec
                frames.append(frame)
        if not frames:
            return pd.DataFrame(columns=["date", "security", *fields])
        out = pd.concat(frames, ignore_index=True)
        out["date"] = pd.to_datetime(out["date"])
        return out[["date", "security", *fields]]

    def portfolio(self, port_ids, field: str = "PORTFOLIO_DATA",
                  as_of: dt.date | None = None) -> pd.DataFrame:
        """Holdings of PORT portfolios in long format: port_id, security, position[, market_value, ...].

        as_of pulls holdings as at a past date (REFERENCE_DATE override).
        """
        overrides = {"REFERENCE_DATE": as_of.strftime("%Y%m%d")} if as_of else None
        ref = self.reference([f"{p} Client" for p in port_ids], [field], overrides,
                             request_type="PortfolioDataRequest")
        frames = []
        for sec, val in ref[field].items():
            if isinstance(val, list) and val:
                f = pd.DataFrame(val)
                f["port_id"] = sec.rsplit(" ", 1)[0]
                frames.append(f)
        if not frames:
            return pd.DataFrame(columns=["port_id", "security", "position"])
        df = pd.concat(frames, ignore_index=True)
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        return df


# ---------------------------------------------------------------- data pulls
def holdings_history(bbg: Bloomberg, port_ids, start: dt.date, end: dt.date) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    """End-of-day positions for every business day in [start, end]. Returns (long frame, dates queried)."""
    dates = pd.bdate_range(start, end)
    frames = []
    for d in dates:
        h = bbg.portfolio(port_ids, "PORTFOLIO_MPOSITION", as_of=d.date())
        if not h.empty:
            h["date"] = d
            frames.append(h[["date", "port_id", "security", "position"]])
    if not frames:
        return pd.DataFrame(columns=["date", "port_id", "security", "position"]), dates
    return pd.concat(frames, ignore_index=True), dates


def normalise_ccy(c) -> str:
    """GBp -> GBP, ZAr -> ZAR, etc. (minor-unit quotes)."""
    return c.upper() if isinstance(c, str) else c


# ---------------------------------------------------------------- exposure
def exposure_summary(mv: pd.Series, nav: float, beta_bbg: pd.Series, beta_calc: pd.Series) -> dict:
    long_, short = mv.clip(lower=0).sum(), mv.clip(upper=0).sum()
    gross, net = long_ - short, long_ + short
    pct = lambda x: 100 * x / nav  # noqa: E731
    return {
        "n_long": int((mv > 0).sum()),
        "n_short": int((mv < 0).sum()),
        "long_mv": long_, "short_mv": short, "gross_mv": gross, "net_mv": net,
        "long_pct_nav": pct(long_), "short_pct_nav": pct(short),
        "gross_pct_nav": pct(gross), "net_pct_nav": pct(net),
        "long_short_ratio": long_ / -short if short else np.nan,
        "beta_adj_net_pct_nav_bbg": pct((mv * beta_bbg.reindex(mv.index)).sum()),
        "beta_adj_net_pct_nav_calc": pct((mv * beta_calc.reindex(mv.index)).sum()),
    }


def group_exposure(pos: pd.DataFrame, dims, nav: float) -> pd.DataFrame:
    """Long/short/net/gross by each dimension, stacked into one table."""
    frames = []
    for dim in dims:
        g = (pos.assign(long=pos["mv"].clip(lower=0), short=pos["mv"].clip(upper=0))
             .groupby(pos[dim].fillna("Unknown"))[["long", "short"]].sum())
        g["net"] = g["long"] + g["short"]
        g["gross"] = g["long"] - g["short"]
        for c in ["long", "short", "net", "gross"]:
            g[f"{c}_pct_nav"] = 100 * g[c] / nav
        g = g.sort_values("gross", ascending=False).reset_index(names="bucket")
        g.insert(0, "dimension", dim)
        frames.append(g)
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------- concentration & liquidity
def concentration(pos: pd.DataFrame) -> dict:
    gross = pos["mv"].abs().sum()
    wg = pos["mv"].abs() / gross
    hhi = float((wg ** 2).sum())
    return {
        "largest_position": pos["mv"].abs().idxmax(),
        "largest_position_pct_nav": float(pos["weight_nav"].abs().max() * 100),
        "largest_long_pct_nav": float(pos["weight_nav"].clip(lower=0).max() * 100),
        "largest_short_pct_nav": float(pos["weight_nav"].clip(upper=0).min() * 100),
        "top5_pct_gross": float(wg.nlargest(5).sum() * 100),
        "top10_pct_gross": float(wg.nlargest(10).sum() * 100),
        "hhi": hhi,
        "effective_n_positions": 1 / hhi if hhi else np.nan,
    }


def liquidity(pos: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    liq = pos[["name", "position", "mv", "adv_20d", "price_base", "short_interest",
               "float_mn", "days_to_cover"]].copy()
    liq["adv_20d_value_base"] = liq["adv_20d"] * liq["price_base"]
    liq["pct_of_adv"] = 100 * liq["position"].abs() / liq["adv_20d"]
    liq["days_to_liquidate"] = liq["position"].abs() / (liq["adv_20d"] * ADV_PARTICIPATION)
    liq["short_interest_pct_float"] = 100 * liq["short_interest"] / (liq["float_mn"] * 1e6)
    liq["liquidity_bucket"] = pd.cut(liq["days_to_liquidate"], LIQUIDITY_BUCKETS,
                                     labels=LIQUIDITY_LABELS, right=False)
    gross = liq["mv"].abs().sum()
    buckets = (liq.groupby("liquidity_bucket", observed=False)["mv"]
               .apply(lambda s: 100 * s.abs().sum() / gross)
               .rename("pct_gross").reset_index())
    buckets["cum_pct_gross"] = buckets["pct_gross"].cumsum()
    return liq.sort_values("days_to_liquidate", ascending=False), buckets


# ---------------------------------------------------------------- risk
def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.sort_index().ffill().pct_change(fill_method=None).iloc[1:]


def weekly_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.sort_index().ffill().resample("W-FRI").last().pct_change(fill_method=None).iloc[1:]


def risk_metrics(pos: pd.DataFrame, rets: pd.DataFrame, nav: float, warnings: list[str]):
    """Ex-ante vol, risk contribution, historical/parametric VaR & ES, correlation."""
    secs = list(pos.index)
    window = rets[secs].tail(COV_WINDOW)
    coverage = window.notna().mean()
    for s in coverage[coverage < 0.9].index:
        warnings.append(f"{s}: only {coverage[s]:.0%} of the last {COV_WINDOW} daily returns available "
                        f"(missing treated as 0)")
    window = window.fillna(0.0)

    w = (pos["mv"] / nav).to_numpy()
    cov = window.cov().to_numpy() * TRADING_DAYS
    port_vol = float(np.sqrt(w @ cov @ w))
    mcr = cov @ w / port_vol if port_vol else np.zeros_like(w)
    contrib = pd.DataFrame({
        "name": pos["name"], "sector": pos["sector"],
        "weight_pct_nav": 100 * w,
        "standalone_vol_pct": 100 * np.sqrt(np.diag(cov)),
        "marginal_contrib_pct": 100 * mcr,
        "risk_contrib_pct_vol": 100 * w * mcr,  # sums to portfolio vol
        "risk_contrib_share_pct": 100 * w * mcr / port_vol if port_vol else np.nan,  # sums to 100
    }, index=pos.index).sort_values("risk_contrib_share_pct", ascending=False)

    # Historical simulation: today's holdings through every day of history
    hist_pnl = rets[secs].fillna(0.0) @ pos["mv"]
    var = {}
    for cl in (95, 99):
        q = hist_pnl.quantile(1 - cl / 100)
        var[f"var_{cl}_gbp"] = float(-q)
        var[f"es_{cl}_gbp"] = float(-hist_pnl[hist_pnl <= q].mean())
        var[f"var_{cl}_pct_nav"] = 100 * var[f"var_{cl}_gbp"] / nav
        var[f"es_{cl}_pct_nav"] = 100 * var[f"es_{cl}_gbp"] / nav
    daily_vol = port_vol / np.sqrt(TRADING_DAYS)
    var["var_95_parametric_pct_nav"] = 100 * 1.645 * daily_vol
    var["var_99_parametric_pct_nav"] = 100 * 2.326 * daily_vol
    var["var_history_days"] = int(len(hist_pnl))

    corr = window.corr()
    sector_contrib = (contrib.groupby("sector")[["weight_pct_nav", "risk_contrib_pct_vol",
                                                 "risk_contrib_share_pct"]].sum()
                      .sort_values("risk_contrib_share_pct", ascending=False).reset_index())
    hist_pnl = hist_pnl.rename("pnl_gbp").to_frame()
    hist_pnl["pnl_pct_nav"] = 100 * hist_pnl["pnl_gbp"] / nav
    return {"ex_ante_vol_pct": 100 * port_vol, **var}, contrib, sector_contrib, corr, hist_pnl


def factor_exposures(pos: pd.DataFrame, wk: pd.DataFrame, nav: float):
    """Weekly OLS of each stock on market + factor spreads. Returns (per-stock table, portfolio row, simple betas)."""
    wk = wk.tail(BETA_WEEKS)
    X = pd.DataFrame({"market": wk[BENCHMARK]})
    for name, tick in FACTORS.items():
        X[name] = wk[tick] - wk[BENCHMARK]
    X = X.dropna()

    def ols(y: pd.Series, cols):
        d = pd.concat([y, X[cols]], axis=1).dropna()
        if len(d) < MIN_WEEKS:
            return None
        A = np.column_stack([np.ones(len(d)), d[cols].to_numpy()])
        yv = d.iloc[:, 0].to_numpy()
        coef, *_ = np.linalg.lstsq(A, yv, rcond=None)
        resid = yv - A @ coef
        r2 = 1 - resid.var() / yv.var() if yv.var() else np.nan
        return coef, r2, len(d), resid.std() * np.sqrt(52)

    cols = list(X.columns)
    rows, beta = {}, {}
    for s in pos.index:
        if s not in wk:
            continue
        one = ols(wk[s], ["market"])
        if one:
            beta[s] = one[0][1]
        full = ols(wk[s], cols)
        if full:
            coef, r2, n, idio = full
            rows[s] = {"alpha_weekly": coef[0], **dict(zip(cols, coef[1:])),
                       "r2": r2, "idio_vol_pct": 100 * idio, "n_weeks": n}
    per_stock = pd.DataFrame.from_dict(rows, orient="index")
    per_stock.index.name = "security"

    w = pos["mv"] / nav
    port_rets = (wk[[s for s in pos.index if s in wk]].fillna(0.0) @ w.reindex(
        [s for s in pos.index if s in wk])).rename("portfolio")
    port = ols(port_rets, cols)
    port_row = {}
    if port:
        coef, r2, n, idio = port
        port_row = {**{f"factor_{c}": v for c, v in zip(cols, coef[1:])},
                    "factor_r2_systematic_pct": 100 * r2, "factor_idio_vol_pct": 100 * idio,
                    "factor_n_weeks": n}
    return per_stock, port_row, pd.Series(beta, name="beta_calc")


# ---------------------------------------------------------------- performance
def positions_wide(hist: pd.DataFrame, port_id: str, sampled: pd.DatetimeIndex,
                   price_dates: pd.DatetimeIndex) -> pd.DataFrame | None:
    h = hist[hist["port_id"] == port_id]
    if h.empty:
        return None
    w = h.pivot_table(index="date", columns="security", values="position", aggfunc="sum")
    w = w.reindex(sampled).fillna(0.0)  # absent on a queried date = not held
    return w.reindex(price_dates, method="ffill").fillna(0.0)


def performance(hist, sampled, prices, ref, nav_today, warnings):
    """Rebuild daily P&L, exposure and returns from end-of-day holdings."""
    fund_h = hist[hist["port_id"] == FUND]
    if fund_h.empty:
        warnings.append("No holdings history found; performance skipped")
        return {}, {}
    start = fund_h["date"].min()
    P = prices.sort_index().ffill()
    dates = P.index[P.index >= start - pd.Timedelta(days=7)]
    P = P.loc[dates]

    def pnl_for(port_id):
        pos = positions_wide(hist, port_id, sampled, dates)
        if pos is None:
            return None, None
        px = P.reindex(columns=pos.columns)
        pnl = (pos.shift(1) * px.diff()).fillna(0.0)
        return pos, pnl

    pos, pnl = pnl_for(FUND)
    mv = pos * P.reindex(columns=pos.columns)
    exp = pd.DataFrame({"long_mv": mv.clip(lower=0).sum(axis=1), "short_mv": mv.clip(upper=0).sum(axis=1)})
    exp["gross_mv"] = exp["long_mv"] - exp["short_mv"]
    exp["net_mv"] = exp["long_mv"] + exp["short_mv"]

    daily = pd.DataFrame({
        "pnl": pnl.sum(axis=1),
        "pnl_long_book": pnl.where(pos.shift(1) > 0, 0.0).sum(axis=1),
        "pnl_short_book": pnl.where(pos.shift(1) < 0, 0.0).sum(axis=1),
    }).join(exp)
    daily = daily[daily.index >= start]

    if nav_today:
        # NAV(t) = today's NAV less P&L earned after t (assumes no subscriptions/redemptions)
        daily["nav"] = nav_today - daily["pnl"][::-1].cumsum()[::-1].shift(-1).fillna(0.0)
        denom = daily["nav"].shift(1)
    else:
        denom = daily["gross_mv"].shift(1)
    daily["return"] = daily["pnl"] / denom.replace(0, np.nan)
    daily["cum_return"] = (1 + daily["return"].fillna(0)).cumprod() - 1
    wealth = 1 + daily["cum_return"]
    daily["drawdown"] = wealth / wealth.cummax() - 1
    daily["cum_pnl"] = daily["pnl"].cumsum()

    r = daily["return"].dropna()
    month = daily.index[-1].to_period("M")
    mtd = (1 + daily.loc[daily.index.to_period("M") == month, "return"].fillna(0)).prod() - 1
    vol = r.std() * np.sqrt(TRADING_DAYS) if len(r) > 1 else np.nan
    ann_ret = (1 + r).prod() ** (TRADING_DAYS / len(r)) - 1 if len(r) else np.nan
    perf = {
        "perf_start": str(daily.index[0].date()), "perf_days": int(len(r)),
        "pnl_since_inception_gbp": float(daily["pnl"].sum()),
        "return_since_inception_pct": 100 * float(daily["cum_return"].iloc[-1]),
        "return_mtd_pct": 100 * float(mtd),
        "realised_vol_pct": 100 * float(vol),
        "sharpe": float((ann_ret - RISK_FREE_RATE) / vol) if vol else np.nan,
        "max_drawdown_pct": 100 * float(daily["drawdown"].min()),
        "current_drawdown_pct": 100 * float(daily["drawdown"].iloc[-1]),
        "best_day_pct": 100 * float(r.max()) if len(r) else np.nan,
        "worst_day_pct": 100 * float(r.min()) if len(r) else np.nan,
    }
    if len(r) < 60:
        warnings.append(f"Only {len(r)} days of fund history: realised vol, Sharpe and drawdown are not yet meaningful")

    # Attribution
    pnl = pnl[pnl.index >= start]
    by_security = pd.DataFrame({"pnl_gbp": pnl.sum()}).join(ref[["name", "sector", "country", "currency"]])
    by_security = by_security.sort_values("pnl_gbp", ascending=False)
    sector_map = ref["sector"].reindex(pnl.columns).fillna("Unknown")
    by_sector_daily = pnl.T.groupby(sector_map).sum().T

    sleeve_pnl = {}
    for pid, name in SLEEVES.items():
        _, sp = pnl_for(pid)
        if sp is not None:
            sleeve_pnl[name] = sp[sp.index >= start].sum(axis=1)
    by_sleeve_daily = pd.DataFrame(sleeve_pnl, index=daily.index).fillna(0.0)
    by_sleeve_daily["Unallocated"] = daily["pnl"] - by_sleeve_daily.sum(axis=1)

    tables = {
        "perf_daily": daily,
        "pnl_by_security": by_security,
        "pnl_by_sector_daily": by_sector_daily,
        "pnl_by_sleeve_daily": by_sleeve_daily,
        "pnl_attribution": pd.concat([
            pd.DataFrame({"dimension": "book", "bucket": ["Long", "Short"],
                          "pnl_gbp": [daily["pnl_long_book"].sum(), daily["pnl_short_book"].sum()]}),
            pd.DataFrame({"dimension": "sector", "bucket": by_sector_daily.columns,
                          "pnl_gbp": by_sector_daily.sum().to_numpy()}),
            pd.DataFrame({"dimension": "sleeve", "bucket": by_sleeve_daily.columns,
                          "pnl_gbp": by_sleeve_daily.sum().to_numpy()}),
        ], ignore_index=True),
        "exposure_history": exp[exp.index >= start],
    }
    return perf, tables


def check_limits(summary: dict) -> pd.DataFrame:
    if not LIMITS:
        return pd.DataFrame([{"metric": "(none)", "status": "LIMITS not set - see README"}])
    rows = []
    for k, (lo, hi) in LIMITS.items():
        v = summary.get(k)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            status = "NO DATA"
        elif (lo is not None and v < lo) or (hi is not None and v > hi):
            status = "BREACH"
        else:
            status = "OK"
        rows.append({"metric": k, "value": v, "min": lo, "max": hi, "status": status})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- main
def run(nav: float | None = None, base_ccy: str = "GBP", years: int = 3, out_dir: Path = RESULTS_DIR) -> dict:
    today = dt.date.today()
    start = today - dt.timedelta(days=365 * years)
    ports = [FUND, *SLEEVES]

    with Bloomberg() as bbg:
        print("Pulling current holdings...")
        current = bbg.portfolio(ports, "PORTFOLIO_DATA")
        print(f"Pulling holdings history from {INCEPTION}...")
        hist, sampled = holdings_history(bbg, ports, INCEPTION, today)
        universe = sorted(set(current["security"]) | set(hist["security"]))
        if not universe:
            raise ValueError(f"No holdings found for {FUND}. Warnings: {bbg.warnings}")

        print(f"Pulling reference data and {years}y prices for {len(universe)} securities...")
        ref = bbg.reference(universe, list(REF_FIELDS), overrides={"EQY_FUND_CRNCY": base_ccy})
        ref = ref.rename(columns=REF_FIELDS)
        for c in NUMERIC:
            ref[c] = pd.to_numeric(ref[c], errors="coerce")
        ref["currency"] = ref["currency"].map(normalise_ccy)

        px = bbg.history(universe + [BENCHMARK, *FACTORS.values()], ["PX_LAST"], start, today, currency=base_ccy)
        prices = px.pivot(index="date", columns="security", values="PX_LAST").sort_index()
        warnings = bbg.warnings

    # Current fund positions
    pos = current[current["port_id"] == FUND].set_index("security")
    pos = pos[["position", "market_value"]].join(ref)
    pos["mv"] = np.sign(pos["position"]) * pos["market_value"].abs()  # signed, base ccy
    gross = pos["mv"].abs().sum()
    if nav:
        nav_source = "user (--nav)"
    else:
        nav, nav_source = gross, "proxy: gross market value (PORT has no cash; pass --nav)"
        warnings.append("NAV not supplied: all % of NAV figures use gross market value")
    pos["weight_nav"] = pos["mv"] / nav
    pos["weight_gross"] = pos["mv"].abs() / gross
    pos["side"] = np.where(pos["mv"] >= 0, "Long", "Short")

    # Sleeve membership check
    sleeve_pos = current[current["port_id"].isin(SLEEVES)].groupby("security")["position"].sum()
    diff = pos["position"].sub(sleeve_pos.reindex(pos.index).fillna(0.0))
    for s, d in diff[diff.abs() > 1e-6].items():
        warnings.append(f"{s}: fund position differs from sum of sleeves by {d:,.0f}")
    pos["sleeve"] = (current[current["port_id"].isin(SLEEVES)]
                     .assign(sleeve=lambda d: d["port_id"].map(SLEEVES))
                     .groupby("security")["sleeve"].agg(", ".join).reindex(pos.index))

    rets = daily_returns(prices)
    wk = weekly_returns(prices)

    factor_stock, factor_port, beta_calc = factor_exposures(pos, wk, nav)
    pos = pos.join(beta_calc)
    risk, contrib, sector_contrib, corr, hist_pnl = risk_metrics(pos, rets, nav, warnings)
    liq, liq_buckets = liquidity(pos)
    perf, perf_tables = performance(hist, sampled, prices, ref, nav if nav_source.startswith("user") else None,
                                    warnings)

    summary = {
        "as_of": str(today), "fund": FUND, "base_ccy": base_ccy,
        "nav": nav, "nav_source": nav_source,
        **exposure_summary(pos["mv"], nav, pos["beta_bbg"], pos["beta_calc"]),
        **concentration(pos),
        "pct_gross_liquid_1d": float(liq_buckets["cum_pct_gross"].iloc[0]),
        "pct_gross_liquid_5d": float(liq_buckets["cum_pct_gross"].iloc[1]),
        "max_days_to_liquidate": float(liq["days_to_liquidate"].max()),
        **risk, **factor_port, **perf,
    }

    sleeve_rows = []
    for pid, name in SLEEVES.items():
        s = current[current["port_id"] == pid].set_index("security")
        if s.empty:
            continue
        smv = pos["mv"].reindex(s.index) * (s["position"] / pos["position"].reindex(s.index))
        sleeve_rows.append({"sleeve": name, "port_id": pid,
                            **exposure_summary(smv, nav, pos["beta_bbg"], pos["beta_calc"])})

    positions_out = pos.drop(columns=["market_value"]).sort_values("weight_gross", ascending=False)
    tables = {
        "positions": positions_out,
        "exposure_by_group": group_exposure(pos, ["sector", "industry", "country", "currency", "sleeve"], nav),
        "exposure_by_sleeve": pd.DataFrame(sleeve_rows),
        "liquidity": liq,
        "liquidity_buckets": liq_buckets,
        "risk_contribution": contrib,
        "risk_contrib_by_sector": sector_contrib,
        "correlation": corr,
        "factor_exposure_stocks": factor_stock,
        "var_hist_pnl": hist_pnl,
        **perf_tables,
        "limits": check_limits(summary),
        "holdings_history": hist,
        "prices": prices,
    }

    # Write
    stamp = today.strftime("%Y%m%d")
    out = out_dir / stamp
    out.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=not isinstance(df.index, pd.RangeIndex))
    with pd.ExcelWriter(out / f"risk_data_{stamp}.xlsx") as xl:
        pd.Series(summary, name="value").to_frame().to_excel(xl, sheet_name="summary")
        for name, df in tables.items():
            df.to_excel(xl, sheet_name=name[:31], index=not isinstance(df.index, pd.RangeIndex))
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (out / "warnings.txt").write_text("\n".join(warnings), encoding="utf-8")

    print(f"\nNAV {nav:,.0f} {base_ccy} ({nav_source})")
    print(f"Gross {summary['gross_pct_nav']:.1f}% | Net {summary['net_pct_nav']:.1f}% | "
          f"Beta-adj net {summary['beta_adj_net_pct_nav_calc']:.1f}% | "
          f"{summary['n_long']} long / {summary['n_short']} short")
    print(f"Ex-ante vol {summary['ex_ante_vol_pct']:.1f}% | 1d VaR99 {summary['var_99_pct_nav']:.2f}% "
          f"| ES99 {summary['es_99_pct_nav']:.2f}%")
    if warnings:
        print(f"{len(warnings)} warnings -> warnings.txt")
    print(f"Outputs: {out}")
    return {"summary": summary, "tables": tables, "warnings": warnings}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nav", type=float, help="Fund NAV in base currency, including cash")
    ap.add_argument("--ccy", default="GBP", help="Base currency (default GBP)")
    ap.add_argument("--years", type=int, default=3, help="Years of price history (default 3)")
    args = ap.parse_args()
    run(args.nav, args.ccy, args.years)
