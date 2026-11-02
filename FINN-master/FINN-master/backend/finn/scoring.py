"""Materiality score (0-100) and tiers. Every point is itemised so the UI can show the sum.

    score = BASE (what the filing is)
          + WEIGHT (how much of the portfolio it touches, max +8)
          + MARKET (did the stock react: volume +8, price +8, max +16)
          - CONFIDENCE penalty (if the classifier is unsure)
          then clamped by CAPS and GATES

Design rule: the filing itself must be material. Market reaction and portfolio weight can
reorder items and lift minor items within Know, but they can never promote a routine
filing into "Needs you". That is what the gates enforce:

  * Act needs: total >= 72  AND  base >= 60 (a high-impact event)  AND  classifier confidence >= 0.8
  * Routine compliance is capped at 30 (always Skim); Other and Needs review are capped at 45.
"""
from dataclasses import dataclass
from .classify import TAXONOMY

ACT, KNOW = 72, 38
ACT_MIN_BASE = 60
ACT_MIN_CONFIDENCE = 0.8
MARKET_ELIGIBLE_BASE = 30   # below this the event is too minor for weight/market to matter
MAX_WEIGHT_POINTS = 8
CAPS = {"routine_compliance": 30, "other": 45, "needs_review": 45}
NOT_ACT_CEILING = ACT - 3   # 69: top of Know when a gate blocks Act

# (category, subtype) -> (base, chip label). Subtype None = category default.
BASE: dict[tuple[str, str | None], tuple[int, str]] = {
    ("results", None): (75, "Results"), ("results", "outcome"): (82, "Results"),
    ("results", "integrated"): (68, "Quarterly integrated filing"),
    ("management_change", None): (45, "Management change"),
    ("management_change", "top_exit"): (85, "Senior exit"),
    ("management_change", "top_entry"): (72, "Senior appointment"),
    ("management_change", "director_exit"): (60, "Director exit"),
    ("management_change", "director_entry"): (50, "Director appointment"),
    ("management_change", "auditor_exit"): (62, "Auditor resigned"),
    ("management_change", "kmp_exit"): (40, "Compliance/secretary exit"),
    ("management_change", "kmp_entry"): (30, "Compliance/secretary appointment"),
    ("management_change", "change"): (45, "Management change"),
    ("m_and_a", None): (78, "M&A"), ("m_and_a", "deal"): (78, "M&A"),
    ("m_and_a", "open_offer"): (80, "Open offer"), ("m_and_a", "minor"): (38, "Minor corporate restructuring"),
    ("credit_rating", None): (35, "Credit rating"), ("credit_rating", "downgrade"): (80, "Rating downgrade"),
    ("credit_rating", "upgrade"): (52, "Rating upgrade"), ("credit_rating", "reaffirm"): (22, "Rating reaffirmed"),
    ("credit_rating", "assign"): (40, "Rating assigned"),
    ("litigation_regulatory", None): (62, "Litigation / regulatory"),
    ("litigation_regulatory", "order"): (66, "Regulatory order"),
    ("litigation_regulatory", "compliance_fine"): (40, "Late-filing style fine"),
    ("fund_raise", None): (62, "Fundraising"), ("fund_raise", "issue"): (62, "Fundraising"),
    ("corporate_action", None): (45, "Corporate action"), ("corporate_action", "dividend"): (55, "Dividend"),
    ("corporate_action", "record_date"): (40, "Record date"), ("corporate_action", "bonus"): (62, "Bonus issue"),
    ("corporate_action", "split"): (62, "Stock split"), ("corporate_action", "buyback"): (58, "Buyback"),
    ("shareholding_change", None): (26, "Shareholding change"),
    ("shareholding_change", "insider"): (24, "Insider trade"), ("shareholding_change", "sast"): (40, "Stake disclosure"),
    ("shareholding_change", "pledge_invoked"): (80, "Pledge invoked"),
    ("shareholding_change", "pledge_created"): (58, "Pledge created"),
    ("shareholding_change", "pledge_released"): (35, "Pledge released"),
    ("investor_events", None): (30, "Investor event"), ("investor_events", "transcript"): (48, "Call transcript"),
    ("investor_events", "presentation"): (45, "Investor presentation"),
    ("investor_events", "recording"): (30, "Call recording"), ("investor_events", "call_notice"): (24, "Call notice"),
    ("investor_events", "meet_schedule"): (18, "Investor meeting"), ("investor_events", "update"): (20, "Investor event"),
    ("board_meeting", None): (28, "Board meeting"), ("board_meeting", "outcome"): (28, "Board meeting outcome"),
    ("board_meeting", "intimation"): (24, "Board meeting notice"),
    ("board_meeting", "intimation_results"): (30, "Results date announced"),
    ("board_meeting", "intimation_fund_raise"): (34, "Board to consider fundraise"),
    ("board_meeting", "intimation_m_and_a"): (36, "Board to consider M&A"),
    ("board_meeting", "intimation_dividend"): (32, "Board to consider dividend"),
    ("board_meeting", "intimation_buyback"): (32, "Board to consider buyback"),
    ("business_update", None): (34, "Business update"), ("business_update", "press_release"): (32, "Press release"),
    ("business_update", "order_win"): (48, "Order win"), ("business_update", "capex"): (52, "Capacity / capex"),
    ("business_update", "agreement"): (36, "Agreement / MoU"),
    ("shareholder_meeting", None): (18, "Shareholder meeting"), ("shareholder_meeting", "voting_results"): (14, "Voting results"),
    ("shareholder_meeting", "postal_ballot"): (18, "Postal ballot"),
    ("routine_compliance", None): (8, "Routine compliance"), ("routine_compliance", "annual_report"): (22, "Annual report"),
    ("routine_compliance", "auditor_change"): (14, "Auditor appointment"),
    ("other", None): (20, "Other"), ("other", "clarification"): (26, "Exchange clarification"),
    ("needs_review", None): (22, "Needs review"),
}
SEVERE_WORDS = ("fraud", "default", "insolvency", "search and seizure", "sebi order", "winding up", "winding-up")


