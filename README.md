# BIF Risk Team

Working folder for the BIF risk team.

- `members/<first-last>/` each person's individual research space (`code/`, `notebooks/`, `data/`, `results/`)
- `infrastructure/` shared code, utilities and setup used by everyone
- `reports/` finished team reports
- `claude/` hand-over notes for Claude Code sessions (see `claude/README.md`)

> **This repository is public.** Never commit holdings, prices, results, Bloomberg output,
> passwords or API keys. `data/` and `results/` folders (anywhere in the repo) are
> excluded by `.gitignore` and stay in OneDrive only.

## Getting a copy

Clone the repo **into your University OneDrive**, so the same folder is available on the
university machines that have the Bloomberg Terminal.

Windows (university machine):
```
cd "%OneDrive%\Documents"
git clone https://github.com/Oscar339/BIF-risk-team.git BIF
```

Mac:
```
cd ~/Library/CloudStorage/OneDrive-UniversityofBristol/Documents
git clone https://github.com/Oscar339/BIF-risk-team.git BIF
```

The first `git push` opens a browser window to log in to GitHub. You need to have
accepted the collaborator invite first.

## Python setup

Keep the virtual environment **outside** OneDrive so it doesn't sync. On university
machines it lives on that PC only, so repeat this if you move to a different PC.

Windows:
```
python -m venv %LOCALAPPDATA%\envs\bif-risk-team
%LOCALAPPDATA%\envs\bif-risk-team\Scripts\python -m pip install -r requirements.txt
```

Mac:
```
python3 -m venv ~/.venvs/bif-risk-team
~/.venvs/bif-risk-team/bin/python -m pip install -r requirements.txt
```

Bloomberg API (`blpapi`) must come from Bloomberg's own index, and only works while the
Bloomberg Terminal is open and logged in on that machine (so in practice, university
Bloomberg PCs only):
```
%LOCALAPPDATA%\envs\bif-risk-team\Scripts\python -m pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi
```

## House rules

1. Work in your own `members/<first-last>/` folder. Shared code goes in `infrastructure/`;
   say so in the group before changing something there.
2. `git pull` before you start, commit small and often, `git push` when you finish.
3. If you use the same OneDrive folder from two computers, let OneDrive finish syncing
   before running git on the other one, and never run git on both at the same time.
4. Nothing confidential in commits (see the note at the top). If you commit something by
   mistake, tell Oscar straight away rather than just deleting it, because it stays in history.
5. `main` is protected against force-pushes and deletion.
