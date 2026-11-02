"""Comprehensive unit tests for RELIANCE primary source extraction & research dossier assembly.

Executes layout parsing directly against local primary PDF documents in data/documents/RELIANCE/:
- reliance_q2_fy27_results.pdf
- reliance_q2_fy27_investor_presentation.pdf
"""
import json
import sqlite3
import pytest
from pathlib import Path

from finn.config import ROOT
from finn.db import SCHEMA, migrate
from finn.research_extract import (
    build_reliance_research_dossier,
    extract_reliance_balance_sheet,
    extract_reliance_cash_flow,
    extract_reliance_presentation,
    extract_reliance_segments,
    save_research_report,
)

DOCS_DIR = ROOT / "data" / "documents" / "RELIANCE"
RESULTS_PDF = DOCS_DIR / "reliance_q2_fy27_results.pdf"
PRESENTATION_PDF = DOCS_DIR / "reliance_q2_fy27_investor_presentation.pdf"


@pytest.fixture(scope="module")
def check_docs_exist():
    assert RESULTS_PDF.exists(), f"Results PDF missing at {RESULTS_PDF}"
    assert PRESENTATION_PDF.exists(), f"Presentation PDF missing at {PRESENTATION_PDF}"


def test_balance_sheet_extraction(check_docs_exist):
    bs = extract_reliance_balance_sheet(RESULTS_PDF)

    # Statutory Assets & Liabilities (Page 12)
    assert bs["total_assets"] == 2275033.0
    assert bs["total_equity"] == 1132648.0
    assert bs["non_current_borrowings"] == 289744.0
    assert bs["current_borrowings"] == 95208.0
    assert bs["gross_debt"] == 384952.0  # 289,744 + 95,208
    assert bs["cash_and_equivalents"] == 181723.0
    assert bs["current_investments"] == 78591.0
    assert bs["inventories"] == 185480.0
    assert bs["trade_receivables"] == 59564.0
    assert bs["total_current_assets"] == 635305.0
    assert bs["total_current_liabilities"] == 559764.0

    # Statutory Ratios (Page 11)
    assert bs["debt_equity_ratio"] == 0.41
    assert bs["current_ratio"] == 1.13
    assert bs["dscr"] == 3.52
    assert bs["iscr"] == 5.55
    assert bs["net_worth"] == 906204.0


def test_cash_flow_extraction(check_docs_exist):
    cf = extract_reliance_cash_flow(RESULTS_PDF)

    # Half-year ended 30th Sept 2026 (Page 13)
    assert cf["pbt_as_per_pnl"] == 69243.0
    assert cf["operating_profit_before_wc"] == 104203.0
    assert cf["cash_generated_from_operations"] == 99165.0
    assert cf["cfo"] == 93055.0  # Net Cash Flow from Operating Activities
    assert cf["capex"] == -52813.0  # Expenditure on Property, Plant and Equipment
    assert cf["cf_investing"] == -52951.0 or cf["cf_investing"] == -31202.0
    assert cf["interest_paid"] == -21875.0
    assert cf["dividends_paid"] == -8120.0
    assert cf["closing_cash"] == 181723.0
    assert cf["net_cash_increase"] == 35746.0


def test_segment_information_extraction(check_docs_exist):
    seg = extract_reliance_segments(RESULTS_PDF)

    # Segment Revenue (Gross Value of Sales and Services)
    rev = seg["segment_revenue"]
    assert rev["Oil to Chemicals (O2C)"] == 231601.0
    assert rev["Retail"] == 91717.0
    assert rev["Digital Services (Jio)"] == 48486.0
    assert rev["Oil and Gas"] == 6020.0
    assert rev["Others"] == 25317.0
    assert rev["Less: Inter Segment Transfers"] == -40873.0

    # Segment EBITDA
    ebitda = seg["segment_ebitda"]
    assert ebitda["Oil to Chemicals (O2C)"] == 25203.0
    assert ebitda["Retail"] == 6120.0
    assert ebitda["Digital Services (Jio)"] == 22223.0
    assert ebitda["Oil and Gas"] == 4901.0
    assert ebitda["Total Segment EBITDA"] == 61224.0

    # Segment EBIT
    ebit = seg["segment_ebit"]
    assert ebit["Oil to Chemicals (O2C)"] == 22347.0
    assert ebit["Retail"] == 4300.0
    assert ebit["Digital Services (Jio)"] == 14249.0
    assert ebit["Oil and Gas"] == 3941.0
    assert ebit["Total Segment EBIT"] == 46291.0


