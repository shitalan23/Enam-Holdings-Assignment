"""Unit tests for deterministic commitment evaluation logic (backend/finn/commitments_eval.py).

Verifies strict ENAM financial intelligence criteria:
1. Distinguishes genuine commitments from strategic intentions and milestones.
2. Metric-specific evaluation rules with tolerances.
3. Unambiguous flagging of disputed/ambiguous items as NEEDS_REVIEW.
4. Missing actual data is NEVER marked MISSED (returns UNVERIFIABLE or IN_PROGRESS).
5. Safe handling of nullable actual values and citations.
6. Honest delivery score calculation: evaluated count displayed, zero fabrication.
7. Multi-quarter audit checkpoints.
"""
import pytest
from finn.commitments_eval import (
    CommitmentItem,
    QuarterEvaluation,
    TrackRecordSummary,
    parse_period_rank,
    compare_periods,
    is_genuine_commitment,
    evaluate_commitment_status,
    calculate_track_record_summary,
)


class TestPeriodComparison:
    def test_quarter_ranks(self):
        assert parse_period_rank("Q1 FY26") < parse_period_rank("Q2 FY26")
        assert parse_period_rank("Q2 FY26") < parse_period_rank("Q3 FY26")
        assert parse_period_rank("Q4 FY26") < parse_period_rank("Q1 FY27")
        assert parse_period_rank("Q2 FY27") == 2027.2

    def test_fy_ranks(self):
        assert parse_period_rank("FY26") == 2026.4
        assert parse_period_rank("FY27") == 2027.4
        assert parse_period_rank("FY28 - FY29") == 2029.4

    def test_compare_periods(self):
        assert compare_periods("Q1 FY26", "Q2 FY27") == -1
        assert compare_periods("Q2 FY27", "Q2 FY27") == 0
        assert compare_periods("FY28", "Q2 FY27") == 1


class TestCommitmentClassification:
    def test_genuine_commitments(self):
        assert is_genuine_commitment("EXPLICIT_COMMITMENT") is True
        assert is_genuine_commitment("FORWARD_GUIDANCE") is True

    def test_non_promissory_items(self):
        assert is_genuine_commitment("STRATEGIC_INTENTION") is False
        assert is_genuine_commitment("OPERATIONAL_MILESTONE") is False

    def test_strategic_intention_evaluation(self):
        res = evaluate_commitment_status(
            commitment_type="STRATEGIC_INTENTION",
            target_period="FY28",
            as_of_period="Q2 FY27",
            metric_type="BINARY_MILESTONE",
        )
        assert res.contributes_to_score is False
        assert res.status == "IN_PROGRESS"
        assert "Excluded from quantitative delivery score" in res.evaluation_reasoning

    def test_operational_milestone_evaluation(self):
        res = evaluate_commitment_status(
            commitment_type="OPERATIONAL_MILESTONE",
            target_period="Q2 FY27",
            as_of_period="Q2 FY27",
            metric_type="BINARY_MILESTONE",
            is_binary_completed=True,
        )
        assert res.contributes_to_score is False
        assert res.status == "ACHIEVED"
        assert "Excluded from quantitative delivery score denominator" in res.evaluation_reasoning


