"""Build the one-page A4 risk dashboard (first page of the risk section) from a dashboard_v2 run.

No Bloomberg needed: reads results/v2/<YYYYMMDD>/ (synced by OneDrive) and writes
results/v2/<YYYYMMDD>/dashboard/risk_dashboard_<layout>.html (+ .pdf with --pdf).

Usage:
    python build_dashboard.py                    # latest run
    python build_dashboard.py 20261106 --pdf
    python build_dashboard.py --demo --pdf       # invented 8-team book, for design work

Commentary: the first run creates results/v2/<date>/commentary.md with one "## key" section
per editorial box. Write in it, then re-run. Empty sections render as grey placeholders.

Outputs contain holdings, so they stay in results/ (gitignored). Never commit them.
"""
from __future__ import annotations

import argparse
import ast
import html
import io
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

CODE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = CODE_DIR.parent / "results" / "v2"
STYLE = CODE_DIR / "dashboard_style.css"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
VAR_CONF, VAR_WINDOW = 0.99, 5  # component VaR: average position P&L over 2*5+1 scenarios around the VaR day
MIN_DAYS_FOR_STATS = 60  # template rule: realised vol / Sharpe N/A before 60 daily returns
LIMIT_LABELS = {"gross_pct_nav": "Gross % NAV", "net_pct_nav": "Net % NAV",
                "largest_position_pct_nav": "Largest position % NAV", "var_99_pct_nav": "1-day VaR99 % NAV"}
REPORT_TEAMS = ["Financials", "Healthcare", "Industrials", "Consumer", "Materials",
                "Energy & Utilities", "Special Situations", "TMT"]

# Chart palette (validated: CVD-safe pair + neutral)
INK, MUTED, GRID = "#0B2160", "#6B7A90", "#E6E9EF"
BLUE, AMBER, GREY, LIGHT = "#2F5BB7", "#C98A1A", "#8A93A6", "#BFCCE6"
plt.rcParams.update({
    "font.family": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 8.5,
    "axes.edgecolor": "#B8C0CE", "axes.labelcolor": MUTED, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "svg.fonttype": "none", "axes.titlesize": 8,
})

COMMENTARY_SECTIONS = {
    "headline": "One-line headline: the risk story this period",
    "body": "About 100 words: what changed in the risk profile and why, what is driving it, and what we are "
            "watching next. Short paragraphs; '- ' for bullets.",
}
LAYOUTS = {"nofactors": "Factor chart replaced by mandate checks", "onebox": "Factor chart kept; mandate checks along the bottom"}


# ---------------------------------------------------------------- data
def sleeve_teams() -> dict[str, str]:
    """Sleeve display name -> team, read from dashboard_v2.py config (no blpapi import)."""
    tree = ast.parse((CODE_DIR / "dashboard_v2.py").read_text(encoding="utf-8"))
    cfg = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(target, ast.Name) and target.id in ("SLEEVES", "SLEEVE_TEAMS"):
                cfg[target.id] = ast.literal_eval(node.value)
    teams = cfg.get("SLEEVE_TEAMS", {})
    return {name: teams.get(pid) or "Unassigned" for pid, name in cfg.get("SLEEVES", {}).items()}


def load(run: Path) -> dict:
    rd = lambda n, **k: pd.read_csv(run / f"{n}.csv", **k) if (run / f"{n}.csv").exists() else pd.DataFrame()  # noqa: E731
    d = {
        "summary": json.loads((run / "summary.json").read_text(encoding="utf-8").replace("NaN", "null")),
        "warnings": [w for w in (run / "warnings.txt").read_text(encoding="utf-8").splitlines() if w.strip()]
        if (run / "warnings.txt").exists() else [],
        "positions": rd("positions"), "risk": rd("risk_contribution"), "perf": rd("perf_daily", parse_dates=["date"]),
        "var": rd("var_hist_pnl"), "limits": rd("limits"), "liq": rd("liquidity_buckets"),
    }
    teams = sleeve_teams()
    pos = d["positions"]
    pos["team"] = pos["sleeve"].map(lambda s: teams.get(s.split(", ")[0], "Unassigned") if isinstance(s, str) else "Unassigned")
    pos["short_name"] = pos["security"].str.replace(r" (Equity|Index)$", "", regex=True)
    d["positions"] = pos
    if (run / "prices.csv").exists():
        px = pd.read_csv(run / "prices.csv", index_col=0, parse_dates=True)
        secs = [x for x in pos["security"] if x in px.columns]
        rets = px.sort_index().ffill().pct_change(fill_method=None).iloc[1:]  # as dashboard_v2.daily_returns
        d["pos_pnl"] = rets[secs].fillna(0.0) * pos.set_index("security")["mv"][secs]
    prev = sorted(p for p in run.parent.iterdir() if p.is_dir() and p.name.isdigit() and p.name < run.name
                  and (p / "summary.json").exists())
    if prev:
        d["prev"] = json.loads((prev[-1] / "summary.json").read_text(encoding="utf-8").replace("NaN", "null"))
    return d


