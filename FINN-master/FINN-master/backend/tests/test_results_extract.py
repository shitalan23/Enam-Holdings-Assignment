"""Tests for local PDF extraction using actual RELIANCE quarterly results filing."""
from pathlib import Path
import pytest
from finn.results_extract import (
    extract_quarterly_results_from_pdf,
    save_quarterly_results_to_db,
)
from finn.results_math import calculate_metric_change

PDF_PATH = Path("data/documents/RELIANCE/reliance_q2_fy27_results.pdf")
OFFICIAL_URL = "https://nsearchives.nseindia.com/corporate/kavinavora_30102026193935_SE_30102026_Results.pdf"


@pytest.mark.skipif(not PDF_PATH.exists(), reason="Reliance results PDF not downloaded")
class TestRelianceResultsExtraction:
    def test_extract_consolidated_and_standalone(self):
        results = extract_quarterly_results_from_pdf(
            pdf_path=PDF_PATH,
            symbol="RELIANCE",
            source_url=OFFICIAL_URL,
            filing_id="70d0cbf0b448b8ca",
        )
        assert len(results) == 2

        # 1. Consolidated
        consol = next(r for r in results if r["nature"] == "consolidated")
        assert consol["page_num"] == 10
        assert consol["unit"] == "crore"
        assert consol["table_name"] == "UNAUDITED CONSOLIDATED FINANCIAL RESULTS"

        curr = consol["current"]
        # Revenue distinction: Gross vs Net Operations
        assert curr["gross_revenue"] == 362268.0
        assert curr["gst_recovered"] == 29407.0
        assert curr["revenue"] == 332861.0
        assert curr["gross_revenue"] - curr["gst_recovered"] == curr["revenue"]

        assert curr["pbt"] == 38613.0
        assert curr["finance_costs"] == 8481.0
        assert curr["depreciation"] == 15315.0
        assert curr["other_income"] == 5793.0

        # PAT reconciliation: Before associates vs with associates vs owners
        assert curr["pat"] == 29250.0  # Before associates
        assert curr["share_of_associates"] == 300.0  # Share of associates/JVs
        assert curr["pat_with_associates"] == 29550.0  # Reported headline IR PAT (29,250 + 300)
        assert curr["pat_attributable_to_owners"] == 25548.0  # Attributable to owners

        # EBITDA reconciliation: Derived Operating EBITDA vs Reported EBITDA
        # Derived Operating EBITDA = 38613 + 8481 + 15315 - 5793 = 56616
        assert curr["derived_ebitda"] == 56616.0
        assert curr["reported_ebitda"] == 62409.0  # Reported in Investor Presentation
        assert curr["derived_ebitda"] + curr["other_income"] == curr["reported_ebitda"]
        assert "Company-Reported EBITDA (₹62,409 Cr)" in curr["ebitda_reconciliation_note"]
        assert "Other Income (₹5,793 Cr)" in curr["ebitda_reconciliation_note"]

        # QoQ & YoY comparisons for Consolidated
        prev = consol["previous_quarter"]
        assert prev["gross_revenue"] == 340257.0
        assert prev["revenue"] == 311850.0
        assert prev["pbt"] == 30630.0
        assert prev["pat"] == 23001.0
        assert prev["pat_with_associates"] == 23196.0
        assert prev["pat_attributable_to_owners"] == 20946.0
        assert prev["derived_ebitda"] == 47517.0
        assert prev["reported_ebitda"] == 54067.0

        yoy = consol["yoy_quarter"]
        assert yoy["gross_revenue"] == 283548.0
        assert yoy["revenue"] == 258898.0
        assert yoy["pbt"] == 29124.0
        assert yoy["pat"] == 22146.0
        assert yoy["pat_with_associates"] == 22092.0
        assert yoy["pat_attributable_to_owners"] == 18165.0
        assert yoy["derived_ebitda"] == 45885.0
        assert yoy["reported_ebitda"] == 50367.0

        # Calculations
        rev_qoq = calculate_metric_change(curr["revenue"], prev["revenue"])
        assert rev_qoq.pct_change == 6.74
        assert rev_qoq.label == "+6.74%"

        rev_yoy = calculate_metric_change(curr["revenue"], yoy["revenue"])
        assert rev_yoy.pct_change == 28.57
        assert rev_yoy.label == "+28.57%"

        # Gross revenue comparisons
        gross_qoq = calculate_metric_change(curr["gross_revenue"], prev["gross_revenue"])
        assert gross_qoq.pct_change == 6.47
        gross_yoy = calculate_metric_change(curr["gross_revenue"], yoy["gross_revenue"])
        assert gross_yoy.pct_change == 27.76

        ebitda_qoq = calculate_metric_change(curr["derived_ebitda"], prev["derived_ebitda"])
        assert ebitda_qoq.pct_change == 19.15
        assert ebitda_qoq.label == "+19.15%"

        ebitda_yoy = calculate_metric_change(curr["derived_ebitda"], yoy["derived_ebitda"])
        assert ebitda_yoy.pct_change == 23.39
        assert ebitda_yoy.label == "+23.39%"

        # Reported EBITDA comparisons
        rep_ebitda_qoq = calculate_metric_change(curr["reported_ebitda"], prev["reported_ebitda"])
        assert rep_ebitda_qoq.pct_change == 15.43
        rep_ebitda_yoy = calculate_metric_change(curr["reported_ebitda"], yoy["reported_ebitda"])
        assert rep_ebitda_yoy.pct_change == 23.91

        # PAT with associates comparisons (Headline IR PAT)
        pat_assoc_qoq = calculate_metric_change(curr["pat_with_associates"], prev["pat_with_associates"])
        assert pat_assoc_qoq.pct_change == 27.39

        pat_assoc_yoy = calculate_metric_change(curr["pat_with_associates"], yoy["pat_with_associates"])
        assert pat_assoc_yoy.pct_change == 33.76

        # PAT attributable to owners
        owners_qoq = calculate_metric_change(curr["pat_attributable_to_owners"], prev["pat_attributable_to_owners"])
        assert owners_qoq.pct_change == 21.97
        owners_yoy = calculate_metric_change(curr["pat_attributable_to_owners"], yoy["pat_attributable_to_owners"])
        assert owners_yoy.pct_change == 40.64

        # 2. Standalone
        stnd = next(r for r in results if r["nature"] == "standalone")
        assert stnd["page_num"] == 22
        assert stnd["unit"] == "crore"
        assert stnd["table_name"] == "UNAUDITED STANDALONE FINANCIAL RESULTS"

        s_curr = stnd["current"]
        assert s_curr["revenue"] == 174668.0
        assert s_curr["pbt"] == 20339.0
        assert s_curr["pat"] == 15354.0
        assert s_curr["finance_costs"] == 1953.0
        assert s_curr["depreciation"] == 3994.0
        assert s_curr["other_income"] == 3899.0
        # Derived EBITDA = 20339 + 1953 + 3994 - 3899 = 22387
        assert s_curr["derived_ebitda"] == 22387.0

        s_prev = stnd["previous_quarter"]
        assert s_prev["revenue"] == 166013.0
        assert s_prev["pbt"] == 17600.0
        assert s_prev["pat"] == 13272.0
        assert s_prev["derived_ebitda"] == 19526.0

        s_yoy = stnd["yoy_quarter"]
        assert s_yoy["revenue"] == 130610.0
        assert s_yoy["pbt"] == 11592.0
        assert s_yoy["pat"] == 9129.0
        assert s_yoy["derived_ebitda"] == 14389.0

        s_rev_qoq = calculate_metric_change(s_curr["revenue"], s_prev["revenue"])
        assert s_rev_qoq.pct_change == 5.21
        assert s_rev_qoq.label == "+5.21%"

        s_rev_yoy = calculate_metric_change(s_curr["revenue"], s_yoy["revenue"])
        assert s_rev_yoy.pct_change == 33.73
        assert s_rev_yoy.label == "+33.73%"

    def test_database_persistence_in_test_db(self):
        from finn.db import session

        results = extract_quarterly_results_from_pdf(
            pdf_path=PDF_PATH,
            symbol="RELIANCE",
            source_url=OFFICIAL_URL,
            filing_id="70d0cbf0b448b8ca",
        )
        save_quarterly_results_to_db(results, period_end_date="2026-09-30")

        with session() as con:
            rows = con.execute("SELECT * FROM quarterly_results WHERE symbol='RELIANCE'").fetchall()
            assert len(rows) == 2
            natures = {r["nature"] for r in rows}
            assert natures == {"consolidated", "standalone"}

            c_row = next(r for r in rows if r["nature"] == "consolidated")
            assert c_row["gross_revenue"] == 362268.0
            assert c_row["gst_recovered"] == 29407.0
            assert c_row["revenue"] == 332861.0
            assert c_row["pbt"] == 38613.0
            assert c_row["pat"] == 29250.0
            assert c_row["share_of_associates"] == 300.0
            assert c_row["pat_with_associates"] == 29550.0
            assert c_row["pat_attributable_to_owners"] == 25548.0
            assert c_row["derived_ebitda"] == 56616.0
            assert c_row["reported_ebitda"] == 62409.0
            assert "Company-Reported EBITDA (₹62,409 Cr)" in c_row["ebitda_reconciliation_note"]
            assert c_row["source_page"] == 10
            assert c_row["source_doc_url"] == OFFICIAL_URL