class TestBinaryMilestones:
    def test_achieved_on_time(self):
        res = evaluate_commitment_status(
            commitment_type="EXPLICIT_COMMITMENT",
            target_period="Q2 FY27",
            as_of_period="Q2 FY27",
            metric_type="BINARY_MILESTONE",
            is_binary_completed=True,
        )
        assert res.status == "ACHIEVED"
        assert res.contributes_to_score is True

    def test_delayed_when_timeline_extended(self):
        res = evaluate_commitment_status(
            commitment_type="EXPLICIT_COMMITMENT",
            target_period="Q1 FY27",
            as_of_period="Q2 FY27",
            metric_type="BINARY_MILESTONE",
            is_binary_completed=False,
            is_timeline_extended=True,
        )
        assert res.status == "DELAYED"
        assert "officially extended" in res.evaluation_reasoning

    def test_expired_deadline_without_evidence_is_unverifiable_not_missed(self):
        # Crucial requirement: An expired commitment is never marked MISSED solely because its deadline passed.
        res = evaluate_commitment_status(
            commitment_type="EXPLICIT_COMMITMENT",
            target_period="Q1 FY27",
            as_of_period="Q2 FY27",
            metric_type="BINARY_MILESTONE",
            is_binary_completed=False,
            is_timeline_extended=False,
            has_evidence_of_non_delivery=False,
        )
        assert res.status == "UNVERIFIABLE"
        assert "cannot be marked MISSED solely due to an expired deadline" in res.evaluation_reasoning

    def test_missed_requires_primary_source_evidence_of_non_delivery(self):
        res = evaluate_commitment_status(
            commitment_type="EXPLICIT_COMMITMENT",
            target_period="Q1 FY27",
            as_of_period="Q2 FY27",
            metric_type="BINARY_MILESTONE",
            is_binary_completed=False,
            is_timeline_extended=False,
            has_evidence_of_non_delivery=True,
            failure_evidence="Primary filing confirms project tender cancelled and targets abandoned.",
        )
        assert res.status == "MISSED"
        assert "project tender cancelled" in res.evaluation_reasoning

    def test_in_progress_when_future(self):
        res = evaluate_commitment_status(
            commitment_type="EXPLICIT_COMMITMENT",
            target_period="FY28",
            as_of_period="Q2 FY27",
            metric_type="BINARY_MILESTONE",
            is_binary_completed=False,
        )
        assert res.status == "IN_PROGRESS"


class TestNumericTargetsWithTolerance:
    def test_achieved_exact(self):
        res = evaluate_commitment_status(
            commitment_type="EXPLICIT_COMMITMENT",
            target_period="Q2 FY27",
            as_of_period="Q2 FY27",
            metric_type="NUMERIC_TARGET",
            target_value=100.0,
            actual_value=100.0,
        )
        assert res.status == "ACHIEVED"

    def test_achieved_within_tolerance(self):
        # Target 100 with 5% tolerance -> threshold is 95. Actual 96 meets target.
        res = evaluate_commitment_status(
            commitment_type="EXPLICIT_COMMITMENT",
            target_period="Q2 FY27",
            as_of_period="Q2 FY27",
            metric_type="NUMERIC_TARGET",
            target_value=100.0,
            actual_value=96.0,
            target_tolerance_pct=5.0,
        )
        assert res.status == "ACHIEVED"
        assert "within 5.0% tolerance" in res.evaluation_reasoning

    def test_partially_achieved_metric_specific(self):
        # Target 100, actual 75 (75% delivered, above 70% threshold)
        res = evaluate_commitment_status(
            commitment_type="FORWARD_GUIDANCE",
            target_period="Q1 FY27",
            as_of_period="Q2 FY27",
            metric_type="NUMERIC_TARGET",
            target_value=100.0,
            actual_value=75.0,
            partial_threshold_pct=70.0,
        )
        assert res.status == "PARTIALLY_ACHIEVED"

    def test_missed_below_partial_threshold(self):
        # Target 100, actual 50 (below 70% partial threshold)
        res = evaluate_commitment_status(
            commitment_type="EXPLICIT_COMMITMENT",
            target_period="Q1 FY27",
            as_of_period="Q2 FY27",
            metric_type="NUMERIC_TARGET",
            target_value=100.0,
            actual_value=50.0,
            partial_threshold_pct=70.0,
        )
        assert res.status == "MISSED"


class TestNumericCeilingsAndBudgets:
    def test_ceiling_under_budget_achieved(self):
        # Net debt ceiling 40,000 Cr, actual 35,000 Cr
        res = evaluate_commitment_status(
            commitment_type="FORWARD_GUIDANCE",
            target_period="Q2 FY27",
            as_of_period="Q2 FY27",
            metric_type="NUMERIC_CEILING",
            target_value=40000.0,
            target_unit="crore",
            actual_value=35000.0,
            actual_unit="crore",
        )
        assert res.status == "ACHIEVED"
        assert "remained below ceiling target" in res.evaluation_reasoning

    def test_ceiling_partial_overrun(self):
        # Ceiling 40,000 Cr, actual 44,000 Cr (10% overrun, <= 20% partial cap)
        res = evaluate_commitment_status(
            commitment_type="FORWARD_GUIDANCE",
            target_period="Q1 FY27",
            as_of_period="Q2 FY27",
            metric_type="NUMERIC_CEILING",
            target_value=40000.0,
            target_unit="crore",
            actual_value=44000.0,
            actual_unit="crore",
        )
        assert res.status == "PARTIALLY_ACHIEVED"
        assert "within allowable 20% overrun" in res.evaluation_reasoning

    def test_ceiling_excessive_overrun_missed(self):
        # Ceiling 40,000 Cr, actual 55,000 Cr (>20% overrun), expired
        res = evaluate_commitment_status(
            commitment_type="FORWARD_GUIDANCE",
            target_period="Q1 FY27",
            as_of_period="Q2 FY27",
            metric_type="NUMERIC_CEILING",
            target_value=40000.0,
            target_unit="crore",
            actual_value=55000.0,
            actual_unit="crore",
        )
        assert res.status == "MISSED"


