"""Settings shared by the data pull and the PDF builder. Change fund set-up and limits here."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parents[1]  # reports/dashboard
DESIGN_DIR = DASHBOARD_DIR / "design"
PREVIEW_DIR = DESIGN_DIR / "preview"
HISTORY_FILE = DASHBOARD_DIR / "metrics_history.csv"  # gitignored; rebuilt from the report folders on every build

# Fund cash balances (date,cash; one row whenever cash changes). Kept in OneDrive, never git.
# The first file that exists is used.
CASH_FILES = [
    DASHBOARD_DIR / "data" / "fund_cash.csv",
    DASHBOARD_DIR.parents[1] / "members" / "oscar-butler" / "dashboard testing" / "data" / "fund_cash.csv",
]

# ---------------------------------------------------------------- portfolio (Bloomberg PORT)
FUND = "U15794802-9231"  # BIF Portfolio 2026/27:All
SLEEVES = {  # member sleeves, from PRTU
    "U15794802-9236": "A. Jeffery",
    "U15794802-9232": "C. Hook",
    "U15794802-9237": "F. Howe",
    "U15794802-9307": "G. Smith",
    "U15794802-9233": "J. Wilczewski",
    "U15794802-9235": "L. Fowler",
    "U15794802-9234": "M. Yadukha",
    "U15794802-9238": "S. Dominguez",
    "U15794802-9308": "Y. Atasay",
}
# Sleeve -> investment team. CIO and Chairman sleeves are not sector teams and show as extra rows.
# TODO: add the Financials sleeve (J. Heyworth) here and to SLEEVES once it exists in PORT.
SLEEVE_TEAMS = {
    "U15794802-9236": "Consumer",
    "U15794802-9232": "CIO",
    "U15794802-9237": "Special Situations",
    "U15794802-9307": "TMT",
    "U15794802-9233": "Industrials",
    "U15794802-9235": "Materials",
    "U15794802-9234": "Healthcare",
    "U15794802-9238": "Chairman",
    "U15794802-9308": "Energy & Utilities",
}
REPORT_TEAMS = ["Financials", "Healthcare", "Industrials", "Consumer", "Materials",
                "Energy & Utilities", "Special Situations", "TMT"]  # always shown, in this order
INCEPTION = dt.date(2026, 10, 1)  # first date to look for holdings (drawdown starts here)

# ---------------------------------------------------------------- market data
BASE_CCY = "GBP"
HISTORY_YEARS = 5  # price history for VaR/ES and regressions
BENCHMARK = "MXWO Index"  # MSCI World (price), used for beta and factor regressions
BENCHMARK_TR = "NDDUWI Index"  # MSCI World net total return
FACTORS = {  # MSCI World factor indices; exposure is to (factor index - MSCI World)
    "value": "M1WO000V Index",
    "momentum": "M1WOMOM Index",
    "quality": "M1WOQU Index",
    "min_vol": "M1WOMVOL Index",
    "small_cap": "M1WOSC Index",
}
YIELDS = {"USGG10YR Index": "us_10y", "GUKG10 Index": "uk_10y"}  # for rates sensitivities

# ---------------------------------------------------------------- method
TRADING_DAYS = 252
COV_WINDOW = 252  # daily returns for ex-ante vol and risk contribution
BETA_WEEKS = 104  # weekly returns for beta / factor / rates regressions
MIN_WEEKS = 26
VAR_CONF = 0.99
VAR_WINDOW = 5  # component VaR: average position P&L over 2*5+1 scenarios around the VaR day
MIN_DAYS_FOR_STATS = 60  # below this, drawdown is flagged as indicative

# ---------------------------------------------------------------- mandate limits
# {summary metric: (min, max)}, None = no bound.
# TODO: confirm against the BIF risk policy. These are the working values from the mockup.
LIMITS: dict[str, tuple[float | None, float | None]] = {
    "gross_pct_nav": (None, 200),
    "net_pct_nav": (-20, 80),
    "largest_position_pct_nav": (None, 10),
    "var_99_pct_nav": (None, 3),
}
LIMIT_LABELS = {"gross_pct_nav": "Gross % NAV", "net_pct_nav": "Net % NAV",
                "largest_position_pct_nav": "Largest position % NAV", "var_99_pct_nav": "1-day VaR99 % NAV"}

# ---------------------------------------------------------------- headline tiles
# (summary key, label, value format, delta unit, risk sense) where risk sense says which way is MORE risk:
#   "up"   higher = more risk     "abs"  further from zero = more risk     "down"  lower = more risk
TILES = [
    ("var_99_pct_nav", "1-day VaR 99", "{:.2f}%", "pp", "up"),
    ("es_99_pct_nav", "1-day ES 99", "{:.2f}%", "pp", "up"),
    ("ex_ante_vol_pct", "Ex-ante volatility", "{:.1f}%", "pp", "up"),
    ("beta", "Beta to MSCI World", "{:.2f}", "", "abs"),
    ("gross_pct_nav", "Gross exposure", "{:.1f}%", "pp", "up"),
    ("net_pct_nav", "Net exposure", "{:+.1f}%", "pp", "abs"),
    ("largest_position_pct_nav", "Largest position", "{:.1f}%", "pp", "up"),
    ("current_drawdown_pct", "Drawdown from peak", "{:.1f}%", "pp", "down"),
]
