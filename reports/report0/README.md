# Report 0: START HERE

Report 0 is the Risk team's part of the **BIF Monthly Research Review, November 2026 issue**,
published **Mon 7 Dec 2026**. Everything for it lives in this folder.

**This repo is public: treat every commit as public.** Never commit BIF holdings, NAV or position
sizes, or raw Bloomberg exports. Public-company information and numbers you derive are fine.

## What the report is

| Part | What | Who | Where |
|---|---|---|---|
| R1 | One-page risk dashboard, built automatically from the Bloomberg pull | Oscar | `commentary.md` (text), `data/` (pull, OneDrive only) |
| R2+ | **AI supply chain as a thematic risk**, sections 1-3 | Teams 1 and 2, then the Risk team | [`report.md`](report.md) |

[`report.md`](report.md) is **the report**: one document with every section. Each section names
its lead and status. When every section 1.1-2.6 says "Ready for review", we have a full draft
apart from our recommendations (section 3, written last). Oscar then cuts it into the printed
pages (`pages.md`, built with `python infrastructure/dashboard/build_report.py 0`).

Team 1: Baily, Johnny, Alex, Dom. Team 2: Guiseppe, Bea, Alexia.

## Where to work

```
report0/
  README.md                 this page
  report.md                 THE REPORT: write your sections here
  commentary.md             dashboard text (R1)
  ai-thematic/              all the work behind sections 1-2
    README.md               agreed method: basket, benchmark, shock rule, dates, data
    basket.csv              the shared AI basket (Team 1 owns it)
    benchmark.csv           S&P 500 ex-AI tickers (Team 1 adds it; tickers only)
    code/                   shared code, used by both teams
    figures/                charts used in report.md, named fig_<section>_<name>.png
    work/                   one folder per task, each with a README saying what to do
      t1-a-basket/              Team 1: final basket and benchmark (do first)
      t1-b-correlation/         Team 1: sections 2.1, 2.2
      t1-c-single-points-of-failure/  Team 1: sections 1.3, 1.4
      t1-d-context/             Team 1: sections 1.1, 1.2, 1.5
      t2-a-shock-rule/          Team 2: section 2.3 (definition)
      t2-b-frequency-events/    Team 2: section 2.3 (counts, events)
      t2-c-shock-correlation/   Team 2: sections 2.4, 2.5
    drafts/team-1/, team-2/ the 23 Nov drafts (reference only, don't edit)
    planning/               briefing and the team to-do lists
```

Raw Bloomberg exports (prices, index weights, SPLC) go in the shared OneDrive folder
**`BIF-risk-team-shared-data/ai-supply-chain/bloomberg/`**, never in the repo. Log each file in
that folder's README.

## How to work

1. `git pull` before you start.
2. Open your task's folder under `ai-thematic/work/` and read its README.
3. Export what you need from Bloomberg into the shared OneDrive `bloomberg/` folder.
4. Run the shared code (`ai-thematic/code/`). Save result tables in your task folder and charts
   in `ai-thematic/figures/`.
5. Write your text into your sections of `report.md`, add sources to its Sources list, and set
   your section's status line (Not started / Drafting / Ready for review).
6. Commit and `git push` when you finish a session. Edit only your own sections of `report.md`.

The full to-do lists, task by task: [`ai-thematic/planning/team_todo_lists.md`](ai-thematic/planning/team_todo_lists.md).

## Order of work

1. Team 1 finishes `basket.csv` and `benchmark.csv` (task t1-a). **Team 2 waits for this.**
2. Both teams run their analysis on Bloomberg prices, in parallel.
3. Both teams write their sections of `report.md`, including section 2.6 (methods).
4. The Risk team reviews and writes section 3. Oscar builds the PDF.
