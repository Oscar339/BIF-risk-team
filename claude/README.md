# Claude hand-over notes

Claude Code sessions on different computers (e.g. a laptop without Bloomberg and a
university Bloomberg PC) can't message each other. This folder is how they pass work
back and forth, through git (and OneDrive).

Each person has one file: `handoff/<first-last>.md`. Only that person's sessions edit it.

## Protocol

**Start of session**
1. `git pull`
2. Read `handoff/<you>.md`. Do anything under "Requests" addressed to this machine
   type (`bloomberg` or `no-bloomberg`).

**End of session**
1. Update `handoff/<you>.md`:
   - Move finished requests to "Done" with a one-line result (where outputs are, any
     warnings). Keep only the last ~10 entries in "Done".
   - Add new requests for the other machine.
   - Update "State" if anything important changed.
2. Commit the hand-over file with the code changes, then `git push`.

## Rules
- **The repo is public.** Describe results ("v2 run OK, 3 warnings, see results/v2/20261106"),
  never paste holdings, prices, P&L or position sizes. The numbers stay in `results/` on OneDrive.
- Date every entry (YYYY-MM-DD) and say which machine wrote it.
- Keep it short. This is a to-do list, not a log.

## Template

```markdown
# Hand-over: <Name>

## State
- <what exists, what's in progress, open decisions>

## Requests
- [ ] YYYY-MM-DD for: bloomberg | no-bloomberg (from: <machine>) <what to do, how to check it worked>

## Done
- YYYY-MM-DD (<machine>) <request> -> <outcome, where outputs are>
```
