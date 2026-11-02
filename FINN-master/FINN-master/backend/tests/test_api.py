import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from finn import api
from finn.db import session
from helpers import NOW, add_bar, add_filing

@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(api, "now_ist", lambda: NOW)

c = TestClient(api.app)

def seed_basic():
    for sym in ("TCS", "RELIANCE"):
        add_bar(sym, "2026-10-29", 100); add_bar(sym, "2026-10-30", 101)
    add_filing("TCS", 3, "Financial Results", "Unaudited financial results for the quarter ended", "results", "outcome")
    add_filing("TCS", 4, "Copy of Newspaper Publication", "Extract of financial results published", "routine_compliance", "newspaper_ad")
    add_filing("RELIANCE", 5, "Analysts/Institutional Investor Meet/Con. Call Updates",
               "Intimation of call on financial results", "investor_events", "call_notice")
    add_filing("RELIANCE", 6, "Mystery Label", "unclear", "needs_review", None, conf=0.2)

def test_brief_shape_and_counts():
    seed_basic()
    b = c.get("/api/brief?window=24h").json()
    assert set(b["counts"]) == {"act", "know", "skim", "total"}
    assert b["counts"]["total"] == len(b["items"]) == 4
    assert sum(b["counts"][t] for t in ("act", "know", "skim")) == 4

def test_reported_failures_are_not_results_and_routine_stays_out_of_needs_you():
    seed_basic()
    items = {i["headline"]: i for i in c.get("/api/brief?window=24h").json()["items"]}
    assert items["Copy of Newspaper Publication"]["category"] == "routine_compliance"
    assert items["Copy of Newspaper Publication"]["tier"] == "skim"
    call = items["Analysts/Institutional Investor Meet/Con. Call Updates"]
    assert call["category"] == "investor_events" and call["tier"] != "act"
    assert items["Financial Results"]["tier"] == "act"
    assert items["Mystery Label"]["category_label"] == "Needs review"

def test_every_item_exposes_a_breakdown_that_sums_to_its_score():
    seed_basic()
    for i in c.get("/api/brief?window=24h").json()["items"]:
        assert sum(r["points"] for r in i["breakdown"]) == i["score"]
        assert 0 <= i["confidence"] <= 1 and i["classified_by"]

def test_items_are_sorted_tier_then_score():
    seed_basic()
    items = c.get("/api/brief?window=24h").json()["items"]
    order = {"act": 0, "know": 1, "skim": 2}
    keys = [(order[i["tier"]], -i["score"]) for i in items]
    assert keys == sorted(keys)

def test_legacy_rows_are_reclassified_on_the_fly_and_flagged():
    seed_basic()
    # a row stored by the old classifier: category 'results' and no confidence
    add_filing("TCS", 2, "Copy of Newspaper Publication", "Financial results published", "results", None, conf=None, fid="legacy1")
    b = c.get("/api/brief?window=24h").json()
    legacy = next(i for i in b["items"] if i["id"] == "legacy1")
    assert legacy["category"] == "routine_compliance"           # fixed without touching the DB
    assert b["status"]["classification"]["needs_reclassify"] == 1
    with session() as con:   # and the stored row is unchanged until `reclassify --apply`
        assert con.execute("SELECT category FROM announcements WHERE id='legacy1'").fetchone()[0] == "results"

def test_scoring_rules_endpoint_explains_the_gates():
    r = c.get("/api/scoring").json()
    assert r["thresholds"]["act"] == 72 and len(r["gates"]) >= 3 and r["examples"]

def test_status_reports_eod_and_delayed():
    seed_basic()
    s = c.get("/api/status").json()
    assert s["prices"]["status"] == "EOD" and s["announcements"]["status"] in ("DELAYED", "CACHED")

def test_window_validation_custom_range_and_404s():
    assert c.get("/api/brief?window=9y").status_code == 400
    assert c.get("/api/brief?from_ts=notadate").status_code == 400
    assert c.get("/api/brief?from_ts=2026-10-01&to_ts=2026-10-31").status_code == 200
    assert c.get("/api/nope").status_code == 404   # regression: SPA catch-all once swallowed unknown API routes

def test_portfolio_uses_real_status_label():
    seed_basic()
    p = c.get("/api/portfolio").json()
    tcs = next(h for h in p["holdings"] if h["symbol"] == "TCS")
    assert tcs["price_status"] == "EOD" and tcs["stats"]["close"] == 101


