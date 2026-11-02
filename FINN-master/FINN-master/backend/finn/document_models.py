"""Data structures and types for document intelligence extraction.

Used across Annual Report, Earnings Call Transcript, and official disclosure pipelines.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DocumentType(str, Enum):
    ANNUAL_REPORT = "annual_report"
    CONCALL_TRANSCRIPT = "concall_transcript"
    RESULTS_PDF = "results_pdf"
    INVESTOR_PRESENTATION = "investor_presentation"


class SpeakerRole(str, Enum):
    MANAGEMENT = "MANAGEMENT"
    ANALYST = "ANALYST"
    AUDITOR = "AUDITOR"
    MODERATOR = "MODERATOR"
    UNKNOWN = "UNKNOWN"


class StatementType(str, Enum):
    FORWARD_GUIDANCE = "FORWARD_GUIDANCE"
    FINANCIAL_COMMENTARY = "FINANCIAL_COMMENTARY"
    BUSINESS_STRATEGY = "BUSINESS_STRATEGY"
    RISK_DISCLOSURE = "RISK_DISCLOSURE"
    AUDITOR_OBSERVATION = "AUDITOR_OBSERVATION"
    ANALYST_QUESTION = "ANALYST_QUESTION"
    GENERAL_STATEMENT = "GENERAL_STATEMENT"


@dataclass
class ExtractedClaim:
    """An atomic, auditable claim extracted from an official primary-source document."""

    id: str
    symbol: str
    doc_title: str
    doc_type: str
    page: int
    section: str
    statement_type: str
    claim: str
    verbatim_text: str
    official_url: str
    speaker_name: Optional[str] = None
    speaker_designation: Optional[str] = None
    speaker_role: str = SpeakerRole.UNKNOWN.value
    confidence: float = 1.0
    needs_review: bool = False
    review_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def generate_claim_id(symbol: str, doc_title: str, page: int, section: str, verbatim_text: str) -> str:
    """Deterministic SHA-1 identifier for an extracted claim."""
    key = f"{symbol}:{doc_title}:{page}:{section}:{verbatim_text.strip()}".encode("utf-8")
    return hashlib.sha1(key).hexdigest()
