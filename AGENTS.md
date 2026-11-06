# BIF Risk Team: notes for Codex

Shared by every team member who uses Codex. Personal instructions go in
`CLAUDE.local.md` (gitignored, never pushed).

## Context
- University of Bristol investment fund (BIF) risk team. Python research code that
  pulls portfolio and market data from Bloomberg and computes risk metrics.
- Layout: `members/<first-last>/` personal work, `infrastructure/` shared code,
  `reports/` finished write-ups, `claude/` hand-over notes between sessions.
- The repo lives in each person's University OneDrive and is also on GitHub
  (https://github.com/Oscar339/BIF-risk-team, **public**).

## Rules
- **Never commit data**: no holdings, prices, results, Bloomberg output, credentials.
  `data/` and `results/` are gitignored; keep outputs there.
- Only edit the current user's own `members/` folder unless asked. Ask before changing
  `infrastructure/` or another member's folder.
- `main` is protected against force-push and deletion. Never rewrite pushed history.
- The same OneDrive folder (including `.git`) may be open on two computers. Run git on
  one machine at a time; if git reports a lock file or odd state, stop and tell the user
  rather than deleting things.

## Bloomberg
- `blpapi` only works on a machine with the Bloomberg Terminal open and logged in
  (university Bloomberg PCs). Check with `python -c "import blpapi"` and whether the
  Terminal is running before trying a pull.
- On a machine without Bloomberg, code can be edited but not run against live data. Use
  existing outputs under `results/` (synced by OneDrive) to test, and leave a hand-over
  note asking the Bloomberg machine to run it.

## Hand-over between machines
Sessions on different machines can't talk to each other directly. They communicate
through `claude/handoff/` (shared with Claude Code sessions). See `claude/README.md`. At the start of a session, read
the current user's hand-over file; before finishing, update it.
