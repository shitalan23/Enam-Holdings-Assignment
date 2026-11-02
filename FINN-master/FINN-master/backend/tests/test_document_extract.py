"""Unit tests for Annual Report and Concall Transcript intelligence extraction.

Tests layout-aware and stream-aware extraction against primary official documents:
1. data/documents/RELIANCE/reliance_integrated_annual_report_2025_26.pdf
2. data/documents/RELIANCE/reliance_concall_transcript_q2_fy26.pdf
"""
import pytest
from pathlib import Path

from finn.config import ROOT
from finn.annual_report_extract import (
    DEFAULT_AR_PATH,
    RELIANCE_AR_URL,
    RELIANCE_AR_TITLE,
    _extract_pages_layout as _ar_pages_layout,
    _extract_pages_text as _ar_pages_text,
    extract_reliance_annual_report,
    extract_mda_strategy_evidence,
    extract_risk_management_evidence,
    extract_auditors_report_evidence,
    extract_debt_and_notes_evidence,
)
from finn.transcript_extract import (
    DEFAULT_CONCALL_PATH,
    RELIANCE_CONCALL_URL,
    RELIANCE_CONCALL_TITLE,
    _extract_pages_layout as _concall_pages_layout,
    extract_reliance_concall_transcript,
    parse_call_participants,
    parse_concall_turns,
)
from finn.document_models import DocumentType, SpeakerRole, StatementType


@pytest.fixture(scope="module")
def check_primary_docs_exist():
    assert DEFAULT_AR_PATH.exists(), f"Annual Report missing at {DEFAULT_AR_PATH}"
    assert DEFAULT_CONCALL_PATH.exists(), f"Concall transcript missing at {DEFAULT_CONCALL_PATH}"


# =============================================================================
# Annual Report Extraction Tests
# =============================================================================
class TestAnnualReportExtraction:

    def test_annual_report_total_claims_and_uniqueness(self, check_primary_docs_exist):
        claims = extract_reliance_annual_report()
        assert len(claims) >= 20, f"Expected at least 20 AR claims, got {len(claims)}"

        # Check unique IDs
        claim_ids = [c.id for c in claims]
        assert len(claim_ids) == len(set(claim_ids)), "Duplicate claim IDs detected"

        # Check all claims belong to RELIANCE and point to official URL
        for c in claims:
            assert c.symbol == "RELIANCE"
            assert c.doc_type == DocumentType.ANNUAL_REPORT.value
            assert c.official_url == RELIANCE_AR_URL
            assert c.page >= 1 and c.page <= 147
            assert len(c.verbatim_text) > 20
            assert len(c.claim) > 10

    def test_mda_and_strategy_sections(self, check_primary_docs_exist):
        claims = extract_mda_strategy_evidence(DEFAULT_AR_PATH)
        assert len(claims) >= 10

        sections = {c.section for c in claims}
        assert any("Chairman" in s for s in sections)
        assert any("10-Year" in s for s in sections)
        assert any("Retail" in s for s in sections)
        assert any("Digital Services" in s for s in sections)
        assert any("Oil to Chemicals" in s for s in sections)
        assert any("Oil and Gas" in s for s in sections)
        assert any("New Energy" in s for s in sections)

        # Chairman statement verification
        cm_claim = next(c for c in claims if c.page == 4)
        assert cm_claim.speaker_name == "Mukesh D. Ambani"
        assert "first Indian company to cross $10 billion in annual net profit" in cm_claim.verbatim_text

        # New energy forward guidance verification
        solar_claim = next(c for c in claims if c.page == 15 and "Solar PV" in c.verbatim_text)
        assert solar_claim.statement_type == StatementType.FORWARD_GUIDANCE.value
        assert "10 GWp" in solar_claim.verbatim_text
        assert solar_claim.confidence == 1.0

        bess_claim = next(c for c in claims if c.page == 15 and "40 GWh" in c.verbatim_text)
        assert bess_claim.statement_type == StatementType.FORWARD_GUIDANCE.value
        assert "40 GWh" in bess_claim.verbatim_text
        assert bess_claim.confidence == 1.0

    def test_risk_management_extraction(self, check_primary_docs_exist):
        claims = extract_risk_management_evidence(DEFAULT_AR_PATH)
        assert len(claims) >= 4

        for c in claims:
            assert c.statement_type == StatementType.RISK_DISCLOSURE.value
            assert c.page in (15, 16)
            assert "Risk and Governance" in c.section

        # Check key risk domains
        claim_texts = " ".join(c.verbatim_text for c in claims)
        assert "Climate Change and Energy Transition" in claim_texts
        assert "Health, Safety and Environmental (HSE) Risks" in claim_texts
        assert "Foreign Exchange Risk" in claim_texts
        assert "Cybersecurity" in claim_texts

    def test_auditors_report_extraction(self, check_primary_docs_exist):
        claims = extract_auditors_report_evidence(DEFAULT_AR_PATH)
        assert len(claims) >= 4

        # 1. Unmodified opinion
        op_claim = next(c for c in claims if "Auditor Opinion" in c.section or c.page == 94)
        assert op_claim.statement_type == StatementType.AUDITOR_OBSERVATION.value
        assert op_claim.speaker_role == SpeakerRole.AUDITOR.value
        assert "Deloitte Haskins & Sells" in op_claim.speaker_name
        assert "Chaturvedi & Shah" in op_claim.speaker_name
        assert "true and fair view in conformity with the Indian Accounting Standards" in op_claim.verbatim_text

        # 2. Key Audit Matters (Litigations, JDFPL Fair Value, Revenue Recognition)
        kam_claims = [c for c in claims if "Key Audit Matters" in c.section]
        assert len(kam_claims) >= 3

        kam_texts = " ".join(c.verbatim_text for c in kam_claims)
        assert "Litigation matters" in kam_texts
        assert "77,852" in kam_texts  # JDFPL Preference Shares
        assert "Revenue Recognition" in kam_texts

    def test_balance_sheet_and_notes_extraction(self, check_primary_docs_exist):
        claims = extract_debt_and_notes_evidence(DEFAULT_AR_PATH)
        assert len(claims) >= 4

        # Consolidated Balance sheet total (P.100)
        bs_claim = next(c for c in claims if c.page == 100)
        assert "21,78,140" in bs_claim.verbatim_text
        assert "10,85,866" in bs_claim.verbatim_text

        # Note 16 Borrowings (P.113)
        b_claim = next(c for c in claims if c.page == 113)
        assert "2,70,751" in b_claim.verbatim_text
        assert "20,545" in b_claim.verbatim_text

        # Note 17 Spectrum Liabilities (P.114)
        spec_claim = next(c for c in claims if c.page == 114)
        assert "73,425" in spec_claim.verbatim_text

        # Note 34 Capital Commitments (P.124)
        comm_claim = next(c for c in claims if c.page == 124)
        assert "61,642" in comm_claim.verbatim_text
        assert "4,875" in comm_claim.verbatim_text

    def test_ar_verbatim_page_attribution(self, check_primary_docs_exist):
        """Audit that every claim's key verbatim phrase strictly exists on the declared PDF page."""
        import re
        claims = extract_reliance_annual_report()

        def clean(s):
            return re.sub(r"[^\w\s]", " ", s).lower()

        for c in claims:
            # Test stream or layout text on c.page
            stream_page = _ar_pages_text(DEFAULT_AR_PATH, c.page, c.page)[0]
            layout_page = _ar_pages_layout(DEFAULT_AR_PATH, c.page, c.page)[0]

            combined_norm = " ".join(clean(stream_page + " " + layout_page).split())

            words = clean(c.verbatim_text).split()[:4]
            anchor = " ".join(words)
            assert anchor in combined_norm, (
                f"Page attribution failed on P.{c.page}: anchor '{anchor}' not found on page. "
                f"Section: {c.section}"
            )


