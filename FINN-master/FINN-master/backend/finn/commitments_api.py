"""Promise vs Delivered API helpers and response formatters (backend/finn/commitments_api.py).

Provides clean REST API handlers for:
- GET /api/commitments/{symbol}
- GET /api/commitments/{symbol}/summary

Adheres to ENAM Holdings financial intelligence principles:
- Exposes complete citations (original promise citation and actual performance citation).
- Transparently distinguishes genuine commitments from strategic intentions and operational milestones.
- Displays delivery score with evaluated count and explicit statistical caveat.
- Handles unknown companies (404) and companies without commitments (UNAVAILABLE).
"""
import json
import sqlite3
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .commitments_eval import calculate_track_record_summary, TrackRecordSummary


def format_commitment_row(row: sqlite3.Row | Dict[str, Any]) -> Dict[str, Any]:
    """Format a SQLite commitment row into a structured, citation-complete JSON dict."""
    r = dict(row)
    q_evals_raw = r.get("quarter_evaluations")
    if isinstance(q_evals_raw, str):
        try:
            quarter_evaluations = json.loads(q_evals_raw)
        except Exception:
            quarter_evaluations = []
    elif isinstance(q_evals_raw, list):
        quarter_evaluations = q_evals_raw
    else:
        quarter_evaluations = []

    return {
        "id": r["id"],
        "symbol": r["symbol"],
        "commitment_type": r["commitment_type"],
        "category": r["category"],
        "title": r["title"],
        "statement": r["statement"],
        "speaker": r["speaker"],
        "commitment_date": r["commitment_date"],
        "commitment_period": r["commitment_period"],
        "target_period": r["target_period"],
        "target": {
            "value": r["target_value"],
            "unit": r["target_unit"],
            "tolerance_pct": r["target_tolerance_pct"],
        },
        "source_citation": {
            "doc_title": r["source_doc_title"],
            "doc_type": r["source_doc_type"],
            "page_or_slide": r["source_page_or_slide"],
            "url": r["source_url"],
        },
        "actual_performance": r["actual_performance"],
        "actual": {
            "value": r["actual_value"],
            "unit": r["actual_unit"],
        },
        "actual_citation": {
            "doc_title": r["actual_source_doc"],
            "page_or_slide": r["actual_source_page_or_slide"],
            "url": r["actual_source_url"],
            "reported_period": r["actual_reported_period"],
        } if r["actual_source_doc"] else None,
        "quarter_evaluations": quarter_evaluations,
        "status": r["status"],
        "evaluation_reasoning": r["evaluation_reasoning"],
        "is_quantified": bool(r["is_quantified"]),
        "contributes_to_score": bool(r["contributes_to_score"]),
        "needs_review": bool(r["needs_review"]),
        "review_reason": r["review_reason"],
        "created_at": r["created_at"],
    }


def get_commitments_by_symbol(con: sqlite3.Connection, symbol: str) -> Dict[str, Any]:
    """Retrieve full commitments dossier with evaluations and summary for a symbol."""
    sym = symbol.strip().upper()
    comp = con.execute("SELECT * FROM companies WHERE symbol = ?", (sym,)).fetchone()
    if not comp:
        return {
            "status": "NOT_FOUND",
            "symbol": sym,
            "company_name": None,
            "count": 0,
            "summary": None,
            "commitments": [],
            "message": f"Company symbol '{sym}' is not tracked in the database.",
        }

    rows = con.execute(
        "SELECT * FROM commitments WHERE symbol = ? ORDER BY commitment_date ASC, target_period ASC",
        (sym,),
    ).fetchall()

    if not rows:
        return {
            "status": "UNAVAILABLE",
            "symbol": sym,
            "company_name": comp["name"],
            "count": 0,
            "summary": None,
            "commitments": [],
            "message": f"No management commitments tracked yet for {sym}.",
        }

    commitments_list = [format_commitment_row(r) for r in rows]
    summary = calculate_track_record_summary(rows)

    return {
        "status": "OK",
        "symbol": sym,
        "company_name": comp["name"],
        "count": len(commitments_list),
        "summary": summary.to_dict(),
        "commitments": commitments_list,
    }


def get_commitments_summary_by_symbol(con: sqlite3.Connection, symbol: str) -> Dict[str, Any]:
    """Retrieve track record summary and delivery score for a symbol."""
    sym = symbol.strip().upper()
    comp = con.execute("SELECT * FROM companies WHERE symbol = ?", (sym,)).fetchone()
    if not comp:
        return {
            "status": "NOT_FOUND",
            "symbol": sym,
            "company_name": None,
            "count": 0,
            "summary": None,
            "message": f"Company symbol '{sym}' is not tracked in the database.",
        }

    rows = con.execute(
        "SELECT * FROM commitments WHERE symbol = ?",
        (sym,),
    ).fetchall()

    if not rows:
        return {
            "status": "UNAVAILABLE",
            "symbol": sym,
            "company_name": comp["name"],
            "count": 0,
            "summary": None,
            "message": f"No management commitments tracked yet for {sym}.",
        }

    summary = calculate_track_record_summary(rows)

    return {
        "status": "OK",
        "symbol": sym,
        "company_name": comp["name"],
        "count": len(rows),
        "summary": summary.to_dict(),
    }