class TestRangeTargets:
    def test_within_range_achieved(self):
        # Capex run rate ₹35,000 - ₹40,000 Cr, actual 38,000 Cr
        res = evaluate_commitment_status(
            commitment_type="FORWARD_GUIDANCE",
            target_period="Q2 FY27",
            as_of_period="Q2 FY27",
            metric_type="RANGE_TARGET",
            range_min=35000.0,
            range_max=40000.0,
            actual_value=38000.0,
            target_unit="crore",
            actual_unit="crore",
        )
        assert res.status == "ACHIEVED"

    def test_partially_within_range(self):
        # Capex run rate ₹35,000 - ₹40,000 Cr, actual 42,000 Cr
        res = evaluate_commitment_status(
            commitment_type="FORWARD_GUIDANCE",
            target_period="Q1 FY27",
            as_of_period="Q2 FY27",
            metric_type="RANGE_TARGET",
            range_min=35000.0,
            range_max=40000.0,
            actual_value=42000.0,
            target_unit="crore",
            actual_unit="crore",
        )
        assert res.status == "PARTIALLY_ACHIEVED"


class TestMissingActualDataSafety:
    def test_missing_actual_is_never_missed_when_expired(self):
        # Target period has passed, but actual figure was never reported
        res = evaluate_commitment_status(
            commitment_type="EXPLICIT_COMMITMENT",
            target_period="Q1 FY27",
            as_of_period="Q2 FY27",
            metric_type="NUMERIC_TARGET",
            target_value=50.0,
            actual_value=None,
            actual_performance=None,
        )
        # CRUCIAL RULE: Must NOT be MISSED. Must be UNVERIFIABLE!
        assert res.status != "MISSED"
        assert res.status == "UNVERIFIABLE"
        assert "zero-fabrication rules" in res.evaluation_reasoning

    def test_missing_actual_is_in_progress_when_active(self):
        # Target period is future
        res = evaluate_commitment_status(
            commitment_type="EXPLICIT_COMMITMENT",
            target_period="FY28",
            as_of_period="Q2 FY27",
            metric_type="NUMERIC_TARGET",
            target_value=100.0,
            actual_value=None,
            actual_performance=None,
        )
        assert res.status == "IN_PROGRESS"


class TestReviewAndDiscrepancyHandling:
    def test_ambiguity_flag_sets_needs_review(self):
        res = evaluate_commitment_status(
            commitment_type="EXPLICIT_COMMITMENT",
            target_period="Q2 FY27",
            as_of_period="Q2 FY27",
            metric_type="NUMERIC_TARGET",
            target_value=100.0,
            actual_value=100.0,
            is_ambiguous=True,
            ambiguity_reason="Restated accounting definition between quarters requires reconciliation.",
        )
        assert res.status == "NEEDS_REVIEW"
        assert res.needs_review is True
        assert "Restated accounting definition" in res.review_reason

    def test_unit_mismatch_sets_needs_review(self):
        res = evaluate_commitment_status(
            commitment_type="EXPLICIT_COMMITMENT",
            target_period="Q2 FY27",
            as_of_period="Q2 FY27",
            metric_type="NUMERIC_TARGET",
            target_value=50.0,
            target_unit="megawatt",
            actual_value=50.0,
            actual_unit="crore",
        )
        assert res.status == "NEEDS_REVIEW"
        assert res.needs_review is True
        assert "Unit mismatch" in res.review_reason


