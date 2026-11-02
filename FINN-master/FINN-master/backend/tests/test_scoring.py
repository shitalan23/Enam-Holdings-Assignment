import itertools
import pytest
from finn.scoring import (ACT, KNOW, ACT_MIN_BASE, ACT_MIN_CONFIDENCE, BASE, CAPS,
                          score_announcement, tier_for)

WEIGHTS = [0, 2, 6, 9]
MOVES = [None, 0.5, 3.5, -6.0, 9.0]
VOLS = [None, 1.0, 1.7, 3.5]
CONFS = [0.2, 0.6, 0.79, 0.8, 0.95, 1.0]

def sweep():
    for (cat, sub) in BASE:
        for w, m, v, c in itertools.product(WEIGHTS, MOVES, VOLS, CONFS):
            yield cat, sub, w, m, v, c, score_announcement(cat, sub, "", w, m, v, confidence=c)

def test_breakdown_always_sums_exactly_to_the_score():
    n = 0
    for cat, sub, w, m, v, c, s in sweep():
        assert sum(r["points"] for r in s.breakdown) == s.score, (cat, sub, w, m, v, c)
        assert 0 <= s.score <= 100
        n += 1
    assert n > 5000  # the sweep really ran

def test_act_requires_a_high_impact_filing_and_a_confident_classifier():
    for cat, sub, w, m, v, c, s in sweep():
        if s.tier == "act":
            assert s.base >= ACT_MIN_BASE, (cat, sub, s)
            assert c >= ACT_MIN_CONFIDENCE, (cat, sub, c)
            assert s.score >= ACT

def test_routine_other_and_needs_review_cannot_dominate():
    for cat, sub, w, m, v, c, s in sweep():
        if cat in CAPS:
            assert s.score <= CAPS[cat], (cat, sub, s.score)
            assert s.tier != "act"
        if cat == "routine_compliance":
            assert s.tier == "skim"   # routine paperwork never leaves the collapsed pile

def test_market_reaction_and_weight_cannot_promote_a_minor_filing_to_act():
    # Heaviest holding, 9% move, 3.5x volume: a dividend or a results-date notice still isn't "Needs you"
    for cat, sub in [("corporate_action", "dividend"), ("board_meeting", "intimation_results"),
                     ("investor_events", "transcript"), ("business_update", "order_win"),
                     ("shareholding_change", "insider"), ("credit_rating", "reaffirm")]:
        s = score_announcement(cat, sub, "", 9, 9.0, 3.5)
        assert s.tier != "act", (cat, sub, s.score)
        assert s.gate or s.score < ACT

def test_the_events_that_should_need_you_do():
    cases = [("results", "outcome"), ("management_change", "top_exit"), ("credit_rating", "downgrade"),
             ("m_and_a", "deal"), ("shareholding_change", "pledge_invoked")]
    for cat, sub in cases:
        assert score_announcement(cat, sub, "", 2, None, None).tier == "act", (cat, sub)

def test_low_confidence_blocks_needs_you_and_is_visible_in_the_breakdown():
    sure = score_announcement("management_change", "top_exit", "", 6, None, None, confidence=0.95)
    unsure = score_announcement("management_change", "top_exit", "", 6, None, None, confidence=0.62)
    assert sure.tier == "act" and unsure.tier != "act"
    assert any(r["kind"] == "confidence" for r in unsure.breakdown)
    assert unsure.gate

def test_gate_explanation_is_present_whenever_a_gate_blocks_act():
    s = score_announcement("corporate_action", "dividend", "", 9, 9.0, 3.5)  # raw would be >= 72
    assert s.tier == "know" and s.gate and any(r["label"].startswith("Gate") for r in s.breakdown)

def test_market_points_are_not_awarded_to_trivial_filings():
    s = score_announcement("routine_compliance", "newspaper_ad", "", 9, 9.0, 3.5)
    assert not any(r["kind"] in ("market", "weight") for r in s.breakdown)

def test_tier_boundaries():
    assert tier_for(ACT) == "act" and tier_for(ACT - 1) == "know"
    assert tier_for(KNOW) == "know" and tier_for(KNOW - 1) == "skim"

def test_severe_wording_only_lifts_real_regulatory_orders():
    order = score_announcement("litigation_regulatory", "order", "SEBI order fraud", 5, None, None)
    fine = score_announcement("litigation_regulatory", "compliance_fine", "fraud", 5, None, None)
    assert any(r["kind"] == "flag" for r in order.breakdown) and order.tier == "act"
    assert not any(r["kind"] == "flag" for r in fine.breakdown) and fine.tier != "act"
