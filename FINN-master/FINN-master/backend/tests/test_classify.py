"""Classifier tests.

Label strings follow NSE's controlled `desc` vocabulary as closely as known, including the two
reported failures. They are NOT a dump of your database: run `python -m finn.cli export-fixtures`
and `pytest tests/test_real_fixtures.py` to check the invariants against your real filings.
"""
import pytest
from finn.classify import TAXONOMY, MIN_CONFIDENCE, classify

MGMT = "Change in Directors/ Key Managerial Personnel/ Auditor/ Compliance Officer/ Share Transfer Agent"
ANALYST = "Analysts/Institutional Investor Meet/Con. Call Updates"

CASES = [
    # --- the two reported failures
    (ANALYST, "Intimation of conference call to discuss the financial results for the quarter ended September 30, 2026", "investor_events", "call_notice"),
    ("Copy of Newspaper Publication", "Extract of unaudited financial results for the quarter ended September 30, 2026 published in newspapers", "routine_compliance", "newspaper_ad"),
    # --- results vs. things that merely mention results
    ("Financial Results", "Unaudited financial results for the quarter ended", "results", "outcome"),
    ("Integrated Filing- Financial", "Integrated filing for the quarter ended", "results", "integrated"),
    ("Outcome of Board Meeting", "The Board approved the unaudited standalone and consolidated financial results for the quarter ended", "results", "outcome"),
    ("Board Meeting Intimation", "to consider and approve the unaudited financial results for the quarter ended", "board_meeting", "intimation_results"),
    ("Investor Presentation", "Presentation on results for the quarter", "investor_events", "presentation"),
    (ANALYST, "Transcript of the earnings call held on", "investor_events", "transcript"),
    (ANALYST, "Audio recording of the earnings call", "investor_events", "recording"),
    (ANALYST, "Schedule of one-on-one meetings with institutional investors", "investor_events", "meet_schedule"),
    ("Clarification - Financial Results", "Clarification on financial results sought by exchange", "other", "clarification"),
    # --- management
    ("Announcement under Regulation 30 (LODR)-Change in Management", "Resignation of Chief Financial Officer", "management_change", "top_exit"),
    (MGMT, "Appointment of Mr X as Chief Executive Officer", "management_change", "top_entry"),
    (MGMT, "Resignation of Mr Y as Independent Director", "management_change", "director_exit"),
    (MGMT, "Resignation of Company Secretary and Compliance Officer", "management_change", "kmp_exit"),
    (MGMT, "Appointment of Statutory Auditors of the company", "routine_compliance", "auditor_change"),
    (MGMT, "Resignation of Statutory Auditor of the Company", "management_change", "auditor_exit"),
    # --- M&A / corporate actions / fundraising
    ("Acquisition", "Acquisition of 100% stake in ABC Pvt Ltd", "m_and_a", "deal"),
    ("Incorporation of wholly owned subsidiary", "Incorporation of a wholly owned subsidiary", "m_and_a", "minor"),
    ("Dividend", "Interim dividend of Rs 10 per share declared", "corporate_action", "dividend"),
    ("Dividend", "Transfer of unclaimed dividend to IEPF", "routine_compliance", "iepf"),
    ("Record Date", "Record date for interim dividend", "corporate_action", "record_date"),
    ("Bonus", "Issue of bonus shares in ratio 1:1", "corporate_action", "bonus"),
    ("Buyback", "Buyback of equity shares", "corporate_action", "buyback"),
    ("Outcome of Board Meeting", "Board approved fund raising by issue of NCDs up to Rs 5000 crore", "fund_raise", None),
    ("Allotment of Securities", "Allotment of equity shares pursuant to ESOP scheme", "routine_compliance", "esop"),
    ("Allotment of Securities", "Allotment of non-convertible debentures on private placement basis", "fund_raise", None),
    # --- litigation / shareholding / rating
    ("Action(s) initiated or orders passed", "SEBI order against the company for fraud", "litigation_regulatory", "order"),
    ("Action(s) initiated or orders passed", "Fine for delay in submission of financial results under Regulation 33", "litigation_regulatory", "compliance_fine"),
    ("Disclosure under SEBI Takeover Regulations", "Invocation of pledge on promoter shares", "shareholding_change", "pledge_invoked"),
    ("Disclosure under SEBI Takeover Regulations", "Disclosure under Regulation 29 of SEBI SAST", "shareholding_change", "sast"),
    ("Disclosure under SEBI Insider Trading Regulation", "Disclosure under Regulation 7(2)", "shareholding_change", "insider"),
    ("Announcement under Regulation 30 (LODR)-Credit Rating", "CRISIL has downgraded the long term rating", "credit_rating", "downgrade"),
    ("Credit Rating", "ICRA reaffirmed the rating", "credit_rating", "reaffirm"),
    # --- routine compliance
    ("Trading Window", "Closure of trading window", "routine_compliance", "trading_window"),
    ("Reg. 34 (1) Annual Report.", "Annual report for FY26", "routine_compliance", "annual_report"),
    ("Integrated Filing- Governance", "Corporate governance report", "routine_compliance", "governance"),
    ("Shareholding Pattern", "Shareholding pattern for the quarter", "routine_compliance", "shareholding_pattern"),
    ("Loss of Share Certificates", "Loss of share certificate", "routine_compliance", "share_certificate"),
    ("Compliances-Reg. 24(A)- Annual Secretarial Compliance", "Annual secretarial compliance report", "routine_compliance", None),
    # --- other business / meetings
    ("Press Release", "Company bags order worth Rs 2,000 crore", "business_update", "order_win"),
    ("Press Release", "Company launches new product range", "business_update", "press_release"),
    ("Postal Ballot", "Notice of postal ballot", "shareholder_meeting", "postal_ballot"),
    ("Outcome of Board Meeting", "Board met and took note of routine matters", "board_meeting", "outcome"),
    # --- generic and unknown labels
    ("Updates", "", "other", None),
    ("Updates", "Resignation of Chief Financial Officer with effect from", "management_change", "top_exit"),
    ("Brand New NSE Label", "something unusual happened", "needs_review", None),
    ("Allotment of Securities", "", "needs_review", None),
]