class TestDeliveryScoreCalculation:
    def test_standard_track_record_summary(self):
        # 5 commitments:
        # 1. EXPLICIT: ACHIEVED (1.0 pt)
        # 2. EXPLICIT: PARTIALLY_ACHIEVED (0.5 pt)
        # 3. FORWARD: MISSED (0.0 pt)
        # 4. EXPLICIT: IN_PROGRESS (excluded from denominator)
        # 5. STRATEGIC_INTENTION: ACHIEVED (excluded from denominator)
        commitments = [
            CommitmentItem(
                id="c1", symbol="RELIANCE", commitment_type="EXPLICIT_COMMITMENT", category="capex",
                title="Capex target", statement="Capex target statement", speaker="Management",
                source_doc_title="Pres", source_doc_type="investor_presentation", source_page_or_slide="Slide 12",
                source_url="https://nse.com", commitment_date="2025-10-15", commitment_period="Q2 FY26",
                target_period="Q2 FY27", target_value=38000.0, target_unit="crore", target_tolerance_pct=5.0,
                actual_performance="Delivered ₹38,500 Cr", actual_value=38500.0, actual_unit="crore",
                actual_source_doc="Pres", actual_source_page_or_slide="Slide 12", actual_source_url="https://nse.com",
                actual_reported_period="Q2 FY27", status="ACHIEVED", evaluation_reasoning="Within tolerance",
                contributes_to_score=True,
            ),
            CommitmentItem(
                id="c2", symbol="RELIANCE", commitment_type="EXPLICIT_COMMITMENT", category="operational_targets",
                title="Broadband rollouts", statement="Target 30M homes", speaker="Management",
                source_doc_title="Pres", source_doc_type="investor_presentation", source_page_or_slide="Slide 15",
                source_url="https://nse.com", commitment_date="2025-10-15", commitment_period="Q2 FY26",
                target_period="Q2 FY27", target_value=30.0, target_unit="mn_homes", target_tolerance_pct=0.0,
                actual_performance="Reached 24M homes", actual_value=24.0, actual_unit="mn_homes",
                actual_source_doc="Pres", actual_source_page_or_slide="Slide 15", actual_source_url="https://nse.com",
                actual_reported_period="Q2 FY27", status="PARTIALLY_ACHIEVED", evaluation_reasoning="Reached 80%",
                contributes_to_score=True,
            ),
            CommitmentItem(
                id="c3", symbol="RELIANCE", commitment_type="FORWARD_GUIDANCE", category="capacity_commissioning",
                title="Old plant commissioning", statement="Commission by Q1 FY27", speaker="Management",
                source_doc_title="Pres", source_doc_type="investor_presentation", source_page_or_slide="Slide 20",
                source_url="https://nse.com", commitment_date="2025-10-15", commitment_period="Q2 FY26",
                target_period="Q1 FY27", target_value=None, target_unit=None, target_tolerance_pct=0.0,
                actual_performance="Not commissioned", actual_value=None, actual_unit=None,
                actual_source_doc="Pres", actual_source_page_or_slide="Slide 20", actual_source_url="https://nse.com",
                actual_reported_period="Q2 FY27", status="MISSED", evaluation_reasoning="Missed deadline",
                contributes_to_score=True,
            ),
            CommitmentItem(
                id="c4", symbol="RELIANCE", commitment_type="EXPLICIT_COMMITMENT", category="strategic_milestone",
                title="Giga factory scale", statement="Target FY28 launch", speaker="Management",
                source_doc_title="Pres", source_doc_type="investor_presentation", source_page_or_slide="Slide 22",
                source_url="https://nse.com", commitment_date="2025-10-15", commitment_period="Q2 FY26",
                target_period="FY28", target_value=None, target_unit=None, target_tolerance_pct=0.0,
                actual_performance=None, actual_value=None, actual_unit=None,
                actual_source_doc=None, actual_source_page_or_slide=None, actual_source_url=None,
                actual_reported_period=None, status="IN_PROGRESS", evaluation_reasoning="Ongoing",
                contributes_to_score=True,
            ),
            CommitmentItem(
                id="c5", symbol="RELIANCE", commitment_type="STRATEGIC_INTENTION", category="strategic_milestone",
                title="Global footprint", statement="Explore global telecom expansion", speaker="Management",
                source_doc_title="Pres", source_doc_type="investor_presentation", source_page_or_slide="Slide 25",
                source_url="https://nse.com", commitment_date="2025-10-15", commitment_period="Q2 FY26",
                target_period="FY29", target_value=None, target_unit=None, target_tolerance_pct=0.0,
                actual_performance="Partnerships signed", actual_value=None, actual_unit=None,
                actual_source_doc=None, actual_source_page_or_slide=None, actual_source_url=None,
                actual_reported_period="Q2 FY27", status="ACHIEVED", evaluation_reasoning="Milestone met",
                contributes_to_score=False, # Strategic intention does not contribute
            ),
        ]

        summary = calculate_track_record_summary(commitments)
        assert summary.total_commitments == 5
        assert summary.explicit_commitments_count == 3
        assert summary.forward_guidance_count == 1
        assert summary.strategic_intentions_count == 1
        assert summary.operational_milestones_count == 0
        assert summary.eligible_count == 4
        # Evaluated eligible count: c1 (ACHIEVED) + c2 (PARTIAL) + c3 (MISSED) = 3
        assert summary.eligible_evaluated_count == 3
        assert summary.evaluated_count == 3
        assert summary.eligible_achieved_count == 1
        assert summary.total_achieved_count == 2  # c1 (eligible) + c5 (strategic intention)
        assert summary.eligible_in_progress_count == 1  # c4
        assert summary.total_in_progress_count == 1
        # Score = (1.0 + 0.5) / 3 * 100 = 50.0%
        assert summary.delivery_score == 50.0
        assert "50.0% (1.5 of 3 eligible evaluated commitments delivered" in summary.score_label

    def test_zero_evaluated_returns_none(self):
        # When only IN_PROGRESS or UNVERIFIABLE commitments exist
        commitments = [
            {
                "commitment_type": "EXPLICIT_COMMITMENT",
                "status": "IN_PROGRESS",
                "contributes_to_score": 1,
            },
            {
                "commitment_type": "EXPLICIT_COMMITMENT",
                "status": "UNVERIFIABLE",
                "contributes_to_score": 1,
            },
        ]
        summary = calculate_track_record_summary(commitments)
        assert summary.eligible_evaluated_count == 0
        assert summary.evaluated_count == 0
        assert summary.delivery_score is None
        assert "Insufficient evaluated evidence" in summary.score_label