def var_contributions(d) -> pd.DataFrame:
    """Component historical VaR: each position's average P&L over the scenarios around the VaR
    day, rescaled so contributions sum to fund VaR. Positive = adds to VaR."""
    pnl = d.get("pos_pnl")
    if pnl is None or pnl.empty:
        return pd.DataFrame(columns=["security", "contrib", "pct"])
    port = pnl.sum(axis=1)
    var = -port.quantile(1 - VAR_CONF)
    k = int(round((1 - VAR_CONF) * len(port)))
    tail = port.sort_values().index[max(0, k - VAR_WINDOW):k + VAR_WINDOW + 1]
    c = -pnl.loc[tail].mean()
    c = c * var / c.sum() if c.sum() else c
    out = c.rename("contrib").reset_index().rename(columns={"index": "security"})
    out["pct"] = 100 * out["contrib"] / var
    return out


def load_commentary(run: Path) -> dict[str, str]:
    f = run / "commentary.md"
    if f.exists() and not re.sub(r"<!--.*?-->|^#.*$|Write under.*placeholder\.", "", f.read_text(encoding="utf-8"), flags=re.S | re.M).strip():
        f.unlink()  # still the empty template: replace with the current sections
    if not f.exists():
        f.write_text("# Risk dashboard commentary\n\nWrite under each heading, then re-run "
                     "build_dashboard.py. Leave a section empty to show a placeholder.\n\n"
                     + "".join(f"## {k}\n<!-- {v} -->\n\n" for k, v in COMMENTARY_SECTIONS.items()),
                     encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", f.read_text(encoding="utf-8"), flags=re.S)
    parts = re.split(r"^## +(\w+)\s*$", text, flags=re.M)
    return {k: v.strip() for k, v in zip(parts[1::2], parts[2::2])}


# ---------------------------------------------------------------- formatting
def num(v, fmt="{:.1f}", suffix="%", na="N/A"):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return na
    return fmt.format(v) + suffix


def commentary_html(text: str | None, key: str) -> str:
    if not text:
        return f'<p class="ph">[{html.escape(COMMENTARY_SECTIONS[key])}]</p>'
    out, items = [], []
    for line in text.splitlines():
        if line.lstrip().startswith(("- ", "* ")):
            items.append(f"<li>{html.escape(line.lstrip()[2:])}</li>")
        elif line.strip():
            if items:
                out.append(f"<ul>{''.join(items)}</ul>"); items = []
            out.append(f"<p>{html.escape(line.strip())}</p>")
    if items:
        out.append(f"<ul>{''.join(items)}</ul>")
    return "".join(out)


def top_legend(ax, ncol):
    ax.legend(frameon=False, fontsize=7.5, ncol=ncol, loc="lower left", bbox_to_anchor=(0, 1.0),
              borderaxespad=0.2, handlelength=1.2, columnspacing=1.2)


def svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", transparent=True)
    plt.close(fig)
    s = buf.getvalue()
    s = s[s.index("<svg"):]
    return re.sub(r'<svg([^>]*?) width="[^"]+" height="[^"]+"', r'<svg\1', s, count=1)


# ---------------------------------------------------------------- charts
def chart_vs_market(d, w=3.6, h=1.7):
    p = d["perf"]
    fig, ax = plt.subplots(figsize=(w, h), layout="constrained")
    if p.empty:
        return svg(fig)
    fund = 100 * (1 + p["cum_return"]); mkt = 100 * (1 + p["benchmark_cum_return"])
    ax.plot(p["date"], fund, color=BLUE, lw=1.8, label="BIF")
    ax.plot(p["date"], mkt, color=GREY, lw=1.4, ls=(0, (4, 2)), label="MSCI World (net TR, GBP)")
    ax.axhline(100, color="#B8C0CE", lw=0.8)
    for s, c in ((fund, BLUE), (mkt, GREY)):
        ax.annotate(f"{s.iloc[-1]:.1f}", (p["date"].iloc[-1], s.iloc[-1]), xytext=(4, 0),
                    textcoords="offset points", va="center", color=INK, fontsize=7.5)
    ax.grid(axis="y", color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%-d %b"))
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(5))
    top_legend(ax, 2)
    return svg(fig)


def chart_weights_vs_risk(d, w=3.6, h=1.9):
    r = d["risk"].copy()
    fig, ax = plt.subplots(figsize=(w, h), layout="constrained")
    if r.empty:
        return svg(fig)
    r["label"] = r["security"].str.replace(r" (Equity|Index)$", "", regex=True)
    r = r.sort_values("risk_contrib_share_pct").tail(10)
    y = np.arange(len(r))
    ax.barh(y + 0.2, r["weight_pct_nav"].abs(), 0.36, color=LIGHT, label="% of NAV")
    ax.barh(y - 0.2, r["risk_contrib_share_pct"], 0.36, color=BLUE, label="% of risk")
    for yi, v in zip(y, r["risk_contrib_share_pct"]):
        ax.text(v + 0.8, yi - 0.2, f"{v:.0f}%", va="center", fontsize=7.5, color=INK)
    ax.set_yticks(y, r["label"]); ax.tick_params(axis="y", length=0)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(decimals=0))
    ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    top_legend(ax, 2)
    return svg(fig)


