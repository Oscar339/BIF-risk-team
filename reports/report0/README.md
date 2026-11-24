# Report 0

The Risk team's pages in the BIF Monthly Research Review, November 2026 issue, out Mon 7 Dec 2026:
the risk dashboard (R1) plus the thematic piece *AI supply chain as a thematic risk*.

**The work happens in OneDrive, not here.** Open the shared folder
`BIF-risk-team-shared-data/report0/` and read **`START HERE.docx`**. That folder holds the report
(`Report 0.docx`), the to-do lists, task folders for results, charts and raw Bloomberg exports.

GitHub holds only the code:

| Path | What |
|---|---|
| `ai-thematic/basket.csv`, `benchmark.csv` | The shared AI basket and the S&P 500 ex-AI benchmark tickers |
| `ai-thematic/code/` | Shared analysis scripts (read from and write to the OneDrive folder) |
| `ai-thematic/README.md` | The agreed method, and how scripts find the OneDrive folder |
| `commentary.md` | Dashboard (R1) text, read by the build |

The dashboard build tools are in [`infrastructure/dashboard/`](../../infrastructure/dashboard/README.md).
`data/`, `pages.md`, `figures/` and the PDF in this folder are created by the build and stay out of git.

**This repo is public.** Never commit BIF holdings, NAV, position sizes or raw Bloomberg data.
