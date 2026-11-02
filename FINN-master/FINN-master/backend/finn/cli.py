"""Command-line entry point.  Usage (from the backend/ folder):

  python -m finn.cli init
  python -m finn.cli ingest-prices
  python -m finn.cli ingest-announcements --days 30
  python -m finn.cli probe RELIANCE
  python -m finn.cli issues

Classification tools (these never touch prices, and `reclassify` backs up first):
  python -m finn.cli review-classification   # per-label report: what each NSE label becomes, how sure we are
  python -m finn.cli reclassify              # DRY RUN: shows what would change, writes nothing
  python -m finn.cli reclassify --apply      # backs up the DB, then updates classifications in place
  python -m finn.cli export-fixtures         # saves real descriptions from YOUR db as test fixtures

  python -m finn.cli seed-mock               # MOCK data for UI work only; refuses if real data exists
"""
import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .classify import LEGACY_MAP, TAXONOMY, classify
from .config import DB_PATH, PORTFOLIO, ROOT
from .db import init_db, session

FIXTURE_PATH = ROOT / "backend" / "tests" / "fixtures" / "real_announcements.json"


def _rows(con, include_mock=False):
    q = "SELECT id, symbol, headline, detail, category, subtype, confidence FROM announcements"
    if not include_mock:
        q += " WHERE source != 'MOCK'"
    return con.execute(q).fetchall()


def cmd_review() -> None:
    with session() as con:
        rows = _rows(con)
    if not rows:
        print("No real announcements in the database.")
        return
    by_label = defaultdict(list)
    for r in rows:
        c = classify(r["headline"], r["detail"] or "")
        by_label[r["headline"].strip()].append(c)
    print(f"{len(rows)} real filings, {len(by_label)} distinct NSE labels\n")
    print(f"{'n':>4}  {'min conf':>8}  {'category (share)':<44}  NSE label")
    for label, cs in sorted(by_label.items(), key=lambda kv: -len(kv[1])):
        cnt = Counter(c.category for c in cs)
        top = ", ".join(f"{k} {v}" for k, v in cnt.most_common(3))
        print(f"{len(cs):>4}  {min(c.confidence for c in cs):>8.2f}  {top:<44}  {label[:70]}")
    tot = Counter(classify(r["headline"], r["detail"] or "").category for r in rows)
    print("\nOverall:", ", ".join(f"{TAXONOMY[k]} {v}" for k, v in tot.most_common()))
    nr = tot.get("needs_review", 0)
    print(f"Needs review: {nr} of {len(rows)} ({nr / len(rows):.0%}). "
          "Paste the labels marked needs_review above back to the developer to extend the rules.")


def cmd_reclassify(apply: bool) -> None:
    with session() as con:
        rows = _rows(con)
        if not rows:
            print("No real announcements to reclassify.")
            return
        moves, changed, new_cat = Counter(), 0, Counter()
        updates = []
        for r in rows:
            c = classify(r["headline"], r["detail"] or "")
            old = r["category"]
            old_mapped = LEGACY_MAP.get(old, old)
            new_cat[c.category] += 1
            if old_mapped != c.category or r["confidence"] is None:
                moves[(old, c.category)] += 1
            if old_mapped != c.category:
                changed += 1
            updates.append((c.category, c.subtype, c.method, c.confidence, c.reason, r["id"]))
        print(f"{len(rows)} real filings. Category differs from the old classifier on {changed}.\n")
        print("Most common moves (old -> new):")
        for (o, n), v in moves.most_common(15):
            if LEGACY_MAP.get(o, o) != n:
                print(f"  {v:>4}  {o:<18} -> {n}")
        print("\nNew distribution:", ", ".join(f"{TAXONOMY[k]} {v}" for k, v in new_cat.most_common()))
        if not apply:
            print("\nDRY RUN: nothing written. Re-run with --apply to update (a backup is made first).")
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = Path(str(DB_PATH) + f".bak-{stamp}")
        dst = sqlite3.connect(backup)
        con.backup(dst)  # consistent copy, safe even if the app is running
        dst.close()
        con.executemany("UPDATE announcements SET category=?, subtype=?, category_method=?, confidence=?, reason=? WHERE id=?", updates)
        print(f"\nBackup written to {backup}\nUpdated {len(updates)} filings.")


def cmd_export_fixtures() -> None:
    with session() as con:
        rows = _rows(con)
    if not rows:
        print("No real announcements to export.")
        return
    seen = defaultdict(list)
    for r in rows:
        key = r["headline"].strip()
        if len(seen[key]) < 3:
            c = classify(r["headline"], r["detail"] or "")
            seen[key].append({"desc": r["headline"], "text": r["detail"] or "",
                              "classified_as": c.category, "subtype": c.subtype, "confidence": c.confidence})
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps([x for v in seen.values() for x in v], indent=1, ensure_ascii=False))
    print(f"Wrote {sum(len(v) for v in seen.values())} samples across {len(seen)} labels to {FIXTURE_PATH}")
    print("Run `PYTHONPATH=. pytest tests/test_real_fixtures.py -q` to check the invariants against them.")


def main() -> None:
    ap = argparse.ArgumentParser(prog="finn")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("ingest-prices")
    a = sub.add_parser("ingest-announcements"); a.add_argument("--days", type=int, default=30)
    p = sub.add_parser("probe"); p.add_argument("symbol")
    sub.add_parser("seed-mock")
    sub.add_parser("issues")
    sub.add_parser("review-classification")
    r = sub.add_parser("reclassify"); r.add_argument("--apply", action="store_true")
    sub.add_parser("export-fixtures")
    args = ap.parse_args()
    init_db()
    symbols = [s for s, *_ in PORTFOLIO]
    if args.cmd == "ingest-prices":
        from .ingest.prices import ingest_prices
        print(ingest_prices(symbols))
    elif args.cmd == "ingest-announcements":
        from .ingest.nse_announcements import ingest_announcements
        print(ingest_announcements(symbols, args.days))
    elif args.cmd == "probe":
        from .ingest.nse_announcements import probe
        probe(args.symbol.upper())
    elif args.cmd == "seed-mock":
        from .ingest.seed_mock import seed_mock
        print(seed_mock())
    elif args.cmd == "issues":
        with session() as con:
            for row in con.execute("SELECT * FROM ingest_issues ORDER BY at DESC LIMIT 40"):
                print(dict(row))
    elif args.cmd == "review-classification":
        cmd_review()
    elif args.cmd == "reclassify":
        cmd_reclassify(args.apply)
    elif args.cmd == "export-fixtures":
        cmd_export_fixtures()
    else:
        print("DB ready.")


if __name__ == "__main__":
    main()
