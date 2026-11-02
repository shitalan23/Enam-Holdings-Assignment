import pytest
from finn.classify_v1 import classify
from finn.scoring_v1 import score_announcement

CASES = [
    # (desc, text, expected_category, expected_subtype or None-to-skip)
    ("Financial Results", "Unaudited financial results for the quarter ended September 30, 2026", "results", "outcome"),
    ("Board Meeting Intimation", "Intimation of board meeting to consider and approve financial results for the quarter ended", "results", "intimation"),
    ("Outcome of Board Meeting", "Board approved unaudited financial results; also declared interim dividend of Rs 10", "results", "outcome"),
    ("Change in Directors/Key Managerial Personnel", "Resignation of Chief Financial Officer with effect from", "management_change", "top_exit"),
    ("Appointment", "Appointment of Mr X as Chief Executive Officer", "management_change", "top_entry"),
    ("Appointment", "Appointment of Statutory Auditors of the company", None, None),  # must NOT be mgmt change
    ("Resignation", "Resignation of Company Secretary and Compliance Officer", "management_change", "kmp_exit"),
    ("Credit Rating", "CRISIL has downgraded the long term rating", "credit_rating", "downgrade"),
    ("Credit Rating", "ICRA reaffirmed the rating", "credit_rating", "reaffirm"),
    ("Allotment of Securities", "Allotment of equity shares pursuant to ESOP scheme", None, None),  # ESOP: not fund_raise
    ("Analysts/Institutional Investor Meet/Con. Call Updates", "Schedule of one-on-one meetings with investors", "investor_meetings", None),
    ("Analysts/Institutional Investor Meet/Con. Call Updates", "Transcript of earnings call for Q2", "earnings_call", None),
    ("Dividend", "Transfer of unclaimed dividend to IEPF", None, None),  # routine, not dividend
    ("Acquisition", "Acquisition of 100% stake in ABC Pvt Ltd", "M&A", None),
    ("Disclosure under SEBI Takeover Regulations", "Disclosure under Regulation 29 of SEBI SAST", None, None),
    ("Pledging", "Invocation of pledge on promoter shares", "pledging", "invoked"),
    ("Press Release", "Company bags order worth Rs 2,000 crore", "press_release", None),
    ("Postal Ballot", "Notice of postal ballot", "postal_ballot", None),
    ("Trading Window", "Closure of trading window", "unclassified", "routine"),
    ("Litigation", "Show cause notice received from SEBI", "litigation", None),
]

@pytest.mark.parametrize("desc,text,cat,sub", CASES)
def test_classify(desc, text, cat, sub):
    r = classify(desc, text)
    if cat is None:
        assert r.category in ("unclassified", "press_release", "postal_ballot"), r
        assert r.category not in ("management_change", "fund_raise", "dividend", "M&A"), r
    else:
        assert r.category == cat, r
        if sub:
            assert r.subtype == sub, r

def test_tiers():
    # Senior exit at a big holding with a volume spike -> Act
    s = score_announcement("management_change", "top_exit", "", 9, -4.2, 2.6)
    assert s.tier == "act", s
    # Routine ESOP-style filing never escapes Skim
    assert score_announcement("unclassified", None, "", 9, 8.0, 5.0).tier == "skim"
    # Results outcome is Act; results date notice is not
    assert score_announcement("results", "outcome", "", 5, None, None).tier == "act"
    assert score_announcement("results", "intimation", "", 5, None, None).tier != "act"
    # Reaffirmed rating stays Skim, downgrade is Act
    assert score_announcement("credit_rating", "reaffirm", "", 5, None, None).tier == "skim"
    assert score_announcement("credit_rating", "downgrade", "", 5, None, None).tier == "act"
