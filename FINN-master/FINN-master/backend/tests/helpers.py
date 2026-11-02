from datetime import datetime, timedelta
from finn.db import session
from finn.market import IST

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=IST)   # a Sunday, fixed so tests are deterministic

def add_filing(sym, hours_ago, desc, text="", category="results", subtype=None, conf=0.95,
               source="NSE", fetched=None, now=NOW, fid=None):
    ts = (now - timedelta(hours=hours_ago)).isoformat(timespec="seconds")
    fid = fid or f"{sym}-{hours_ago}-{abs(hash(desc)) % 10**6}"
    with session() as con:
        con.execute("INSERT OR REPLACE INTO announcements (id,symbol,ts,headline,detail,category,subtype,"
                    "category_method,pdf_url,source,fetched_at,confidence,reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (fid, sym, ts, desc, text, category, subtype, "rules-v2", None, source,
                     fetched or (now - timedelta(hours=1)).isoformat(timespec="seconds"), conf,
                     "test" if conf is not None else None))
    return fid

def add_bar(sym, date, close=100.0, vol=1000, source="yfinance", fetched=None, now=NOW):
    with session() as con:
        con.execute("INSERT OR REPLACE INTO prices_eod VALUES (?,?,?,?,?,?,?,?,?)",
                    (sym, date, close, close, close, close, vol, source,
                     fetched or (now - timedelta(hours=2)).isoformat(timespec="seconds")))
