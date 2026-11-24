# T2-A: Shock rule (Team 2)

**Feeds:** `report.md` section 2.3 (definition) and 2.6. **Needs:** T1-A done.
**Code:** `../../code/shocks.py`. **Outputs:** shock list and episode tables (CSV) in this folder.

- [ ] Write `shocks.py`: tickers from `basket.csv` (supply chain side) and `benchmark.csv`, Bloomberg
      prices from the shared OneDrive `bloomberg/` folder. Port the rule from your midterm code.
- [ ] Headline rule: basket daily return beyond ±2.5 sd of its previous 250 trading days (today
      excluded); shock days within 5 trading days form one episode; up and down counted separately.
- [ ] Label each shock AI-led (basket also trails/beats S&P ex-AI by more than 2.5 sd) or broad.
- [ ] Sensitivity at 2 and 3 sd.
- [ ] Write the definition in 2.3, with a worked example (e.g. 5 Nov 2026) in 2.6.
