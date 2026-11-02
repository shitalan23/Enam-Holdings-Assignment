"""Deterministic evaluation logic for P1.3 Promise vs Delivered engine.

Strictly executed in deterministic Python (never LLM-generated math/evaluations).
Adheres strictly to ENAM Holdings financial intelligence principles:
1. Distinguishes genuine commitments (EXPLICIT_COMMITMENT, FORWARD_GUIDANCE)
   from non-promissory items (STRATEGIC_INTENTION, OPERATIONAL_MILESTONE).
   Only genuine commitments contribute to the delivery score.
2. Does NOT automatically treat reported KPIs or completed events as prior promises.
3. Metric-specific evaluation rules (never a blanket 70% threshold).
4. Never marks a commitment MISSED simply because actual performance is unavailable
   (uses UNVERIFIABLE or IN_PROGRESS).
5. Safe handling of nullable actual values and missing citations.
6. Evaluates multi-quarter tracking across at least 4 quarters.
7. Flags ambiguous or disputed data as NEEDS_REVIEW without fabrication.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Literal, Optional, List, Dict, Any


CommitmentType = Literal[
    "EXPLICIT_COMMITMENT",
    "FORWARD_GUIDANCE",
    "STRATEGIC_INTENTION",
    "OPERATIONAL_MILESTONE",
]

CommitmentStatus = Literal[
    "ACHIEVED",
    "PARTIALLY_ACHIEVED",
    "IN_PROGRESS",
    "DELAYED",
    "MISSED",
    "UNVERIFIABLE",
    "NEEDS_REVIEW",
]

CommitmentCategory = Literal[
    "capex",
    "capacity_commissioning",
    "revenue_margin",
    "operational_targets",
    "strategic_milestone",
]

MetricType = Literal[
    "BINARY_MILESTONE",
    "NUMERIC_TARGET",
    "NUMERIC_CEILING",
    "RANGE_TARGET",
]


@dataclass(frozen=True)
class QuarterEvaluation:
    """Quarter-by-quarter audit checkpoint for tracking progress across 4+ quarters."""
    quarter: str                         # e.g. 'Q3 FY26', 'Q4 FY26', 'Q1 FY27', 'Q2 FY27'
    disclosed_value: Optional[float]     # Disclosed metric if reported
    disclosed_unit: Optional[str]        # Disclosed unit if reported
    status: str                          # 'ON_TRACK', 'DELAYED', 'COMPLETED', 'NOT_MENTIONED', 'PARTIALLY_MET'
    commentary: str                      # Verbatim extract / summary from official filing
    source_doc: str                      # Document title
    source_page_or_slide: str            # Page or slide citation
    source_url: str                      # Official URL


@dataclass(frozen=True)
class EvaluationResult:
    status: CommitmentStatus
    evaluation_reasoning: str
    contributes_to_score: bool
    needs_review: bool = False
    review_reason: Optional[str] = None


@dataclass
class CommitmentItem:
    id: str
    symbol: str
    commitment_type: CommitmentType
    category: CommitmentCategory
    title: str
    statement: str
    speaker: Optional[str]
    source_doc_title: str
    source_doc_type: str
    source_page_or_slide: str
    source_url: str
    commitment_date: str
    commitment_period: str
    target_period: str
    target_value: Optional[float]
    target_unit: Optional[str]
    target_tolerance_pct: float
    actual_performance: Optional[str]
    actual_value: Optional[float]
    actual_unit: Optional[str]
    actual_source_doc: Optional[str]
    actual_source_page_or_slide: Optional[str]
    actual_source_url: Optional[str]
    actual_reported_period: Optional[str]
    quarter_evaluations: List[QuarterEvaluation] = field(default_factory=list)
    status: CommitmentStatus = "IN_PROGRESS"
    evaluation_reasoning: str = ""
    is_quantified: bool = False
    contributes_to_score: bool = True
    needs_review: bool = False
    review_reason: Optional[str] = None
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["quarter_evaluations"] = [asdict(q) for q in self.quarter_evaluations]
        return d


@dataclass(frozen=True)
class TrackRecordSummary:
    total_commitments: int
    explicit_commitments_count: int
    forward_guidance_count: int
    strategic_intentions_count: int
    operational_milestones_count: int
    excluded_count: int

    # Overall Status Counts (across all commitments)
    total_achieved_count: int
    total_partially_achieved_count: int
    total_delayed_count: int
    total_missed_count: int
    total_in_progress_count: int
    total_unverifiable_count: int
    total_needs_review_count: int

    # Score-Eligible Commitment Counts (strictly genuine commitments where contributes_to_score is True)
    eligible_count: int
    eligible_evaluated_count: int
    eligible_achieved_count: int
    eligible_partially_achieved_count: int
    eligible_delayed_count: int
    eligible_missed_count: int
    eligible_in_progress_count: int
    eligible_unverifiable_count: int
    eligible_needs_review_count: int

    # Evaluated Delivery Score
    delivery_score: Optional[float]
    score_label: str
    methodology_note: str
    stat_caveat: str = ""

    # Convenience aliases matching eligible evaluation fields
    @property
    def evaluated_count(self) -> int:
        return self.eligible_evaluated_count

    @property
    def achieved_count(self) -> int:
        return self.eligible_achieved_count

    @property
    def partially_achieved_count(self) -> int:
        return self.eligible_partially_achieved_count

    @property
    def delayed_count(self) -> int:
        return self.eligible_delayed_count

    @property
    def missed_count(self) -> int:
        return self.eligible_missed_count

    @property
    def in_progress_count(self) -> int:
        return self.eligible_in_progress_count

    @property
    def unverifiable_count(self) -> int:
        return self.eligible_unverifiable_count

    @property
    def needs_review_count(self) -> int:
        return self.eligible_needs_review_count

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary including both explicit fields and convenience alias keys."""
        d = asdict(self)
        d["evaluated_count"] = self.eligible_evaluated_count
        d["achieved_count"] = self.eligible_achieved_count
        d["partially_achieved_count"] = self.eligible_partially_achieved_count
        d["delayed_count"] = self.eligible_delayed_count
        d["missed_count"] = self.eligible_missed_count
        d["in_progress_count"] = self.eligible_in_progress_count
        d["unverifiable_count"] = self.eligible_unverifiable_count
        d["needs_review_count"] = self.eligible_needs_review_count
        return d