class TestSummaryCountRelationshipsAndInvariants:
    """Regression tests verifying all count identities and score calculation rules."""

    def test_complete_status_count_relationships(self):
        # Setup heterogeneous set of 9 commitments:
        # - 2 EXPLICIT: 1 Achieved, 1 Unverifiable
        # - 4 FORWARD: 2 Achieved, 2 In Progress
        # - 1 STRATEGIC_INTENTION: In Progress (Excluded)
        # - 2 OPERATIONAL_MILESTONE: 2 Achieved (Excluded)
        items = [
            {"commitment_type": "EXPLICIT_COMMITMENT", "status": "ACHIEVED", "contributes_to_score": 1},
            {"commitment_type": "EXPLICIT_COMMITMENT", "status": "UNVERIFIABLE", "contributes_to_score": 1},
            {"commitment_type": "FORWARD_GUIDANCE", "status": "ACHIEVED", "contributes_to_score": 1},
            {"commitment_type": "FORWARD_GUIDANCE", "status": "ACHIEVED", "contributes_to_score": 1},
            {"commitment_type": "FORWARD_GUIDANCE", "status": "IN_PROGRESS", "contributes_to_score": 1},
            {"commitment_type": "FORWARD_GUIDANCE", "status": "IN_PROGRESS", "contributes_to_score": 1},
            {"commitment_type": "STRATEGIC_INTENTION", "status": "IN_PROGRESS", "contributes_to_score": 0},
            {"commitment_type": "OPERATIONAL_MILESTONE", "status": "ACHIEVED", "contributes_to_score": 0},
            {"commitment_type": "OPERATIONAL_MILESTONE", "status": "ACHIEVED", "contributes_to_score": 0},
        ]

        summary = calculate_track_record_summary(items)

        # 1. Total counts
        assert summary.total_commitments == 9
        assert summary.explicit_commitments_count == 2
        assert summary.forward_guidance_count == 4
        assert summary.strategic_intentions_count == 1
        assert summary.operational_milestones_count == 2
        assert summary.excluded_count == 3

        # 2. Total Invariants
        assert summary.total_commitments == summary.eligible_count + summary.excluded_count
        assert summary.excluded_count == summary.strategic_intentions_count + summary.operational_milestones_count

        # 3. Overall status counts across all items
        assert summary.total_achieved_count == 5  # 3 eligible + 2 milestones
        assert summary.total_in_progress_count == 3  # 2 eligible + 1 strategic
        assert summary.total_unverifiable_count == 1
        assert summary.total_delayed_count == 0
        assert summary.total_missed_count == 0
        assert summary.total_partially_achieved_count == 0
        assert summary.total_needs_review_count == 0

        # Sum of all overall statuses equals total_commitments
        assert summary.total_commitments == (
            summary.total_achieved_count +
            summary.total_partially_achieved_count +
            summary.total_delayed_count +
            summary.total_missed_count +
            summary.total_in_progress_count +
            summary.total_unverifiable_count +
            summary.total_needs_review_count
        )

        # 4. Score-eligible status counts (strictly for genuine commitments)
        assert summary.eligible_count == 6
        assert summary.eligible_evaluated_count == 3
        assert summary.eligible_achieved_count == 3
        assert summary.eligible_partially_achieved_count == 0
        assert summary.eligible_delayed_count == 0
        assert summary.eligible_missed_count == 0
        assert summary.eligible_in_progress_count == 2
        assert summary.eligible_unverifiable_count == 1
        assert summary.eligible_needs_review_count == 0

        # Eligible Invariant: evaluated + in_progress + unverifiable + needs_review == eligible_count
        assert summary.eligible_count == (
            summary.eligible_evaluated_count +
            summary.eligible_in_progress_count +
            summary.eligible_unverifiable_count +
            summary.eligible_needs_review_count
        )

        # Evaluated Invariant: achieved + partial + delayed + missed == evaluated_count
        assert summary.eligible_evaluated_count == (
            summary.eligible_achieved_count +
            summary.eligible_partially_achieved_count +
            summary.eligible_delayed_count +
            summary.eligible_missed_count
        )

        # 5. Score calculation: 3 achieved of 3 evaluated = 100.0%
        assert summary.delivery_score == 100.0
        assert "100.0% (3 of 3 eligible evaluated commitments delivered" in summary.score_label
        assert "Sample excludes 3 non-promissory items" in summary.stat_caveat
        assert "2 active in-progress commitments, and 1 unverifiable targets" in summary.stat_caveat


