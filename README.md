# BIF Risk Team

Working folder for the BIF risk team.

- `members/<first-last>/` each person's individual research space (`code/`, `notebooks/`, `data/`, `results/`)
- `infrastructure/` shared code, utilities and setup used by everyone
- `reports/` finished team reports

`data/` and `results/` folders (anywhere in the repo) are OneDrive only and are excluded from git.

## Setup (any machine)
```
python -m venv %LOCALAPPDATA%\envs\bif-risk-team
%LOCALAPPDATA%\envs\bif-risk-team\Scripts\python -m pip install -r requirements.txt
```
Bloomberg API (`blpapi`) must come from Bloomberg's own index, and only works while the Bloomberg Terminal is open and logged in on that machine:
```
%LOCALAPPDATA%\envs\bif-risk-team\Scripts\python -m pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi
```
Keep the virtual environment outside OneDrive so it doesn't sync.
