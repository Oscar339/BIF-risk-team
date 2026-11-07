"""Page design: loads a report folder, draws the charts and writes the one-page A4 dashboard (HTML + PDF)."""
from __future__ import annotations

import html
import io
import logging
import json
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)  # Helvetica missing on Windows is fine
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from design import config as C  # noqa: E402
from design import risk  # noqa: E402

STYLE = C.DESIGN_DIR / "style.css"

# Chart palette (CVD-safe pair + neutral)
INK, MUTED, GRID = "#0B2160", "#6B7A90", "#E6E9EF"
BLUE, AMBER, LIGHT = "#2F5BB7", "#C98A1A", "#BFCCE6"
plt.rcParams.update({
    "font.family": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 8.5,
    "axes.edgecolor": "#B8C0CE", "axes.labelcolor": MUTED, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "svg.fonttype": "none",
})
CHART_H = 1.8  # inches; chart heights in the 2x2 grid

COMMENTARY_SECTIONS = {
    "authors": "Names for the byline, e.g. Risk team: A. Smith, B. Jones",
    "headline": "One line: the risk story this period",
    "body": "About 100 words: what changed in the risk profile and why, what is driving it, and what we are "
            "watching next. Short paragraphs; start a line with '- ' for a bullet.",
}


# ---------------------------------------------------------------- report folders
def report_dir(n: int) -> Path:
    return C.DASHBOARD_DIR / f"report_{n:02d}"


def report_number(p: Path) -> int | None:
    m = re.fullmatch(r"report_(\d+)", p.name)
    return int(m.group(1)) if m else None


def reports_with_data() -> list[tuple[int, Path]]:
    """All report folders that have pulled data, in order."""
    out = [(report_number(p), p) for p in C.DASHBOARD_DIR.iterdir() if p.is_dir() and report_number(p) is not None]
    return sorted((n, p) for n, p in out if (p / "data" / "summary.json").exists())


def read_summary(p: Path) -> dict:
    return json.loads((p / "data" / "summary.json").read_text(encoding="utf-8").replace("NaN", "null"))


def load_report(n: int) -> dict:
    rdir = report_dir(n)
    dd = rdir / "data"
    if not (dd / "summary.json").exists():
        raise SystemExit(f"No data in {dd}. Run pull_data.py {n} on the Bloomberg PC first.")

    def rd(name):
        f = dd / f"{name}.csv"
        return pd.read_csv(f) if f.exists() else pd.DataFrame()

    d = {"n": n, "summary": read_summary(rdir), "positions": rd("positions"), "var_contrib": rd("var_contribution"),
         "var": rd("var_hist_pnl"), "limits": rd("limits")}
    earlier = [(m, p) for m, p in reports_with_data() if m < n]
    if earlier:
        m, p = earlier[-1]
        ps = read_summary(p)
        d["prev"] = {"summary": ps, "label": day_mon(ps.get("as_of")) or f"report {m}"}
    return d


# ---------------------------------------------------------------- commentary
def commentary_template(n: int) -> str:
    return (f"# Risk dashboard commentary: report {n}\n\n"
            "Write under each heading below (replace nothing, just type under the grey comment), save, then\n"
            "rebuild the PDF from the repo folder:\n\n"
            f"    python reports/dashboard/build_report.py {n}\n\n"
            "Empty sections show a grey placeholder on the PDF.\n\n"
            "PUBLIC REPO: this file is committed to GitHub. Do not name holdings or give position sizes,\n"
            "NAV or £ amounts here. Teams, sectors, themes and % risk figures are fine.\n\n"
            + "".join(f"## {k}\n<!-- {v} -->\n\n\n" for k, v in COMMENTARY_SECTIONS.items()))


def ensure_commentary(n: int) -> Path:
    f = report_dir(n) / "commentary.md"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(commentary_template(n), encoding="utf-8")
    return f


def load_commentary(n: int) -> dict[str, str]:
    text = re.sub(r"<!--.*?-->", "", ensure_commentary(n).read_text(encoding="utf-8"), flags=re.S)
    parts = re.split(r"^## +(\w+)\s*$", text, flags=re.M)
    return {k: v.strip() for k, v in zip(parts[1::2], parts[2::2])}