def parse_period_rank(period: str) -> float:
    """Convert financial period string into an ordinal float for timeline comparisons.
    
    Examples:
    - 'Q1 FY26' -> 2026.1
    - 'Q2 FY26' -> 2026.2
    - 'H1 FY26' -> 2026.2
    - 'Q3 FY26' -> 2026.3
    - 'Q4 FY26' -> 2026.4
    - 'H2 FY26' -> 2026.4
    - 'FY26'    -> 2026.4 (end of FY26)
    - 'FY27 Ongoing' -> 2027.4
    - 'FY28 - FY29'  -> 2029.4
    """
    p = period.strip().upper()

    # Match FY range: FY28 - FY29 or FY28-FY29
    m_range = re.search(r"FY(\d{2})\s*-\s*FY(\d{2})", p)
    if m_range:
        end_yy = int(m_range.group(2))
        return (2000 + end_yy) + 0.4

    # Match Quarter + FY: Q2 FY27
    m_q = re.search(r"Q([1-4])\s*FY(\d{2})", p)
    if m_q:
        q = int(m_q.group(1))
        yy = int(m_q.group(2))
        return (2000 + yy) + (q * 0.1)

    # Match Half Year + FY: H1 FY27
    m_h = re.search(r"H([1-2])\s*FY(\d{2})", p)
    if m_h:
        h = int(m_h.group(1))
        yy = int(m_h.group(2))
        return (2000 + yy) + (0.2 if h == 1 else 0.4)

    # Match standalone FY: FY27 or FY27 Ongoing
    m_fy = re.search(r"FY(\d{2})", p)
    if m_fy:
        yy = int(m_fy.group(1))
        return (2000 + yy) + 0.4

    # Match calendar years if any: 2026 or 2027
    m_cy = re.search(r"(20\d{2})", p)
    if m_cy:
        return float(m_cy.group(1)) + 0.4

    # Default fallback: neutral high rank
    return 2099.0


