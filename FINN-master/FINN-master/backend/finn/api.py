"""FastAPI app: JSON API + the built React app served from the same process (one URL)."""
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .classify import TAXONOMY, classify, clean_label
from .commitments_api import get_commitments_by_symbol, get_commitments_summary_by_symbol
from .config import DEFAULT_PRICE_MOVE_PCT, DEFAULT_VOLUME_MULT, STATIC_DIR
from .db import init_db, session
from .market import IST, bars, latest_stats, now_ist, reaction
from .research_api import get_company_research_dossier, search_research_companies
from .results_api import get_results_by_filing, get_results_by_symbol
from .scoring import ACT, KNOW, rules_summary, score_announcement

app = FastAPI(title="FINN", version="0.2.0")
init_db()

WINDOWS = {"24h": 24, "3d": 72, "7d": 168, "30d": 720}
TIER_ORDER = {"act": 0, "know": 1, "skim": 2}
FILINGS_FRESH_HOURS = 6


# ------------------------------------------------------------------ provenance
def expected_last_session(now: datetime) -> str:
    """Most recent weekday whose close should be published by now (NSE closes 15:30 IST;
    allow until 16:00 for vendors). Exchange holidays aren't modelled, so 'behind' can be a holiday."""
    d = now.date()
    if d.weekday() < 5 and now.hour * 60 + now.minute < 16 * 60:
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def _age_hours(iso: str | None):
    return None if not iso else round((now_ist() - datetime.fromisoformat(iso)).total_seconds() / 3600, 1)


def prices_status(con) -> dict:
    """EOD prices are never 'live'. Status is derived from the data, not from a stored label:
    MOCK (synthetic) / EOD (latest close present) / CACHED (snapshot missing recent sessions) / UNAVAILABLE."""
    row = con.execute("SELECT MAX(date) d FROM prices_eod WHERE close IS NOT NULL").fetchone()
    if not row or not row["d"]:
        return {"feed": "prices", "status": "UNAVAILABLE", "as_of": None, "fetched_at": None, "age_hours": None,
                "note": "No prices loaded. Run: python -m finn.cli ingest-prices"}
    as_of = row["d"]
    real = con.execute("SELECT MAX(fetched_at) f FROM prices_eod WHERE source!='MOCK'").fetchone()["f"]
    if not real:
        f = con.execute("SELECT MAX(fetched_at) f FROM prices_eod").fetchone()["f"]
        return {"feed": "prices", "status": "MOCK", "as_of": as_of, "fetched_at": f, "age_hours": _age_hours(f),
                "note": "Synthetic random-walk prices, not real quotes."}
    behind = con.execute("SELECT COUNT(*) n FROM (SELECT symbol, MAX(date) d FROM prices_eod GROUP BY symbol) WHERE d < ?", (as_of,)).fetchone()["n"]
    expected = expected_last_session(now_ist())
    stale = as_of < expected
    note = f"Official end-of-day close for {as_of}. Not intraday, not live."
    if stale:
        note = (f"Newest close in this snapshot is {as_of}, but {expected} should exist. "
                "Re-run ingest-prices (or it may be an exchange holiday).")
    if behind:
        note += f" {behind} symbol(s) have older data than the rest."
    return {"feed": "prices", "status": "CACHED" if stale else "EOD", "as_of": as_of, "fetched_at": real,
            "age_hours": _age_hours(real), "note": note}


