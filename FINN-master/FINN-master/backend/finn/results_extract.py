"""Local PDF extraction for quarterly financial results from official exchange filings.

Zero-cost, deterministic extraction using layout-aware local parsing.
Extracts Consolidated and Standalone statements, preserves primary source citations
(URL, page number, table name), and validates against cumulative YTD confusion.
"""
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ROOT
from .db import session
from .results_math import (
    calculate_derived_ebitda,
    calculate_metric_change,
    get_comparison_period_dates,
    get_indian_fiscal_period,
    normalize_unit_name,
    validate_not_cumulative_ytd,
)

DOCS_DIR = ROOT / "data" / "documents"


def _parse_num(s: str) -> float | None:
    """Parse comma-formatted numbers and handle parenthesized negatives."""
    s = s.replace(",", "").strip()
    # (123) or {123) or (123} notation for negative values
    if (s.startswith("(") or s.startswith("{")) and (s.endswith(")") or s.endswith("}")):
        try:
            return -float(s[1:-1])
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def extract_text_from_pdf(pdf_path: str | Path, start_page: int | None = None, end_page: int | None = None) -> list[str]:
    """Extract layout-aware text from PDF using local pdftotext utility."""
    cmd = ["pdftotext", "-layout"]
    if start_page:
        cmd.extend(["-f", str(start_page)])
    if end_page:
        cmd.extend(["-l", str(end_page)])
    cmd.extend([str(pdf_path), "-"])

    res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    if res.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {res.stderr[:200]}")

    # Split by form feed character (\x0c) which represents page breaks
    pages = res.stdout.split("\x0c")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages


