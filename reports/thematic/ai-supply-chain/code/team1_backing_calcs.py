"""
BIF Risk Team 1 - backing calculations for "The AI supply chain as a thematic risk".

Reproduces every price-based number in the deck and writes them to one workbook.

Run:  pip install yfinance pandas numpy openpyxl
      python bif_team1_backing_calcs.py

Output: BIF_Team1_backing_calcs.xlsx  (sheets listed in the README sheet)

Data: Yahoo Finance adjusted daily closes, 2 Jan 2020 to 20 Nov 2026.
Yahoo occasionally restates adjusted prices (dividends, splits), so results can
differ from the deck in the second decimal place.
"""
import itertools

import numpy as np
import pandas as pd
import yfinance as yf

START, END = "2020-01-01", "2026-11-21"   # END is exclusive: last close is 20 Nov 2026
SPLIT = "2022-11-30"                      # ChatGPT launch; "before" = up to and including this date
WINDOW = 60
OUT = "BIF_Team1_backing_calcs.xlsx"

LAYERS = {
    "Chip design": ["NVDA", "AMD", "AVGO"],
    "Foundry": ["TSM"],
    "Memory": ["MU"],
    "Equipment": ["ASML", "AMAT", "LRCX"],
    "Networking": ["ANET", "MRVL"],
    "Power and cooling": ["VRT", "ETN"],
    "Data centre operators": ["EQIX", "DLR"],
    "Hyperscalers": ["MSFT", "AMZN", "GOOGL", "META", "ORCL"],
}
CONTROL = ["JNJ", "PG", "KO", "PEP", "WMT", "COST", "JPM", "BAC", "XOM", "CVX",
           "UNH", "LLY", "MRK", "HD", "MCD", "CAT", "UNP", "NEE", "LIN", "V"]
FOREIGN = ["000660.KS", "005930.KS", "SU.PA"]   # SK Hynix, Samsung, Schneider: weekly check only
MARKET = ["SPY", "RSP"]                         # cap-weighted and equal-weight S&P 500 ETFs

AI = [t for names in LAYERS.values() for t in names]
LAYER_OF = {t: l for l, names in LAYERS.items() for t in names}


def download(tickers):
    px = yf.download(tickers, start=START, end=END, auto_adjust=True, progress=False)["Close"]
    return px[tickers]


def avg_corr(c: np.ndarray, idx_pairs) -> float:
    return float(np.mean([c[i, j] for i, j in idx_pairs]))


def rolling_measures(rets: pd.DataFrame, window: int) -> pd.DataFrame:
    """Rolling average pairwise correlations, raw and with RSP beta removed in-window."""
    names = AI + CONTROL
    X = rets[names].to_numpy()
    m = rets["RSP"].to_numpy()
    pos = {t: k for k, t in enumerate(names)}
    P = {
        "AI basket (all pairs)": [(pos[a], pos[b]) for a, b in itertools.combinations(AI, 2)],
        "AI cross-layer pairs": [(pos[a], pos[b]) for a, b in itertools.combinations(AI, 2)
                                 if LAYER_OF[a] != LAYER_OF[b]],
        "AI within-layer pairs": [(pos[a], pos[b]) for a, b in itertools.combinations(AI, 2)
                                  if LAYER_OF[a] == LAYER_OF[b]],
        "Control basket": [(pos[a], pos[b]) for a, b in itertools.combinations(CONTROL, 2)],
        "AI names vs control names": [(pos[a], pos[b]) for a in AI for b in CONTROL],
    }
    for layer, ns in LAYERS.items():
        if len(ns) > 1:
            P[f"Layer: {layer}"] = [(pos[a], pos[b]) for a, b in itertools.combinations(ns, 2)]
    rows, index = [], []
    for e in range(window, len(X) + 1):
        w, mw = X[e - window:e], m[e - window:e]
        c = np.corrcoef(w, rowvar=False)
        md = mw - mw.mean()
        beta = (w - w.mean(axis=0)).T @ md / (md @ md)
        resid = w - np.outer(mw, beta)          # intercept does not affect correlation
        cr = np.corrcoef(resid, rowvar=False)
        row = {k: avg_corr(c, v) for k, v in P.items()}
        row["AI basket, market-adjusted"] = avg_corr(cr, P["AI basket (all pairs)"])
        row["AI cross-layer, market-adjusted"] = avg_corr(cr, P["AI cross-layer pairs"])
        row["Control basket, market-adjusted"] = avg_corr(cr, P["Control basket"])
        rows.append(row)
        index.append(rets.index[e - 1])
    out = pd.DataFrame(rows, index=index)
    out["Gap: AI minus control"] = out["AI basket (all pairs)"] - out["Control basket"]
    return out