def chart_team_exposure(d, w=3.6, h=1.9):
    g = team_frame(d)
    fig, ax = plt.subplots(figsize=(w, h), layout="constrained")
    y = np.arange(len(g))[::-1]
    ax.barh(y, g["long"], 0.6, color=BLUE, label="Long")
    ax.barh(y, g["short"], 0.6, color=AMBER, label="Short")
    ax.scatter(g["net"].where(g["n"] > 0), y, marker="|", s=60, color=INK, linewidths=1.6, zorder=3, label="Net")
    for yi, lo, net, n in zip(y, g["long"], g["net"], g["n"]):
        ax.text(lo + 1, yi, f"net {net:+.0f}%" if n else "no positions", va="center", fontsize=7.5, color=INK if n else MUTED)
    ax.set_yticks(y, g.index); ax.tick_params(axis="y", length=0)
    ax.axvline(0, color="#B8C0CE", lw=0.8)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(decimals=0))
    ax.set_xlim(min(-5, g["short"].min() * 1.15), max(10, g["long"].max() * 1.4))
    ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    top_legend(ax, 3)
    return svg(fig)


def team_frame(d) -> pd.DataFrame:
    """Per team: long, short, gross, net (% NAV), risk share (%), positions. Always all 8 sector teams."""
    pos, nav = d["positions"], d["summary"]["nav"]
    risk = d["risk"].set_index("security")["risk_contrib_share_pct"] if not d["risk"].empty else pd.Series(dtype=float)
    pos = pos.assign(risk_share=pos["security"].map(risk).fillna(0), long=pos["mv"].clip(lower=0), short=pos["mv"].clip(upper=0))
    g = pos.groupby("team").agg(long=("long", "sum"), short=("short", "sum"), risk=("risk_share", "sum"), n=("mv", "size"))
    g[["long", "short"]] = g[["long", "short"]] / nav * 100
    g["gross"], g["net"] = g["long"] - g["short"], g["long"] + g["short"]
    order = REPORT_TEAMS + sorted(set(g.index) - set(REPORT_TEAMS))
    return g.reindex(order).fillna({"long": 0, "short": 0, "gross": 0, "net": 0, "risk": 0, "n": 0})


def chart_team_risk(d, w=3.6, h=1.9):
    g = team_frame(d)
    gs, rs = g["gross"] / g["gross"].sum() * 100, g["risk"]
    fig, ax = plt.subplots(figsize=(w, h), layout="constrained")
    y = np.arange(len(g))[::-1]
    ax.barh(y + 0.19, gs, 0.34, color=LIGHT, label="% of gross")
    ax.barh(y - 0.19, rs, 0.34, color=BLUE, label="% of risk")
    for yi, a, b, n in zip(y, gs, rs, g["n"]):
        hot = b > 1.4 * a and b > 10
        ax.text(max(a, b) + 1, yi, f"{a:.0f} / {b:.0f}" if n else "no positions", va="center", fontsize=7.5,
                color=AMBER if hot else (INK if n else MUTED), fontweight="bold" if hot else "normal")
    ax.set_yticks(y, g.index); ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, max(10, max(gs.max(), rs.max()) * 1.3))
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(decimals=0))
    ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    top_legend(ax, 2)
    return svg(fig)