# ---------------------------------------------------------------- formatting
def day_mon(x, year=False) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    t = pd.Timestamp(x)
    return f"{t.day} {t:%b}" + (f" {t.year}" if year else "")


def isnum(v) -> bool:
    return isinstance(v, (int, float)) and not (math.isnan(v) or math.isinf(v))


def num(v, fmt="{:.1f}%", na="N/A") -> str:
    return fmt.format(v) if isnum(v) else na


def short_name(sec) -> str:
    return re.sub(r" (Equity|Index)$", "", str(sec)) if sec else ""


def commentary_html(text: str | None, key: str) -> str:
    if not text:
        return f'<p class="ph">[{html.escape(COMMENTARY_SECTIONS[key])}]</p>'
    out, items = [], []
    for line in text.splitlines():
        if line.lstrip().startswith(("- ", "* ")):
            items.append(f"<li>{html.escape(line.lstrip()[2:])}</li>")
        elif line.strip():
            if items:
                out.append(f"<ul>{''.join(items)}</ul>")
                items = []
            out.append(f"<p>{html.escape(line.strip())}</p>")
    if items:
        out.append(f"<ul>{''.join(items)}</ul>")
    return "".join(out)


def svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", transparent=True)
    plt.close(fig)
    s = buf.getvalue()
    s = s[s.index("<svg"):]
    return re.sub(r'<svg([^>]*?) width="[^"]+" height="[^"]+"', r'<svg\1', s, count=1)


def top_legend(ax, ncol):
    ax.legend(frameon=False, fontsize=7.5, ncol=ncol, loc="lower left", bbox_to_anchor=(0, 1.0),
              borderaxespad=0.2, handlelength=1.2, columnspacing=1.2)


# ---------------------------------------------------------------- charts
def team_frame(d) -> pd.DataFrame:
    """Per team: long, short, gross, net (% NAV), risk share (%), positions. Always all report teams."""
    pos, nav = d["positions"], d["summary"]["nav"]
    pos = pos.assign(long=pos["mv"].clip(lower=0), short=pos["mv"].clip(upper=0))
    g = pos.groupby("team").agg(long=("long", "sum"), short=("short", "sum"), risk=("risk_share_pct", "sum"), n=("mv", "size"))
    g[["long", "short"]] = g[["long", "short"]] / nav * 100
    g["gross"], g["net"] = g["long"] - g["short"], g["long"] + g["short"]
    order = C.REPORT_TEAMS + sorted(set(g.index) - set(C.REPORT_TEAMS))
    return g.reindex(order).fillna({"long": 0, "short": 0, "gross": 0, "net": 0, "risk": 0, "n": 0})


def chart_team_exposure(d, w=3.6, h=CHART_H):
    g = team_frame(d)
    fig, ax = plt.subplots(figsize=(w, h), layout="constrained")
    y = np.arange(len(g))[::-1]
    ax.barh(y, g["long"], 0.6, color=BLUE, label="Long")
    ax.barh(y, g["short"], 0.6, color=AMBER, label="Short")
    ax.scatter(g["net"].where(g["n"] > 0), y, marker="|", s=60, color=INK, linewidths=1.6, zorder=3, label="Net")
    for yi, lo, net, n in zip(y, g["long"], g["net"], g["n"]):
        ax.text(lo + 1, yi, f"net {net:+.0f}%" if n else "no positions", va="center", fontsize=7.5, color=INK if n else MUTED)
    ax.set_yticks(y, g.index)
    ax.tick_params(axis="y", length=0)
    ax.axvline(0, color="#B8C0CE", lw=0.8)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(decimals=0))
    ax.set_xlim(min(-5, g["short"].min() * 1.15), max(10, g["long"].max() * 1.4))
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    top_legend(ax, 3)
    return svg(fig)


def chart_team_risk(d, w=3.6, h=CHART_H):
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
    ax.set_yticks(y, g.index)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, max(10, max(gs.max(), rs.max()) * 1.3))
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(decimals=0))
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    top_legend(ax, 2)
    return svg(fig)