def period_means(roll: pd.DataFrame) -> pd.DataFrame:
    def yr(y):
        return roll.loc[f"{y}-01-01":f"{y}-12-31"].mean()
    return pd.DataFrame({
        "Before Dec 2022": roll.loc[:SPLIT].mean(),
        "Since Dec 2022": roll.loc[pd.Timestamp(SPLIT) + pd.Timedelta(days=1):].mean(),
        "2023": yr(2023), "2024": yr(2024), "2025": yr(2025), "2026 to date": yr(2026),
        "Latest": roll.iloc[-1],
    }).round(3)


def period_corr(a: pd.Series, b: pd.Series) -> dict:
    after = pd.Timestamp(SPLIT) + pd.Timedelta(days=1)
    return {
        "Whole sample": a.corr(b),
        "Before Dec 2022": a.loc[:SPLIT].corr(b.loc[:SPLIT]),
        "Since Dec 2022": a.loc[after:].corr(b.loc[after:]),
        "2023": a.loc["2023"].corr(b.loc["2023"]),
        "2024": a.loc["2024"].corr(b.loc["2024"]),
        "2025": a.loc["2025"].corr(b.loc["2025"]),
        "2026 to date": a.loc["2026"].corr(b.loc["2026"]),
        "Last 252 days": a.iloc[-252:].corr(b.iloc[-252:]),
        "Last 60 days": a.iloc[-60:].corr(b.iloc[-60:]),
    }


