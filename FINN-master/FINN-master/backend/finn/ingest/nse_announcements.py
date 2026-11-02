"""Corporate announcements from NSE's public corporate-announcements JSON API.

NSE needs a browser-like session: hit the homepage first to receive cookies, then call
the API with a Referer. Cloud/datacenter IPs are often blocked, which is why the design
is snapshot-first: run this locally, commit data/finn.db, deploy the snapshot.

NOTE: field names below (an_dt, desc, attchmntText, attchmntFile, seq_id) follow NSE's
documented response shape but were NOT verifiable from the build sandbox. Run
`python -m finn.cli probe RELIANCE` once; it prints the real keys so any drift is a
one-line fix instead of silent bad data.
"""
import hashlib
import time
from datetime import datetime, timedelta
import httpx
from ..classify import classify
from ..db import session, set_feed_status
from ..market import IST, now_ist

BASE = "https://www.nseindia.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{BASE}/companies-listing/corporate-filings-announcements",
}
DT_FORMATS = ("%d-%b-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%m-%Y %H:%M:%S")


def _client() -> httpx.Client:
    c = httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True)
    c.get(BASE)  # cookie handshake
    return c


def fetch_raw(client: httpx.Client, symbol: str, days: int) -> list[dict]:
    end = now_ist().date()
    start = end - timedelta(days=days)
    r = client.get(f"{BASE}/api/corporate-announcements", params={
        "index": "equities", "symbol": symbol,
        "from_date": start.strftime("%d-%m-%Y"), "to_date": end.strftime("%d-%m-%Y")})
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("data", [])


def _parse_ts(rec: dict) -> str | None:
    for key in ("an_dt", "sort_date", "dt"):
        raw = rec.get(key)
        if not raw:
            continue
        for fmt in DT_FORMATS:
            try:
                return datetime.strptime(str(raw).strip(), fmt).replace(tzinfo=IST).isoformat(timespec="seconds")
            except ValueError:
                continue
    return None  # never invent a timestamp


def ingest_announcements(symbols: list[str], days: int = 30) -> dict:
    fetched = now_ist().isoformat(timespec="seconds")
    ok, failed, added = 0, [], 0
    try:
        client = _client()
    except Exception as e:
        with session() as con:
            set_feed_status(con, "announcements", "UNAVAILABLE", fetched, f"NSE session failed: {e}"[:200])
        return {"ok": 0, "failed": symbols, "added": 0}
    with session() as con:
        con.execute("DELETE FROM announcements WHERE source='MOCK'")
        for sym in symbols:
            try:
                for rec in fetch_raw(client, sym, days):
                    ts = _parse_ts(rec)
                    desc = (rec.get("desc") or "").strip()
                    text = (rec.get("attchmntText") or "").strip()
                    if not ts or not (desc or text):
                        continue
                    c = classify(desc, text)
                    uid = rec.get("seq_id") or f"{sym}|{ts}|{desc}|{rec.get('attchmntFile')}"
                    aid = hashlib.sha1(f"NSE|{uid}".encode()).hexdigest()[:16]
                    con.execute(
                        "INSERT OR REPLACE INTO announcements (id,symbol,ts,headline,detail,category,subtype,"
                        "category_method,pdf_url,source,fetched_at,confidence,reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (aid, sym, ts, desc or text[:120], text[:600] or None, c.category,
                         c.subtype, c.method, rec.get("attchmntFile") or None, "NSE", fetched,
                         c.confidence, c.reason))
                    added += 1
                ok += 1
            except Exception as e:
                failed.append(sym)
                con.execute("INSERT INTO ingest_issues VALUES ('announcements',?,?,?)",
                            (sym, fetched, str(e)[:300]))
            time.sleep(0.8)
        status = "DELAYED" if ok else "UNAVAILABLE"  # fetched snapshot, never "live"
        note = f"{ok}/{len(symbols)} symbols, {added} filings" + (f"; failed: {', '.join(failed)}" if failed else "")
        set_feed_status(con, "announcements", status, fetched, note)
    return {"ok": ok, "failed": failed, "added": added}


def probe(symbol: str) -> None:
    """Print the real response shape so field-name drift is visible immediately."""
    recs = fetch_raw(_client(), symbol, 14)
    print(f"{len(recs)} records")
    if recs:
        print("keys:", sorted(recs[0].keys()))
        print("sample:", {k: (str(v)[:80]) for k, v in recs[0].items()})
