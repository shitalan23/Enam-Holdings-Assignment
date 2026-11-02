"""MOCK data generator, used only to exercise the UI where live feeds are unreachable.

Everything written here has source='MOCK' and the app shows a MOCK badge and banner.
Prices are a seeded random walk from arbitrary base levels, NOT real quotes. Filing text
is generic template wording with no figures. The real ingest deletes MOCK rows first, and
this seeder refuses to run if real rows exist, so the two never mix.
"""
import hashlib
import random
from datetime import datetime, timedelta
from ..classify import classify
from ..config import PORTFOLIO
from ..db import session, set_feed_status
from ..market import IST, now_ist

# (desc, text) templates; classification is done by the real classifier, not hard-coded.
POOL = [
    ("Trading Window", "Closure of trading window for designated persons"),
    ("Updates", "Newspaper publication of notice to shareholders"),
    ("Allotment of Securities", "Allotment of equity shares pursuant to ESOP scheme"),
    ("Analysts/Institutional Investor Meet/Con. Call Updates", "Schedule of one-on-one meetings with institutional investors"),
    ("Analysts/Institutional Investor Meet/Con. Call Updates", "Audio recording and transcript of earnings call"),
    ("Press Release", "Company announces new partnership with a technology provider"),
    ("Credit Rating", "Rating agency reaffirmed the long term credit rating"),
    ("Dividend", "Transfer of unclaimed dividend to IEPF"),
    ("Compliance Certificate", "Compliance certificate under Regulation 74(5) for the quarter"),
    ("Postal Ballot", "Notice of postal ballot for shareholder approval"),
    ("Appointment", "Appointment of Statutory Auditors of the company"),
    ("Capex", "Board approves capacity expansion at an existing manufacturing facility"),
    ("Insider Trading", "Disclosure under Regulation 7(2) of SEBI Prohibition of Insider Trading Regulations"),
    ("Board Meeting Intimation", "Intimation of board meeting to consider financial results for the quarter ended"),
    ("Bonus/Split", "Board recommends bonus issue of equity shares"),
]
# Hand-placed, high-signal filings so every tier is visible in the demo: (symbol, hours_ago, desc, text)
FEATURED = [
    ("HDFCBANK",  3,  "Change in Directors/Key Managerial Personnel", "Resignation of Chief Financial Officer with effect from the close of business hours"),
    ("RELIANCE",  5,  "Financial Results", "Unaudited consolidated financial results for the quarter and half year ended"),
    ("BAJFINANCE", 9, "Credit Rating", "Rating agency has downgraded the long term rating of the company"),
    ("TCS",       11, "Outcome of Board Meeting", "Board approved unaudited financial results; interim dividend declared"),
    ("DIXON",     14, "Acquisition", "Acquisition of a controlling stake in an electronics manufacturing company"),
    ("MARUTI",    20, "Pledging", "Invocation of pledge on promoter shares"),
    ("POLYCAB",   30, "Litigation", "Show cause notice received from a regulatory authority"),
    ("TITAN",     41, "Appointment", "Appointment of Chief Executive Officer of a business division"),
    ("INFY",      52, "Fund Raising", "Board approves buy-back of equity shares"),
    ("ITC",       70, "Financial Results", "Audited standalone and consolidated results for the year ended"),
]


def _has_real(con) -> bool:
    return bool(con.execute("SELECT 1 FROM prices_eod WHERE source!='MOCK' LIMIT 1").fetchone()
                or con.execute("SELECT 1 FROM announcements WHERE source!='MOCK' LIMIT 1").fetchone())


def seed_mock(seed: int = 7) -> str:
    rng = random.Random(seed)
    now = now_ist()
    stamp = now.isoformat(timespec="seconds")
    with session() as con:
        if _has_real(con):
            return "Refused: real (non-MOCK) data exists. Mock data is never mixed with real data."
        con.execute("DELETE FROM prices_eod WHERE source='MOCK'")
        con.execute("DELETE FROM announcements WHERE source='MOCK'")

        # ~70 weekdays of prices ending at the most recent weekday
        d = now.date()
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        days = []
        while len(days) < 70:
            if d.weekday() < 5:
                days.append(d)
            d -= timedelta(days=1)
        days.reverse()
        spike = {"HDFCBANK": (-6.1, 3.1), "BAJFINANCE": (-5.4, 2.7), "DIXON": (7.2, 3.4),
                 "RELIANCE": (1.4, 1.8), "MARUTI": (-2.2, 1.2)}
        for sym, *_ in PORTFOLIO:
            r = random.Random(f"{seed}-{sym}")
            px = 200 + (int(hashlib.md5(sym.encode()).hexdigest(), 16) % 4800)
            base_vol = 400_000 + int(hashlib.md5(sym[::-1].encode()).hexdigest(), 16) % 3_000_000
            for i, day in enumerate(days):
                prev = px
                px *= 1 + r.gauss(0.0004, 0.012)
                vol = max(1, int(base_vol * r.uniform(0.75, 1.3)))
                if i == len(days) - 1 and sym in spike:
                    px = prev * (1 + spike[sym][0] / 100)
                    vol = int(base_vol * spike[sym][1])
                con.execute("INSERT INTO prices_eod VALUES (?,?,?,?,?,?,?,?,?)", (
                    sym, day.isoformat(), round(prev, 2), round(max(px, prev) * 1.004, 2),
                    round(min(px, prev) * 0.996, 2), round(px, 2), vol, "MOCK", stamp))

        syms = [s for s, *_ in PORTFOLIO]
        items = [(s, now - timedelta(hours=h), desc, text) for s, h, desc, text in FEATURED]
        for _ in range(38):
            desc, text = rng.choice(POOL)
            hrs = rng.choice([rng.uniform(0.5, 24), rng.uniform(0.5, 24), rng.uniform(24, 240)])
            items.append((rng.choice(syms), now - timedelta(hours=hrs), desc, text))
        for sym, ts, desc, text in items:
            c = classify(desc, text)
            aid = hashlib.sha1(f"MOCK|{sym}|{ts.isoformat()}|{desc}|{text}".encode()).hexdigest()[:16]
            con.execute("INSERT OR REPLACE INTO announcements (id,symbol,ts,headline,detail,category,subtype,"
                        "category_method,pdf_url,source,fetched_at,confidence,reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (aid, sym, ts.isoformat(timespec="seconds"), desc, text, c.category,
                         c.subtype, c.method, None, "MOCK", stamp, c.confidence, c.reason))
        set_feed_status(con, "prices", "MOCK", stamp, "Synthetic random-walk prices, not real quotes")
        set_feed_status(con, "announcements", "MOCK", stamp, "Template filings, not real disclosures")
    return f"Seeded MOCK data: {len(days)} days x {len(PORTFOLIO)} symbols, {len(items)} filings."