# =============================================================================
# Concall Transcript Extraction Tests
# =============================================================================
class TestConcallTranscriptExtraction:

    def test_participant_roster_parsing(self, check_primary_docs_exist):
        p1_text = _concall_pages_layout(DEFAULT_CONCALL_PATH, 1, 1)[0]
        participants = parse_call_participants(p1_text)

        # Must parse all 8 official executive participants
        assert len(participants) == 8, f"Expected 8 participants, got {len(participants)}"

        assert "Sh V Srikanth" in participants
        assert "CFO" in participants["Sh V Srikanth"].designation
        assert "Reliance Industries Limited" in participants["Sh V Srikanth"].organization

        assert "Sh Anshuman Thakur" in participants
        assert "Strategy" in participants["Sh Anshuman Thakur"].designation

        assert "Sh Dinesh Taluja" in participants
        assert "Retail" in participants["Sh Dinesh Taluja"].organization or "Retail" in participants["Sh Dinesh Taluja"].designation

        assert "Sh Sriram Ramakrishnan" in participants
        assert "Battery" in participants["Sh Sriram Ramakrishnan"].organization or "Battery" in participants["Sh Sriram Ramakrishnan"].designation

        assert "Sh Amit Chaturvedi" in participants
        assert "Petrochemicals" in participants["Sh Amit Chaturvedi"].organization or "Petrochemicals" in participants["Sh Amit Chaturvedi"].designation

    def test_concall_turn_parsing(self, check_primary_docs_exist):
        p1_text = _concall_pages_layout(DEFAULT_CONCALL_PATH, 1, 1)[0]
        participants = parse_call_participants(p1_text)

        turns = parse_concall_turns(DEFAULT_CONCALL_PATH, participants, 1, 36)
        assert len(turns) >= 50, f"Expected 50+ turns, parsed {len(turns)}"

        # Check presentation vs Q&A
        pres_turns = [t for t in turns if t.section == "PRESENTATION"]
        qa_turns = [t for t in turns if t.section == "Q&A"]

        assert len(pres_turns) >= 8
        assert len(qa_turns) >= 40

        # Check speaker role assignment
        analyst_turns = [t for t in turns if t.speaker_role == SpeakerRole.ANALYST.value]
        management_turns = [t for t in turns if t.speaker_role == SpeakerRole.MANAGEMENT.value]

        assert len(analyst_turns) >= 15
        assert len(management_turns) >= 30

    def test_concall_claims_and_evidence(self, check_primary_docs_exist):
        claims = extract_reliance_concall_transcript()
        assert len(claims) >= 12

        # Check claim IDs uniqueness
        ids = [c.id for c in claims]
        assert len(ids) == len(set(ids)), "Duplicate claim IDs detected"

        # Check statement types
        types = {c.statement_type for c in claims}
        assert StatementType.FORWARD_GUIDANCE.value in types
        assert StatementType.FINANCIAL_COMMENTARY.value in types
        assert StatementType.ANALYST_QUESTION.value in types
        assert StatementType.BUSINESS_STRATEGY.value in types

    def test_forward_guidance_and_timelines(self, check_primary_docs_exist):
        claims = extract_reliance_concall_transcript()
        guidance_claims = [c for c in claims if c.statement_type == StatementType.FORWARD_GUIDANCE.value]

        assert len(guidance_claims) >= 5

        # PV cell line startup next month (P.21)
        pv_claim = next(c for c in guidance_claims if c.page == 21)
        assert pv_claim.speaker_name == "Sh Sriram Ramakrishnan"
        assert "first line will be commissioned as I was telling you next month" in pv_claim.verbatim_text
        assert pv_claim.confidence == 1.0
        assert not pv_claim.needs_review

        # 40 GWh Battery gigafactory early next year (P.22)
        bess_claim = next(c for c in guidance_claims if c.page == 22 and "40 gigawatt" in c.verbatim_text)
        assert "early next year" in bess_claim.verbatim_text
        assert "40 gigawatt hours" in bess_claim.verbatim_text
        assert bess_claim.confidence == 1.0
        assert not bess_claim.needs_review

        # PVC project target completion next year end (P.34)
        pvc_claim = next(c for c in guidance_claims if c.page == 34 and "Amit Chaturvedi" in (c.speaker_name or ""))
        assert "target is to complete them by next year, next year end" in pvc_claim.verbatim_text

        # Quick commerce 30-minute delivery (P.36)
        qc_claim = next(c for c in guidance_claims if c.page == 36)
        assert "30-minute timeline" in qc_claim.verbatim_text
        assert qc_claim.speaker_name == "Sh Dinesh Taluja"

    def test_ambiguous_evidence_detection(self, check_primary_docs_exist):
        """Verify ambiguous guidance or management divergence is cleanly flagged with needs_review=True."""
        claims = extract_reliance_concall_transcript()

        # 1. Vague tariff response on P.22 ("will happen when they will happen")
        tariff_claim = next(c for c in claims if c.page == 22 and "will happen when they will happen" in c.verbatim_text)
        assert tariff_claim.needs_review is True
        assert "Vague forward statement" in (tariff_claim.review_reason or "")
        assert tariff_claim.confidence < 0.9

        # 2. CFO qualification on PVC timeline on P.34 ("take it as his personal target")
        cfo_qual_claim = next(c for c in claims if c.page == 34 and "personal target" in c.verbatim_text)
        assert cfo_qual_claim.needs_review is True
        assert "Management divergence" in (cfo_qual_claim.review_reason or "")
        assert cfo_qual_claim.speaker_name == "Sh V. Srikanth"

    def test_concall_verbatim_page_attribution(self, check_primary_docs_exist):
        """Audit that every concall claim's key verbatim phrase strictly exists on the declared PDF page."""
        import re
        claims = extract_reliance_concall_transcript()

        def clean(s):
            return re.sub(r"[^\w\s]", " ", s).lower()

        for c in claims:
            page_text = _concall_pages_layout(DEFAULT_CONCALL_PATH, c.page, c.page)[0]
            norm_page = " ".join(clean(page_text).split())

            words = clean(c.verbatim_text).split()[:4]
            anchor = " ".join(words)
            assert anchor in norm_page, (
                f"Concall page attribution failed on P.{c.page}: anchor '{anchor}' not found on page. "
                f"Speaker: {c.speaker_name}, Section: {c.section}"
            )


# =============================================================================
# Error Handling and Edge Cases
# =============================================================================
def test_missing_files_error_handling():
    missing_path = ROOT / "data" / "documents" / "RELIANCE" / "non_existent_file.pdf"
    with pytest.raises(FileNotFoundError):
        _ar_pages_layout(missing_path, 1, 1)

    with pytest.raises(FileNotFoundError):
        _concall_pages_layout(missing_path, 1, 1)
