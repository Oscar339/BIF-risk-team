"""Free pages after the dashboard (R2, R3, ...): blank space the Risk team fills each month.

Each report has `report_XX/pages.md`. Every `# page` heading starts a new A4 page. Under it, optional
`key: value` lines set the header, then anything in the body:

    # page
    kicker: Stress test
    title: What a 2022-style rates shock does to the book
    byline: Risk team: A. Smith, B. Jones
    sources: S01 Bloomberg prices to 30 Nov 2026. Shocks are assumptions, not forecasts.

    Paragraph text. **bold**, *italic*.

    ## Sub-heading                     ### Small heading
    - bullet                           1. numbered
    > **Box title**                    (a beige box; "> !" for a blue box)
    > Box text
    ![Figure 2 | Caption | Source S01](rates_shock.svg)   (file in report_XX/figures/)
    | Table | header |                 (Markdown table; numbers right-align)
    ::: tiles                          (number tiles, one per line: label | value | note)
    Fund impact | -4.2% NAV | £-126k
    :::
    ::: cols                           (side-by-side columns; a line with ||| starts the next column)
    left ...
    |||
    right ...
    :::
    ::: text2                          (one block of text flowing over two columns)
    :::
    Note: small grey footnote line.

No Markdown library needed, so this runs in the bare team venv on any machine.
"""
from __future__ import annotations

import base64
import html
import re
from pathlib import Path

PAGES_FILE = "pages.md"
FIGURES_DIR = "figures"

TEMPLATE = """# Risk pages: report {n}

Free pages after the dashboard. Fill them with whatever this month needs: a stress test, modelling,
advice to the teams, a thematic piece, or a risk view of recent events (leave market narrative to
Investment Reporting). Then rebuild:

    python reports/dashboard/build_report.py {n}

Every "# page" heading starts a new A4 page (R2, R3, ...). If a page overflows, the PDF shows a red
warning bar and the build says so: cut text or shrink a figure. Figures go in report_{n:02d}/figures/.
Formatting cheat sheet: top of reports/dashboard/design/pages.py, or the preview pages.md.

This file and figures/ stay in OneDrive only (gitignored), so naming holdings is fine here.

# page
kicker: Risk
title: [Page title]
byline: Risk team [authors]
sources:

<!-- R2: anything this month needs. Delete this comment and write. -->

# page
kicker: Risk
title: [Page title]
byline: Risk team [authors]
sources:

<!-- R3: anything this month needs. Delete this comment and write. -->
"""

HEADER_KEYS = ("kicker", "title", "byline", "sources")


def ensure_pages(folder: Path, n: int) -> Path:
    f = folder / PAGES_FILE
    if not f.exists():
        folder.mkdir(parents=True, exist_ok=True)
        f.write_text(TEMPLATE.format(n=n), encoding="utf-8")
    return f


