"""Unit tests for RELIANCE commitments extraction engine (backend/finn/commitments_extract.py).

Validates extraction directly against official primary sources:
1. Reliance Q2 FY27 Unaudited Financial Results (NSE filing 30-Oct-2026)
2. Reliance Q2 FY27 Investor Presentation (NSE filing 30-Oct-2026)

Tests cover:
- Discrimination between genuine commitments, strategic intentions, and operational milestones.
- Accurate extraction of target values, units, periods, verbatim statements, and official URLs.
- Multi-quarter audit checkpoints spanning 4 quarters.
- Safety rule: expired target without primary-source failure evidence is UNVERIFIABLE, never MISSED.
- Track record summary & delivery score computation displaying evaluated count.
- Idempotent database persistence.
"""
import sqlite3
import pytest
from finn.commitments_extract import (
    extract_reliance_commitments,
    save_commitments,
    RESULTS_PDF_TITLE,
    PRESENTATION_PDF_TITLE,
    RESULTS_NSE_URL,
    PRESENTATION_NSE_URL,
)
from finn.commitments_eval import calculate_track_record_summary
from finn.db import SCHEMA


@pytest.fixture
def test_db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.execute(
        "INSERT INTO companies (symbol, name, sector, size_bucket, weight, in_portfolio) "
        "VALUES ('RELIANCE', 'Reliance Industries Ltd', 'Energy / Conglomerate', 'Large', 0.12, 1)"
    )
    con.commit()
    yield con
    con.close()