def compare_periods(period_a: str, period_b: str) -> int:
    """Returns -1 if period_a < period_b, 0 if equal, 1 if period_a > period_b."""
    ra = parse_period_rank(period_a)
    rb = parse_period_rank(period_b)
    if abs(ra - rb) < 1e-4:
        return 0
    return -1 if ra < rb else 1


def is_genuine_commitment(commitment_type: str) -> bool:
    """Return True only if commitment_type represents an advance commitment or guidance."""
    return commitment_type in ("EXPLICIT_COMMITMENT", "FORWARD_GUIDANCE")


def evaluate_commitment_status(
    commitment_type: str,
    target_period: str,
    as_of_period: str,
    metric_type: MetricType = "BINARY_MILESTONE",
    target_value: Optional[float] = None,
    target_unit: Optional[str] = None,
    actual_value: Optional[float] = None,
    actual_unit: Optional[str] = None,
    actual_performance: Optional[str] = None,
    target_tolerance_pct: float = 0.0,
    partial_threshold_pct: float = 70.0,
    range_min: Optional[float] = None,
    range_max: Optional[float] = None,
    is_binary_completed: Optional[bool] = None,
    is_timeline_extended: bool = False,
    has_evidence_of_non_delivery: bool = False,
    failure_evidence: Optional[str] = None,
    is_ambiguous: bool = False,
    ambiguity_reason: Optional[str] = None,
    has_advance_promise_evidence: bool = True,
    advance_promise_reason: Optional[str] = None,
) -> EvaluationResult:
    """Deterministic evaluation of a single commitment against reported actuals.
    
    Rules enforced:
    - Ambiguous metrics or conflicts are marked NEEDS_REVIEW.
    - STRATEGIC_INTENTION and OPERATIONAL_MILESTONE do not contribute to score.
    - If advance promise is missing/unverified prior to outcome, returns UNVERIFIABLE.
    - If actual is unavailable, returns UNVERIFIABLE (if period expired) or IN_PROGRESS (if active).
      NEVER returns MISSED solely because a deadline passed without evidence of non-delivery.
    - MISSED requires primary-source evidence of non-delivery / cancellation. Otherwise, UNVERIFIABLE.
    - Metric-specific thresholds with tolerance for numeric targets and ceilings.
    """
    contributes = is_genuine_commitment(commitment_type)

    # 1. Ambiguity / Review Flag
    if is_ambiguous or ambiguity_reason:
        return EvaluationResult(
            status="NEEDS_REVIEW",
            evaluation_reasoning=ambiguity_reason or "Ambiguous disclosure or conflicting reporting requires analyst review.",
            contributes_to_score=contributes,
            needs_review=True,
            review_reason=ambiguity_reason or "Disclosed figures require reconciliation.",
        )

    # 1b. Chronology Check: Must have verified advance promise published before actual outcome
    if not has_advance_promise_evidence:
        return EvaluationResult(
            status="UNVERIFIABLE",
            evaluation_reasoning=(
                advance_promise_reason or
                "Under FINN chronology rules, a management track record requires primary-source evidence of an advance "
                "promise published before the actual outcome. In the absence of an advance primary document, this commitment "
                "cannot be verified as an achieved promise based solely on a post-outcome disclosure."
            ),
            contributes_to_score=contributes,
        )

    # 2. Strategic Intention (Non-promissory aspirational statement)
    if commitment_type == "STRATEGIC_INTENTION":
        if is_binary_completed is True:
            return EvaluationResult(
                status="ACHIEVED",
                evaluation_reasoning="Strategic intention accomplished. Excluded from quantitative delivery score per methodology.",
                contributes_to_score=False,
            )
        period_comp = compare_periods(target_period, as_of_period)
        if period_comp >= 0:
            return EvaluationResult(
                status="IN_PROGRESS",
                evaluation_reasoning="Directional strategic intention actively pursued. Excluded from quantitative delivery score.",
                contributes_to_score=False,
            )
        return EvaluationResult(
            status="IN_PROGRESS",
            evaluation_reasoning="Directional strategic intention without binding gate. Excluded from quantitative delivery score.",
            contributes_to_score=False,
        )

    # 3. Operational Milestone (Historical accomplishment, not a forward promise)
    if commitment_type == "OPERATIONAL_MILESTONE":
        return EvaluationResult(
            status="ACHIEVED",
            evaluation_reasoning="Historical operational milestone disclosed as completed. Excluded from quantitative delivery score denominator.",
            contributes_to_score=False,
        )

    period_comp = compare_periods(target_period, as_of_period)
    is_target_expired = period_comp < 0
    is_target_current = period_comp == 0
    is_target_future = period_comp > 0

    # 4. Check for completely missing actual data
    has_actual_data = (
        actual_value is not None or
        (actual_performance is not None and actual_performance.strip() != "") or
        is_binary_completed is not None
    )

    if not has_actual_data:
        if is_target_expired:
            return EvaluationResult(
                status="UNVERIFIABLE",
                evaluation_reasoning=(
                    f"Target period {target_period} has passed, but actual performance was not disclosed "
                    "in subsequent primary filings. Under FINN zero-fabrication rules, an undisclosed target "
                    "is marked UNVERIFIABLE and is never marked MISSED without negative evidence."
                ),
                contributes_to_score=contributes,
            )
        else:
            return EvaluationResult(
                status="IN_PROGRESS",
                evaluation_reasoning=f"Commitment timeline {target_period} is active/future. Execution is underway.",
                contributes_to_score=contributes,
            )

    # 5. Unit Mismatch Check
    if target_unit and actual_unit and target_unit.strip().lower() != actual_unit.strip().lower():
        # Allow identical base crore
        if not (target_unit.strip().lower() in ("cr", "crore", "inr crore") and
                actual_unit.strip().lower() in ("cr", "crore", "inr crore")):
            return EvaluationResult(
                status="NEEDS_REVIEW",
                evaluation_reasoning=f"Unit discrepancy between target ('{target_unit}') and actual ('{actual_unit}').",
                contributes_to_score=contributes,
                needs_review=True,
                review_reason=f"Unit mismatch: target is {target_unit}, actual reported is {actual_unit}.",
            )

    # 6. Binary Milestone Evaluation
    if metric_type == "BINARY_MILESTONE":
        if is_binary_completed is True:
            return EvaluationResult(
                status="ACHIEVED",
                evaluation_reasoning=f"Milestone successfully delivered and verified in official disclosures by {as_of_period}.",
                contributes_to_score=contributes,
            )
        if is_binary_completed is False:
            if is_timeline_extended:
                return EvaluationResult(
                    status="DELAYED",
                    evaluation_reasoning=(
                        f"Milestone target for {target_period} was not met, but company has officially extended "
                        "the timeline in subsequent disclosures."
                    ),
                    contributes_to_score=contributes,
                )
            if is_target_expired:
                # Crucial requirement: MISSED requires primary-source evidence of non-delivery.
                # An expired commitment is NEVER marked MISSED solely because its deadline passed.
                if has_evidence_of_non_delivery or failure_evidence:
                    return EvaluationResult(
                        status="MISSED",
                        evaluation_reasoning=(
                            failure_evidence or
                            f"Target period {target_period} passed with primary-source evidence of non-delivery: commitment abandoned or confirmed missed."
                        ),
                        contributes_to_score=contributes,
                    )
                return EvaluationResult(
                    status="UNVERIFIABLE",
                    evaluation_reasoning=(
                        f"Target period {target_period} has passed without verified completion; however, in the absence of primary-source "
                        "evidence of non-delivery or project cancellation, this commitment cannot be marked MISSED solely due to an expired deadline "
                        "and is classified as UNVERIFIABLE."
                    ),
                    contributes_to_score=contributes,
                )
            return EvaluationResult(
                status="IN_PROGRESS",
                evaluation_reasoning=f"Milestone target {target_period} is active and currently uncompleted.",
                contributes_to_score=contributes,
            )

    # 7. Numeric Target (Higher is better, e.g. subscriber count, store count, revenue)
    if metric_type == "NUMERIC_TARGET":
        if target_value is None or actual_value is None:
            # Descriptive text given without clean numeric actual
            if is_target_expired:
                return EvaluationResult(
                    status="UNVERIFIABLE",
                    evaluation_reasoning=f"Quantitative target of {target_value} {target_unit or ''} could not be verified from reported disclosures.",
                    contributes_to_score=contributes,
                )
            return EvaluationResult(
                status="IN_PROGRESS",
                evaluation_reasoning=f"Quantitative target of {target_value} {target_unit or ''} is ongoing for {target_period}.",
                contributes_to_score=contributes,
            )

        full_threshold = target_value * (1.0 - (target_tolerance_pct / 100.0))
        part_threshold = target_value * (partial_threshold_pct / 100.0)

        if actual_value >= full_threshold:
            return EvaluationResult(
                status="ACHIEVED",
                evaluation_reasoning=(
                    f"Delivered {actual_value:g} {actual_unit or ''} vs target of {target_value:g} {target_unit or ''} "
                    f"({'within ' + str(target_tolerance_pct) + '% tolerance' if target_tolerance_pct > 0 else 'meeting target'})."
                ),
                contributes_to_score=contributes,
            )

        if actual_value >= part_threshold:
            if is_target_expired or is_target_current:
                return EvaluationResult(
                    status="PARTIALLY_ACHIEVED",
                    evaluation_reasoning=(
                        f"Delivered {actual_value:g} {actual_unit or ''} ({round(actual_value/target_value*100, 1)}% of {target_value:g} target), "
                        f"meeting partial delivery threshold (>= {partial_threshold_pct}%)."
                    ),
                    contributes_to_score=contributes,
                )
            return EvaluationResult(
                status="IN_PROGRESS",
                evaluation_reasoning=(
                    f"Current actual of {actual_value:g} {actual_unit or ''} ({round(actual_value/target_value*100, 1)}% of {target_value:g} target) "
                    f"on track for target period {target_period}."
                ),
                contributes_to_score=contributes,
            )

        # actual_value < part_threshold
        if is_timeline_extended:
            return EvaluationResult(
                status="DELAYED",
                evaluation_reasoning=(
                    f"Delivered {actual_value:g} {actual_unit or ''} vs target {target_value:g}; timeline extended by management."
                ),
                contributes_to_score=contributes,
            )
        if is_target_expired:
            return EvaluationResult(
                status="MISSED",
                evaluation_reasoning=(
                    f"Delivered {actual_value:g} {actual_unit or ''} vs target {target_value:g} {target_unit or ''} "
                    f"for expired period {target_period} (< {partial_threshold_pct}% threshold)."
                ),
                contributes_to_score=contributes,
            )
        return EvaluationResult(
            status="IN_PROGRESS",
            evaluation_reasoning=(
                f"Actual progress {actual_value:g} {actual_unit or ''} vs target {target_value:g} for active period {target_period}."
            ),
            contributes_to_score=contributes,
        )

    # 8. Numeric Ceiling (Lower is better / budget cap, e.g. Net Debt ceiling, Capex budget limit)
    if metric_type == "NUMERIC_CEILING":
        if target_value is None or actual_value is None:
            if is_target_expired:
                return EvaluationResult(
                    status="UNVERIFIABLE",
                    evaluation_reasoning=f"Ceiling target of {target_value} {target_unit or ''} could not be verified from reported disclosures.",
                    contributes_to_score=contributes,
                )
            return EvaluationResult(
                status="IN_PROGRESS",
                evaluation_reasoning=f"Ceiling target of {target_value} {target_unit or ''} is ongoing for {target_period}.",
                contributes_to_score=contributes,
            )

        full_threshold = target_value * (1.0 + (target_tolerance_pct / 100.0))
        part_ceiling = target_value * 1.20  # up to 20% budget overrun allowed for partial

        if actual_value <= full_threshold:
            return EvaluationResult(
                status="ACHIEVED",
                evaluation_reasoning=(
                    f"Actual {actual_value:g} {actual_unit or ''} remained below ceiling target of {target_value:g} {target_unit or ''}."
                ),
                contributes_to_score=contributes,
            )

        if actual_value <= part_ceiling:
            if is_target_expired or is_target_current:
                return EvaluationResult(
                    status="PARTIALLY_ACHIEVED",
                    evaluation_reasoning=(
                        f"Actual {actual_value:g} {actual_unit or ''} exceeded ceiling {target_value:g} by "
                        f"{round((actual_value - target_value)/target_value*100, 1)}%, but remained within allowable 20% overrun."
                    ),
                    contributes_to_score=contributes,
                )
            return EvaluationResult(
                status="IN_PROGRESS",
                evaluation_reasoning=f"Run-rate of {actual_value:g} is slightly over baseline ceiling for {target_period}.",
                contributes_to_score=contributes,
            )

        # actual_value > part_ceiling
        if is_timeline_extended:
            return EvaluationResult(
                status="DELAYED",
                evaluation_reasoning=f"Actual {actual_value:g} over ceiling {target_value:g}; timeline extended.",
                contributes_to_score=contributes,
            )
        if is_target_expired:
            return EvaluationResult(
                status="MISSED",
                evaluation_reasoning=(
                    f"Actual {actual_value:g} {actual_unit or ''} exceeded ceiling target {target_value:g} {target_unit or ''} "
                    f"by >20% for period {target_period}."
                ),
                contributes_to_score=contributes,
            )
        return EvaluationResult(
            status="IN_PROGRESS",
            evaluation_reasoning=f"Ceiling target of {target_value:g} active for {target_period}.",
            contributes_to_score=contributes,
        )

    # 9. Range Target (e.g. Capex run rate ₹35,000 - ₹40,000 Cr)
    if metric_type == "RANGE_TARGET":
        r_min = range_min if range_min is not None else target_value
        r_max = range_max if range_max is not None else target_value
        if r_min is None or r_max is None or actual_value is None:
            if is_target_expired:
                return EvaluationResult(
                    status="UNVERIFIABLE",
                    evaluation_reasoning=f"Range target [{r_min}, {r_max}] could not be verified from reported disclosures.",
                    contributes_to_score=contributes,
                )
            return EvaluationResult(
                status="IN_PROGRESS",
                evaluation_reasoning=f"Range target [{r_min}, {r_max}] is active for {target_period}.",
                contributes_to_score=contributes,
            )

        min_bound = r_min * (1.0 - (target_tolerance_pct / 100.0))
        max_bound = r_max * (1.0 + (target_tolerance_pct / 100.0))

        if min_bound <= actual_value <= max_bound:
            return EvaluationResult(
                status="ACHIEVED",
                evaluation_reasoning=(
                    f"Actual {actual_value:g} {actual_unit or ''} fell within target range "
                    f"[{r_min:g}, {r_max:g}] {target_unit or ''}."
                ),
                contributes_to_score=contributes,
            )

        if (0.80 * min_bound) <= actual_value <= (1.20 * max_bound):
            if is_target_expired or is_target_current:
                return EvaluationResult(
                    status="PARTIALLY_ACHIEVED",
                    evaluation_reasoning=(
                        f"Actual {actual_value:g} {actual_unit or ''} fell near target range [{r_min:g}, {r_max:g}] "
                        f"within +/-20% variation."
                    ),
                    contributes_to_score=contributes,
                )
            return EvaluationResult(
                status="IN_PROGRESS",
                evaluation_reasoning=f"Actual {actual_value:g} close to target range for {target_period}.",
                contributes_to_score=contributes,
            )

        if is_timeline_extended:
            return EvaluationResult(
                status="DELAYED",
                evaluation_reasoning=f"Actual {actual_value:g} outside range [{r_min:g}, {r_max:g}]; timeline extended.",
                contributes_to_score=contributes,
            )
        if is_target_expired:
            return EvaluationResult(
                status="MISSED",
                evaluation_reasoning=(
                    f"Actual {actual_value:g} {actual_unit or ''} missed target range [{r_min:g}, {r_max:g}] {target_unit or ''}."
                ),
                contributes_to_score=contributes,
            )
        return EvaluationResult(
            status="IN_PROGRESS",
            evaluation_reasoning=f"Range target [{r_min:g}, {r_max:g}] active for {target_period}.",
            contributes_to_score=contributes,
        )

    # Fallback
    return EvaluationResult(
        status="IN_PROGRESS" if not is_target_expired else "UNVERIFIABLE",
        evaluation_reasoning=f"Evaluation completed for {target_period}.",
        contributes_to_score=contributes,
    )