def chart_var_contrib(d, w=3.6, h=2.0):
    c = var_contributions(d)
    fig, ax = plt.subplots(figsize=(w, h), layout="constrained")
    if c.empty:
        return svg(fig)
    team = d["positions"].set_index("security")["team"]
    c = c.reindex(c["contrib"].abs().sort_values(ascending=False).index).head(8).iloc[::-1]
    labels = [f"{x.replace(' Equity', '')} · {team.get(x, '')}" for x in c["security"]]
    y = np.arange(len(c))
    ax.barh(y, c["pct"], 0.6, color=[BLUE if v >= 0 else AMBER for v in c["pct"]])
    for yi, v, g in zip(y, c["pct"], c["contrib"]):
        ax.text(v + (1 if v >= 0 else -1), yi, f"{v:.0f}%  £{g / 1e3:,.0f}k", va="center",
                ha="left" if v >= 0 else "right", fontsize=7.5, color=INK)
    ax.set_yticks(y, labels); ax.tick_params(axis="y", length=0)
    ax.axvline(0, color="#B8C0CE", lw=0.8)
    lo, hi = min(0, c["pct"].min()), c["pct"].max()
    ax.set_xlim(lo * 1.4 - 2, hi * 1.45 + 2)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(decimals=0))
    ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    return svg(fig)


def chart_var(d, w=3.6, h=1.7):
    s, v = d["summary"], d["var"]
    fig, ax = plt.subplots(figsize=(w, h), layout="constrained")
    if v.empty:
        return svg(fig)
    x = v["pnl_pct_nav"].clip(-8, 8)
    bins = np.linspace(-8, 8, 49)
    cnt, edges = np.histogram(x, bins)
    var95 = -s.get("var_95_pct_nav", np.nan)
    cols = [AMBER if e < var95 else LIGHT for e in edges[1:]]
    ax.bar(edges[:-1], cnt, width=np.diff(edges) * 0.85, align="edge", color=cols)
    for val, lab, yfrac, ha in ((var95, "VaR95", 0.92, "left"), (-s.get("var_99_pct_nav", np.nan), "VaR99", 0.72, "right")):
        ax.axvline(val, color=INK, lw=0.9, ls=(0, (3, 2)))
        ax.text(val + (0.2 if ha == "left" else -0.2), cnt.max() * yfrac, f"{lab} {-val:.2f}%", ha=ha, fontsize=7.5, color=INK)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(decimals=0))
    ax.set_yticks([]); ax.spines["left"].set_visible(False)
    return svg(fig)


def chart_factors(d, w=3.6, h=1.5):
    s = d["summary"]
    names = ["market", "value", "momentum", "quality", "min_vol", "small_cap"]
    vals = [s.get(f"factor_{n}") for n in names]
    fig, ax = plt.subplots(figsize=(w, h), layout="constrained")
    y = np.arange(len(names))[::-1]
    v = np.array([np.nan if x is None else x for x in vals])
    ax.barh(y, np.nan_to_num(v), 0.6, color=[INK if i == 0 else BLUE for i in range(len(v))])
    for yi, x in zip(y, v):
        ax.text(x + (0.03 if x >= 0 else -0.03), yi, f"{x:+.2f}", va="center", ha="left" if x >= 0 else "right", fontsize=7.5, color=INK)
    ax.axvline(0, color="#B8C0CE", lw=0.8)
    ax.set_yticks(y, [n.replace("_", " ").capitalize() for n in names]); ax.tick_params(axis="y", length=0)
    lim = max(1.0, np.nanmax(np.abs(v)) * 1.35)
    ax.set_xlim(-lim, lim); ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    return svg(fig)


# ---------------------------------------------------------------- page components
def kpis(d) -> str:
    s, p = d["summary"], d.get("prev") or {}
    prev_date = pd.Timestamp(p["as_of"]).strftime("%-d %b") if p.get("as_of") else None

    def delta(key, scale=1.0, unit="pp"):
        if not prev_date or s.get(key) is None or p.get(key) is None:
            return ""
        return f"{(s[key] - p[key]) * scale:+.2f}{unit} vs {prev_date}" if unit == "" else \
            f"{(s[key] - p[key]) * scale:+.1f}{unit} vs {prev_date}"

    def beta(x):
        return None if x.get("beta_adj_net_pct_nav_calc") is None else x["beta_adj_net_pct_nav_calc"] / 100

    b, pb = beta(s), beta(p)
    beta_d = f"{b - pb:+.2f} vs {prev_date}" if b is not None and pb is not None and prev_date else "NAV-weighted, 2y weekly"
    nav_proxy = str(s.get("nav_source", "")).startswith("proxy")
    tiles = [
        ("1-day VaR 99", num(s.get("var_99_pct_nav"), "{:.2f}"), delta("var_99_pct_nav") or f"£{s.get('var_99_gbp', 0):,.0f} · historical"),
        ("1-day ES 99", num(s.get("es_99_pct_nav"), "{:.2f}"), delta("es_99_pct_nav") or f"£{s.get('es_99_gbp', 0):,.0f} · average beyond VaR"),
        ("Ex-ante volatility", num(s.get("ex_ante_vol_pct")), delta("ex_ante_vol_pct") or "annualised, holdings-based"),
        ("Beta to MSCI World", "N/A" if b is None else f"{b:.2f}", beta_d),
        ("Gross exposure", num(s.get("gross_pct_nav")), delta("gross_pct_nav") or f"{s.get('n_long', 0)} long / {s.get('n_short', 0)} short"),
        ("Net exposure", num(s.get("net_pct_nav"), "{:+.1f}"), delta("net_pct_nav") or f"beta-adj. {num(s.get('beta_adj_net_pct_nav_calc'), '{:+.1f}')}"),
        ("Largest position", num(s.get("largest_position_pct_nav")), str(s.get("largest_position", "")).replace(" Equity", "")),
        ("Drawdown from peak", num(-abs(s.get("current_drawdown_pct") or 0)), f"max {num(s.get('max_drawdown_pct'))} since start"),
    ]
    note = " · NAV = gross MV (no cash data)" if nav_proxy else ""
    return ('<div class="kpis eight">' + "".join(
        f'<div class="kpi"><div class="l">{t[0]}</div><div class="v">{t[1]}</div><div class="d">{html.escape(t[2])}</div></div>'
        for t in tiles) + f'</div><div class="note">% of NAV unless stated; NAV £{s["nav"] / 1e6:.2f}m{note}.</div>')