def chart_var_contrib(d, w=3.6, h=CHART_H):
    c = d["var_contrib"]
    fig, ax = plt.subplots(figsize=(w, h), layout="constrained")
    if c.empty:
        return svg(fig)
    pos = d["positions"]
    team = pos.loc[pos["mv"].abs().groupby(pos["security"]).idxmax()].set_index("security")["team"]
    c = c.reindex(c["contrib_gbp"].abs().sort_values(ascending=False).index).head(8).iloc[::-1]
    labels = [f"{short_name(x)} · {team.get(x, '')}" for x in c["security"]]
    y = np.arange(len(c))
    ax.barh(y, c["pct"], 0.6, color=[BLUE if v >= 0 else AMBER for v in c["pct"]])
    for yi, v, g in zip(y, c["pct"], c["contrib_gbp"]):  # negative bars: label right of zero, clear of the names
        ax.text(max(v, 0) + 1, yi, f"{v:.0f}%  {'−' if g < 0 else ''}£{abs(g) / 1e3:,.0f}k", va="center",
                ha="left", fontsize=7.5, color=INK)
    ax.set_yticks(y, labels)
    ax.tick_params(axis="y", length=0)
    ax.axvline(0, color="#B8C0CE", lw=0.8)
    lo, hi = min(0, c["pct"].min()), c["pct"].max()
    ax.set_xlim(lo * 1.15 - 1, hi * 1.45 + 2)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(decimals=0))
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    return svg(fig)


def chart_factors(d, w=3.6, h=CHART_H):
    s = d["summary"]
    names = ["market", *C.FACTORS]
    v = np.array([s.get(f"factor_{n}") if isnum(s.get(f"factor_{n}")) else np.nan for n in names], dtype=float)
    fig, ax = plt.subplots(figsize=(w, h), layout="constrained")
    y = np.arange(len(names))[::-1]
    ax.barh(y, np.nan_to_num(v), 0.6, color=[INK if i == 0 else BLUE for i in range(len(v))])
    for yi, x in zip(y, v):
        ax.text(np.nan_to_num(x) + (0.03 if not x < 0 else -0.03), yi, "N/A" if np.isnan(x) else f"{x:+.2f}",
                va="center", ha="right" if x < 0 else "left", fontsize=7.5, color=INK)
    ax.axvline(0, color="#B8C0CE", lw=0.8)
    ax.set_yticks(y, [n.replace("_", " ").capitalize() for n in names])
    ax.tick_params(axis="y", length=0)
    lim = max(1.0, np.nanmax(np.abs(v)) * 1.35) if not np.isnan(v).all() else 1.0
    ax.set_xlim(-lim, lim)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    return svg(fig)


# ---------------------------------------------------------------- page components
def change(cur, prev, fmt, unit, sense, label) -> str:
    """Arrow = direction of the number. Colour = risk: red if risk rose, green if it fell."""
    if label is None:
        return '<span class="chg flat">first report</span>'
    if not (isnum(cur) and isnum(prev)):
        return f'<span class="chg flat">no data</span> for {label}'
    dec = 2 if ".2f" in fmt else 1
    delta = cur - prev
    if abs(delta) < 0.5 * 10 ** -dec:
        return f'<span class="chg flat">– unchanged</span> vs {label}'
    more_risk = {"up": delta > 0, "down": delta < 0, "abs": abs(cur) > abs(prev)}[sense]
    return (f'<span class="chg {"worse" if more_risk else "better"}">{"▲" if delta > 0 else "▼"} '
            f'{delta:+.{dec}f}{unit}</span> vs {label}')


def kpis(d) -> str:
    s, p = d["summary"], d.get("prev")
    extra = {"largest_position_pct_nav": short_name(s.get("largest_position")),
             "current_drawdown_pct": f"max {num(s.get('max_drawdown_pct'))}"}
    tiles = []
    for key, label, fmt, unit, sense in C.TILES:
        chg = change(s.get(key), p["summary"].get(key) if p else None, fmt, unit, sense, p["label"] if p else None)
        more = f" · {html.escape(extra[key])}" if extra.get(key) else ""
        tiles.append(f'<div class="kpi"><div class="l">{label}</div><div class="v">{num(s.get(key), fmt)}</div>'
                     f'<div class="d">{chg}{more}</div></div>')
    proxy = " · NAV = gross MV (no cash data)" if str(s.get("nav_source", "")).startswith("proxy") else ""
    return (f'<div class="kpis">{"".join(tiles)}</div>'
            f'<div class="note">% of NAV unless stated; NAV £{s["nav"] / 1e6:.2f}m{proxy}. '
            f'Arrows: change since previous report; red = more risk, green = less.</div>')