class TestMultiQuarterAuditCheckpoints:
    def test_quarter_evaluation_series(self):
        q_evals = [
            QuarterEvaluation(
                quarter="Q3 FY26",
                disclosed_value=10.0,
                disclosed_unit="MW",
                status="ON_TRACK",
                commentary="Initial civil construction commenced.",
                source_doc="Reliance Q3 FY26 Financial Results",
                source_page_or_slide="Slide 18",
                source_url="https://archives.nseindia.com/doc1.pdf",
            ),
            QuarterEvaluation(
                quarter="Q4 FY26",
                disclosed_value=25.0,
                disclosed_unit="MW",
                status="ON_TRACK",
                commentary="Equipment installation completed.",
                source_doc="Reliance Q4 FY26 Investor Presentation",
                source_page_or_slide="Slide 22",
                source_url="https://archives.nseindia.com/doc2.pdf",
            ),
            QuarterEvaluation(
                quarter="Q1 FY27",
                disclosed_value=40.0,
                disclosed_unit="MW",
                status="ON_TRACK",
                commentary="Grid synchronization trials initiated.",
                source_doc="Reliance Q1 FY27 Investor Presentation",
                source_page_or_slide="Slide 19",
                source_url="https://archives.nseindia.com/doc3.pdf",
            ),
            QuarterEvaluation(
                quarter="Q2 FY27",
                disclosed_value=50.0,
                disclosed_unit="MW",
                status="COMPLETED",
                commentary="Commissioned initial 50 MW capacity at Jamnagar.",
                source_doc="Reliance Q2 FY27 Investor Presentation",
                source_page_or_slide="Slide 14",
                source_url="https://archives.nseindia.com/doc4.pdf",
            ),
        ]
        assert len(q_evals) == 4
        assert q_evals[3].status == "COMPLETED"
        assert q_evals[3].disclosed_value == 50.0
