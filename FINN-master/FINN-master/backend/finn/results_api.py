"""Results Intelligence API helpers and response formatters."""
import json
import sqlite3
from typing import Any

from .results_math import calculate_derived_ebitda, calculate_metric_change


def format_result_card(r: sqlite3.Row) -> dict[str, Any]:
    """Format a quarterly_results database row into a structured comparison card."""
    raw = json.loads(r["raw_figures"]) if r["raw_figures"] else {}

    def get_comp(key: str, curr_val: float | None):
        series = raw.get(key, [])
        prev_val = series[1] if len(series) > 1 else None
        yoy_val = series[2] if len(series) > 2 else None
        qoq = calculate_metric_change(curr_val, prev_val)
        yoy = calculate_metric_change(curr_val, yoy_val)
        return {
            "current": curr_val,
            "previous": prev_val,
            "yoy": yoy_val,
            "qoq": {
                "pct": qoq.pct_change,
                "label": qoq.label,
                "status": qoq.status,
                "abs_change": qoq.absolute_change,
            },
            "yoy_cmp": {
                "pct": yoy.pct_change,
                "label": yoy.label,
                "status": yoy.status,
                "abs_change": yoy.absolute_change,
            },
        }

    gross = get_comp("gross_revenue", r["gross_revenue"])
    rev = get_comp("revenue", r["revenue"])

    # Derived Operating EBITDA
    derived_ebitda = get_comp("derived_ebitda", r["derived_ebitda"])
    pbt_s = raw.get("pbt", [])
    fin_s = raw.get("finance_costs", [])
    dep_s = raw.get("depreciation", [])
    oth_s = raw.get("other_income", [])

    if derived_ebitda["previous"] is None and len(pbt_s) > 1 and len(fin_s) > 1 and len(dep_s) > 1:
        prev_eb, _ = calculate_derived_ebitda(
            pbt_s[1], pbt_s[1], 0, fin_s[1], dep_s[1], oth_s[1] if len(oth_s) > 1 else 0
        )
        derived_ebitda["previous"] = prev_eb
        qoq = calculate_metric_change(r["derived_ebitda"], prev_eb)
        derived_ebitda["qoq"] = {
            "pct": qoq.pct_change,
            "label": qoq.label,
            "status": qoq.status,
            "abs_change": qoq.absolute_change,
        }

    if derived_ebitda["yoy"] is None and len(pbt_s) > 2 and len(fin_s) > 2 and len(dep_s) > 2:
        yoy_eb, _ = calculate_derived_ebitda(
            pbt_s[2], pbt_s[2], 0, fin_s[2], dep_s[2], oth_s[2] if len(oth_s) > 2 else 0
        )
        derived_ebitda["yoy"] = yoy_eb
        yoy = calculate_metric_change(r["derived_ebitda"], yoy_eb)
        derived_ebitda["yoy_cmp"] = {
            "pct": yoy.pct_change,
            "label": yoy.label,
            "status": yoy.status,
            "abs_change": yoy.absolute_change,
        }

    # Reported EBITDA
    reported_ebitda = get_comp("reported_ebitda", r["reported_ebitda"])
    if (
        reported_ebitda["previous"] is None
        and derived_ebitda["previous"] is not None
        and len(oth_s) > 1
    ):
        prev_rep = round(derived_ebitda["previous"] + (oth_s[1] or 0.0), 2)
        reported_ebitda["previous"] = prev_rep
        qoq = calculate_metric_change(r["reported_ebitda"], prev_rep)
        reported_ebitda["qoq"] = {
            "pct": qoq.pct_change,
            "label": qoq.label,
            "status": qoq.status,
            "abs_change": qoq.absolute_change,
        }

    if (
        reported_ebitda["yoy"] is None
        and derived_ebitda["yoy"] is not None
        and len(oth_s) > 2
    ):
        yoy_rep = round(derived_ebitda["yoy"] + (oth_s[2] or 0.0), 2)
        reported_ebitda["yoy"] = yoy_rep
        yoy = calculate_metric_change(r["reported_ebitda"], yoy_rep)
        reported_ebitda["yoy_cmp"] = {
            "pct": yoy.pct_change,
            "label": yoy.label,
            "status": yoy.status,
            "abs_change": yoy.absolute_change,
        }

    pbt = get_comp("pbt", r["pbt"])
    pat = get_comp("pat", r["pat"])
    pat_with_associates = get_comp("pat_with_associates", r["pat_with_associates"])
    pat_owners = get_comp("pat_attributable_to_owners", r["pat_attributable_to_owners"])

    # Reconciliations
    rev_reconciliation = None
    if r["gross_revenue"] is not None and r["gst_recovered"] is not None:
        rev_reconciliation = (
            f"Gross Revenue (₹{r['gross_revenue']:,.0f} Cr) − GST Recovered (₹{r['gst_recovered']:,.0f} Cr) = "
            f"Revenue from Operations (₹{r['revenue']:,.0f} Cr)"
        )

    pat_reconciliation = None
    if r["pat"] is not None and r["share_of_associates"] is not None and r["pat_with_associates"] is not None:
        pat_reconciliation = (
            f"PAT before Associates (₹{r['pat']:,.0f} Cr) + Share of Associates & JVs (₹{r['share_of_associates']:,.0f} Cr) = "
            f"Consolidated Net Profit (₹{r['pat_with_associates']:,.0f} Cr)"
        )

    return {
        "id": r["id"],
        "symbol": r["symbol"],
        "filing_id": r["filing_id"],
        "period_label": r["period_label"],
        "period_end_date": r["period_end_date"],
        "nature": r["nature"],
        "currency": r["currency"] or "INR",
        "unit": r["unit"] or "crore",
        "metrics": {
            "gross_revenue": gross,
            "revenue": rev,
            "derived_ebitda": {**derived_ebitda, "method": r["derived_ebitda_method"]},
            "reported_ebitda": {**reported_ebitda, "note": r["ebitda_reconciliation_note"]},
            "pbt": pbt,
            "pat": pat,
            "share_of_associates": r["share_of_associates"],
            "pat_with_associates": pat_with_associates,
            "pat_attributable_to_owners": pat_owners,
        },
        "reconciliation": {
            "ebitda_note": r["ebitda_reconciliation_note"],
            "revenue_breakdown": rev_reconciliation,
            "pat_breakdown": pat_reconciliation,
        },
        "source": {
            "doc_url": r["source_doc_url"],
            "page": r["source_page"],
            "table_name": r["source_table_name"],
            "extracted_at": r["extracted_at"],
        },
    }