def mandate(d) -> str:
    lim = d["limits"]
    if lim.empty or "value" not in lim.columns:
        return '<p class="ph">Risk limits not set: add BIF limits to LIMITS in dashboard_v2.py.</p>'
    rows = []
    for r in lim.itertuples():
        lo = None if pd.isna(r.min) else float(r.min)
        hi = None if pd.isna(r.max) else float(r.max)
        breach = (lo is not None and r.value < lo) or (hi is not None and r.value > hi)
        near = not breach and hi is not None and r.value > 0.9 * hi
        st = ('<span class="badge b-breach">▲ Breach</span>' if breach else
              '<span class="badge b-watch">● Near</span>' if near else '<span class="badge b-ok">✓ OK</span>')
        bound = " to ".join(f"{x:g}" for x in (lo, hi) if x is not None)
        rows.append(f'<tr><td>{LIMIT_LABELS.get(r.metric, r.metric)}</td><td class="n">{r.value:.1f}</td>'
                    f'<td class="n">{"≤ " if lo is None else "≥ " if hi is None else ""}{bound}</td><td>{st}</td></tr>')
    return ('<table class="mt"><tr><th>Limit</th><th class="n">Actual</th><th class="n">Limit</th><th>Status</th></tr>'
            + "".join(rows) + "</table>")


def sensitivities(d) -> str:
    """Quick what-ifs from data already pulled: market shock via beta, rates regressions, worst historical day."""
    s, nav = d["summary"], d["summary"]["nav"]
    rows = []
    if s.get("beta_adj_net_pct_nav_calc") is not None:
        rows.append(("MSCI World −10%", -0.10 * s["beta_adj_net_pct_nav_calc"], "via beta"))
    for k, lab in (("uk", "UK 10y +100bp"), ("us", "US 10y +100bp")):
        v = s.get(f"rates_sens_{k}_10y_pct_per_100bp")
        if v is not None:
            rows.append((lab, v, "2y regression"))
    v = d["var"]
    if not v.empty:
        i = v["pnl_pct_nav"].idxmin()
        when = pd.Timestamp(v.loc[i, "date"]).strftime("%-d %b %Y") if "date" in v.columns else "in history"
        rows.append(("Worst day, today's book", v.loc[i, "pnl_pct_nav"], when))
    out = "".join(f'<tr><td>{lab}</td><td class="n">{x:+.1f}%</td><td class="n">{"−" if x < 0 else "+"}£{abs(x) / 100 * nav / 1e3:,.0f}k</td>'
                  f'<td class="src">{src}</td></tr>' for lab, x, src in rows)
    return ('<table class="mt"><tr><th>Sensitivity</th><th class="n">%&nbsp;NAV</th><th class="n">£</th><th></th></tr>'
            + out + "</table>")


def data_notes(d) -> str:
    """Data-quality caveats for the footnote."""
    s, notes = d["summary"], []
    if str(s.get("nav_source", "")).startswith("proxy"):
        notes.append("NAV excludes cash, so % NAV figures are % of gross.")
    if (s.get("perf_days") or 0) < MIN_DAYS_FOR_STATS:
        notes.append(f"Only {s.get('perf_days')} days of fund history: drawdown is indicative and realised vol and Sharpe are not shown.")
    return " ".join(notes)


