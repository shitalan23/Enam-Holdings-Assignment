"""Invariant checks against REAL announcement descriptions exported from your own database.

Create the fixture on your machine:   python -m finn.cli export-fixtures
This test is skipped when the fixture file doesn't exist (e.g. in a fresh clone or CI).
"""
import json, re
from pathlib import Path
import pytest
from finn.classify import MIN_CONFIDENCE, TAXONOMY, classify, clean_label

FIX = Path(__file__).parent / "fixtures" / "real_announcements.json"
pytestmark = pytest.mark.skipif(not FIX.exists(), reason="no fixture: run `python -m finn.cli export-fixtures` first")

def rows():
    return json.loads(FIX.read_text())

def test_every_real_filing_gets_a_valid_confident_or_flagged_result():
    for r in rows():
        c = classify(r["desc"], r["text"])
        assert c.category in TAXONOMY, r["desc"]
        assert 0 <= c.confidence <= 1
        assert c.category == "needs_review" or c.confidence >= MIN_CONFIDENCE, (r["desc"], c)

def test_newspaper_and_investor_labels_are_never_results():
    for r in rows():
        lab = clean_label(r["desc"]).lower()
        c = classify(r["desc"], r["text"])
        if "newspaper" in lab:
            assert c.category == "routine_compliance", (r["desc"], c)
        if re.search(r"investor|analyst|con\.? ?call|transcript|presentation", lab):
            assert c.category != "results", (r["desc"], c)
            assert c.category in ("investor_events", "needs_review", "other"), (r["desc"], c)

def test_results_only_come_from_results_labels_or_board_outcomes():
    for r in rows():
        lab = clean_label(r["desc"]).lower()
        if classify(r["desc"], r["text"]).category == "results":
            assert re.search(r"result|integrated filing|outcome of board", lab), r["desc"]

def test_needs_review_share_is_reasonable():
    rs = rows()
    share = sum(classify(r["desc"], r["text"]).category == "needs_review" for r in rs) / len(rs)
    assert share <= 0.4, f"{share:.0%} of real filings need review: extend the label rules (run review-classification)"