def mandate(d) -> str:
    lim = d["limits"]
    if lim.empty or "value" not in lim.columns:
        return '<p class="ph">Risk limits not set: add them to LIMITS in design/config.py.</p>'
    rows = []
    for r in lim.itertuples():
        lo = None if pd.isna(r.min) else float(r.min)
        hi = None if pd.isna(r.max) else float(r.max)
        if pd.isna(r.value):
            st, val = '<span class="badge b-watch">No data</span>', "N/A"
        else:
            breach = (lo is not None and r.value < lo) or (hi is not None and r.value > hi)
            near = not breach and hi is not None and r.value > 0.9 * hi
            st = ('<span class="badge b-breach">▲ Breach</span>' if breach else
                  '<span class="badge b-watch">● Near</span>' if near else '<span class="badge b-ok">✓ OK</span>')
            val = f"{r.value:.1f}"
        bound = " to ".join(f"{x:g}" for x in (lo, hi) if x is not None)
        rows.append(f'<tr><td>{C.LIMIT_LABELS.get(r.metric, r.metric)}</td><td class="n">{val}</td>'
                    f'<td class="n">{"≤ " if lo is None else "≥ " if hi is None else ""}{bound}</td><td>{st}</td></tr>')
    return ('<table class="mt"><tr><th>Limit</th><th class="n">Actual</th><th class="n">Limit</th><th>Status</th></tr>'
            + "".join(rows) + "</table>")


def flags(d) -> str:
    """Automatic risk flags shown under the mandate table."""
    s, items = d["summary"], []
    c = d["var_contrib"]
    if not c.empty:
        top = c.sort_values("pct").iloc[-1]
        if top["pct"] > 30:
            items.append(f"{short_name(top['security'])} drives {top['pct']:.0f}% of VaR")
    if not items:
        return ""
    return '<ul class="flags">' + "".join(f'<li class="f-watch"><span>●</span>{html.escape(t)}</li>' for t in items) + "</ul>"


def sensitivities(d) -> str:
    """What-ifs from data already pulled: market shock via beta, rates regressions, worst historical day."""
    s, nav, rows = d["summary"], d["summary"]["nav"], []
    if isnum(s.get("beta")):
        rows.append(("MSCI World −10%", -10 * s["beta"], "via beta"))
    for k, lab in (("uk", "UK 10y +100bp"), ("us", "US 10y +100bp")):
        v = s.get(f"rates_sens_{k}_10y_pct_per_100bp")
        if isnum(v):
            rows.append((lab, v, "2y regression"))
    v = d["var"]
    if not v.empty:
        i = v["pnl_pct_nav"].idxmin()
        rows.append(("Worst day, today's book", v.loc[i, "pnl_pct_nav"], day_mon(v.loc[i, "date"], year=True) if "date" in v else ""))
    out = "".join(f'<tr><td>{lab}</td><td class="n">{x:+.1f}%</td><td class="n">{"−" if x < 0 else "+"}£{abs(x) / 100 * nav / 1e3:,.0f}k</td>'
                  f'<td class="src">{src}</td></tr>' for lab, x, src in rows)
    return ('<table class="mt"><tr><th>Sensitivity</th><th class="n">%&nbsp;NAV</th><th class="n">£</th><th></th></tr>'
            + out + "</table>")


def method_note(d) -> str:
    s = d["summary"]
    notes = [f"Data: Bloomberg PORT and prices to {s.get('as_of')}, {s.get('base_ccy', 'GBP')}. VaR/ES: historical "
             f"simulation, today's holdings over {s.get('var_history_days', '?')} days; contributions scaled to sum to VaR. "
             f"Ex-ante vol: {C.COV_WINDOW}-day covariance. Beta and factors: {C.BETA_WEEKS}-week regressions. "
             f"Team figures % of fund NAV."]
    if str(s.get("nav_source", "")).startswith("proxy"):
        notes.append("NAV excludes cash, so % NAV figures are % of gross.")
    if (s.get("perf_days") or 0) < C.MIN_DAYS_FOR_STATS:
        notes.append(f"Only {s.get('perf_days')} days of fund history: drawdown is indicative.")
    if d.get("demo"):
        notes.append("ILLUSTRATIVE DATA, NOT BIF HOLDINGS.")
    return " ".join(notes)