def flags(d) -> str:
    """Automatic data-quality and risk flags (limit results are in mandate())."""
    s, items = d["summary"], []
    if (s.get("largest_position_pct_nav") or 0) > 20:
        items.append(("watch", f"Concentration: largest position {s['largest_position_pct_nav']:.1f}%, "
                               f"effective N {s.get('effective_n_positions', 0):.1f} positions"))
    top = var_contributions(d).sort_values("pct").tail(1)
    if not top.empty and top["pct"].iloc[0] > 30:
        items.append(("watch", f"{top['security'].iloc[0].replace(' Equity', '')} drives {top['pct'].iloc[0]:.0f}% of VaR"))
    if not items:
        return ""
    icon = {"ok": "✓", "watch": "●", "breach": "▲", "na": "–"}
    return '<ul class="flags">' + "".join(f'<li class="f-{c}"><span>{icon[c]}</span>{html.escape(t)}</li>' for c, t in items) + "</ul>"


def team_table(d) -> str:
    g, pos, nav = team_frame(d), d["positions"], d["summary"]["nav"]
    rows = []
    for team, r in g.iterrows():
        if not r["n"]:
            rows.append(f'<tr class="empty"><td>{team}</td>' + '<td class="n">–</td>' * 5 + '<td>No positions</td></tr>')
            continue
        t = pos[pos["team"] == team]
        big = t.loc[t["mv"].abs().idxmax()]
        rows.append(f'<tr><td>{team}</td><td class="n">{r["gross"]:.1f}</td><td class="n">{r["net"]:+.1f}</td>'
                    f'<td class="n">{r["risk"]:.0f}</td><td class="n">{int(r["n"])}</td><td class="n">{int((t["mv"] < 0).sum())}</td>'
                    f'<td>{html.escape(big["short_name"])} {big["mv"] / nav * 100:+.1f}%</td></tr>')
    return ('<table class="tt"><tr><th>Team</th><th class="n">Gross %</th><th class="n">Net %</th>'
            '<th class="n">Risk share %</th><th class="n">Positions</th><th class="n">Shorts</th><th>Largest position (% NAV)</th></tr>'
            + "".join(rows) + "</table>")


def editorial(com) -> str:
    head = html.escape(com["headline"]) if com.get("headline") else f'<span class="ph">[{COMMENTARY_SECTIONS["headline"]}]</span>'
    return (f'<div class="box editorial"><span class="tag ed">EDITORIAL</span><h3>{head}</h3>'
            f'<div class="cols">{commentary_html(com.get("body"), "body")}</div></div>')


def box(title: str, body: str, tag: str, cls: str = "") -> str:
    return f'<div class="box {cls}"><span class="tag {tag}">{"AUTO" if tag == "auto" else "EDITORIAL"}</span><h3>{title}</h3>{body}</div>'


def chart(title: str, sub: str, body: str) -> str:
    return f'<div class="chart"><span class="tag auto">AUTO</span><div class="ct">{title}</div><div class="cs">{sub}</div>{body}</div>'