def test_presentation_extraction(check_docs_exist):
    pres = extract_reliance_presentation(PRESENTATION_PDF)

    # Slide 11 & 12 disclosures
    net_debt = pres["net_debt_disclosure"]
    assert net_debt["net_debt_sep26"] == 117140.0
    assert net_debt["net_debt_jun26"] == 122914.0
    assert net_debt["net_debt_to_ebitda_sep26"] == 0.47
    assert net_debt["quarterly_capex"] == 38153.0

    # Jio KPIs (Slides 14-15)
    jio = pres["jio_metrics"]
    assert jio["total_subscribers_mn"] == 542.4
    assert jio["five_g_subscribers_mn"] == 300.0
    assert jio["arpu_rs_per_month"] == 218.8
    assert jio["jio_ipo_proceeds_cr"] == 30188.0

    # Retail KPIs (Slides 21-24)
    retail = pres["retail_metrics"]
    assert retail["gross_revenue_cr"] == 91716.0
    assert retail["stores_count"] == 19947
    assert retail["stores_opened_q2"] == 303
    assert retail["registered_customers_mn"] == 400.0

    # Guidance statements
    guidance = pres["guidance_statements"]
    assert len(guidance) >= 3


def test_assembled_dossier_contains_all_eight_dimensions(check_docs_exist):
    dossier = build_reliance_research_dossier()

    assert dossier["symbol"] == "RELIANCE"
    assert dossier["as_of_period"] == "Q2 FY27"
    assert dossier["as_of_date"] == "2026-09-30"

    # 1. Business Snapshot
    bs = dossier["business_snapshot"]
    assert len(bs["segments"]) >= 4
    assert any("O2C" in s["name"] for s in bs["segments"])
    assert any("Retail" in s["name"] for s in bs["segments"])
    assert any("Jio" in s["name"] for s in bs["segments"])
    assert len(bs["core_platforms"]) == 4

    # 2. Financial Snapshot
    fs = dossier["financial_snapshot"]
    assert fs["revenue_from_operations_cr"] == 332861.0
    assert fs["reported_ebitda_cr"] == 62409.0
    assert fs["derived_operating_ebitda_cr"] == 56616.0
    assert fs["headline_pat_cr"] == 29550.0
    assert "Statutory operations revenue is ₹332,861 Cr" in fs["reconciliation_summary"]

    # 3. Trajectory
    traj = dossier["trajectory"]
    assert len(traj["growing_segments"]) >= 2
    assert len(traj["compressing_segments"]) >= 2
    o2c_grow = next(s for s in traj["growing_segments"] if "O2C" in s["segment"])
    assert o2c_grow["yoy_ebitda_growth_pct"] == 67.9

    # 4. Balance Sheet
    bal = dossier["balance_sheet"]
    assert bal["gross_debt_cr"] == 384952.0
    assert bal["cash_and_equivalents_cr"] == 181723.0
    assert bal["management_reported_net_debt_cr"] == 117140.0
    assert bal["management_net_debt_to_ebitda"] == 0.47
    assert bal["debt_equity_ratio"] == 0.41

    # 5. Cash Quality
    cq = dossier["cash_quality"]
    assert cq["cfo_cr"] == 93055.0
    assert cq["capex_h1_cr"] == 52813.0
    assert cq["fcf_h1_cr"] == 40242.0  # 93,055 - 52,813
    assert cq["cash_conversion_status"] == "STRONG_CONVERSION"
    assert cq["fcf_status"] == "POSITIVE_FCF"

    # 6. Narrative vs Numbers
    nvn = dossier["narrative_vs_numbers"]
    assert len(nvn) >= 3
    assert any(item["verdict"] == "Divergence" for item in nvn)
    assert any(item["verdict"] == "Agreement" for item in nvn)

    # 7. Guidance
    guid = dossier["guidance"]
    assert len(guid) >= 3
    assert any("Capex" in item["metric_or_area"] for item in guid)

    # 8. Bull vs Bear
    bvb = dossier["bull_vs_bear"]
    assert len(bvb["bull_case"]) >= 3
    assert len(bvb["bear_case"]) >= 3

    # Citations
    cits = dossier["citations"]
    assert len(cits) >= 9
    for cit in cits:
        assert cit["id"]
        assert cit["doc_title"]
        assert cit["doc_type"] in ["results_pdf", "investor_presentation", "annual_report", "concall_transcript"]
        assert cit["page"] > 0
        assert cit["section"]
        assert cit["claim"]
        assert cit["url"].startswith("https://")


def test_save_and_retrieve_from_database(check_docs_exist):
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    migrate(con)

    # Ensure companies table has RELIANCE
    con.execute("INSERT OR IGNORE INTO companies(symbol, name) VALUES ('RELIANCE', 'Reliance Industries Limited')")

    dossier = build_reliance_research_dossier()
    save_research_report(con, dossier)

    row = con.execute("SELECT * FROM company_research WHERE symbol='RELIANCE'").fetchone()
    assert row is not None
    assert row["as_of_period"] == "Q2 FY27"
    assert row["as_of_date"] == "2026-09-30"

    bs_loaded = json.loads(row["business_snapshot"])
    assert len(bs_loaded["segments"]) >= 4

    fs_loaded = json.loads(row["financial_snapshot"])
    assert fs_loaded["headline_pat_cr"] == 29550.0

    cq_loaded = json.loads(row["cash_quality"])
    assert cq_loaded["fcf_h1_cr"] == 40242.0

    cits_loaded = json.loads(row["citations"])
    assert len(cits_loaded) >= 9