@pytest.mark.parametrize("desc,text,cat,sub", CASES)
def test_classify(desc, text, cat, sub):
    r = classify(desc, text)
    assert r.category == cat, f"{desc!r} -> {r}"
    if sub:
        assert r.subtype == sub, f"{desc!r} -> {r}"

def test_every_category_is_in_the_taxonomy_and_all_required_types_exist():
    assert {x[2] for x in CASES} <= set(TAXONOMY)
    required = {"results", "investor_events", "management_change", "m_and_a", "board_meeting", "corporate_action",
                "fund_raise", "litigation_regulatory", "shareholding_change", "routine_compliance", "other", "needs_review"}
    assert required <= set(TAXONOMY)

def test_body_text_can_never_override_a_specific_label():
    # A specific label stays put however much the body talks about other things.
    for label, expected in [("Copy of Newspaper Publication", "routine_compliance"),
                            (ANALYST, "investor_events"), ("Trading Window", "routine_compliance")]:
        body = "Unaudited financial results for the quarter ended; resignation of Chief Financial Officer; acquisition of ABC"
        assert classify(label, body).category == expected

def test_low_confidence_always_becomes_needs_review():
    for desc, text in [("Allotment of Securities", ""), ("???", ""), ("Weird Label", "nothing here")]:
        r = classify(desc, text)
        assert r.category == "needs_review"
    # and a needs_review result keeps its best guess for the human reviewer
    assert "best guess" in classify("Allotment of Securities", "").reason

def test_confidence_is_reported_and_bounded():
    for desc, text, *_ in CASES:
        r = classify(desc, text)
        assert 0 <= r.confidence <= 1
        assert r.category == "needs_review" or r.confidence >= MIN_CONFIDENCE