def base_for(category: str, subtype: str | None) -> tuple[int, str]:
    return (BASE.get((category, subtype)) or BASE.get((category, None))
            or (10, TAXONOMY.get(category, category)))


def tier_for(score: int) -> str:
    return "act" if score >= ACT else ("know" if score >= KNOW else "skim")


@dataclass
class Scored:
    score: int
    tier: str
    why: list[dict]
    breakdown: list[dict]
    gate: str | None = None
    base: int = 0


def score_announcement(category: str, subtype: str | None, text: str, weight: float,
                       move_pct: float | None, vol_x: float | None,
                       price_thr: float = 5.0, vol_thr: float = 2.0,
                       confidence: float = 1.0) -> Scored:
    base, label = base_for(category, subtype)
    rows = [{"label": label, "points": base, "kind": "base"}]
    chips = [{"label": label, "kind": "category"}]

    if category == "litigation_regulatory" and subtype != "compliance_fine" and any(
            w in (text or "").lower() for w in SEVERE_WORDS):
        rows.append({"label": "Severe wording (fraud, default, insolvency…)", "points": 12, "kind": "flag"})
        chips.append({"label": "Severe wording", "kind": "flag"})

    if confidence < 0.8:
        pen = -round((0.8 - confidence) * 50)
        if pen:
            rows.append({"label": f"Classifier only {confidence:.0%} sure", "points": pen, "kind": "confidence"})
            chips.append({"label": f"{confidence:.0%} sure", "kind": "flag"})

    if base >= MARKET_ELIGIBLE_BASE:
        wp = round(min(MAX_WEIGHT_POINTS, (weight / 9.0) * MAX_WEIGHT_POINTS))
        if wp:
            rows.append({"label": f"Holding is {weight:g}% of portfolio", "points": wp, "kind": "weight"})
            if weight >= 6:
                chips.append({"label": f"{weight:g}% of portfolio", "kind": "weight"})
        if vol_x is not None and vol_x >= vol_thr:
            rows.append({"label": f"Volume {vol_x:.1f}× its 20-day average", "points": 8, "kind": "market"})
            chips.append({"label": f"Volume {vol_x:.1f}×", "kind": "market"})
        elif vol_x is not None and vol_x >= 1.5:
            rows.append({"label": f"Volume {vol_x:.1f}× its 20-day average", "points": 3, "kind": "market"})
        if move_pct is not None and abs(move_pct) >= price_thr:
            rows.append({"label": f"Price {move_pct:+.1f}% that day", "points": 8, "kind": "market"})
            chips.append({"label": f"{move_pct:+.1f}% that day", "kind": "market"})
        elif move_pct is not None and abs(move_pct) >= 3:
            rows.append({"label": f"Price {move_pct:+.1f}% that day", "points": 4, "kind": "market"})
            chips.append({"label": f"{move_pct:+.1f}% that day", "kind": "market"})

    score = sum(r["points"] for r in rows)
    gate = None

    cap = CAPS.get(category)
    if cap is not None and score > cap:
        name = TAXONOMY.get(category, category).lower()
        rows.append({"label": f"Cap: {name} never ranks above {cap}", "points": cap - score, "kind": "cap"})
        score, gate = cap, f"{TAXONOMY.get(category, category)} filings are capped at {cap}."
    if score >= ACT:
        why_not = None
        if base < ACT_MIN_BASE:
            why_not = (f"The filing itself isn't high-impact (base {base} < {ACT_MIN_BASE}); "
                       "market moves and portfolio weight can't promote it.")
        elif confidence < ACT_MIN_CONFIDENCE:
            why_not = f"The classifier is only {confidence:.0%} sure; Needs you requires {ACT_MIN_CONFIDENCE:.0%}."
        if why_not:
            rows.append({"label": "Gate: held below Needs you", "points": NOT_ACT_CEILING - score, "kind": "cap"})
            score, gate = NOT_ACT_CEILING, why_not
    if score > 100:
        rows.append({"label": "Capped at 100", "points": 100 - score, "kind": "cap"})
        score = 100
    if score < 0:
        rows.append({"label": "Floor at 0", "points": -score, "kind": "cap"})
        score = 0

    assert sum(r["points"] for r in rows) == score  # the breakdown always sums to the score
    return Scored(score, tier_for(score), chips, rows, gate, base)


def rules_summary() -> dict:
    """Machine-readable description of the scoring, served at /api/scoring for the UI."""
    show = [("results", "outcome"), ("management_change", "top_exit"), ("credit_rating", "downgrade"),
            ("m_and_a", "deal"), ("shareholding_change", "pledge_invoked"), ("fund_raise", "issue"),
            ("corporate_action", "dividend"), ("investor_events", "transcript"),
            ("board_meeting", "intimation_results"), ("routine_compliance", None)]
    return {
        "formula": "base + portfolio weight (max +8) + market reaction (max +16) − low-confidence penalty, then gates",
        "thresholds": {"act": ACT, "know": KNOW},
        "gates": [
            f"Needs you requires a score of {ACT}+ and a high-impact filing (base {ACT_MIN_BASE}+).",
            f"The classifier must be {ACT_MIN_CONFIDENCE:.0%}+ sure to reach Needs you.",
            "Routine compliance never ranks above 30, so it always stays in the collapsed pile.",
            "Other and Needs-review filings never rank above 45.",
        ],
        "examples": [{"label": base_for(c, s)[1], "base": base_for(c, s)[0]} for c, s in show],
        "market_note": "Market points use the first end-of-day bar after the filing, so a price move can be coincidence.",
    }
