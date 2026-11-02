"""Deterministic materiality score (0-100) and the three tiers shown in the Brief.

Why not ask an LLM to rank? Because a ranking you can't explain is a ranking an
investor can't trust. Every point here maps to a chip the user can see:
category/subtype -> base score, then portfolio weight and the market's own
reaction (price move, volume spike) nudge it. Tiers: Act >= 70, Know >= 35.
"""
from dataclasses import dataclass

BASE = {
    "results": 80, "M&A": 78, "litigation": 66, "management_change": 58,
    "fund_raise": 62, "credit_rating": 38, "pledging": 58, "bonus_split": 55,
    "capex": 52, "dividend": 50, "earnings_call": 42, "press_release": 30,
    "insider_trading": 28, "investor_meetings": 14, "agm_egm": 18,
    "postal_ballot": 15, "unclassified": 5,
}
# (category, subtype) -> delta
SUBTYPE_DELTA = {
    ("results", "intimation"): -40,
    ("dividend", "intimation"): -15,
    ("fund_raise", "intimation"): -15,
    ("earnings_call", "intimation"): -20,
    ("agm_egm", "outcome"): -5,
    ("management_change", "top_exit"): +27,
    ("management_change", "top_entry"): +17,
    ("management_change", "kmp_exit"): -25,
    ("management_change", "kmp_entry"): -28,
    ("credit_rating", "downgrade"): +45,
    ("credit_rating", "upgrade"): +20,
    ("credit_rating", "reaffirm"): -15,
    ("pledging", "invoked"): +25,
    ("pledging", "released"): -22,
    ("unclassified", "routine"): -5,
}
SUBTYPE_LABEL = {
    ("results", "intimation"): "Results date notice",
    ("results", "outcome"): "Results",
    ("management_change", "top_exit"): "Senior exit",
    ("management_change", "top_entry"): "Senior appointment",
    ("management_change", "director_exit"): "Director exit",
    ("management_change", "director_entry"): "Director appointment",
    ("management_change", "kmp_exit"): "Compliance/secretarial exit",
    ("management_change", "kmp_entry"): "Compliance/secretarial appointment",
    ("credit_rating", "downgrade"): "Rating downgrade",
    ("credit_rating", "upgrade"): "Rating upgrade",
    ("credit_rating", "reaffirm"): "Rating reaffirmed",
    ("pledging", "invoked"): "Pledge invoked",
    ("pledging", "released"): "Pledge released",
}
CATEGORY_LABEL = {
    "results": "Results", "M&A": "M&A", "fund_raise": "Fund raise",
    "management_change": "Management change", "litigation": "Litigation / regulatory",
    "insider_trading": "Insider trade", "earnings_call": "Earnings call",
    "investor_meetings": "Investor meeting", "credit_rating": "Credit rating",
    "dividend": "Dividend", "bonus_split": "Bonus / split", "capex": "Capex",
    "press_release": "Press release", "postal_ballot": "Postal ballot",
    "agm_egm": "AGM / EGM", "pledging": "Pledging", "unclassified": "Routine filing",
}
SEVERE_WORDS = ("fraud", "default", "insolvency", "search and seizure", "sebi order", "winding up", "winding-up")

ACT, KNOW = 70, 35


@dataclass
class Scored:
    score: int
    tier: str
    why: list[dict]


def tier_for(score: int) -> str:
    return "act" if score >= ACT else ("know" if score >= KNOW else "skim")


def score_announcement(category: str, subtype: str | None, text: str, weight: float,
                       move_pct: float | None, vol_x: float | None,
                       price_thr: float = 5.0, vol_thr: float = 2.0) -> Scored:
    s = BASE.get(category, 5)
    why: list[dict] = []
    label = SUBTYPE_LABEL.get((category, subtype)) or CATEGORY_LABEL.get(category, category)
    why.append({"label": label, "kind": "category"})
    s += SUBTYPE_DELTA.get((category, subtype), 0)

    low = (text or "").lower()
    if category == "litigation" and any(w in low for w in SEVERE_WORDS):
        s += 12
        why.append({"label": "Severe wording", "kind": "flag"})

    if category != "unclassified":
        bump = round(min(10.0, (weight / 9.0) * 10.0))
        s += bump
        if weight >= 6:
            why.append({"label": f"{weight:g}% of portfolio", "kind": "weight"})

        if vol_x is not None and vol_x >= vol_thr:
            s += 10
            why.append({"label": f"Volume {vol_x:.1f}×", "kind": "market"})
        elif vol_x is not None and vol_x >= 1.5:
            s += 4
        if move_pct is not None and abs(move_pct) >= price_thr:
            s += 10
            why.append({"label": f"{move_pct:+.1f}% that day", "kind": "market"})
        elif move_pct is not None and abs(move_pct) >= 3:
            s += 5
            why.append({"label": f"{move_pct:+.1f}% that day", "kind": "market"})

    s = max(0, min(100, s))
    return Scored(s, tier_for(s), why)