def get_results_by_symbol(con: sqlite3.Connection, symbol: str, nature: str = "consolidated") -> list[dict[str, Any]]:
    """Retrieve all quarterly results cards for a company symbol."""
    q = "SELECT * FROM quarterly_results WHERE symbol=?"
    params = [symbol.upper()]
    if nature in ("consolidated", "standalone"):
        q += " AND nature=?"
        params.append(nature)
    q += " ORDER BY period_end_date DESC"

    rows = con.execute(q, params).fetchall()
    return [format_result_card(r) for r in rows]


def get_results_by_filing(con: sqlite3.Connection, filing_id: str) -> dict[str, Any] | None:
    """Retrieve both Consolidated and Standalone results linked to a specific announcement filing.
    
    Strictly mapped via filing_id to guarantee one quarterly result maps to its exact filing.
    """
    rows = con.execute(
        "SELECT * FROM quarterly_results WHERE filing_id=? ORDER BY nature ASC",
        (filing_id,),
    ).fetchall()
    if not rows:
        return None

    cards = {r["nature"]: format_result_card(r) for r in rows}
    # Primary view is consolidated if available, else standalone
    primary_nature = "consolidated" if "consolidated" in cards else list(cards.keys())[0]
    return {
        "filing_id": filing_id,
        "result_id": rows[0]["id"],
        "symbol": rows[0]["symbol"],
        "period_label": rows[0]["period_label"],
        "primary_nature": primary_nature,
        "statements": cards,
    }
