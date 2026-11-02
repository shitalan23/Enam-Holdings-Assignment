"""Integration tests for Research Intelligence API endpoints.

Tests:
- GET /api/research/search
- GET /api/research/{symbol} for available dossier (RELIANCE)
- GET /api/research/{symbol} for tracked company without dossier (e.g. TCS -> UNAVAILABLE)
- GET /api/research/{symbol} for unknown company (404)
- Verification of 8 dimensions, citations completeness, and absence of hallucinated data
"""
from fastapi.testclient import TestClient
import pytest
from finn.api import app
from finn.db import session
from finn.research_extract import build_reliance_research_dossier, save_research_report

client = TestClient(app)


@pytest.fixture(autouse=True)
def populate_test_research():
    """Ensure test database has RELIANCE research dossier loaded."""
    dossier = build_reliance_research_dossier()
    with session() as con:
        save_research_report(con, dossier)
    yield


def test_research_search_all_companies():
    res = client.get("/api/research/search")
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == ""
    assert data["count"] >= 17
    # Verify portfolio flags and research status
    symbols = {c["symbol"]: c for c in data["results"]}
    assert "RELIANCE" in symbols
    assert "TCS" in symbols
    assert "INFY" in symbols
    assert symbols["RELIANCE"]["has_research"] is True
    assert symbols["RELIANCE"]["as_of_period"] == "Q2 FY27"
    assert symbols["TCS"]["has_research"] is False


def test_research_search_filtered():
    # Search by symbol
    res1 = client.get("/api/research/search?q=rel")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["count"] >= 1
    assert any(c["symbol"] == "RELIANCE" for c in data1["results"])

    # Search by company name case-insensitively
    res2 = client.get("/api/research/search?q=tata")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["count"] >= 1
    assert any("Tata" in c["name"] for c in data2["results"])

    # Search non-existent
    res3 = client.get("/api/research/search?q=xyznonexistent123")
    assert res3.status_code == 200
    assert res3.json()["count"] == 0
    assert res3.json()["results"] == []


def test_research_reliance_available_dossier():
    res = client.get("/api/research/RELIANCE")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "AVAILABLE"
    assert data["symbol"] == "RELIANCE"
    assert "Reliance Industries" in data["company_name"]
    assert data["has_research"] is True
    assert data["as_of_period"] == "Q2 FY27"
    assert data["as_of_date"] == "2026-09-30"

    dossier = data["dossier"]
    assert dossier is not None

    # 1. Business Snapshot
    bs = dossier["business_snapshot"]
    assert len(bs["segments"]) >= 4
    assert any("O2C" in s["name"] for s in bs["segments"])
    assert any("Retail" in s["name"] for s in bs["segments"])
    assert any("Jio" in s["name"] for s in bs["segments"])
    assert len(bs["core_platforms"]) == 4

    # 2. Financial Snapshot & Reconciliations
    fs = dossier["financial_snapshot"]
    assert fs["revenue_from_operations_cr"] == 332861.0
    assert fs["reported_ebitda_cr"] == 62409.0
    assert fs["derived_operating_ebitda_cr"] == 56616.0
    assert fs["headline_pat_cr"] == 29550.0
    assert fs["total_segment_ebitda_cr"] == 61224.0
    assert "ebitda_reconciliation_note" in fs
    assert "Statutory Segment EBITDA totals ₹61,224 Cr" in fs["ebitda_reconciliation_note"]
    assert fs["retail_performance"]["ebitda_after_impairment_cr"] == 6120.0
    assert fs["retail_performance"]["gross_revenue_yoy_pct"] == 6.4

    # 3. Trajectory
    traj = dossier["trajectory"]
    assert len(traj["growing_segments"]) >= 2
    assert len(traj["compressing_segments"]) >= 2
    o2c = next(s for s in traj["growing_segments"] if "O2C" in s["segment"])
    assert o2c["yoy_ebitda_growth_pct"] == 67.9

    # 4. Balance Sheet
    bal = dossier["balance_sheet"]
    assert bal["gross_debt_cr"] == 384952.0
    assert bal["cash_and_equivalents_cr"] == 181723.0
    assert bal["current_investments_cr"] == 78591.0
    assert bal["total_liquid_assets_cr"] == 260314.0
    assert bal["management_reported_net_debt_cr"] == 117140.0
    assert bal["management_net_debt_to_ebitda"] == 0.47
    assert bal["debt_equity_ratio"] == 0.41
    assert bal["total_equity_cr"] == 1132648.0
    assert bal["net_worth_cr"] == 906204.0
    assert "equity_reconciliation_note" in bal
    assert "net_debt_reconciliation_note" in bal
    assert "interest_reconciliation_note" in bal
    assert bal["finance_costs_pnl_h1_cr"] == 16818.0
    assert bal["cash_interest_paid_h1_cr"] == 21875.0

    # 5. Cash Quality
    cq = dossier["cash_quality"]
    assert cq["period"] == "H1 FY27 (Half Year Ended September 30, 2026)"
    assert cq["cfo_cr"] == 93055.0
    assert cq["capex_h1_cr"] == 52813.0
    assert cq["fcf_h1_cr"] == 40242.0
    assert cq["cfo_to_pbt_pct"] == 134.4
    assert cq["cash_conversion_status"] == "STRONG_CONVERSION"
    assert cq["fcf_status"] == "POSITIVE_FCF"
    assert "SEBI LODR Regulation 33" in cq["period_scope_note"]

    # 6. Narrative vs Numbers
    nvn = dossier["narrative_vs_numbers"]
    assert len(nvn) >= 3
    assert any(item["dimension"] == "Retail Performance" and item["verdict"] == "Divergence" for item in nvn)
    assert any(item["dimension"] == "O2C Refining & Energy" and item["verdict"] == "Agreement" for item in nvn)
    assert any(item["dimension"] == "Deleveraging & Balance Sheet" and item["verdict"] == "Qualified Agreement" for item in nvn)

    # 7. Guidance
    guid = dossier["guidance"]
    assert len(guid) >= 3
    assert any(item["metric_or_area"] == "Capital Expenditure (Capex)" and item["status"] == "Delivered" for item in guid)
    assert any(item["metric_or_area"] == "Jio Platforms Value Unlocking" and item["status"] == "Delivered" for item in guid)

    # 8. Bull vs Bear
    bvb = dossier["bull_vs_bear"]
    assert len(bvb["bull_case"]) >= 3
    assert len(bvb["bear_case"]) >= 3

    # Citations completeness
    citations = dossier["citations"]
    assert len(citations) >= 9
    for cit in citations:
        assert cit["id"]
        assert cit["doc_title"]
        assert cit["doc_type"] in ["results_pdf", "investor_presentation", "annual_report", "concall_transcript"]
        assert cit["page"] > 0
        assert cit["section"]
        assert cit["claim"]
        assert cit["url"].startswith("https://")


def test_research_tracked_company_without_dossier_returns_unavailable():
    # TCS is in portfolio / companies table, but has no research synthesized yet
    res = client.get("/api/research/TCS")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UNAVAILABLE"
    assert data["symbol"] == "TCS"
    assert data["has_research"] is False
    assert data["dossier"] is None
    assert "has not yet been generated" in data["message"]


def test_research_unknown_symbol_returns_404():
    res = client.get("/api/research/UNKNOWN_SYMBOL_99")
    assert res.status_code == 404
    data = res.json()
    assert "not tracked in the database" in data["detail"]