def filings_status(con) -> dict:
    """Filings are a fetched snapshot of NSE's feed: Delayed if fetched recently, Cached if not.
    FINN has no real-time stream, so it never reports Live."""
    n = con.execute("SELECT COUNT(*) n FROM announcements").fetchone()["n"]
    if not n:
        return {"feed": "announcements", "status": "UNAVAILABLE", "as_of": None, "fetched_at": None, "age_hours": None,
                "note": "No filings loaded. Run: python -m finn.cli ingest-announcements"}
    real = con.execute("SELECT MAX(fetched_at) f, MAX(ts) t FROM announcements WHERE source!='MOCK'").fetchone()
    if not real["f"]:
        f = con.execute("SELECT MAX(fetched_at) f FROM announcements").fetchone()["f"]
        return {"feed": "announcements", "status": "MOCK", "as_of": None, "fetched_at": f, "age_hours": _age_hours(f),
                "note": "Template filings, not real disclosures."}
    age = _age_hours(real["f"])
    fresh = age is not None and age <= FILINGS_FRESH_HOURS
    note = ("Fetched from NSE's announcement feed" if fresh else "Saved snapshot of NSE's announcement feed") + \
           f"; newest filing {real['t'][:16].replace('T', ' ')} IST. Updates only when ingest is run."
    return {"feed": "announcements", "status": "DELAYED" if fresh else "CACHED", "as_of": real["t"],
            "fetched_at": real["f"], "age_hours": age, "note": note}


# ------------------------------------------------------------------ helpers
def _window(window: str | None, from_ts: str | None, to_ts: str | None, latest_ts: str | None = None):
    end = now_ist()
    is_snapshot = False
    if from_ts:
        try:
            start = datetime.fromisoformat(from_ts).replace(tzinfo=IST)
            if to_ts:
                end = datetime.fromisoformat(to_ts).replace(tzinfo=IST) + timedelta(days=1)
        except ValueError:
            raise HTTPException(400, "from/to must be ISO dates, e.g. 2026-10-25")
        return start, end, "Custom range", False
    hours = WINDOWS.get(window or "24h")
    if hours is None:
        raise HTTPException(400, f"window must be one of {list(WINDOWS)}")
    win_key = window or "24h"
    base_label = {"24h": "Last 24 hours", "3d": "Last 3 days",
                  "7d": "Last 7 days", "30d": "Last 30 days"}[win_key]
    if latest_ts:
        try:
            latest_dt = datetime.fromisoformat(latest_ts)
            if latest_dt.tzinfo is None:
                latest_dt = latest_dt.replace(tzinfo=IST)
            if (now_ist() - latest_dt) > timedelta(hours=FILINGS_FRESH_HOURS):
                is_snapshot = True
                end = latest_dt + timedelta(seconds=1)
                start = latest_dt - timedelta(hours=hours)
                label = f"{base_label} of snapshot"
                return start, end, label, is_snapshot
        except Exception:
            pass
    return end - timedelta(hours=hours), end, base_label, is_snapshot