def parse_sebi_statement_page(page_text: str, page_num: int, nature: str) -> dict[str, Any] | None:
    """Parse a single SEBI Ind-AS Schedule III results table page."""
    lines = page_text.splitlines()

    # Detect unit (e.g. ₹ in crore)
    unit = "crore"
    for line in lines[:10]:
        l_low = line.lower()
        if "in crore" in l_low or "t in crore" in l_low or "in cr" in l_low:
            unit = "crore"
            break
        elif "in lakh" in l_low or "in lac" in l_low:
            unit = "lakh"
            break
        elif "in million" in l_low or "in mn" in l_low:
            unit = "million"
            break

    targets = [
        ("gross_revenue", ["value of sales & services"]),
        ("gst_recovered", ["less: gst recovered", "gst recovered"]),
        ("revenue", ["revenue from operations"]),
        ("other_income", ["other income"]),
        ("finance_costs", ["finance costs"]),
        ("depreciation", ["depreciation"]),
        ("pbt", ["profit before tax"]),
        ("pat_with_associates", ["profit after tax and share of"]),
        ("pat", ["profit after tax"]),
        ("share_of_associates", ["share of profit/ (loss) of associates", "share of profit"]),
        ("pat_attributable_to_owners", ["owners of the company", "owners of the parent"]),
    ]

    parsed_rows: dict[str, list[float]] = {}
    for key, patterns in targets:
        if key in parsed_rows:
            continue
        for i, line in enumerate(lines):
            l_lower = line.lower()
            if any(p in l_lower for p in patterns):
                # Try current line, else lookahead 1 line for wrapped table headers
                tokens = re.findall(r"[\(\{]?\b\d[\d,]*\.?\d*[\)\}]?", line)
                nums = [_parse_num(t) for t in tokens if _parse_num(t) is not None]
                if len(nums) < 3 and i + 1 < len(lines):
                    tokens = re.findall(r"[\(\{]?\b\d[\d,]*\.?\d*[\)\}]?", lines[i + 1])
                    nums = [_parse_num(t) for t in tokens if _parse_num(t) is not None]
                if len(nums) >= 3:
                    parsed_rows[key] = nums
                    break

    # Validate essential line items are present
    if "revenue" not in parsed_rows or "pbt" not in parsed_rows or "pat" not in parsed_rows:
        return None

    # Column index 0: Current Quarter (e.g. 30th Sep 2026)
    # Column index 1: Preceding Quarter (e.g. 30th Jun 2026)
    # Column index 2: YoY Quarter (e.g. 30th Sep 2025)
    # Column index 3: Cumulative YTD (Half-Year / 9M ended)
    current_rev = parsed_rows["revenue"][0]
    prev_rev = parsed_rows["revenue"][1]
    yoy_rev = parsed_rows["revenue"][2]
    ytd_rev = parsed_rows["revenue"][3] if len(parsed_rows["revenue"]) > 3 else None

    # Sanity check: Ensure current quarter is not cumulative YTD
    is_valid_q, reason = validate_not_cumulative_ytd(current_rev, prev_rev, ytd_rev)
    if not is_valid_q:
        return {
            "error": reason,
            "needs_review": 1,
            "review_reason": reason,
        }

    other_inc = parsed_rows.get("other_income", [0.0, 0.0, 0.0])
    fin_costs = parsed_rows.get("finance_costs", [None, None, None])
    depr = parsed_rows.get("depreciation", [None, None, None])
    pbt_row = parsed_rows["pbt"]
    pat_row = parsed_rows["pat"]
    gross_row = parsed_rows.get("gross_revenue", [None, None, None])
    gst_row = parsed_rows.get("gst_recovered", [None, None, None])
    assoc_row = parsed_rows.get("share_of_associates", [0.0, 0.0, 0.0])
    pat_assoc_row = parsed_rows.get("pat_with_associates", [None, None, None])
    owners_row = parsed_rows.get("pat_attributable_to_owners", [None, None, None])

    # If pat_with_associates wasn't explicit, derive from pat + share_of_associates
    if not pat_assoc_row or pat_assoc_row[0] is None:
        pat_assoc_row = [(pat_row[i] + (assoc_row[i] if i < len(assoc_row) and assoc_row[i] is not None else 0.0)) for i in range(len(pat_row))]

    # Calculate Derived Operating EBITDA for all three periods
    derived_ebitda_curr, method_curr = calculate_derived_ebitda(
        pbt=pbt_row[0],
        pbt_before_exceptional=pbt_row[0],
        exceptional_items=0.0,
        finance_costs=fin_costs[0] if fin_costs else None,
        depreciation=depr[0] if depr else None,
        other_income=other_inc[0] if other_inc else 0.0,
    )
    derived_ebitda_prev, _ = calculate_derived_ebitda(
        pbt=pbt_row[1],
        pbt_before_exceptional=pbt_row[1],
        exceptional_items=0.0,
        finance_costs=fin_costs[1] if fin_costs else None,
        depreciation=depr[1] if depr else None,
        other_income=other_inc[1] if other_inc else 0.0,
    )
    derived_ebitda_yoy, _ = calculate_derived_ebitda(
        pbt=pbt_row[2],
        pbt_before_exceptional=pbt_row[2],
        exceptional_items=0.0,
        finance_costs=fin_costs[2] if fin_costs else None,
        depreciation=depr[2] if depr else None,
        other_income=other_inc[2] if other_inc else 0.0,
    )

    # EBITDA reconciliation note: Operating EBITDA excludes other income; reported EBITDA in investor presentation includes it
    reconciliation_note = None
    reported_ebitda_curr = None
    if nature == "consolidated" and derived_ebitda_curr is not None:
        reported_ebitda_curr = round(derived_ebitda_curr + (other_inc[0] or 0.0), 2)
        reconciliation_note = (
            f"Company-Reported EBITDA (₹{reported_ebitda_curr:,.0f} Cr) = Derived Operating EBITDA "
            f"(₹{derived_ebitda_curr:,.0f} Cr) + Other Income (₹{other_inc[0]:,.0f} Cr). "
            f"Derived Operating EBITDA measures core operational performance excluding non-operating other income."
        )

    return {
        "nature": nature,
        "page_num": page_num,
        "unit": unit,
        "currency": "INR",
        "current": {
            "gross_revenue": gross_row[0] if gross_row else None,
            "gst_recovered": gst_row[0] if gst_row else None,
            "revenue": current_rev,
            "other_income": other_inc[0] if other_inc else None,
            "finance_costs": fin_costs[0] if fin_costs else None,
            "depreciation": depr[0] if depr else None,
            "pbt": pbt_row[0],
            "pat": pat_row[0],
            "share_of_associates": assoc_row[0] if assoc_row else None,
            "pat_with_associates": pat_assoc_row[0] if pat_assoc_row else None,
            "pat_attributable_to_owners": owners_row[0] if owners_row else None,
            "derived_ebitda": derived_ebitda_curr,
            "derived_ebitda_method": method_curr,
            "reported_ebitda": reported_ebitda_curr,
            "ebitda_reconciliation_note": reconciliation_note,
        },
        "previous_quarter": {
            "gross_revenue": gross_row[1] if gross_row and len(gross_row) > 1 else None,
            "gst_recovered": gst_row[1] if gst_row and len(gst_row) > 1 else None,
            "revenue": prev_rev,
            "other_income": other_inc[1] if other_inc and len(other_inc) > 1 else None,
            "pbt": pbt_row[1],
            "pat": pat_row[1],
            "share_of_associates": assoc_row[1] if assoc_row and len(assoc_row) > 1 else None,
            "pat_with_associates": pat_assoc_row[1] if pat_assoc_row and len(pat_assoc_row) > 1 else None,
            "pat_attributable_to_owners": owners_row[1] if owners_row and len(owners_row) > 1 else None,
            "derived_ebitda": derived_ebitda_prev,
            "reported_ebitda": round(derived_ebitda_prev + (other_inc[1] or 0.0), 2) if derived_ebitda_prev else None,
        },
        "yoy_quarter": {
            "gross_revenue": gross_row[2] if gross_row and len(gross_row) > 2 else None,
            "gst_recovered": gst_row[2] if gst_row and len(gst_row) > 2 else None,
            "revenue": yoy_rev,
            "other_income": other_inc[2] if other_inc and len(other_inc) > 2 else None,
            "pbt": pbt_row[2],
            "pat": pat_row[2],
            "share_of_associates": assoc_row[2] if assoc_row and len(assoc_row) > 2 else None,
            "pat_with_associates": pat_assoc_row[2] if pat_assoc_row and len(pat_assoc_row) > 2 else None,
            "pat_attributable_to_owners": owners_row[2] if owners_row and len(owners_row) > 2 else None,
            "derived_ebitda": derived_ebitda_yoy,
            "reported_ebitda": round(derived_ebitda_yoy + (other_inc[2] or 0.0), 2) if derived_ebitda_yoy else None,
        },
        "raw_figures": {k: v[:4] for k, v in parsed_rows.items()},
    }


