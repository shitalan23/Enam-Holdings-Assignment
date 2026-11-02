"""Research Intelligence API helpers and response formatters."""
import json
import sqlite3
from typing import Any, Dict, List


def search_research_companies(con: sqlite3.Connection, query: str = "") -> List[Dict[str, Any]]:
    """Search companies by symbol or name and annotate research availability."""
    q = query.strip()
    if q:
        sql = """
        SELECT c.symbol, c.name, c.sector, c.size_bucket, c.weight, c.in_portfolio,
               cr.id as research_id, cr.as_of_period, cr.as_of_date, cr.generated_at
        FROM companies c
        LEFT JOIN company_research cr ON c.symbol = cr.symbol
        WHERE c.symbol LIKE ? OR c.name LIKE ?
        ORDER BY c.in_portfolio DESC, c.weight DESC, c.symbol ASC
        """
        like_param = f"%{q}%"
        rows = con.execute(sql, (like_param, like_param)).fetchall()
    else:
        sql = """
        SELECT c.symbol, c.name, c.sector, c.size_bucket, c.weight, c.in_portfolio,
               cr.id as research_id, cr.as_of_period, cr.as_of_date, cr.generated_at
        FROM companies c
        LEFT JOIN company_research cr ON c.symbol = cr.symbol
        ORDER BY c.in_portfolio DESC, c.weight DESC, c.symbol ASC
        """
        rows = con.execute(sql).fetchall()

    results = []
    for r in rows:
        results.append(
            {
                "symbol": r["symbol"],
                "name": r["name"],
                "sector": r["sector"],
                "size_bucket": r["size_bucket"],
                "weight": r["weight"],
                "in_portfolio": bool(r["in_portfolio"]),
                "has_research": r["research_id"] is not None,
                "as_of_period": r["as_of_period"],
                "as_of_date": r["as_of_date"],
                "generated_at": r["generated_at"],
            }
        )
    return results


def get_company_research_dossier(con: sqlite3.Connection, symbol: str) -> Dict[str, Any]:
    """Retrieve full 8-dimension research dossier for a symbol."""
    sym = symbol.strip().upper()
    comp = con.execute("SELECT * FROM companies WHERE symbol = ?", (sym,)).fetchone()
    if not comp:
        return {
            "status": "NOT_FOUND",
            "symbol": sym,
            "company_name": None,
            "has_research": False,
            "message": f"Company symbol '{sym}' is not tracked in the database.",
            "dossier": None,
        }

    row = con.execute(
        "SELECT * FROM company_research WHERE symbol = ? ORDER BY as_of_period DESC LIMIT 1",
        (sym,),
    ).fetchone()

    if not row:
        return {
            "status": "UNAVAILABLE",
            "symbol": sym,
            "company_name": comp["name"],
            "sector": comp["sector"],
            "size_bucket": comp["size_bucket"],
            "has_research": False,
            "message": f"Research dossier has not yet been generated for {sym}. Ingest primary filings to synthesize fundamentals.",
            "dossier": None,
        }

    dossier = {
        "id": row["id"],
        "symbol": row["symbol"],
        "company_name": comp["name"],
        "sector": comp["sector"],
        "size_bucket": comp["size_bucket"],
        "as_of_period": row["as_of_period"],
        "as_of_date": row["as_of_date"],
        "generated_at": row["generated_at"],
        "needs_review": bool(row["needs_review"]),
        "review_reason": row["review_reason"],
        "source_documents": json.loads(row["source_documents"]) if row["source_documents"] else [],
        "business_snapshot": json.loads(row["business_snapshot"]) if row["business_snapshot"] else {},
        "financial_snapshot": json.loads(row["financial_snapshot"]) if row["financial_snapshot"] else {},
        "trajectory": json.loads(row["trajectory"]) if row["trajectory"] else {},
        "balance_sheet": json.loads(row["balance_sheet"]) if row["balance_sheet"] else {},
        "cash_quality": json.loads(row["cash_quality"]) if row["cash_quality"] else {},
        "narrative_vs_numbers": json.loads(row["narrative_vs_numbers"]) if row["narrative_vs_numbers"] else [],
        "guidance": json.loads(row["guidance"]) if row["guidance"] else [],
        "bull_vs_bear": json.loads(row["bull_vs_bear"]) if row["bull_vs_bear"] else {},
        "citations": json.loads(row["citations"]) if row["citations"] else [],
    }

    return {
        "status": "AVAILABLE",
        "symbol": sym,
        "company_name": comp["name"],
        "sector": comp["sector"],
        "size_bucket": comp["size_bucket"],
        "has_research": True,
        "as_of_period": row["as_of_period"],
        "as_of_date": row["as_of_date"],
        "generated_at": row["generated_at"],
        "needs_review": bool(row["needs_review"]),
        "review_reason": row["review_reason"],
        "dossier": dossier,
    }
