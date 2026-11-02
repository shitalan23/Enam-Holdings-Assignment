"""End-of-day prices via yfinance (NSE tickers use the .NS suffix).

Honest failure handling: a ticker that returns nothing is logged in ingest_issues
and the feed is marked UNAVAILABLE for that symbol; we never fill gaps with guesses.
Run on a machine that can reach Yahoo Finance.
"""
import time
from datetime import datetime
from ..db import session, set_feed_status
from ..market import now_ist


def ingest_prices(symbols: list[str], period: str = "6mo") -> dict:
    import yfinance as yf  # imported lazily so the API can run without it
    fetched = now_ist().isoformat(timespec="seconds")
    ok, failed = 0, []
    with session() as con:
        con.execute("DELETE FROM prices_eod WHERE source='MOCK'")
        for sym in symbols:
            try:
                df = yf.Ticker(f"{sym}.NS").history(period=period, auto_adjust=False)
                if df is None or df.empty:
                    raise ValueError("no rows returned (renamed, delisted, or Yahoo blocked)")
                rows = [(sym, idx.date().isoformat(), _f(r.Open), _f(r.High), _f(r.Low),
                         _f(r.Close), int(r.Volume) if r.Volume == r.Volume else None,
                         "yfinance", fetched) for idx, r in df.iterrows()]
                con.executemany(
                    "INSERT OR REPLACE INTO prices_eod VALUES (?,?,?,?,?,?,?,?,?)", rows)
                ok += 1
            except Exception as e:  # keep going: one bad ticker must not kill the run
                failed.append(sym)
                con.execute("INSERT INTO ingest_issues VALUES ('prices',?,?,?)",
                            (sym, fetched, str(e)[:300]))
            time.sleep(0.4)  # be polite to Yahoo
        status = "EOD" if ok else "UNAVAILABLE"
        note = f"{ok}/{len(symbols)} symbols" + (f"; failed: {', '.join(failed)}" if failed else "")
        set_feed_status(con, "prices", status, fetched, note)
    return {"ok": ok, "failed": failed}


def _f(x):
    return None if x != x else round(float(x), 2)