def test_brief_snapshot_relative_date_filtering(monkeypatch):
    seed_basic()
    # Simulate wall-clock time being 14 days after the latest filing in the database
    future_now = NOW + timedelta(days=14)
    monkeypatch.setattr(api, "now_ist", lambda: future_now)

    # 1. 24h filter is relative to newest snapshot filing (not current wall-clock) and returns all 4 filings
    b24 = c.get("/api/brief?window=24h").json()
    assert b24["window"]["is_snapshot"] is True
    assert "snapshot" in b24["window"]["label"].lower()
    assert b24["counts"]["total"] == 4

    # 2. 7d window also returns filings relative to the snapshot
    b7 = c.get("/api/brief?window=7d").json()
    assert b7["window"]["is_snapshot"] is True
    assert b7["counts"]["total"] == 4

    # 3. Snapshot metadata is exposed accurately
    assert b24["window"]["snapshot_as_of"] is not None
    assert b24["status"]["announcements"]["as_of"] is not None
    assert b24["status"]["prices"]["as_of"] is not None

    # 4. Custom range ignores snapshot anchoring and respects user-provided dates
    b_custom = c.get("/api/brief?from_ts=2026-10-01&to_ts=2026-10-31").json()
    assert b_custom["window"]["is_snapshot"] is False
    assert b_custom["window"]["label"] == "Custom range"

    # 5. Portfolio 7d filings count is also snapshot-aware
    p = c.get("/api/portfolio").json()
    tcs = next(h for h in p["holdings"] if h["symbol"] == "TCS")
    assert sum(tcs["filings_7d"].values()) == 2