def build_items(con, start, end, symbol=None, price_thr=DEFAULT_PRICE_MOVE_PCT, vol_thr=DEFAULT_VOLUME_MULT):
    q = ("SELECT a.*, c.name, c.sector, c.weight FROM announcements a "
         "LEFT JOIN companies c ON c.symbol=a.symbol WHERE a.ts>=? AND a.ts<? ")
    params = [start.isoformat(), end.isoformat()]
    if symbol:
        q += "AND a.symbol=? "
        params.append(symbol.upper())
    rows = con.execute(q + "ORDER BY a.ts DESC", params).fetchall()
    # Map filing_id -> stable result_id from quarterly_results
    filing_to_result = {
        r[0]: r[1]
        for r in con.execute(
            "SELECT filing_id, id FROM quarterly_results WHERE filing_id IS NOT NULL"
        ).fetchall()
    }
    cache: dict[str, list] = {}
    items = []
    for r in rows:
        if r["confidence"] is None:  # classified by the pre-v2 rules and not yet reclassified: classify on the fly
            c = classify(r["headline"], r["detail"] or "")
            category, subtype, conf, reason = c.category, c.subtype, c.confidence, c.reason + " (live; not yet saved)"
        else:
            category, subtype, conf, reason = r["category"], r["subtype"], r["confidence"], r["reason"]
        series = cache.setdefault(r["symbol"], bars(con, r["symbol"], 90))
        rx = reaction(series, r["ts"]) if series else None
        sc = score_announcement(category, subtype, f'{r["headline"]} {r["detail"] or ""}',
                                r["weight"] or 0, rx["pct"] if rx else None,
                                rx["vol_x"] if rx else None, price_thr, vol_thr, conf)
        res_id = filing_to_result.get(r["id"])
        items.append({
            "id": r["id"], "symbol": r["symbol"], "name": r["name"] or r["symbol"],
            "sector": r["sector"], "ts": r["ts"], "headline": clean_label(r["headline"]),
            "detail": r["detail"], "category": category,
            "category_label": TAXONOMY.get(category, category), "subtype": subtype,
            "confidence": conf, "classified_by": reason,
            "score": sc.score, "tier": sc.tier, "why": sc.why,
            "breakdown": sc.breakdown, "gate": sc.gate,
            "pdf_url": r["pdf_url"], "source": r["source"], "reaction": rx,
            "has_results": res_id is not None,
            "result_id": res_id,
        })
    # tier first, then highest score, then newest
    items.sort(key=lambda i: (TIER_ORDER[i["tier"]], -i["score"], -datetime.fromisoformat(i["ts"]).timestamp()))

    # Deduplicate Results Intelligence cards: ensure a specific result_id is surfaced at most once in the feed
    seen_result_ids = set()
    for item in items:
        rid = item.get("result_id")
        if rid:
            if rid in seen_result_ids:
                item["has_results"] = False
            else:
                seen_result_ids.add(rid)

    return items


# ------------------------------------------------------------------ routes
@app.get("/api/status")
def status():
    with session() as con:
        px, fl = prices_status(con), filings_status(con)
        n_ann = con.execute("SELECT COUNT(*) FROM announcements").fetchone()[0]
        n_px = con.execute("SELECT COUNT(DISTINCT symbol) FROM prices_eod").fetchone()[0]
        issues = con.execute("SELECT COUNT(*) FROM ingest_issues").fetchone()[0]
        legacy = con.execute("SELECT COUNT(*) FROM announcements WHERE confidence IS NULL AND source!='MOCK'").fetchone()[0]
    return {"prices": px, "announcements": fl,
            "counts": {"announcements": n_ann, "symbols_with_prices": n_px, "ingest_issues": issues},
            "classification": {"needs_reclassify": legacy},
            "thresholds": {"price_move_pct": DEFAULT_PRICE_MOVE_PCT, "volume_mult": DEFAULT_VOLUME_MULT},
            "tiers": {"act": ACT, "know": KNOW}}


@app.get("/api/scoring")
def scoring():
    return rules_summary()


@app.get("/api/brief")
def brief(window: str | None = "24h", from_ts: str | None = None, to_ts: str | None = None,
          symbol: str | None = None, price_thr: float = Query(DEFAULT_PRICE_MOVE_PCT, ge=0.5, le=50),
          vol_thr: float = Query(DEFAULT_VOLUME_MULT, ge=1, le=20)):
    with session() as con:
        latest_row = con.execute("SELECT MAX(ts) t FROM announcements").fetchone()
        latest_ts = latest_row["t"] if latest_row and latest_row["t"] else None
        start, end, label, is_snapshot = _window(window, from_ts, to_ts, latest_ts=latest_ts)
        items = build_items(con, start, end, symbol, price_thr, vol_thr)
        st = status()
    counts = {t: sum(1 for i in items if i["tier"] == t) for t in ("act", "know", "skim")}
    return {"window": {"label": label, "from": start.isoformat(), "to": end.isoformat(),
                       "is_snapshot": is_snapshot, "snapshot_as_of": latest_ts},
            "counts": {**counts, "total": len(items)}, "items": items, "status": st}