def extract_quarterly_results_from_pdf(
    pdf_path: str | Path,
    symbol: str,
    source_url: str,
    filing_id: str | None = None,
) -> list[dict[str, Any]]:
    """Extract both Consolidated and Standalone results from an official exchange PDF."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found at {pdf_path}")

    pages = extract_text_from_pdf(pdf_path)
    results = []

    # Identify Consolidated and Standalone pages
    for idx, page in enumerate(pages):
        page_num = idx + 1
        p_lower = page.lower()

        # Check for Consolidated table
        if "financial results" in p_lower and "consolidated" in p_lower and "revenue from operations" in p_lower:
            parsed = parse_sebi_statement_page(page, page_num, "consolidated")
            if parsed and "error" not in parsed:
                parsed["symbol"] = symbol
                parsed["source_url"] = source_url
                parsed["filing_id"] = filing_id
                parsed["table_name"] = "UNAUDITED CONSOLIDATED FINANCIAL RESULTS"
                results.append(parsed)
                break

    for idx, page in enumerate(pages):
        page_num = idx + 1
        p_lower = page.lower()

        # Check for Standalone table
        if "financial results" in p_lower and "standalone" in p_lower and "revenue from operations" in p_lower:
            parsed = parse_sebi_statement_page(page, page_num, "standalone")
            if parsed and "error" not in parsed:
                parsed["symbol"] = symbol
                parsed["source_url"] = source_url
                parsed["filing_id"] = filing_id
                parsed["table_name"] = "UNAUDITED STANDALONE FINANCIAL RESULTS"
                results.append(parsed)
                break

    return results


def save_quarterly_results_to_db(parsed_statements: list[dict[str, Any]], period_end_date: str = "2026-09-30") -> None:
    """Save extracted quarterly results into the quarterly_results database table."""
    fiscal = get_indian_fiscal_period(period_end_date)
    period_label = fiscal["label"]
    extracted_at = datetime.now().isoformat(timespec="seconds")

    with session() as con:
        for stmt in parsed_statements:
            curr = stmt["current"]
            symbol = stmt["symbol"]
            nature = stmt["nature"]
            qid = hashlib.sha1(f"{symbol}|{period_label}|{nature}".encode()).hexdigest()[:16]

            con.execute(
                """INSERT OR REPLACE INTO quarterly_results (
                    id, symbol, filing_id, period_label, period_end_date, nature,
                    currency, unit, gross_revenue, gst_recovered, revenue, other_income, total_income, finance_costs,
                    depreciation, pbt_before_exceptional, exceptional_items, pbt,
                    tax_expense, pat, share_of_associates, pat_with_associates, pat_attributable_to_owners,
                    reported_ebitda, derived_ebitda, derived_ebitda_method, ebitda_reconciliation_note,
                    raw_figures, source_doc_url, source_page, source_table_name, needs_review, review_reason, extracted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    qid,
                    symbol,
                    stmt.get("filing_id"),
                    period_label,
                    period_end_date,
                    nature,
                    stmt.get("currency", "INR"),
                    stmt.get("unit", "crore"),
                    curr.get("gross_revenue"),
                    curr.get("gst_recovered"),
                    curr.get("revenue"),
                    curr.get("other_income"),
                    (curr.get("revenue") or 0.0) + (curr.get("other_income") or 0.0),
                    curr.get("finance_costs"),
                    curr.get("depreciation"),
                    curr.get("pbt"),
                    0.0,
                    curr.get("pbt"),
                    None,
                    curr.get("pat"),
                    curr.get("share_of_associates"),
                    curr.get("pat_with_associates"),
                    curr.get("pat_attributable_to_owners"),
                    curr.get("reported_ebitda"),
                    curr.get("derived_ebitda"),
                    curr.get("derived_ebitda_method"),
                    curr.get("ebitda_reconciliation_note"),
                    json.dumps(stmt.get("raw_figures", {})),
                    stmt.get("source_url"),
                    stmt.get("page_num"),
                    stmt.get("table_name"),
                    stmt.get("needs_review", 0),
                    stmt.get("review_reason"),
                    extracted_at,
                ),
            )