# ---------------------------------------------------------------- page
def page(d, com, as_of: str, layout: str) -> str:
    s = d["summary"]
    method = (f"Data: Bloomberg PORT and prices to {as_of}, {s.get('base_ccy', 'GBP')}. VaR/ES: historical simulation over "
              f"{s.get('var_history_days', '?')} days; contributions scaled to sum to VaR. Beta: NAV-weighted position betas. "
              f"Team figures % of fund NAV. Full methods in Methods, sources & people."
              + (" " + data_notes(d) if data_notes(d) else "")
              + (" ILLUSTRATIVE DATA, NOT BIF HOLDINGS." if d.get("demo") else ""))
    head = (f'<div class="hdr"><div class="logo"><b>BF</b><span>Bristol<br>Investment<br>Fund</span></div>'
            f'<div class="month">AS OF {pd.Timestamp(as_of).strftime("%-d %b %Y").upper()}</div></div>')
    h = {"nofactors": 1.95, "onebox": 1.8}[layout]
    teams = chart("Exposure by team", "Long and short, % of fund NAV; tick = net", chart_team_exposure(d, h=h))
    trisk = chart("Risk by team", "Share of gross vs share of ex-ante volatility (amber: risk well above capital)", chart_team_risk(d, h=h))
    varc = chart("Top contributors to VaR", "Top 8 positions, share of 1-day VaR99 (amber: reduces VaR)", chart_var_contrib(d, h=h))
    if layout == "nofactors":
        checks = box("Mandate checks and flags", mandate(d) + flags(d), "auto", "blue grid-cell")
        grid = f'<div class="g2">{teams}{trisk}{varc}{checks}</div>'
    else:
        fac = chart("Factor exposures", f"Fund betas to MSCI World and factor spreads, 2y weekly · R² {num(s.get('factor_r2_systematic_pct'), '{:.0f}')}",
                    chart_factors(d, h=h))
        grid = (f'<div class="g2">{teams}{trisk}{varc}{fac}</div>'
                + f'<div class="g2b">{box("Mandate checks", mandate(d) + flags(d), "auto", "blue")}'
                + f'{box("Sensitivity tests", sensitivities(d), "auto", "blue")}</div>')
    body = f"""<div class="content">
<div class="kicker">Risk</div><h1 class="title">Risk at a glance</h1>
<div class="byline">Risk team [authors]</div>
{kpis(d)}
{editorial(com)}
{grid}</div>"""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>BIF risk dashboard {as_of} ({layout})</title><style>{STYLE.read_text(encoding="utf-8")}</style></head>
<body><div class="page">{head}{body}
<div class="note method">{html.escape(method)}</div>
<div class="foot"><span>SIMULATED PORTFOLIO &nbsp;|&nbsp; Risk</span><b>R1</b></div></div></body></html>"""


# ---------------------------------------------------------------- demo data
def demo_data() -> dict:
    """Invented 8-team long/short book (no real holdings) to design layouts at full scale."""
    rng = np.random.default_rng(7)
    nav, rows = 3_000_000, []
    for i, team in enumerate(REPORT_TEAMS):
        for j in range(rng.integers(3, 7)):
            short = j >= 3 or (j == 2 and i % 3 == 0)
            mv = (-1 if short else 1) * rng.uniform(0.02, 0.09) * nav
            rows.append({"security": f"{team[:3].upper()}{j + 1} XX Equity", "mv": mv, "team": team})
    pos = pd.DataFrame(rows)
    pos["short_name"] = pos["security"].str.replace(" Equity", "")
    share = pos["mv"].abs() * rng.uniform(0.5, 1.8, len(pos)) * np.where(pos["team"] == "TMT", 1.8, 1)
    risk = pd.DataFrame({"security": pos["security"], "weight_pct_nav": pos["mv"] / nav * 100,
                         "risk_contrib_share_pct": share / share.sum() * 100})
    dates = pd.bdate_range("2026-10-01", "2026-11-30")
    m = np.cumprod(1 + rng.normal(0.0003, 0.008, len(dates))) - 1
    f = np.cumprod(1 + 0.45 * np.diff(np.r_[0, m]) + rng.normal(0.0004, 0.005, len(dates))) - 1
    wealth = 1 + f
    long_, short_ = pos["mv"].clip(lower=0).sum(), pos["mv"].clip(upper=0).sum()
    top = pos.loc[pos["mv"].abs().idxmax()]
    summary = {"as_of": "2026-11-30", "nav": nav, "nav_source": "user", "base_ccy": "GBP",
               "n_long": int((pos["mv"] > 0).sum()), "n_short": int((pos["mv"] < 0).sum()),
               "gross_pct_nav": (long_ - short_) / nav * 100, "net_pct_nav": (long_ + short_) / nav * 100,
               "beta_adj_net_pct_nav_calc": (long_ + short_) / nav * 62, "factor_market": 0.62, "factor_value": -0.18,
               "factor_momentum": 0.24, "factor_quality": 0.31, "factor_min_vol": -0.12, "factor_small_cap": 0.09,
               "factor_r2_systematic_pct": 64, "ex_ante_vol_pct": 11.8, "rates_sens_us_10y_pct_per_100bp": -1.4, "var_95_pct_nav": 1.21, "var_99_pct_nav": 1.84,
               "var_99_gbp": 0.0184 * nav, "es_99_gbp": 0.0247 * nav, "es_99_pct_nav": 2.47, "var_history_days": 1825,
               "current_drawdown_pct": 100 * (wealth[-1] / wealth.max() - 1), "max_drawdown_pct": 100 * (wealth / np.maximum.accumulate(wealth) - 1).min(),
               "perf_days": len(dates) - 1, "realised_vol_pct": 10.4, "return_since_inception_pct": 100 * f[-1],
               "benchmark_return_since_inception_pct": 100 * m[-1], "largest_position": top["security"],
               "largest_position_pct_nav": abs(top["mv"]) / nav * 100, "effective_n_positions": 24.0,
               "pct_gross_liquid_1d": 88, "rates_sens_uk_10y_pct_per_100bp": -2.1}
    limits = pd.DataFrame([["gross_pct_nav", summary["gross_pct_nav"], None, 200, "OK"],
                           ["net_pct_nav", summary["net_pct_nav"], -20, 80, "OK"],
                           ["largest_position_pct_nav", summary["largest_position_pct_nav"], None, 10, "OK"],
                           ["var_99_pct_nav", 1.84, None, 3, "OK"]], columns=["metric", "value", "min", "max", "status"])
    mkt = rng.standard_t(4, 1825) * 0.008
    sens = pd.Series(np.where(pos["mv"] > 0, 1.0, 0.8) * rng.uniform(0.6, 1.4, len(pos)), index=pos["security"])
    sens[pos["team"].eq("TMT").to_numpy()] *= 1.6
    rets = np.outer(mkt, sens) + rng.normal(0, 0.014, (1825, len(pos)))
    pos_pnl = pd.DataFrame(rets, columns=pos["security"]) * pos.set_index("security")["mv"]
    port = pos_pnl.sum(axis=1)
    q99, q95 = port.quantile(0.01), port.quantile(0.05)
    summary.update(var_99_gbp=-q99, var_99_pct_nav=-q99 / nav * 100, var_95_pct_nav=-q95 / nav * 100,
                   es_99_gbp=-port[port <= q99].mean(), es_99_pct_nav=-port[port <= q99].mean() / nav * 100,
                   beta_adj_net_pct_nav_calc=float((pos["mv"] * sens.to_numpy()).sum() / nav * 100 * 0.9))
    summary["factor_market"] = round(summary["beta_adj_net_pct_nav_calc"] / 100, 2)
    prev = {k: v for k, v in summary.items()}
    prev.update(as_of="2026-10-31", var_99_pct_nav=summary["var_99_pct_nav"] - 0.21, es_99_pct_nav=summary["es_99_pct_nav"] - 0.3,
                ex_ante_vol_pct=10.9, gross_pct_nav=summary["gross_pct_nav"] - 6.1, net_pct_nav=summary["net_pct_nav"] + 4.2,
                beta_adj_net_pct_nav_calc=summary["beta_adj_net_pct_nav_calc"] - 3)
    return {"demo": True, "pos_pnl": pos_pnl, "prev": prev, "summary": summary, "warnings": [], "positions": pos, "risk": risk,
            "perf": pd.DataFrame({"date": dates, "cum_return": f, "benchmark_cum_return": m}),
            "var": pd.DataFrame({"date": pd.bdate_range(end="2026-11-30", periods=len(port)), "pnl_pct_nav": port / nav * 100}), "limits": limits, "liq": pd.DataFrame()}


DEMO_COMMENTARY = {  # sample text about the invented book, to judge the layout when filled
    "headline": "Gross is back above its limit as TMT shorts grow; risk is concentrated in TMT",
    "body": "Gross rose 6pp to 228%, above the 200% limit, as TMT and Materials added shorts; net fell to 18%.\n"
            "TMT holds 16% of gross but 25% of volatility: its two largest longs, both AI-capex names, top the VaR "
            "contributors and trade almost as one.\n"
            "What we are watching:\n"
            "- Gross breach: TMT and Materials PMs to reduce or justify.\n"
            "- TMT earnings w/c 8 December.\n"
            "- Momentum reversal if rate-cut expectations shift.",
}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("date", nargs="?", help="Run folder YYYYMMDD (default: latest)")
    ap.add_argument("--layout", choices=[*LAYOUTS, "all"], default="all")
    ap.add_argument("--pdf", action="store_true", help="Also print to PDF with headless Chrome")
    ap.add_argument("--demo", action="store_true", help="Invented 8-team book; writes to mockups/ (safe to commit)")
    a = ap.parse_args()
    if a.demo:
        run = CODE_DIR.parent / "mockups" / "demo"
        run.mkdir(parents=True, exist_ok=True)
        d, com = demo_data(), DEMO_COMMENTARY
    else:
        runs = sorted(p for p in RESULTS_DIR.iterdir() if p.is_dir() and p.name.isdigit())
        run = RESULTS_DIR / a.date if a.date else runs[-1]
        d, com = load(run), load_commentary(run)
    out = run if a.demo else run / "dashboard"
    out.mkdir(exist_ok=True)
    as_of = d["summary"].get("as_of", run.name)
    chrome = CHROME if Path(CHROME).exists() else shutil.which("google-chrome") or shutil.which("chrome")
    for layout in LAYOUTS if a.layout == "all" else [a.layout]:
        f = out / f"risk_dashboard_{layout}.html"
        f.write_text(page(d, com, as_of, layout), encoding="utf-8")
        print(f"Wrote {f}")
        if a.pdf and chrome:
            subprocess.run([chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={f.with_suffix('.pdf')}", f.as_uri()], check=False, capture_output=True)
            print(f"Wrote {f.with_suffix('.pdf')}")
    if not a.demo:
        print(f"Commentary: {run / 'commentary.md'}")


if __name__ == "__main__":
    main()