# ---------------------------------------------------------------- parsing
def split_pages(text: str) -> list[dict]:
    """pages.md -> [{kicker, title, byline, sources, body}], one per '# page'. Text before the first is ignored."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    chunks = re.split(r"^# +page\s*$", text, flags=re.M | re.I)[1:]
    pages = []
    for chunk in chunks:
        lines = chunk.strip("\n").splitlines()
        head = {k: "" for k in HEADER_KEYS}
        i = 0
        while i < len(lines):
            m = re.fullmatch(r"(\w+):\s*(.*)", lines[i].strip())
            if m and m.group(1).lower() in HEADER_KEYS:
                head[m.group(1).lower()] = m.group(2).strip()
                i += 1
            elif not lines[i].strip():
                i += 1
            else:
                break
        head["body"] = "\n".join(lines[i:]).strip()
        pages.append(head)
    return pages


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<i>\1</i>", s)
    return s


NUM = re.compile(r"^[−\-+£$€]?[\d.,]+\s*(%|pp|bp|x|k|m|bn)?$|^N/A$|^–$")


class Renderer:
    def __init__(self, fig_dir: Path, warn: list[str]):
        self.fig_dir, self.warn = fig_dir, warn

    def blocks(self, text: str) -> str:
        lines, out, i = text.splitlines(), [], 0
        while i < len(lines):
            ln = lines[i]
            s = ln.strip()
            if not s:
                i += 1
            elif s.startswith(":::"):
                kind = s[3:].strip().split()
                depth, j = 1, i + 1
                while j < len(lines):  # find the matching ':::' (blocks may nest)
                    t = lines[j].strip()
                    if t.startswith(":::") and t[3:].strip():
                        depth += 1
                    elif t == ":::":
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                out.append(self.container(kind, lines[i + 1:j]))
                i = j + 1
            elif s.startswith("### "):
                out.append(f"<h4>{inline(s[4:])}</h4>")
                i += 1
            elif s.startswith("## "):
                out.append(f"<h2>{inline(s[3:])}</h2>")
                i += 1
            elif s.startswith(">"):
                j = i
                while j < len(lines) and lines[j].strip().startswith(">"):
                    j += 1
                out.append(self.callout([re.sub(r"^\s*> ?", "", x) for x in lines[i:j]]))
                i = j
            elif s.startswith("!["):
                out.append(self.figure(s))
                i += 1
            elif s.startswith("|"):
                j = i
                while j < len(lines) and lines[j].strip().startswith("|"):
                    j += 1
                out.append(self.table(lines[i:j]))
                i = j
            elif re.match(r"^([-*]|\d+\.) ", s):
                ordered = bool(re.match(r"^\d+\. ", s))
                items, j = [], i
                while j < len(lines) and re.match(r"^\s*([-*]|\d+\.) ", lines[j]):
                    items.append(f"<li>{inline(re.sub(r'^\s*([-*]|\d+\.) ', '', lines[j]))}</li>")
                    j += 1
                tag = "ol" if ordered else "ul"
                out.append(f"<{tag}>{''.join(items)}</{tag}>")
                i = j
            elif re.match(r"^(Note|Source|Sources):", s):
                out.append(f'<p class="fn">{inline(s)}</p>')
                i += 1
            else:
                j = i
                while j < len(lines) and lines[j].strip() and not re.match(r"^(#|>|!\[|\||:::|([-*]|\d+\.) )", lines[j].strip()):
                    j += 1
                out.append(f"<p>{inline(' '.join(x.strip() for x in lines[i:j]))}</p>")
                i = j
        return "".join(out)

    def container(self, kind: list[str], lines: list[str]) -> str:
        name = kind[0].lower() if kind else ""
        if name == "tiles":
            tiles = []
            for ln in filter(str.strip, lines):
                label, value, note = ([p.strip() for p in ln.split("|")] + ["", ""])[:3]
                tiles.append(f'<div class="kpi"><div class="l">{inline(label)}</div><div class="v">{inline(value)}</div>'
                             f'<div class="d">{inline(note)}</div></div>')
            return f'<div class="kpis free n{min(len(tiles), 4)}">{"".join(tiles)}</div>'
        if name == "cols":
            cols, cur = [], []
            for ln in lines:
                if ln.strip() == "|||":
                    cols.append(cur)
                    cur = []
                else:
                    cur.append(ln)
            cols.append(cur)
            widths = kind[1] if len(kind) > 1 else ""  # e.g. "::: cols 2:1"
            tpl = " ".join(f"{w}fr" for w in widths.split(":")) if re.fullmatch(r"\d+(:\d+)+", widths) else f"repeat({len(cols)},1fr)"
            return (f'<div class="fcols" style="grid-template-columns:{tpl}">'
                    + "".join(f"<div>{self.blocks(chr(10).join(c))}</div>" for c in cols) + "</div>")
        if name == "text2":
            return f'<div class="text2">{self.blocks(chr(10).join(lines))}</div>'
        if name in ("box", "bluebox"):
            return self.callout(lines, blue=name == "bluebox")
        self.warn.append(f"Unknown block '::: {name}' (use tiles, cols, text2, box): shown as plain text.")
        return self.blocks("\n".join(lines))

    def callout(self, lines: list[str], blue: bool = False) -> str:
        if lines and lines[0].strip() == "!":
            blue, lines = True, lines[1:]
        title = ""
        if lines and re.fullmatch(r"\s*\*\*(.+)\*\*\s*", lines[0]):
            title = f"<h3>{inline(lines[0].strip()[2:-2])}</h3>"
            lines = lines[1:]
        return f'<div class="box{" blue" if blue else ""}">{title}{self.blocks(chr(10).join(lines))}</div>'

    def figure(self, s: str) -> str:
        m = re.fullmatch(r"!\[(.*?)\]\((.+?)\)(\{.*\})?", s)
        if not m:
            return f"<p>{inline(s)}</p>"
        cap, src, opts = m.group(1), m.group(2).strip(), (m.group(3) or "")
        f = self.fig_dir / src
        style = ""
        h = re.search(r"height\s*=\s*(\d+)\s*mm", opts)  # ![..](x.svg){height=60mm}
        if h:
            style = f' style="max-height:{h.group(1)}mm"'
        if not f.exists():
            self.warn.append(f"Figure not found: {f}")
            body = f'<div class="figmissing">[Missing figure: {html.escape(src)}]</div>'
        elif f.suffix.lower() == ".svg":
            svg = f.read_text(encoding="utf-8")
            svg = svg[svg.index("<svg"):]
            svg = re.sub(r'<svg([^>]*?) width="[^"]+" height="[^"]+"', r"<svg\1", svg, count=1)
            body = f'<div class="svgwrap"{style}>{svg}</div>'
        else:
            mime = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".gif": "gif"}.get(f.suffix.lower(), "png")
            data = base64.b64encode(f.read_bytes()).decode("ascii")
            body = f'<img src="data:image/{mime};base64,{data}" alt="{html.escape(cap)}"{style}>'
        parts = [p.strip() for p in cap.split("|")]
        title = f'<div class="ct">{inline(parts[0])}</div>' if parts and parts[0] else ""
        sub = f'<div class="cs">{inline(" | ".join(parts[1:]))}</div>' if len(parts) > 1 else ""
        return f'<figure class="ffig">{title}{sub}{body}</figure>'

    def table(self, lines: list[str]) -> str:
        rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]
        rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r if c)]
        if not rows:
            return ""
        head, body = rows[0], rows[1:]

        def cls(c):
            return ' class="n"' if NUM.match(c.replace(" ", "")) else ""

        def numeric_col(k):
            vals = [r[k] for r in body if k < len(r) and r[k]]
            return bool(vals) and all(NUM.match(v.replace(" ", "")) for v in vals)

        th = "".join(f'<th{" class=n" if numeric_col(k) else ""}>{inline(c)}</th>' for k, c in enumerate(head))
        tb = "".join("<tr>" + "".join(f"<td{cls(c)}>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
        return f'<table class="mt free"><tr>{th}</tr>{tb}</table>'


def render(page: dict, fig_dir: Path, warn: list[str]) -> str:
    """The inside of one free page: header block and body HTML."""
    body = Renderer(fig_dir, warn).blocks(page["body"]) if page["body"] else \
        '<p class="ph">[Free page: stress test, modelling, advice to teams, thematic piece or a risk view of recent events.]</p>'
    title = inline(page["title"]) if page["title"] else '<span class="ph">[Page title]</span>'
    return (f'<div class="kicker">{inline(page["kicker"] or "Risk")}</div><h1 class="title">{title}</h1>'
            f'<div class="byline">{inline(page["byline"] or "Risk team [authors]")}</div>'
            f'<div class="free-body">{body}</div>')
