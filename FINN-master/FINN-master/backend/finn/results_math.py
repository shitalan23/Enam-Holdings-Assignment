"""Deterministic financial calculations, unit normalizations, and SEBI results validation.

All math is strictly executed in deterministic Python (never an LLM).
Safely handles zero/negative comparison bases, unit conversions, Indian fiscal calendar,
and cleanly distinguishes Reported EBITDA from Derived Operating EBITDA.
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

# Base unit for uniform cross-company comparison is INR Crore
BASE_UNIT = "crore"

UNIT_MULTIPLIERS_TO_CRORE = {
    "crore": 1.0,
    "crores": 1.0,
    "cr": 1.0,
    "lakh": 0.01,
    "lakhs": 0.01,
    "lac": 0.01,
    "lacs": 0.01,
    "million": 0.1,
    "millions": 0.1,
    "mn": 0.1,
    "billion": 100.0,
    "billions": 100.0,
    "bn": 100.0,
    "thousand": 0.0001,
    "thousands": 0.0001,
}


def normalize_unit_name(unit_str: str | None) -> str:
    """Normalize unit string from various disclosures into standard name."""
    if not unit_str:
        return "crore"
    u = unit_str.strip().lower()
    for clean, aliases in [
        ("crore", ["crore", "crores", "cr", "rs. in crore", "in crore", "in crores", "in cr"]),
        ("lakh", ["lakh", "lakhs", "lac", "lacs", "in lakh", "in lakhs"]),
        ("million", ["million", "millions", "mn", "in million", "in millions"]),
        ("billion", ["billion", "billions", "bn", "in billion"]),
        ("thousand", ["thousand", "thousands", "in thousand"]),
    ]:
        if u == clean or any(a in u for a in aliases):
            return clean
    return u


def normalize_to_crore(val: float | None, unit: str | None) -> float | None:
    """Convert a value in any supported unit to INR Crore."""
    if val is None:
        return None
    unit_norm = normalize_unit_name(unit)
    mult = UNIT_MULTIPLIERS_TO_CRORE.get(unit_norm)
    if mult is None:
        return None
    return round(val * mult, 4)


@dataclass(frozen=True)
class MetricComparison:
    current: float | None
    base: float | None
    absolute_change: float | None
    pct_change: float | None
    status: Literal[
        "GROWTH",
        "DECLINE",
        "FLAT",
        "TURNAROUND",
        "SWING_TO_LOSS",
        "LOSS_NARROWED",
        "LOSS_WIDENED",
        "NOT_APPLICABLE",
        "UNIT_MISMATCH",
        "UNAVAILABLE",
    ]
    label: str
    unit: str = "crore"


def calculate_metric_change(
    current: float | None,
    base: float | None,
    current_unit: str = "crore",
    base_unit: str = "crore",
) -> MetricComparison:
    """Deterministic comparison between current and base quarter values.
    
    Converts both values to base crore before computing.
    Safely handles division by zero, turnaround from loss to profit,
    swing from profit to loss, and loss narrowing/widening.
    """
    if current is None or base is None:
        return MetricComparison(
            current=current,
            base=base,
            absolute_change=None,
            pct_change=None,
            status="UNAVAILABLE",
            label="Unavailable",
        )

    # Normalize units
    c_norm = normalize_to_crore(current, current_unit)
    b_norm = normalize_to_crore(base, base_unit)

    if c_norm is None or b_norm is None:
        return MetricComparison(
            current=current,
            base=base,
            absolute_change=None,
            pct_change=None,
            status="UNIT_MISMATCH",
            label="Unit mismatch",
        )

    abs_change = round(c_norm - b_norm, 2)

    # Both zero
    if abs(b_norm) < 1e-9 and abs(c_norm) < 1e-9:
        return MetricComparison(
            current=c_norm,
            base=b_norm,
            absolute_change=0.0,
            pct_change=0.0,
            status="FLAT",
            label="0.0%",
        )

    # Base is zero, current non-zero (division by zero guard)
    if abs(b_norm) < 1e-9:
        return MetricComparison(
            current=c_norm,
            base=b_norm,
            absolute_change=abs_change,
            pct_change=None,
            status="NOT_APPLICABLE",
            label="N/A (base 0)",
        )

    # Base positive, current positive (standard percentage change)
    if b_norm > 0 and c_norm >= 0:
        pct = round(((c_norm - b_norm) / b_norm) * 100, 2)
        if pct > 0:
            status = "GROWTH"
            label = f"+{pct}%"
        elif pct < 0:
            status = "DECLINE"
            label = f"{pct}%"
        else:
            status = "FLAT"
            label = "0.0%"
        return MetricComparison(
            current=c_norm,
            base=b_norm,
            absolute_change=abs_change,
            pct_change=pct,
            status=status,
            label=label,
        )

    # Turnaround: Base negative (loss), current positive (profit)
    if b_norm < 0 and c_norm >= 0:
        return MetricComparison(
            current=c_norm,
            base=b_norm,
            absolute_change=abs_change,
            pct_change=None,
            status="TURNAROUND",
            label="Turnaround",
        )

    # Swing to loss: Base positive (profit), current negative (loss)
    if b_norm > 0 and c_norm < 0:
        return MetricComparison(
            current=c_norm,
            base=b_norm,
            absolute_change=abs_change,
            pct_change=None,
            status="SWING_TO_LOSS",
            label="Swing to Loss",
        )

    # Both negative: Loss to Loss
    if b_norm < 0 and c_norm < 0:
        curr_loss = abs(c_norm)
        base_loss = abs(b_norm)
        if curr_loss < base_loss:
            narrowed_pct = round(((base_loss - curr_loss) / base_loss) * 100, 2)
            return MetricComparison(
                current=c_norm,
                base=b_norm,
                absolute_change=abs_change,
                pct_change=narrowed_pct,
                status="LOSS_NARROWED",
                label=f"Loss narrowed {narrowed_pct}%",
            )
        else:
            widened_pct = round(((curr_loss - base_loss) / base_loss) * 100, 2)
            return MetricComparison(
                current=c_norm,
                base=b_norm,
                absolute_change=abs_change,
                pct_change=widened_pct,
                status="LOSS_WIDENED",
                label=f"Loss widened {widened_pct}%",
            )

    return MetricComparison(
        current=c_norm,
        base=b_norm,
        absolute_change=abs_change,
        pct_change=None,
        status="UNAVAILABLE",
        label="Unavailable",
    )


def calculate_derived_ebitda(
    pbt: float | None,
    pbt_before_exceptional: float | None,
    exceptional_items: float | None,
    finance_costs: float | None,
    depreciation: float | None,
    other_income: float | None = 0.0,
) -> tuple[float | None, str | None]:
    """Calculate Derived Operating EBITDA from disclosed financial components.
    
    Formula:
      Operating EBITDA = PBT (before exceptional) + Finance Costs + Depreciation - Other Income
      
    Never conflated with company-reported EBITDA.
    """
    # Resolve PBT before exceptional items
    core_pbt = pbt_before_exceptional
    if core_pbt is None and pbt is not None:
        exc = exceptional_items or 0.0
        core_pbt = pbt - exc

    if core_pbt is None:
        return None, None

    # Finance costs and depreciation are required for operating EBITDA
    if finance_costs is None or depreciation is None:
        return None, None

    oi = other_income or 0.0
    derived = round(core_pbt + finance_costs + depreciation - oi, 2)
    components = []
    components.append(f"PBT (core) ₹{core_pbt:,.2f}")
    components.append(f"+ Finance Costs ₹{finance_costs:,.2f}")
    components.append(f"+ Depreciation ₹{depreciation:,.2f}")
    if oi != 0.0:
        components.append(f"- Other Income ₹{oi:,.2f}")
    method = f"Derived: {' '.join(components)}"

    return derived, method


def get_indian_fiscal_period(end_date: str | date) -> dict:
    """Map period end date to Indian Financial Year quarter.
    
    Indian Fiscal Year: April 1 to March 31.
    - End Jun 30: Q1 FY(Year + 1)
    - End Sep 30: Q2 FY(Year + 1)
    - End Dec 31: Q3 FY(Year + 1)
    - End Mar 31: Q4 FY(Year)
    """
    if isinstance(end_date, str):
        d = datetime.strptime(end_date.strip()[:10], "%Y-%m-%d").date()
    else:
        d = end_date

    month = d.month
    year = d.year

    if month == 6:
        q_num = 1
        fy = year + 1
    elif month == 9:
        q_num = 2
        fy = year + 1
    elif month == 12:
        q_num = 3
        fy = year + 1
    elif month == 3:
        q_num = 4
        fy = year
    else:
        # Approximate nearest quarter end
        if month in (4, 5):
            q_num = 1
            fy = year + 1
        elif month in (7, 8):
            q_num = 2
            fy = year + 1
        elif month in (10, 11):
            q_num = 3
            fy = year + 1
        else:
            q_num = 4
            fy = year

    fy_short = str(fy)[-2:]
    return {
        "quarter": f"Q{q_num}",
        "fy": f"FY{fy_short}",
        "label": f"Q{q_num} FY{fy_short}",
        "full_label": f"Quarter ended {d.strftime('%b %d, %Y')}",
        "end_date": d.isoformat(),
    }


def get_comparison_period_dates(current_end_date: str) -> dict:
    """Calculate the expected period end dates for QoQ and YoY comparisons."""
    d = datetime.strptime(current_end_date.strip()[:10], "%Y-%m-%d").date()
    month, year = d.month, d.year

    # Previous quarter
    if month == 6:  # Q1 -> Q4 prev FY (Mar 31)
        prev_date = date(year, 3, 31)
    elif month == 9:  # Q2 -> Q1 (Jun 30)
        prev_date = date(year, 6, 30)
    elif month == 12:  # Q3 -> Q2 (Sep 30)
        prev_date = date(year, 9, 30)
    elif month == 3:  # Q4 -> Q3 prev year (Dec 31)
        prev_date = date(year - 1, 12, 31)
    else:
        prev_date = date(year, max(1, month - 3), 28)

    # Same quarter last year (YoY)
    yoy_year = year - 1
    yoy_day = 30 if month in (6, 9) else (31 if month in (3, 12) else 28)
    yoy_date = date(yoy_year, month, yoy_day)

    return {
        "current": d.isoformat(),
        "prev_quarter": prev_date.isoformat(),
        "yoy_quarter": yoy_date.isoformat(),
    }


def validate_not_cumulative_ytd(
    q_current: float | None,
    q_prev: float | None,
    ytd_candidate: float | None,
) -> tuple[bool, str]:
    """Validate that extracted quarterly figure is not accidentally the cumulative YTD figure.
    
    In Q2 (H1) and Q3 (9M) filings, cumulative figures exist in adjacent columns.
    If q_current == ytd_candidate or (q_prev is available and q_current ~= q_prev + actual_q),
    reject with explanation.
    """
    if q_current is None:
        return True, "Value is None"

    if ytd_candidate is not None:
        # If extracted figure equals the YTD total, it's cumulative!
        if abs(q_current - ytd_candidate) < 1e-4:
            return False, f"Extracted figure ({q_current}) equals cumulative YTD ({ytd_candidate})"

        # For Q2: H1 ~= Q1 + Q2. If q_current > ytd_candidate * 0.8 and q_prev is known, verify
        if q_prev is not None and abs(q_current - (q_prev + (ytd_candidate - q_prev))) < 1e-4:
            if abs(q_current - ytd_candidate) < abs(q_current - (ytd_candidate - q_prev)):
                return False, f"Extracted figure matches H1 cumulative total, not individual Q2"

    return True, "Valid quarterly figure"
