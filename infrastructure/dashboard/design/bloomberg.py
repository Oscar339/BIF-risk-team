"""Minimal Bloomberg Desktop API client (needs the Terminal open and logged in on this machine)."""
from __future__ import annotations

import datetime as dt

import blpapi
import pandas as pd

HOST, PORT = "localhost", 8194
REFDATA = "//blp/refdata"


def _to_py(el: blpapi.Element):
    """Convert a blpapi Element into plain Python (dicts, lists, values)."""
    if el.isArray():
        return [_to_py(v) if isinstance(v, blpapi.Element) else v for v in el.values()]
    if el.isComplexType():
        return {str(e.name()): _to_py(e) for e in el.elements()}
    return el.getValue()


class Bloomberg:
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

    def _send(self, request, max_wait_ms: int = 120000) -> list[blpapi.Message]:
        """Send a request and collect its responses. TIMEOUT only means nothing arrived yet."""
        self.session.sendRequest(request)
        msgs, waited = [], 0
        while True:
            ev = self.session.nextEvent(self.timeout_ms)
            etype = ev.eventType()
            if etype == blpapi.Event.TIMEOUT:
                waited += self.timeout_ms
                if waited >= max_wait_ms:
                    raise TimeoutError(f"Bloomberg request timed out after {waited / 1000:.0f}s")
                print(f"  ...waiting on Bloomberg ({waited / 1000:.0f}s)")
                continue
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
            self.warnings.append(f"{sec}: {sd.getElement('securityError').getElementAsString('message')}")
            return False
        if sd.hasElement("fieldExceptions"):
            for fe in sd.getElement("fieldExceptions").values():
                self.warnings.append(f"{sec} / {fe.getElementAsString('fieldId')}: "
                                     f"{fe.getElement('errorInfo').getElementAsString('message')}")
        return True

    def reference(self, securities, fields, overrides: dict | None = None,
                  request_type: str = "ReferenceDataRequest") -> pd.DataFrame:
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

    def history(self, securities, fields, start: dt.date, end: dt.date, currency: str | None = None) -> pd.DataFrame:
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

    def portfolio(self, port_ids, field: str = "PORTFOLIO_DATA", as_of: dt.date | None = None) -> pd.DataFrame:
        """Holdings of PORT portfolios: port_id, security, position[, market_value, ...]."""
        overrides = {"REFERENCE_DATE": as_of.strftime("%Y%m%d")} if as_of else None
        ref = self.reference([f"{p} Client" for p in port_ids], [field], overrides,
                             request_type="PortfolioDataRequest")
        frames = []
        for sec, val in ref[field].items():
            if isinstance(val, list) and val:
                f = pd.DataFrame(val)
                f["port_id"] = sec.rsplit(" ", 1)[0]
                frames.append(f)
        if not frames:
            return pd.DataFrame(columns=["port_id", "security", "position"])
        df = pd.concat(frames, ignore_index=True)
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        return df

    def holdings_history(self, port_ids, start: dt.date, end: dt.date) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
        """End-of-day positions for every business day in [start, end]."""
        dates = pd.bdate_range(start, end)
        frames = []
        for d in dates:
            h = self.portfolio(port_ids, "PORTFOLIO_MPOSITION", as_of=d.date())
            if not h.empty:
                h["date"] = d
                frames.append(h[["date", "port_id", "security", "position"]])
        if not frames:
            return pd.DataFrame(columns=["date", "port_id", "security", "position"]), dates
        return pd.concat(frames, ignore_index=True), dates
