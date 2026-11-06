"""Dashboard v1: pull BIF portfolio holdings and market data from Bloomberg PORT via blpapi.

Needs the Bloomberg Terminal open and logged in on this machine.

Usage:
    python dashboard_v1.py <PORT_ID> [--ccy GBP] [--years 3]

PORT_ID is the portfolio's ID in Bloomberg PORT (e.g. U1234567-1).
Outputs go to members/oscar-butler/dashboard testing/results/v1/.
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import blpapi
import pandas as pd

HOST, PORT = "localhost", 8194
REFDATA = "//blp/refdata"
RESULTS_DIR = Path(__file__).resolve().parents[1] / "results" / "v1"

# Bloomberg field -> column name in the output
REF_FIELDS = {
    "NAME": "name",
    "SECURITY_TYP": "security_type",
    "CRNCY": "currency",
    "PX_LAST": "price_local",
    "CRNCY_ADJ_PX_LAST": "price_base",  # converted to base ccy via EQY_FUND_CRNCY override
    "GICS_SECTOR_NAME": "sector",
    "COUNTRY_ISO": "country",
    "EQY_BETA": "beta",
    "VOLATILITY_90D": "vol_90d",
    "CRNCY_ADJ_MKT_CAP": "mkt_cap_base",
    "PE_RATIO": "pe_ratio",
    "EQY_DVD_YLD_IND": "div_yield",
}


def _to_py(el: blpapi.Element):
    """Convert a blpapi Element into plain Python (dicts, lists, values)."""
    if el.isArray():
        return [_to_py(v) if isinstance(v, blpapi.Element) else v for v in el.values()]
    if el.isComplexType():
        return {str(e.name()): _to_py(e) for e in el.elements()}
    return el.getValue()


class Bloomberg:
    """Minimal Bloomberg reference/historical data client."""

    def __init__(self, host: str = HOST, port: int = PORT, timeout_ms: int = 30000):
        opts = blpapi.SessionOptions()
        opts.setServerHost(host)
        opts.setServerPort(port)
        self.session = blpapi.Session(opts)
        self.timeout_ms = timeout_ms
        self.warnings: list[str] = []
        if not self.session.start():
            raise ConnectionError("Could not start Bloomberg session. Is the Terminal open and logged in?")
        if not self.session.openService(REFDATA):
            raise ConnectionError(f"Could not open {REFDATA}")
        self.service = self.session.getService(REFDATA)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.session.stop()

    def _send(self, request) -> list[blpapi.Message]:
        self.session.sendRequest(request)
        msgs = []
        while True:
            ev = self.session.nextEvent(self.timeout_ms)
            etype = ev.eventType()
            if etype == blpapi.Event.TIMEOUT:
                raise TimeoutError("Bloomberg request timed out")
            for msg in ev:
                if etype in (blpapi.Event.PARTIAL_RESPONSE, blpapi.Event.RESPONSE):
                    if msg.hasElement("responseError"):
                        raise RuntimeError(str(msg.getElement("responseError")))
                    msgs.append(msg)
            if etype == blpapi.Event.RESPONSE:
                return msgs

    def _collect_errors(self, sd: blpapi.Element, sec: str) -> bool:
        """Record security/field errors as warnings. Returns False if the whole security failed."""
        if sd.hasElement("securityError"):
            err = sd.getElement("securityError").getElementAsString("message")
            self.warnings.append(f"{sec}: {err}")
            return False
        if sd.hasElement("fieldExceptions"):
            for fe in sd.getElement("fieldExceptions").values():
                field = fe.getElementAsString("fieldId")
                msg = fe.getElement("errorInfo").getElementAsString("message")
                self.warnings.append(f"{sec} / {field}: {msg}")
        return True

    def reference(self, securities, fields, overrides: dict | None = None,
                  request_type: str = "ReferenceDataRequest") -> pd.DataFrame:
        """Current values: one row per security, one column per field.

        request_type="PortfolioDataRequest" is needed for PORT portfolios ("<ID> Client");
        its response has the same shape.
        """
        req = self.service.createRequest(request_type)
        for s in securities:
            req.getElement("securities").appendValue(s)
        for f in fields:
            req.getElement("fields").appendValue(f)
        for k, v in (overrides or {}).items():
            o = req.getElement("overrides").appendElement()
            o.setElement("fieldId", k)
            o.setElement("value", v)

        rows = {}
        for msg in self._send(req):
            for sd in msg.getElement("securityData").values():
                sec = sd.getElementAsString("security")
                if self._collect_errors(sd, sec):
                    rows[sec] = _to_py(sd.getElement("fieldData"))
        df = pd.DataFrame.from_dict(rows, orient="index")
        df.index.name = "security"
        return df.reindex(columns=list(fields))

    def history(self, securities, fields, start: dt.date, end: dt.date,
                currency: str | None = None) -> pd.DataFrame:
        """Daily history in long format: date, security, <fields>."""
        req = self.service.createRequest("HistoricalDataRequest")
        for s in securities:
            req.getElement("securities").appendValue(s)
        for f in fields:
            req.getElement("fields").appendValue(f)
        req.set("startDate", start.strftime("%Y%m%d"))
        req.set("endDate", end.strftime("%Y%m%d"))
        req.set("periodicitySelection", "DAILY")
        if currency:
            req.set("currency", currency)

        frames = []
        for msg in self._send(req):
            sd = msg.getElement("securityData")
            sec = sd.getElementAsString("security")
            if not self._collect_errors(sd, sec):
                continue
            data = _to_py(sd.getElement("fieldData"))
            if data:
                frame = pd.DataFrame(data)
                frame["security"] = sec
                frames.append(frame)
        if not frames:
            return pd.DataFrame(columns=["date", "security", *fields])
        out = pd.concat(frames, ignore_index=True)
        out["date"] = pd.to_datetime(out["date"])
        return out[["date", "security", *fields]]

    def holdings(self, port_id: str) -> pd.DataFrame:
        """Holdings and positions of a Bloomberg PORT portfolio."""
        ref = self.reference([f"{port_id} Client"], ["PORTFOLIO_MPOSITION"],
                             request_type="PortfolioDataRequest")
        if ref.empty or not isinstance(ref.iloc[0, 0], list):
            raise ValueError(f"No holdings returned for portfolio '{port_id}'. "
                             f"Check the ID in PORT. Warnings: {self.warnings}")
        df = pd.DataFrame(ref.iloc[0, 0])
        df.columns = [c.lower() for c in df.columns]  # Security, Position -> security, position
        return df[["security", "position"]]


def run(port_id: str, base_ccy: str = "GBP", years: int = 3, out_dir: Path = RESULTS_DIR) -> dict:
    today = dt.date.today()
    start = today - dt.timedelta(days=365 * years)

    with Bloomberg() as bbg:
        holdings = bbg.holdings(port_id)
        tickers = holdings["security"].tolist()

        ref = bbg.reference(tickers, list(REF_FIELDS), overrides={"EQY_FUND_CRNCY": base_ccy})
        ref = ref.rename(columns=REF_FIELDS)

        hist = bbg.history(tickers, ["PX_LAST"], start, today, currency=base_ccy)
        warnings = bbg.warnings

    table = holdings.join(ref, on="security")
    # NOTE: assumes prices are per unit (equities/funds). Bonds quoted per 100 face
    # need position * price / 100 - check totals against PORT.
    table["market_value_base"] = table["position"] * table["price_base"]
    table["weight"] = table["market_value_base"] / table["market_value_base"].sum()

    prices = hist.pivot(index="date", columns="security", values="PX_LAST").sort_index()

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = today.strftime("%Y%m%d")
    paths = {
        "holdings": out_dir / f"holdings_{stamp}.csv",
        "prices": out_dir / f"prices_{base_ccy}_{stamp}.csv",
        "warnings": out_dir / f"warnings_{stamp}.txt",
    }
    table.to_csv(paths["holdings"], index=False)
    prices.to_csv(paths["prices"])
    paths["warnings"].write_text("\n".join(warnings), encoding="utf-8")

    print(f"{len(table)} holdings, total value {table['market_value_base'].sum():,.0f} {base_ccy}")
    print(f"{prices.shape[0]} days of prices for {prices.shape[1]} securities")
    if warnings:
        print(f"{len(warnings)} Bloomberg warnings -> {paths['warnings'].name}")
    for k, p in paths.items():
        print(f"  {k}: {p}")
    return {"holdings": table, "prices": prices, "warnings": warnings}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port_id", help="Bloomberg PORT portfolio ID, e.g. U1234567-1")
    ap.add_argument("--ccy", default="GBP", help="Base currency (default GBP)")
    ap.add_argument("--years", type=int, default=3, help="Years of price history (default 3)")
    args = ap.parse_args()
    run(args.port_id, args.ccy, args.years)