def test_results_api_endpoints():
    import json
    seed_basic()
    raw = {
        "gross_revenue": [362268.0, 340257.0, 283548.0],
        "gst_recovered": [29407.0, 28407.0, 24650.0],
        "revenue": [332861.0, 311850.0, 258898.0],
        "pbt": [38613.0, 30630.0, 29124.0],
        "pat": [29250.0, 23001.0, 22146.0],
        "share_of_associates": [300.0, 195.0, -54.0],
        "pat_with_associates": [29550.0, 23196.0, 22092.0],
        "pat_attributable_to_owners": [25548.0, 20946.0, 18165.0],
        "finance_costs": [8481.0, 8337.0, 6827.0],
        "depreciation": [15315.0, 15100.0, 14416.0],
        "other_income": [5793.0, 6550.0, 4482.0],
    }
    with session() as con:
        con.execute(
            """INSERT INTO quarterly_results (
                id, symbol, filing_id, period_label, period_end_date, nature,
                currency, unit, gross_revenue, gst_recovered, revenue, other_income, total_income,
                finance_costs, depreciation, pbt_before_exceptional, exceptional_items, pbt,
                tax_expense, pat, share_of_associates, pat_with_associates, pat_attributable_to_owners,
                reported_ebitda, derived_ebitda, derived_ebitda_method, ebitda_reconciliation_note,
                raw_figures, source_doc_url, source_page, source_table_name, extracted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "q123", "RELIANCE", "filing_rel_res", "Q2 FY27", "2026-09-30", "consolidated",
                "INR", "crore", 362268.0, 29407.0, 332861.0, 5793.0, 338654.0,
                8481.0, 15315.0, 38613.0, 0.0, 38613.0,
                None, 29250.0, 300.0, 29550.0, 25548.0,
                62409.0, 56616.0, "Derived: PBT + Finance + Depr - Other", "Reported = Derived + Other",
                json.dumps(raw), "https://example.com/res.pdf", 10, "CONSOLIDATED RESULTS", "2026-11-01T00:00:00"
            ),
        )

    # 1. Test GET /api/results/RELIANCE
    res = c.get("/api/results/RELIANCE").json()
    assert res["symbol"] == "RELIANCE"
    assert res["count"] == 1
    card = res["results"][0]
    assert card["period_label"] == "Q2 FY27"
    assert card["metrics"]["revenue"]["current"] == 332861.0
    assert card["metrics"]["revenue"]["qoq"]["pct"] == 6.74
    assert card["metrics"]["revenue"]["yoy_cmp"]["pct"] == 28.57
    assert card["metrics"]["derived_ebitda"]["current"] == 56616.0
    assert card["metrics"]["derived_ebitda"]["qoq"]["pct"] == 19.15
    assert card["metrics"]["reported_ebitda"]["current"] == 62409.0
    assert card["metrics"]["pat_with_associates"]["current"] == 29550.0
    assert card["metrics"]["pat_attributable_to_owners"]["current"] == 25548.0

    # 2. Test GET /api/results/filing/filing_rel_res
    f_res = c.get("/api/results/filing/filing_rel_res").json()
    assert f_res["filing_id"] == "filing_rel_res"
    assert "consolidated" in f_res["statements"]

    # 3. Test 404 for unknown filing
    err = c.get("/api/results/filing/nonexistent")
    assert err.status_code == 404


def test_results_intelligence_not_duplicated_for_duplicate_announcements():
    """Regression test: when a company has multiple results announcements in the feed,
    only the primary filing mapped to the quarterly_results record carries has_results=True.
    The second filing is preserved in the feed as a filing event, but does not duplicate
    the Results Intelligence card."""
    import json
    # Add two announcements for RELIANCE with category='results'
    add_filing("RELIANCE", 2, "Outcome of Board Meeting", "Approved financial results", "results", "outcome", fid="rel_filing_1")
    add_filing("RELIANCE", 2, "Outcome of Board Meeting", "Approved financial results", "results", "outcome", fid="rel_filing_2")

    # Map only rel_filing_1 to a quarterly result
    raw = {
        "gross_revenue": [362268.0, 340257.0, 283548.0],
        "gst_recovered": [29407.0, 28407.0, 24650.0],
        "revenue": [332861.0, 311850.0, 258898.0],
        "pbt": [38613.0, 30630.0, 29124.0],
        "pat": [29250.0, 23001.0, 22146.0],
        "share_of_associates": [300.0, 195.0, -54.0],
        "pat_with_associates": [29550.0, 23196.0, 22092.0],
        "pat_attributable_to_owners": [25548.0, 20946.0, 18165.0],
        "finance_costs": [8481.0, 8337.0, 6827.0],
        "depreciation": [15315.0, 15100.0, 14416.0],
        "other_income": [5793.0, 6550.0, 4482.0],
    }
    with session() as con:
        con.execute(
            """INSERT INTO quarterly_results (
                id, symbol, filing_id, period_label, period_end_date, nature,
                currency, unit, gross_revenue, gst_recovered, revenue, other_income, total_income,
                finance_costs, depreciation, pbt_before_exceptional, exceptional_items, pbt,
                tax_expense, pat, share_of_associates, pat_with_associates, pat_attributable_to_owners,
                reported_ebitda, derived_ebitda, derived_ebitda_method, ebitda_reconciliation_note,
                raw_figures, source_doc_url, source_page, source_table_name, extracted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "q_rel_stable_1", "RELIANCE", "rel_filing_1", "Q2 FY27", "2026-09-30", "consolidated",
                "INR", "crore", 362268.0, 29407.0, 332861.0, 5793.0, 338654.0,
                8481.0, 15315.0, 38613.0, 0.0, 38613.0,
                None, 29250.0, 300.0, 29550.0, 25548.0,
                62409.0, 56616.0, "Derived: PBT + Finance + Depr - Other", "Reported = Derived + Other",
                json.dumps(raw), "https://example.com/res.pdf", 10, "CONSOLIDATED RESULTS", "2026-11-01T00:00:00"
            ),
        )

    # Fetch brief feed
    feed = c.get("/api/brief?window=24h").json()
    rel_items = [i for i in feed["items"] if i["symbol"] == "RELIANCE"]

    # 1. Both filings must exist in the feed (neither is discarded or wiped)
    assert len(rel_items) == 2
    fids = {i["id"] for i in rel_items}
    assert fids == {"rel_filing_1", "rel_filing_2"}

    # 2. Exactly ONE filing has has_results=True
    results_items = [i for i in rel_items if i.get("has_results")]
    assert len(results_items) == 1
    assert results_items[0]["id"] == "rel_filing_1"
    assert results_items[0]["result_id"] == "q_rel_stable_1"

    # 3. The second filing has has_results=False
    non_results_items = [i for i in rel_items if not i.get("has_results")]
    assert len(non_results_items) == 1
    assert non_results_items[0]["id"] == "rel_filing_2"

    # 4. Strict filing-to-result mapping: rel_filing_1 succeeds, rel_filing_2 returns 404
    assert c.get("/api/results/filing/rel_filing_1").status_code == 200
    assert c.get("/api/results/filing/rel_filing_2").status_code == 404


def test_static_frontend_serving():
    """Verify that root / serves index.html and static assets are accessible."""
    res = c.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert '<div id="root"></div>' in res.text
    assert "/assets/index-" in res.text