class TestRelianceCommitmentsExtraction:
    def test_extract_items_structure(self):
        commitments = extract_reliance_commitments(as_of_period="Q2 FY27")
        assert len(commitments) >= 7

        for c in commitments:
            assert c.symbol == "RELIANCE"
            assert len(c.statement) > 20
            assert c.source_doc_title in (RESULTS_PDF_TITLE, PRESENTATION_PDF_TITLE, "Reliance Q2 FY26 Investor Presentation")
            assert c.source_url.startswith("https://")
            assert c.target_period != ""
            assert c.status in ("ACHIEVED", "PARTIALLY_ACHIEVED", "IN_PROGRESS", "DELAYED", "MISSED", "UNVERIFIABLE", "NEEDS_REVIEW")

    def test_genuine_vs_non_promissory_classification(self):
        commitments = extract_reliance_commitments(as_of_period="Q2 FY27")
        by_title = {c.title: c for c in commitments}

        # 1. Forward guidance contributes to score
        capex = by_title["Quarterly Capital Expenditure Run-Rate Guidance"]
        assert capex.commitment_type == "FORWARD_GUIDANCE"
        assert capex.contributes_to_score is True

        # 2. Explicit commitment contributes to score
        ipo = by_title["Jio Platforms Public Listing & De-leveraging IPO"]
        assert ipo.commitment_type == "EXPLICIT_COMMITMENT"
        assert ipo.contributes_to_score is True

        # 3. Strategic intention does NOT contribute to score
        tech = by_title["Strategic Exploration: Global Tech & Deep Tech Solutions"]
        assert tech.commitment_type == "STRATEGIC_INTENTION"
        assert tech.contributes_to_score is False

        # 4. Operational milestone does NOT contribute to score
        milestone = by_title["Operational Milestone: 300 Million 5G Users Milestone"]
        assert milestone.commitment_type == "OPERATIONAL_MILESTONE"
        assert milestone.contributes_to_score is False

    def test_expired_target_without_evidence_is_unverifiable(self):
        commitments = extract_reliance_commitments(as_of_period="Q2 FY27")
        by_title = {c.title: c for c in commitments}

        debottlenecking = by_title["Prior Cycle Jamnagar Specialty Chemicals Debottlenecking Target"]
        assert debottlenecking.target_period == "Q1 FY27"
        # Q1 FY27 is expired relative to as_of Q2 FY27, but no disclosure exists in subsequent filings
        assert debottlenecking.status == "UNVERIFIABLE"
        assert debottlenecking.status != "MISSED"
        assert "never marked MISSED without negative evidence" in debottlenecking.evaluation_reasoning

    def test_chronology_audit_unverifiable_without_advance_promise(self):
        commitments = extract_reliance_commitments(as_of_period="Q2 FY27")
        by_title = {c.title: c for c in commitments}

        # Capex: Target 38,000 Cr, Actual 38,153 Cr (+0.4%), but promise is from same Q2 presentation -> UNVERIFIABLE
        capex = by_title["Quarterly Capital Expenditure Run-Rate Guidance"]
        assert capex.status == "UNVERIFIABLE"
        assert capex.target_value == 38000.0
        assert capex.actual_value == 38153.0
        assert "Slide 12" in capex.actual_source_page_or_slide
        assert "chronology" in capex.evaluation_reasoning.lower()

        # JPL IPO: Raised ₹30,188 Cr, Note 3 of Financial Results, but Slide 14 is post-outcome -> UNVERIFIABLE
        ipo = by_title["Jio Platforms Public Listing & De-leveraging IPO"]
        assert ipo.status == "UNVERIFIABLE"
        assert ipo.target_value == 30000.0
        assert ipo.actual_value == 30188.0
        assert "Note 3" in ipo.actual_source_page_or_slide
        assert "28th October, 2026" in ipo.actual_performance

        # Leverage Ceiling: Net Debt / EBITDA 0.47x vs <1.0x ceiling -> UNVERIFIABLE without advance document
        leverage = by_title["Balance Sheet Leverage Ceiling (< 1.0x Net Debt/EBITDA)"]
        assert leverage.status == "UNVERIFIABLE"
        assert leverage.target_value == 1.0
        assert leverage.actual_value == 0.47
        assert leverage.actual_source_page_or_slide == "Slide 12"

    def test_multi_quarter_audit_checkpoints_presence(self):
        commitments = extract_reliance_commitments(as_of_period="Q2 FY27")
        by_title = {c.title: c for c in commitments}

        # Capex audited checkpoints
        capex = by_title["Quarterly Capital Expenditure Run-Rate Guidance"]
        assert len(capex.quarter_evaluations) == 4
        quarters = [q.quarter for q in capex.quarter_evaluations]
        assert quarters == ["H1 FY26", "Q1 FY27", "Q2 FY27", "H1 FY27"]
        assert capex.quarter_evaluations[2].disclosed_value == 38153.0

        # Leverage audited checkpoints
        leverage = by_title["Balance Sheet Leverage Ceiling (< 1.0x Net Debt/EBITDA)"]
        assert len(leverage.quarter_evaluations) == 3
        assert leverage.quarter_evaluations[-1].disclosed_value == 0.47

        # RJIL 5-quarter continuous pacing
        rjil = by_title["Operational Progression: RJIL 5-Quarter Revenue & EBITDA Pacing"]
        assert len(rjil.quarter_evaluations) == 5
        rjil_quarters = [q.quarter for q in rjil.quarter_evaluations]
        assert rjil_quarters == ["Q2 FY26", "Q3 FY26", "Q4 FY26", "Q1 FY27", "Q2 FY27"]
        assert rjil.quarter_evaluations[-1].disclosed_value == 20505.0

    def test_track_record_summary_for_reliance(self):
        commitments = extract_reliance_commitments(as_of_period="Q2 FY27")
        summary = calculate_track_record_summary(commitments)

        assert summary.total_commitments == len(commitments)
        assert summary.strategic_intentions_count == 1
        assert summary.operational_milestones_count == 2
        assert summary.excluded_count == 3
        assert summary.eligible_count == 6  # 6 genuine forward guidance / explicit commitments

        # Mathematical Invariants
        assert summary.total_commitments == summary.eligible_count + summary.excluded_count
        assert summary.eligible_count == (
            summary.eligible_evaluated_count +
            summary.eligible_in_progress_count +
            summary.eligible_unverifiable_count +
            summary.eligible_needs_review_count
        )
        assert summary.eligible_evaluated_count == (
            summary.eligible_achieved_count +
            summary.eligible_partially_achieved_count +
            summary.eligible_delayed_count +
            summary.eligible_missed_count
        )

        # Evaluated eligible count: With advance proof missing, Capex, IPO, Leverage are UNVERIFIABLE -> 0 evaluated
        assert summary.eligible_evaluated_count == 0
        assert summary.evaluated_count == 0
        assert summary.eligible_achieved_count == 0
        assert summary.achieved_count == 0

        # Overall Status Counts
        assert summary.total_achieved_count == 2  # 2 completed operational milestones
        assert summary.total_in_progress_count == 3  # 2 eligible + 1 strategic intention
        assert summary.eligible_in_progress_count == 2
        assert summary.eligible_unverifiable_count == 4
        assert summary.total_unverifiable_count == 4

        # Delivery Score is None when eligible evaluated count is 0
        assert summary.delivery_score is None
        assert "Insufficient evaluated evidence" in summary.score_label
        assert "No eligible commitments have concluded evaluation yet" in summary.stat_caveat

    def test_save_commitments_idempotency(self, test_db):
        commitments = extract_reliance_commitments(as_of_period="Q2 FY27")
        count1 = save_commitments(test_db, commitments)
        assert count1 == len(commitments)

        # Check DB row count
        row_cnt = test_db.execute("SELECT COUNT(*) FROM commitments WHERE symbol='RELIANCE'").fetchone()[0]
        assert row_cnt == len(commitments)

        # Re-save must be idempotent (no duplicate key error)
        count2 = save_commitments(test_db, commitments)
        assert count2 == len(commitments)
        row_cnt_after = test_db.execute("SELECT COUNT(*) FROM commitments WHERE symbol='RELIANCE'").fetchone()[0]
        assert row_cnt_after == len(commitments)