def calculate_track_record_summary(
    commitments: List[CommitmentItem | Dict[str, Any]],
) -> TrackRecordSummary:
    """Calculate overall delivery score and breakdown across tracked commitments.
    
    Delivery Score Methodology:
    - Numerator: Eligible Achieved * 1.0 + Eligible Partially Achieved * 0.5
    - Denominator: Eligible Evaluated Count (Achieved + Partially Achieved + Delayed + Missed)
    - Eligible commitments include ONLY genuine commitments (EXPLICIT_COMMITMENT, FORWARD_GUIDANCE)
      where contributes_to_score == True.
    - Excluded from score denominator:
      * STRATEGIC_INTENTION and OPERATIONAL_MILESTONE (contributes_to_score == False)
      * IN_PROGRESS (still active)
      * UNVERIFIABLE (not disclosed in subsequent filings)
      * NEEDS_REVIEW (ambiguous / disputed)
    - Distinguishes overall status counts (across all items) from score-eligible status counts.
    - If evaluated_count == 0, score is None with explicit note to avoid misleading investors.
    """
    total = len(commitments)
    explicit_count = 0
    forward_count = 0
    strategic_count = 0
    milestone_count = 0

    # Overall Status Counts (across all commitments)
    total_achieved = 0
    total_partially_achieved = 0
    total_delayed = 0
    total_missed = 0
    total_in_progress = 0
    total_unverifiable = 0
    total_needs_review = 0

    # Score-Eligible Commitment Status Counts
    eligible_count = 0
    eligible_achieved = 0
    eligible_partially_achieved = 0
    eligible_delayed = 0
    eligible_missed = 0
    eligible_in_progress = 0
    eligible_unverifiable = 0
    eligible_needs_review = 0

    for item in commitments:
        if isinstance(item, CommitmentItem):
            c_type = item.commitment_type
            c_status = item.status
            c_contributes = item.contributes_to_score
            c_needs_review = item.needs_review
        else:
            d = dict(item) if not isinstance(item, dict) else item
            c_type = d.get("commitment_type", "")
            c_status = d.get("status", "")
            c_contributes = bool(d.get("contributes_to_score", 1))
            c_needs_review = bool(d.get("needs_review", 0))

        # Tally types
        if c_type == "EXPLICIT_COMMITMENT":
            explicit_count += 1
        elif c_type == "FORWARD_GUIDANCE":
            forward_count += 1
        elif c_type == "STRATEGIC_INTENTION":
            strategic_count += 1
        elif c_type == "OPERATIONAL_MILESTONE":
            milestone_count += 1

        # Tally overall statuses
        if c_needs_review or c_status == "NEEDS_REVIEW":
            total_needs_review += 1
        elif c_status == "ACHIEVED":
            total_achieved += 1
        elif c_status == "PARTIALLY_ACHIEVED":
            total_partially_achieved += 1
        elif c_status == "DELAYED":
            total_delayed += 1
        elif c_status == "MISSED":
            total_missed += 1
        elif c_status == "IN_PROGRESS":
            total_in_progress += 1
        elif c_status == "UNVERIFIABLE":
            total_unverifiable += 1

        # Tally score-eligible statuses
        is_eligible = c_contributes and is_genuine_commitment(c_type)
        if is_eligible:
            eligible_count += 1
            if c_needs_review or c_status == "NEEDS_REVIEW":
                eligible_needs_review += 1
            elif c_status == "ACHIEVED":
                eligible_achieved += 1
            elif c_status == "PARTIALLY_ACHIEVED":
                eligible_partially_achieved += 1
            elif c_status == "DELAYED":
                eligible_delayed += 1
            elif c_status == "MISSED":
                eligible_missed += 1
            elif c_status == "IN_PROGRESS":
                eligible_in_progress += 1
            elif c_status == "UNVERIFIABLE":
                eligible_unverifiable += 1

    excluded_count = strategic_count + milestone_count
    eligible_evaluated_count = (
        eligible_achieved +
        eligible_partially_achieved +
        eligible_delayed +
        eligible_missed
    )

    if eligible_evaluated_count == 0:
        delivery_score = None
        score_label = (
            f"Insufficient evaluated evidence (0 of {eligible_count} eligible commitments evaluated; "
            f"{eligible_in_progress} in progress, {eligible_unverifiable} unverifiable, {eligible_needs_review} need review)"
        )
        stat_caveat = (
            f"No eligible commitments have concluded evaluation yet (0 of {eligible_count} evaluated). "
            f"Sample excludes {excluded_count} non-promissory items ({strategic_count} strategic intentions, "
            f"{milestone_count} historical operational milestones), {eligible_in_progress} active in-progress commitments, "
            f"and {eligible_unverifiable} unverifiable targets without subsequent primary-source disclosures. "
            "A delivery score cannot be reliably computed without evaluated milestones."
        )
    else:
        delivered_points = (eligible_achieved * 1.0) + (eligible_partially_achieved * 0.5)
        delivery_score = round((delivered_points / eligible_evaluated_count) * 100.0, 1)
        score_label = (
            f"{delivery_score:.1f}% ({delivered_points:g} of {eligible_evaluated_count} eligible evaluated commitments delivered; "
            f"{eligible_achieved} achieved, {eligible_partially_achieved} partial, "
            f"{eligible_delayed} delayed, {eligible_missed} missed)"
        )
        stat_caveat = (
            f"Delivery score is computed strictly from {eligible_evaluated_count} eligible evaluated commitments "
            f"({eligible_achieved} achieved, {delivery_score:.1f}% delivery). "
            f"Sample excludes {excluded_count} non-promissory items ({strategic_count} strategic intentions, "
            f"{milestone_count} historical operational milestones), {eligible_in_progress} active in-progress commitments, "
            f"and {eligible_unverifiable} unverifiable targets without subsequent primary-source disclosures. "
            "This sample size measures delivery on evaluated milestones only and does not imply a statistically reliable long-term track record."
        )

    methodology_note = (
        "Delivery score = (Eligible Achieved + 0.5 * Eligible Partially Achieved) / Eligible Evaluated Commitments. "
        "Strategic intentions, historical operational milestones, in-progress targets, unverifiable items, "
        "and items needing review are strictly excluded from the score denominator."
    )

    return TrackRecordSummary(
        total_commitments=total,
        explicit_commitments_count=explicit_count,
        forward_guidance_count=forward_count,
        strategic_intentions_count=strategic_count,
        operational_milestones_count=milestone_count,
        excluded_count=excluded_count,
        total_achieved_count=total_achieved,
        total_partially_achieved_count=total_partially_achieved,
        total_delayed_count=total_delayed,
        total_missed_count=total_missed,
        total_in_progress_count=total_in_progress,
        total_unverifiable_count=total_unverifiable,
        total_needs_review_count=total_needs_review,
        eligible_count=eligible_count,
        eligible_evaluated_count=eligible_evaluated_count,
        eligible_achieved_count=eligible_achieved,
        eligible_partially_achieved_count=eligible_partially_achieved,
        eligible_delayed_count=eligible_delayed,
        eligible_missed_count=eligible_missed,
        eligible_in_progress_count=eligible_in_progress,
        eligible_unverifiable_count=eligible_unverifiable,
        eligible_needs_review_count=eligible_needs_review,
        delivery_score=delivery_score,
        score_label=score_label,
        methodology_note=methodology_note,
        stat_caveat=stat_caveat,
    )