@app.get("/api/portfolio")
def portfolio(price_thr: float = DEFAULT_PRICE_MOVE_PCT, vol_thr: float = DEFAULT_VOLUME_MULT):
    end = now_ist()
    with session() as con:
        latest_row = con.execute("SELECT MAX(ts) t FROM announcements").fetchone()
        latest_ts = latest_row["t"] if latest_row and latest_row["t"] else None
        if latest_ts:
            try:
                latest_dt = datetime.fromisoformat(latest_ts)
                if latest_dt.tzinfo is None:
                    latest_dt = latest_dt.replace(tzinfo=IST)
                if (now_ist() - latest_dt) > timedelta(hours=FILINGS_FRESH_HOURS):
                    end = latest_dt + timedelta(seconds=1)
            except Exception:
                pass
        week = build_items(con, end - timedelta(days=7), end, None, price_thr, vol_thr)
        px = prices_status(con)
        out = []
        for c in con.execute("SELECT * FROM companies WHERE in_portfolio=1 ORDER BY weight DESC, symbol"):
            series = bars(con, c["symbol"], 60)
            st = latest_stats(series)
            mine = [i for i in week if i["symbol"] == c["symbol"]]
            out.append({
                "symbol": c["symbol"], "name": c["name"], "sector": c["sector"],
                "size": c["size_bucket"], "weight": c["weight"],
                "stats": st, "spark": [b["close"] for b in series[-30:]],
                "flags": {"volume": bool(st and st["vol_x"] and st["vol_x"] >= vol_thr),
                          "price": bool(st and st["pct"] is not None and abs(st["pct"]) >= price_thr)},
                "filings_7d": {"act": sum(1 for i in mine if i["tier"] == "act"),
                               "know": sum(1 for i in mine if i["tier"] == "know"),
                               "skim": sum(1 for i in mine if i["tier"] == "skim")},
                "price_status": px["status"] if st else "UNAVAILABLE",
            })
    return {"holdings": out, "status": status()}


# ------------------------------------------------------------------ results intelligence routes
@app.get("/api/results/{symbol}")
def results_by_symbol(symbol: str, nature: str = "consolidated"):
    with session() as con:
        items = get_results_by_symbol(con, symbol, nature)
    return {"symbol": symbol.upper(), "nature": nature, "count": len(items), "results": items}


@app.get("/api/results/filing/{filing_id}")
def results_by_filing(filing_id: str):
    with session() as con:
        card = get_results_by_filing(con, filing_id)
        if not card:
            row = con.execute("SELECT * FROM announcements WHERE id=?", (filing_id,)).fetchone()
            if not row:
                raise HTTPException(404, f"Filing {filing_id} not found")
            raise HTTPException(404, f"No quarterly results extracted for filing {filing_id}")
    return card


# ------------------------------------------------------------------ pull research routes
@app.get("/api/research/search")
def research_search(q: str = ""):
    with session() as con:
        items = search_research_companies(con, q)
    return {"query": q, "count": len(items), "results": items}


@app.get("/api/research/{symbol}")
def research_by_symbol(symbol: str):
    with session() as con:
        res = get_company_research_dossier(con, symbol)
    if res["status"] == "NOT_FOUND":
        raise HTTPException(404, res["message"])
    return res


# ------------------------------------------------------------------ promise vs delivered routes
@app.get("/api/commitments/{symbol}")
def commitments_by_symbol(symbol: str):
    with session() as con:
        res = get_commitments_by_symbol(con, symbol)
    if res["status"] == "NOT_FOUND":
        raise HTTPException(404, res["message"])
    return res


@app.get("/api/commitments/{symbol}/summary")
def commitments_summary(symbol: str):
    with session() as con:
        res = get_commitments_summary_by_symbol(con, symbol)
    if res["status"] == "NOT_FOUND":
        raise HTTPException(404, res["message"])
    return res


# --- static frontend (built by `npm run build` into backend/static) ---
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Unknown API route")
        root = STATIC_DIR.resolve()
        f = (root / path).resolve()
        if path and f.is_file() and root in f.parents:  # never serve outside the static dir
            return FileResponse(f)
        return FileResponse(root / "index.html")
