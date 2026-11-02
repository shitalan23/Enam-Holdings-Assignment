"""Integration tests for Promise vs Delivered API endpoints (backend/finn/api.py).

Tests:
- GET /api/commitments/{symbol} for RELIANCE
- GET /api/commitments/{symbol}/summary for RELIANCE
- GET /api/commitments/{symbol} for tracked company without commitments (TCS -> UNAVAILABLE)
- GET /api/commitments/{symbol}/summary for tracked company without commitments (TCS -> UNAVAILABLE)
- GET /api/commitments/{symbol} for unknown symbol (404)
- Verification of citation completeness (promise and actual citations)
- Delivery score calculation transparency (3 of 3 evaluated commitments)
- Stat caveat presence preventing misleading track record claims
"""
from fastapi.testclient import TestClient
import pytest
from finn.api import app
from finn.db import session
from finn.commitments_extract import extract_reliance_commitments, save_commitments

client = TestClient(app)


@pytest.fixture(autouse=True)
def populate_test_commitments():
    """Ensure test database has audited RELIANCE commitments loaded."""
    items = extract_reliance_commitments()
    with session() as con:
        con.execute("DELETE FROM commitments WHERE symbol='RELIANCE'")
        save_commitments(con, items)
    yield


def test_get_commitments_reliance():
    res = client.get("/api/commitments/RELIANCE")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "OK"
    assert data["symbol"] == "RELIANCE"
    assert data["company_name"] == "Reliance Industries"
    assert data["count"] == 9
    assert len(data["commitments"]) == 9

    summary = data["summary"]
    assert summary["delivery_score"] is None
    assert summary["eligible_evaluated_count"] == 0
    assert summary["evaluated_count"] == 0
    assert summary["eligible_achieved_count"] == 0
    assert summary["achieved_count"] == 0
    assert summary["total_achieved_count"] == 2  # 2 completed operational milestones
    assert summary["eligible_count"] == 6
    assert summary["excluded_count"] == 3
    assert summary["eligible_in_progress_count"] == 2
    assert summary["in_progress_count"] == 2
    assert summary["total_in_progress_count"] == 3  # 2 eligible + 1 strategic intention
    assert summary["eligible_unverifiable_count"] == 4  # Capex, IPO, Leverage, Debottlenecking
    assert summary["unverifiable_count"] == 4
    assert summary["total_unverifiable_count"] == 4

    # Invariants
    assert summary["eligible_count"] == (
        summary["eligible_evaluated_count"] +
        summary["eligible_in_progress_count"] +
        summary["eligible_unverifiable_count"] +
        summary["eligible_needs_review_count"]
    )
    assert summary["eligible_evaluated_count"] == (
        summary["eligible_achieved_count"] +
        summary["eligible_partially_achieved_count"] +
        summary["eligible_delayed_count"] +
        summary["eligible_missed_count"]
    )
    assert summary["total_commitments"] == summary["eligible_count"] + summary["excluded_count"]

    assert "Insufficient evaluated evidence" in summary["score_label"]
    assert "No eligible commitments have concluded evaluation yet" in summary["stat_caveat"]

    # Verify citation completeness for each commitment
    by_title = {c["title"]: c for c in data["commitments"]}

    capex = by_title["Quarterly Capital Expenditure Run-Rate Guidance"]
    assert capex["status"] == "UNVERIFIABLE"
    assert capex["source_citation"]["doc_title"] != ""
    assert capex["source_citation"]["page_or_slide"] == "Slide 12"
    assert capex["source_citation"]["url"].startswith("https://")
    assert capex["actual_citation"] is not None
    assert capex["actual_citation"]["url"].startswith("https://")
    assert capex["target"]["value"] == 38000.0
    assert capex["actual"]["value"] == 38153.0

    ipo = by_title["Jio Platforms Public Listing & De-leveraging IPO"]
    assert ipo["status"] == "UNVERIFIABLE"
    assert ipo["source_citation"]["page_or_slide"] == "Slide 14"
    assert "Note 3" in ipo["actual_citation"]["page_or_slide"]
    assert ipo["actual"]["value"] == 30188.0

    leverage = by_title["Balance Sheet Leverage Ceiling (< 1.0x Net Debt/EBITDA)"]
    assert leverage["status"] == "UNVERIFIABLE"
    assert leverage["actual"]["value"] == 0.47


def test_get_commitments_summary_reliance():
    res = client.get("/api/commitments/RELIANCE/summary")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "OK"
    assert data["symbol"] == "RELIANCE"
    assert data["company_name"] == "Reliance Industries"
    assert data["count"] == 9

    summary = data["summary"]
    assert summary["delivery_score"] is None
    assert summary["eligible_evaluated_count"] == 0
    assert summary["evaluated_count"] == 0
    assert summary["eligible_achieved_count"] == 0
    assert summary["achieved_count"] == 0
    assert summary["total_achieved_count"] == 2
    assert summary["eligible_count"] == 6
    assert summary["excluded_count"] == 3
    assert summary["eligible_in_progress_count"] == 2
    assert summary["total_in_progress_count"] == 3
    assert summary["eligible_unverifiable_count"] == 4
    assert "Insufficient evaluated evidence" in summary["score_label"]


def test_get_commitments_tracked_company_unavailable():
    # TCS is tracked in portfolio but has no commitments yet
    res = client.get("/api/commitments/TCS")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "UNAVAILABLE"
    assert data["symbol"] == "TCS"
    assert data["company_name"] == "Tata Consultancy Services"
    assert data["count"] == 0
    assert data["commitments"] == []
    assert data["summary"] is None
    assert "No management commitments tracked yet" in data["message"]

    res_sum = client.get("/api/commitments/TCS/summary")
    assert res_sum.status_code == 200
    data_sum = res_sum.json()
    assert data_sum["status"] == "UNAVAILABLE"
    assert data_sum["count"] == 0
    assert data_sum["summary"] is None


def test_get_commitments_unknown_symbol_404():
    res1 = client.get("/api/commitments/UNKNOWNXYZ")
    assert res1.status_code == 404
    assert "not tracked" in res1.json()["detail"]

    res2 = client.get("/api/commitments/UNKNOWNXYZ/summary")
    assert res2.status_code == 404
    assert "not tracked" in res2.json()["detail"]


def test_case_and_whitespace_insensitivity():
    res = client.get("/api/commitments/ reliance ")
    assert res.status_code == 200
    assert res.json()["symbol"] == "RELIANCE"
    assert res.json()["status"] == "OK"

    res2 = client.get("/api/commitments/ reliance /summary")
    assert res2.status_code == 200
    assert res2.json()["symbol"] == "RELIANCE"