def chart(title: str, sub: str, body: str) -> str:
    return f'<div class="chart"><div class="ct">{title}</div><div class="cs">{sub}</div>{body}</div>'


def box(title: str, body: str, cls: str = "") -> str:
    return f'<div class="box {cls}"><h3>{title}</h3>{body}</div>'


def editorial(com) -> str:
    head = html.escape(com["headline"]) if com.get("headline") else f'<span class="ph">[{COMMENTARY_SECTIONS["headline"]}]</span>'
    return f'<div class="box editorial"><h3>{head}</h3><div class="cols">{commentary_html(com.get("body"), "body")}</div></div>'


def page(d, com) -> str:
    s = d["summary"]
    authors = html.escape(com.get("authors") or "Risk team [authors]")
    label = "DESIGN PREVIEW: ILLUSTRATIVE DATA" if d.get("demo") else f"BIF risk dashboard &nbsp;|&nbsp; Report {d['n']}"
    factor_sub = f"Fund betas to MSCI World and factor spreads, 2y weekly · R² {num(s.get('factor_r2_systematic_pct'), '{:.0f}%')}"
    grid = (f'<div class="g2">'
            f'{chart("Exposure by team", "Long and short, % of fund NAV; tick = net", chart_team_exposure(d))}'
            f'{chart("Risk by team", "Share of gross vs share of ex-ante volatility (amber: risk well above capital)", chart_team_risk(d))}'
            f'{chart("Top contributors to VaR", "Top 8 positions, share of 1-day VaR99 (amber: reduces VaR)", chart_var_contrib(d))}'
            f'{chart("Factor exposures", factor_sub, chart_factors(d))}'
            f'</div><div class="g2b">{box("Mandate checks", mandate(d) + flags(d), "blue")}'
            f'{box("Sensitivity tests", sensitivities(d), "blue")}</div>')
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>BIF risk dashboard: report {d['n']} ({s.get('as_of')})</title><style>{STYLE.read_text(encoding="utf-8")}</style></head>
<body><div class="page">
<div class="hdr"><div class="logo"><b>BF</b><span>Bristol<br>Investment<br>Fund</span></div>
<div class="month">AS OF {day_mon(s.get('as_of'), year=True).upper()}</div></div>
<div class="content">
<div class="kicker">Risk</div><h1 class="title">Risk at a glance</h1>
<div class="byline">{authors}</div>
{kpis(d)}
{editorial(com)}
{grid}</div>
<div class="note method">{html.escape(method_note(d))}</div>
<div class="foot"><span>{label}</span><b>R1</b></div></div></body></html>"""


# ---------------------------------------------------------------- output
def find_browser() -> str | None:
    for c in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"):
        if Path(c).exists():
            return c
    for name in ("google-chrome", "chromium", "chrome", "msedge"):
        if shutil.which(name):
            return shutil.which(name)
    return None


def print_pdf(html_file: Path, pdf: Path) -> bool:
    """Print the HTML page to PDF with headless Edge/Chrome. Returns True if the PDF was (re)written."""
    browser = find_browser()
    if not browser:
        print("No Edge or Chrome found: open the .html in a browser and print to PDF (A4, no margins).")
        return False
    before = pdf.stat().st_mtime if pdf.exists() else None
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={profile}",
                        f"--print-to-pdf={pdf}", html_file.as_uri()], capture_output=True, timeout=180, check=False)
    if not pdf.exists() or pdf.stat().st_mtime == before:
        print(f"PDF not written: is {pdf.name} open in another program? Close it and run again.")
        return False
    return True


def update_history() -> Path:
    """Rebuild metrics_history.csv: the headline numbers of every report, one row each."""
    rows = []
    for n, p in reports_with_data():
        s = read_summary(p)
        rows.append({"report": n, "as_of": s.get("as_of"), "nav": s.get("nav"),
                     **{k: s.get(k) for k, *_ in C.TILES}, "largest_position": s.get("largest_position")})
    pd.DataFrame(rows).to_csv(C.HISTORY_FILE, index=False)
    return C.HISTORY_FILE


# ---------------------------------------------------------------- demo data (design work, no Bloomberg)
DEMO_COMMENTARY = {
    "authors": "Risk team [authors]",
    "headline": "Gross is back above its limit as TMT shorts grow; risk is concentrated in TMT",
    "body": "Gross rose 6pp to 228%, above the 200% limit, as TMT and Materials added shorts; net fell to 18%.\n"
            "TMT holds 16% of gross but 25% of volatility: its two largest longs, both AI-capex names, top the VaR "
            "contributors and trade almost as one.\n"
            "What we are watching:\n"
            "- Gross breach: TMT and Materials PMs to reduce or justify.\n"
            "- TMT earnings w/c 8 December.\n"
            "- Momentum reversal if rate-cut expectations shift.",
}


def demo_data() -> dict:
    """Invented 8-team long/short book (no real holdings) to work on the layout at full scale."""
    rng = np.random.default_rng(7)
    nav, rows = 3_000_000, []
    for i, team in enumerate(C.REPORT_TEAMS):
        for j in range(rng.integers(3, 7)):
            short = j >= 3 or (j == 2 and i % 3 == 0)
            rows.append({"security": f"{team[:3].upper()}{j + 1} XX Equity", "team": team,
                         "mv": (-1 if short else 1) * rng.uniform(0.02, 0.09) * nav})
    pos = pd.DataFrame(rows)
    share = pos["mv"].abs() * rng.uniform(0.5, 1.8, len(pos)) * np.where(pos["team"] == "TMT", 1.8, 1)
    pos["risk_share_pct"] = share / share.sum() * 100
    mkt = rng.standard_t(4, 1260) * 0.008
    sens = pd.Series(np.where(pos["mv"] > 0, 1.0, 0.8) * rng.uniform(0.6, 1.4, len(pos)), index=pos["security"])
    sens[pos["team"].eq("TMT").to_numpy()] *= 1.6
    dates = pd.bdate_range(end="2026-11-30", periods=len(mkt))
    rets = pd.DataFrame(np.outer(mkt, sens) + rng.normal(0, 0.014, (len(mkt), len(pos))), index=dates, columns=pos["security"])
    pos_pnl = rets * pos.set_index("security")["mv"]
    port = pos_pnl.sum(axis=1)
    q99, q95 = port.quantile(0.01), port.quantile(0.05)
    mv = pos.set_index("security")["mv"]
    beta = float((mv * sens).sum() / nav * 0.9)
    summary = {"as_of": "2026-11-30", "nav": nav, "nav_source": "user", "base_ccy": "GBP",
               **risk.exposure(mv, nav), **risk.concentration(mv, nav), "beta": beta,
               "factor_market": beta, "factor_value": -0.18, "factor_momentum": 0.24, "factor_quality": 0.31,
               "factor_min_vol": -0.12, "factor_small_cap": 0.09, "factor_r2_systematic_pct": 64,
               "ex_ante_vol_pct": 11.8, "rates_sens_uk_10y_pct_per_100bp": -2.1, "rates_sens_us_10y_pct_per_100bp": -1.4,
               "var_99_gbp": -q99, "var_99_pct_nav": -q99 / nav * 100, "var_95_pct_nav": -q95 / nav * 100,
               "es_99_pct_nav": -port[port <= q99].mean() / nav * 100, "var_history_days": len(port),
               "current_drawdown_pct": -2.4, "max_drawdown_pct": -5.9, "perf_days": 42}
    lim = risk.check_limits(summary)
    prev = dict(summary, as_of="2026-10-31", var_99_pct_nav=summary["var_99_pct_nav"] - 0.21,
                es_99_pct_nav=summary["es_99_pct_nav"] + 0.3, ex_ante_vol_pct=10.9, beta=beta - 0.03,
                gross_pct_nav=summary["gross_pct_nav"] - 6.1, net_pct_nav=summary["net_pct_nav"] + 4.2,
                largest_position_pct_nav=summary["largest_position_pct_nav"], current_drawdown_pct=-3.1)
    var = pd.DataFrame({"date": dates, "pnl_pct_nav": port.to_numpy() / nav * 100})
    return {"n": 0, "demo": True, "summary": summary, "prev": {"summary": prev, "label": "31 Oct"}, "positions": pos,
            "var_contrib": risk.var_contributions(pos_pnl), "var": var, "limits": lim}