def main():
    px = download(AI + CONTROL + MARKET).dropna(how="any")
    rets = np.log(px / px.shift(1)).dropna()
    simple = (px / px.shift(1) - 1).dropna()

    roll60 = rolling_measures(rets, WINDOW)
    roll90 = rolling_measures(rets, 90)
    summary60, summary90 = period_means(roll60), period_means(roll90)
    share_above = float((roll60["AI basket (all pairs)"] > roll60["Control basket"]).mean())

    # Layer baskets (equal-weight mean of log returns) against the chip-design basket
    lb = pd.DataFrame({l: rets[ns].mean(axis=1) for l, ns in LAYERS.items()})
    lb["Control basket"] = rets[CONTROL].mean(axis=1)
    layer_vs_chip = pd.DataFrame({
        l: {k: v for k, v in period_corr(lb[l], lb["Chip design"]).items()
            if k in ("Before Dec 2022", "Since Dec 2022", "Last 252 days")}
        for l in lb.columns if l != "Chip design"}).T.round(2)

    # Basket against basket (equal-weight mean of simple returns)
    ai_b, ctl_b = simple[AI].mean(axis=1), simple[CONTROL].mean(axis=1)
    basket_vs_basket = pd.Series(period_corr(ai_b, ctl_b), name="AI basket vs control basket").round(2).to_frame()

    # Beta and volatility
    after = pd.Timestamp(SPLIT) + pd.Timedelta(days=1)
    ai_l, ctl_l = rets[AI].mean(axis=1), rets[CONTROL].mean(axis=1)

    def beta(a, mkt):
        return float(np.cov(a, mkt)[0, 1] / np.var(mkt, ddof=1))
    risk = pd.DataFrame({
        "Beta to SPY, before Dec 2022": [beta(ai_l[:SPLIT], rets["SPY"][:SPLIT]), beta(ctl_l[:SPLIT], rets["SPY"][:SPLIT])],
        "Beta to SPY, since Dec 2022": [beta(ai_l[after:], rets["SPY"][after:]), beta(ctl_l[after:], rets["SPY"][after:])],
        "Beta to SPY, last 252 days": [beta(ai_l[-252:], rets["SPY"][-252:]), beta(ctl_l[-252:], rets["SPY"][-252:])],
        "Annualised vol, before": [ai_l[:SPLIT].std() * 252 ** 0.5, ctl_l[:SPLIT].std() * 252 ** 0.5],
        "Annualised vol, since": [ai_l[after:].std() * 252 ** 0.5, ctl_l[after:].std() * 252 ** 0.5],
    }, index=["AI basket", "Control basket"]).round(2)

    # Sell-off: fall from each stock's 60-day high to the last close
    last60 = px.iloc[-60:]
    dd = pd.DataFrame({
        "Layer": [LAYER_OF.get(t, "Market") for t in AI + MARKET],
        "Date of 60-day high": [last60[t].idxmax().date() for t in AI + MARKET],
        "Fall from 60-day high, %": [(px[t].iloc[-1] / last60[t].max() - 1) * 100 for t in AI + MARKET],
    }, index=AI + MARKET).round(1)
    dd_layer = dd.loc[AI].groupby("Layer")["Fall from 60-day high, %"].mean().round(1).sort_values().to_frame()

    # Worst days for the AI basket since Dec 2022
    worst = pd.DataFrame({
        "AI basket, %": ai_l[after:] * 100,
        "Control basket, %": ctl_l[after:] * 100,
        "SPY, %": rets["SPY"][after:] * 100,
        "AI names down (of 19)": (rets.loc[after:, AI] < 0).sum(axis=1),
    }).sort_values("AI basket, %").head(10).round(1)

    # Weekly robustness check, adding the three non-US names
    wpx = download(AI + CONTROL + FOREIGN).resample("W-FRI").last().dropna(how="any")
    wr = np.log(wpx / wpx.shift(1)).dropna()

    def wavg(names, sl):
        c = wr.loc[sl, names].corr().to_numpy()
        n = len(names)
        return (c.sum() - n) / (n * (n - 1))
    weekly = pd.DataFrame({
        "Before Dec 2022": [wavg(AI + FOREIGN, slice(None, SPLIT)), wavg(AI, slice(None, SPLIT)), wavg(CONTROL, slice(None, SPLIT))],
        "Since Dec 2022": [wavg(AI + FOREIGN, slice(after, None)), wavg(AI, slice(after, None)), wavg(CONTROL, slice(after, None))],
    }, index=["AI basket, 22 names incl. SK Hynix, Samsung, Schneider", "AI basket, 19 US-listed", "Control basket"]).round(3)

    readme = pd.DataFrame({"Item": [
        "Purpose", "Data", "Sample", "AI basket", "Control basket", "Weights", "Returns",
        "Average pairwise correlation", "Market-adjusted", "Before / since",
        "Share of days AI correlation above control (60-day)",
        "Sheets", "Known limits"],
        "Detail": [
        "Backing calculations for BIF Risk Team 1: is the AI supply chain one thematic risk?",
        "Yahoo Finance adjusted daily closes via yfinance. Not yet reproduced on Bloomberg.",
        f"{px.index[0].date()} to {px.index[-1].date()}, {len(rets)} daily returns",
        "; ".join(f"{l}: {', '.join(ns)}" for l, ns in LAYERS.items()),
        ", ".join(CONTROL),
        "Equal weights throughout",
        "Daily log returns for correlations; simple returns for basket-vs-basket",
        f"Mean of all off-diagonal pairwise correlations in a basket over a rolling {WINDOW}-day window",
        "Each stock's beta to RSP (equal-weight S&P 500) is removed inside each window before correlating",
        f"Before = up to {SPLIT} (ChatGPT launch). Since = from the next trading day.",
        f"{share_above:.1%}",
        "Summary_60d, Summary_90d, Rolling_60d, Layer_vs_chip, Basket_vs_basket, Beta_vol, "
        "Drawdown_by_stock, Drawdown_by_layer, Worst_days, Weekly_check, Prices, Returns",
        "Control basket is hand-picked and leans defensive, not the benchmark. AI basket chosen with hindsight. "
        "Correlations rise mechanically when volatility rises. Foundry and Memory are single-stock layers."]})

    with pd.ExcelWriter(OUT, engine="openpyxl") as xl:
        readme.to_excel(xl, "README", index=False)
        summary60.to_excel(xl, "Summary_60d")
        summary90.to_excel(xl, "Summary_90d")
        roll60.round(4).to_excel(xl, "Rolling_60d")
        layer_vs_chip.to_excel(xl, "Layer_vs_chip")
        basket_vs_basket.to_excel(xl, "Basket_vs_basket")
        risk.to_excel(xl, "Beta_vol")
        dd.to_excel(xl, "Drawdown_by_stock")
        dd_layer.to_excel(xl, "Drawdown_by_layer")
        worst.to_excel(xl, "Worst_days")
        weekly.to_excel(xl, "Weekly_check")
        px.round(4).to_excel(xl, "Prices")
        rets.round(6).to_excel(xl, "Returns")
        for ws in xl.book.worksheets:
            ws.column_dimensions["A"].width = 46
            for col in "BCDEFGHI":
                ws.column_dimensions[col].width = 18
        xl.book["README"].column_dimensions["B"].width = 120

    print(f"Sample: {px.index[0].date()} to {px.index[-1].date()}, {len(rets)} daily returns")
    print(f"Share of days AI above control: {share_above:.1%}\n")
    print(summary60.to_string(), "\n")
    print(basket_vs_basket.to_string(), "\n")
    print(dd_layer.to_string())
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()
