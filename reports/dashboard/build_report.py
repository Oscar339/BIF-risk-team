"""Step 2: build the risk dashboard PDF for a report from its pulled data and commentary.

No Bloomberg needed, so this runs on any machine (Mac or Windows).

Usage (from the repo folder):
    python reports/dashboard/build_report.py        # latest report
    python reports/dashboard/build_report.py 3      # report_03
    python reports/dashboard/build_report.py --demo # invented data -> design/preview/, for design changes

Reads  report_XX/data/ (from pull_data.py), report_XX/commentary.md (dashboard, R1) and
       report_XX/pages.md + report_XX/figures/ (free pages R2, R3, ...)
Writes report_XX/risk_dashboard_report_XX.pdf (+ .html), all pages in one file, and metrics_history.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from design import config as C  # noqa: E402
from design import page as P  # noqa: E402
from design import pages as FP  # noqa: E402


def build(n: int | None = None, demo: bool = False) -> Path:
    if demo:
        d, com, out = P.demo_data(), P.DEMO_COMMENTARY, C.PREVIEW_DIR
        stem = "risk_dashboard_preview"
        P.demo_figures(out / FP.FIGURES_DIR)
        pages_file = out / FP.PAGES_FILE
    else:
        if n is None:
            done = P.reports_with_data()
            if not done:
                raise SystemExit("No report has data yet. Run pull_data.py on the Bloomberg PC first.")
            n = done[-1][0]
        d, com, out = P.load_report(n), P.load_commentary(n), P.report_dir(n)
        stem = f"risk_dashboard_report_{n:02d}"
        pages_file = FP.ensure_pages(out, n)
    out.mkdir(parents=True, exist_ok=True)
    warn: list[str] = []
    free = FP.split_pages(pages_file.read_text(encoding="utf-8")) if pages_file.exists() else []
    html_pages = [P.dashboard_page(d, com)] + P.free_pages(d, free, out / FP.FIGURES_DIR, warn)
    f = out / f"{stem}.html"
    f.write_text(P.document(d, html_pages), encoding="utf-8")
    pdf = f.with_suffix(".pdf")
    if P.print_pdf(f, pdf):
        print(f"PDF:        {pdf}  ({len(html_pages)} pages: R1 dashboard + {len(free)} free)")
    for w in warn:
        print(f"WARNING:    {w}")
    over = P.overflowing_pages(f)
    if over:
        print(f"WARNING:    content runs off page {', '.join(over)}. Cut text or shrink a figure, then rebuild.")
    if not demo:
        P.update_history()
        print(f"Commentary: {P.report_dir(n) / 'commentary.md'}  (dashboard text, R1)")
        print(f"Pages:      {pages_file}  (free pages R2+, figures in {out / FP.FIGURES_DIR})")
        if "prev" not in d:
            print("No earlier report found: tiles show 'first report' instead of arrows.")
    return pdf


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", nargs="?", type=int, help="Report number (default: latest with data)")
    ap.add_argument("--demo", action="store_true", help="Render invented data to design/preview/")
    a = ap.parse_args()
    build(a.report, a.demo)
