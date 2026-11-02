"""Deterministic fundamental financial calculations for research intelligence.

Strictly executed in deterministic Python (never an LLM).
Safely handles:
- Missing figures without fabrication (returns explicit UNAVAILABLE/MISSING status)
- Zero denominators (returns ZERO_DENOMINATOR status instead of crashing)
- Negative cash flows and net loss regimes
- Cross-unit normalization to base Crore
- Working capital movements
- Segment revenue and profit contribution analysis
"""
from dataclasses import dataclass
from typing import Literal, Dict, Any, List
from .results_math import normalize_to_crore, BASE_UNIT


@dataclass(frozen=True)
class NetDebtResult:
    gross_debt: float | None
    cash_and_equivalents: float | None
    liquid_investments: float | None
    net_debt: float | None
    status: Literal["NET_DEBT", "NET_CASH", "ZERO_NET_DEBT", "MISSING_DATA", "UNIT_MISMATCH"]
    label: str
    unit: str = "crore"


def calculate_net_debt(
    gross_debt: float | None,
    cash_and_equivalents: float | None,
    liquid_investments: float | None = 0.0,
    debt_unit: str = "crore",
    cash_unit: str = "crore",
    investments_unit: str = "crore",
) -> NetDebtResult:
    """Calculate Net Debt = Gross Debt - (Cash & Cash Equivalents + Liquid Current Investments).
    
    If either gross_debt or cash_and_equivalents is missing, Net Debt cannot be fabricated.
    """
    if gross_debt is None or cash_and_equivalents is None:
        return NetDebtResult(
            gross_debt=gross_debt,
            cash_and_equivalents=cash_and_equivalents,
            liquid_investments=liquid_investments,
            net_debt=None,
            status="MISSING_DATA",
            label="Net debt cannot be determined: missing debt or cash data in filing",
        )
    
    gd = normalize_to_crore(gross_debt, debt_unit)
    cash = normalize_to_crore(cash_and_equivalents, cash_unit)
    inv = normalize_to_crore(liquid_investments or 0.0, investments_unit) if liquid_investments is not None else 0.0
    
    if gd is None or cash is None or inv is None:
        return NetDebtResult(
            gross_debt=gross_debt,
            cash_and_equivalents=cash_and_equivalents,
            liquid_investments=liquid_investments,
            net_debt=None,
            status="UNIT_MISMATCH",
            label="Unsupported unit provided for debt or cash components",
        )
    
    total_liquid = round(cash + inv, 2)
    net = round(gd - total_liquid, 2)
    
    if net > 0:
        return NetDebtResult(
            gross_debt=gd,
            cash_and_equivalents=cash,
            liquid_investments=inv,
            net_debt=net,
            status="NET_DEBT",
            label=f"Net Debt of ₹{net:,.2f} Cr (Gross Debt ₹{gd:,.2f} Cr less ₹{total_liquid:,.2f} Cr liquid assets)",
        )
    elif net < 0:
        return NetDebtResult(
            gross_debt=gd,
            cash_and_equivalents=cash,
            liquid_investments=inv,
            net_debt=net,
            status="NET_CASH",
            label=f"Net Cash surplus of ₹{abs(net):,.2f} Cr (Liquid assets exceed gross debt)",
        )
    else:
        return NetDebtResult(
            gross_debt=gd,
            cash_and_equivalents=cash,
            liquid_investments=inv,
            net_debt=0.0,
            status="ZERO_NET_DEBT",
            label="Zero Net Debt (Liquid assets exactly match gross debt)",
        )


@dataclass(frozen=True)
class CashConversionResult:
    cfo: float | None
    base_metric: float | None      # PAT or EBITDA
    base_metric_name: str          # "PAT" or "EBITDA"
    ratio: float | None            # e.g. 1.15
    pct: float | None              # e.g. 115.0%
    status: Literal[
        "STRONG_CONVERSION",
        "MODERATE_CONVERSION",
        "POOR_CONVERSION",
        "NEGATIVE_CONVERSION",
        "CASH_BURN_DESPITE_PROFIT",
        "CASH_POSITIVE_DESPITE_LOSS",
        "BOTH_NEGATIVE",
        "ZERO_DENOMINATOR",
        "MISSING_DATA",
        "UNIT_MISMATCH",
    ]
    label: str
    unit: str = "crore"


def calculate_cfo_to_pat(
    cfo: float | None,
    pat: float | None,
    cfo_unit: str = "crore",
    pat_unit: str = "crore",
) -> CashConversionResult:
    """Calculate Cash Conversion Ratio: Cash Flow from Operations (CFO) / Profit After Tax (PAT).
    
    Measures the degree to which accounting net profit is translated into real operating cash.
    Handles loss-making periods, negative operating cash, and division by zero safely.
    """
    if cfo is None or pat is None:
        return CashConversionResult(
            cfo=cfo,
            base_metric=pat,
            base_metric_name="PAT",
            ratio=None,
            pct=None,
            status="MISSING_DATA",
            label="CFO to PAT conversion unavailable: required cash flow or PAT figures missing",
        )
    
    c = normalize_to_crore(cfo, cfo_unit)
    p = normalize_to_crore(pat, pat_unit)
    
    if c is None or p is None:
        return CashConversionResult(
            cfo=cfo,
            base_metric=pat,
            base_metric_name="PAT",
            ratio=None,
            pct=None,
            status="UNIT_MISMATCH",
            label="Unsupported unit provided for CFO or PAT",
        )
    
    if abs(p) < 1e-6:
        return CashConversionResult(
            cfo=c,
            base_metric=p,
            base_metric_name="PAT",
            ratio=None,
            pct=None,
            status="ZERO_DENOMINATOR",
            label="PAT is zero; ratio is undefined",
        )
    
    # Negative regimes
    if p > 0 and c <= 0:
        ratio = round(c / p, 2)
        pct = round((c / p) * 100, 1)
        return CashConversionResult(
            cfo=c,
            base_metric=p,
            base_metric_name="PAT",
            ratio=ratio,
            pct=pct,
            status="CASH_BURN_DESPITE_PROFIT",
            label=f"Earnings quality risk: Reported PAT of ₹{p:,.2f} Cr but operating cash flow is negative (₹{c:,.2f} Cr)",
        )
    elif p < 0 and c > 0:
        ratio = round(c / p, 2)
        pct = round((c / p) * 100, 1)
        return CashConversionResult(
            cfo=c,
            base_metric=p,
            base_metric_name="PAT",
            ratio=ratio,
            pct=pct,
            status="CASH_POSITIVE_DESPITE_LOSS",
            label=f"Cash generative despite net loss: Operating cash of ₹{c:,.2f} Cr vs accounting loss of ₹{p:,.2f} Cr",
        )
    elif p < 0 and c <= 0:
        ratio = round(c / p, 2)
        pct = round((c / p) * 100, 1)
        return CashConversionResult(
            cfo=c,
            base_metric=p,
            base_metric_name="PAT",
            ratio=ratio,
            pct=pct,
            status="BOTH_NEGATIVE",
            label=f"Severe cash burn: Negative operating cash flow (₹{c:,.2f} Cr) alongside net loss (₹{p:,.2f} Cr)",
        )
    
    # Both positive (standard regime)
    ratio = round(c / p, 2)
    pct = round((c / p) * 100, 1)
    if ratio >= 1.0:
        status = "STRONG_CONVERSION"
        label = f"High earnings quality: CFO converts {pct}% of PAT (₹{c:,.2f} Cr CFO vs ₹{p:,.2f} Cr PAT)"
    elif ratio >= 0.70:
        status = "MODERATE_CONVERSION"
        label = f"Healthy conversion: CFO converts {pct}% of PAT (₹{c:,.2f} Cr CFO vs ₹{p:,.2f} Cr PAT)"
    else:
        status = "POOR_CONVERSION"
        label = f"Weak conversion: CFO converts only {pct}% of PAT (₹{c:,.2f} Cr CFO vs ₹{p:,.2f} Cr PAT)"
        
    return CashConversionResult(
        cfo=c,
        base_metric=p,
        base_metric_name="PAT",
        ratio=ratio,
        pct=pct,
        status=status,
        label=label,
    )


def calculate_cfo_to_ebitda(
    cfo: float | None,
    ebitda: float | None,
    cfo_unit: str = "crore",
    ebitda_unit: str = "crore",
) -> CashConversionResult:
    """Calculate Cash Conversion Ratio: Operating Cash Flow (CFO) / Operating EBITDA.
    
    Measures working capital friction and operational cash leakage before tax/interest.
    """
    if cfo is None or ebitda is None:
        return CashConversionResult(
            cfo=cfo,
            base_metric=ebitda,
            base_metric_name="EBITDA",
            ratio=None,
            pct=None,
            status="MISSING_DATA",
            label="CFO to EBITDA conversion unavailable: required cash flow or EBITDA figures missing",
        )
    
    c = normalize_to_crore(cfo, cfo_unit)
    e = normalize_to_crore(ebitda, ebitda_unit)
    
    if c is None or e is None:
        return CashConversionResult(
            cfo=cfo,
            base_metric=ebitda,
            base_metric_name="EBITDA",
            ratio=None,
            pct=None,
            status="UNIT_MISMATCH",
            label="Unsupported unit provided for CFO or EBITDA",
        )
    
    if abs(e) < 1e-6:
        return CashConversionResult(
            cfo=c,
            base_metric=e,
            base_metric_name="EBITDA",
            ratio=None,
            pct=None,
            status="ZERO_DENOMINATOR",
            label="EBITDA is zero; ratio is undefined",
        )
    
    if e > 0 and c <= 0:
        ratio = round(c / e, 2)
        pct = round((c / e) * 100, 1)
        return CashConversionResult(
            cfo=c,
            base_metric=e,
            base_metric_name="EBITDA",
            ratio=ratio,
            pct=pct,
            status="CASH_BURN_DESPITE_PROFIT",
            label=f"Operational cash leakage: Operating EBITDA is ₹{e:,.2f} Cr, but CFO is negative (₹{c:,.2f} Cr)",
        )
    elif e < 0 and c > 0:
        ratio = round(c / e, 2)
        pct = round((c / e) * 100, 1)
        return CashConversionResult(
            cfo=c,
            base_metric=e,
            base_metric_name="EBITDA",
            ratio=ratio,
            pct=pct,
            status="CASH_POSITIVE_DESPITE_LOSS",
            label=f"Positive operating cash flow (₹{c:,.2f} Cr) despite negative operating EBITDA (₹{e:,.2f} Cr)",
        )
    elif e < 0 and c <= 0:
        ratio = round(c / e, 2)
        pct = round((c / e) * 100, 1)
        return CashConversionResult(
            cfo=c,
            base_metric=e,
            base_metric_name="EBITDA",
            ratio=ratio,
            pct=pct,
            status="BOTH_NEGATIVE",
            label=f"Operating loss and cash drain: EBITDA ₹{e:,.2f} Cr, CFO ₹{c:,.2f} Cr",
        )
        
    ratio = round(c / e, 2)
    pct = round((c / e) * 100, 1)
    if ratio >= 0.80:
        status = "STRONG_CONVERSION"
        label = f"Strong operating conversion: CFO represents {pct}% of EBITDA (₹{c:,.2f} Cr CFO vs ₹{e:,.2f} Cr EBITDA)"
    elif ratio >= 0.50:
        status = "MODERATE_CONVERSION"
        label = f"Moderate operating conversion: CFO represents {pct}% of EBITDA (₹{c:,.2f} Cr CFO vs ₹{e:,.2f} Cr EBITDA)"
    else:
        status = "POOR_CONVERSION"
        label = f"Low operating conversion: CFO represents only {pct}% of EBITDA (₹{c:,.2f} Cr CFO vs ₹{e:,.2f} Cr EBITDA)"
        
    return CashConversionResult(
        cfo=c,
        base_metric=e,
        base_metric_name="EBITDA",
        ratio=ratio,
        pct=pct,
        status=status,
        label=label,
    )


@dataclass(frozen=True)
class FreeCashFlowResult:
    cfo: float | None
    capex: float | None
    fcf: float | None
    status: Literal["POSITIVE_FCF", "NEGATIVE_FCF", "BREAKEVEN_FCF", "MISSING_DATA", "UNIT_MISMATCH"]
    label: str
    unit: str = "crore"


def calculate_free_cash_flow(
    cfo: float | None,
    capex: float | None,
    cfo_unit: str = "crore",
    capex_unit: str = "crore",
) -> FreeCashFlowResult:
    """Calculate Free Cash Flow (FCF) = Operating Cash Flow (CFO) - Capex.
    
    Capex is normalized to positive magnitude before subtraction.
    FCF > 0 indicates self-funding capacity after capital expenditure.
    FCF < 0 indicates capital expenditure exceeds operating cash flow (external funding required).
    """
    if cfo is None or capex is None:
        return FreeCashFlowResult(
            cfo=cfo,
            capex=capex,
            fcf=None,
            status="MISSING_DATA",
            label="Free Cash Flow cannot be calculated: CFO or Capex missing from filing",
        )
        
    c = normalize_to_crore(cfo, cfo_unit)
    raw_capex_mag = abs(capex)
    cap = normalize_to_crore(raw_capex_mag, capex_unit)
    
    if c is None or cap is None:
        return FreeCashFlowResult(
            cfo=cfo,
            capex=capex,
            fcf=None,
            status="UNIT_MISMATCH",
            label="Unsupported unit for CFO or Capex",
        )
        
    fcf = round(c - cap, 2)
    
    if fcf > 0:
        return FreeCashFlowResult(
            cfo=c,
            capex=cap,
            fcf=fcf,
            status="POSITIVE_FCF",
            label=f"Positive Free Cash Flow of ₹{fcf:,.2f} Cr (CFO ₹{c:,.2f} Cr exceeds Capex ₹{cap:,.2f} Cr)",
        )
    elif fcf < 0:
        return FreeCashFlowResult(
            cfo=c,
            capex=cap,
            fcf=fcf,
            status="NEGATIVE_FCF",
            label=f"Negative Free Cash Flow of ₹{fcf:,.2f} Cr (Capex ₹{cap:,.2f} Cr exceeds CFO ₹{c:,.2f} Cr)",
        )
    else:
        return FreeCashFlowResult(
            cfo=c,
            capex=cap,
            fcf=0.0,
            status="BREAKEVEN_FCF",
            label="Breakeven Free Cash Flow (CFO exactly matches Capex)",
        )


@dataclass(frozen=True)
class WorkingCapitalResult:
    current_wc: float | None
    previous_wc: float | None
    wc_change: float | None          # current - previous
    status: Literal[
        "CASH_ABSORBED",             # WC increased -> cash tied up
        "CASH_RELEASED",             # WC decreased -> cash unlocked
        "UNCHANGED",
        "MISSING_DATA",
        "UNIT_MISMATCH",
    ]
    label: str
    unit: str = "crore"


def calculate_working_capital(
    current_assets: float | None,
    current_liabilities: float | None,
    cash_and_equivalents: float | None = 0.0,
    short_term_borrowings: float | None = 0.0,
    assets_unit: str = "crore",
    liab_unit: str = "crore",
    cash_unit: str = "crore",
    borrowings_unit: str = "crore",
) -> float | None:
    """Calculate Net Operating Working Capital = (Current Assets - Cash) - (Current Liabilities - Short Debt).
    
    If operating adjustments are not separated, calculates standard Current Assets - Current Liabilities.
    """
    if current_assets is None or current_liabilities is None:
        return None
    
    ca = normalize_to_crore(current_assets, assets_unit)
    cl = normalize_to_crore(current_liabilities, liab_unit)
    cash = normalize_to_crore(cash_and_equivalents or 0.0, cash_unit) if cash_and_equivalents is not None else 0.0
    st_debt = normalize_to_crore(short_term_borrowings or 0.0, borrowings_unit) if short_term_borrowings is not None else 0.0
    
    if ca is None or cl is None or cash is None or st_debt is None:
        return None
        
    operating_ca = ca - cash
    operating_cl = cl - st_debt
    return round(operating_ca - operating_cl, 2)


def calculate_working_capital_change(
    current_wc: float | None,
    previous_wc: float | None,
    current_unit: str = "crore",
    previous_unit: str = "crore",
) -> WorkingCapitalResult:
    """Calculate change in Working Capital: Current WC - Previous WC.
    
    An increase in Working Capital (change > 0) absorbs cash (cash outflow).
    A decrease in Working Capital (change < 0) releases cash (cash inflow).
    """
    if current_wc is None or previous_wc is None:
        return WorkingCapitalResult(
            current_wc=current_wc,
            previous_wc=previous_wc,
            wc_change=None,
            status="MISSING_DATA",
            label="Working capital change unavailable: current or prior period figures missing",
        )
        
    c_wc = normalize_to_crore(current_wc, current_unit)
    p_wc = normalize_to_crore(previous_wc, previous_unit)
    
    if c_wc is None or p_wc is None:
        return WorkingCapitalResult(
            current_wc=current_wc,
            previous_wc=previous_wc,
            wc_change=None,
            status="UNIT_MISMATCH",
            label="Unsupported unit provided for working capital",
        )
        
    delta = round(c_wc - p_wc, 2)
    
    if delta > 0:
        return WorkingCapitalResult(
            current_wc=c_wc,
            previous_wc=p_wc,
            wc_change=delta,
            status="CASH_ABSORBED",
            label=f"Working capital expansion of ₹{delta:,.2f} Cr absorbed cash (funds tied up in operations)",
        )
    elif delta < 0:
        return WorkingCapitalResult(
            current_wc=c_wc,
            previous_wc=p_wc,
            wc_change=delta,
            status="CASH_RELEASED",
            label=f"Working capital optimization released ₹{abs(delta):,.2f} Cr of cash back to balance sheet",
        )
    else:
        return WorkingCapitalResult(
            current_wc=c_wc,
            previous_wc=p_wc,
            wc_change=0.0,
            status="UNCHANGED",
            label="Working capital remained unchanged across periods",
        )


@dataclass(frozen=True)
class SegmentItem:
    name: str
    value: float
    contribution_pct: float
    is_elimination: bool = False


@dataclass(frozen=True)
class SegmentContributionResult:
    segments: List[SegmentItem]
    total_gross_value: float
    net_value: float
    status: Literal["SUCCESS", "ZERO_TOTAL", "EMPTY_SEGMENTS", "MISSING_DATA"]
    label: str
    unit: str = "crore"


def calculate_segment_contributions(
    segments_data: Dict[str, float] | List[Dict[str, Any]],
    unit: str = "crore",
    value_key: str = "revenue",
    name_key: str = "name",
) -> SegmentContributionResult:
    """Calculate segment contribution percentages against total segment activity.
    
    Handles:
    - Dict mapping { "Segment Name": value } or list of dicts [{ "name": "...", "revenue": ... }]
    - Identification of 'Inter-segment transfers', 'Eliminations', or 'Unallocated'
    - Contribution percentage calculated on gross operating segments (excluding negative eliminations from denominator)
    - Zero/empty datasets safely handled without division by zero
    - Normalizes values to crore
    """
    if not segments_data:
        return SegmentContributionResult(
            segments=[],
            total_gross_value=0.0,
            net_value=0.0,
            status="EMPTY_SEGMENTS",
            label="No segment data provided",
        )
    
    raw_list: List[tuple[str, float]] = []
    if isinstance(segments_data, dict):
        for k, v in segments_data.items():
            if v is not None:
                norm_v = normalize_to_crore(float(v), unit)
                if norm_v is not None:
                    raw_list.append((str(k).strip(), norm_v))
    elif isinstance(segments_data, list):
        for item in segments_data:
            name = str(item.get(name_key, "Unknown")).strip()
            raw_val = item.get(value_key)
            if raw_val is not None:
                norm_v = normalize_to_crore(float(raw_val), unit)
                if norm_v is not None:
                    raw_list.append((name, norm_v))
                    
    if not raw_list:
        return SegmentContributionResult(
            segments=[],
            total_gross_value=0.0,
            net_value=0.0,
            status="MISSING_DATA",
            label="All segment values were missing or invalid",
        )
        
    elimination_keywords = {"elimination", "eliminations", "inter segment", "intersegment", "less: inter"}
    gross_total = 0.0
    net_total = 0.0
    
    for name, val in raw_list:
        is_elim = any(k in name.lower() for k in elimination_keywords) or val < 0
        net_total += val
        if not is_elim and val > 0:
            gross_total += val
            
    denom = gross_total if gross_total > 0 else (net_total if net_total > 0 else 0.0)
    
    if abs(denom) < 1e-6:
        items = [
            SegmentItem(
                name=name,
                value=round(val, 2),
                contribution_pct=0.0,
                is_elimination=any(k in name.lower() for k in elimination_keywords) or val < 0,
            )
            for name, val in raw_list
        ]
        return SegmentContributionResult(
            segments=items,
            total_gross_value=0.0,
            net_value=round(net_total, 2),
            status="ZERO_TOTAL",
            label="Total segment value is zero; contributions are zero",
        )
        
    items = []
    for name, val in raw_list:
        is_elim = any(k in name.lower() for k in elimination_keywords) or val < 0
        pct = round((val / denom) * 100, 2)
        items.append(
            SegmentItem(
                name=name,
                value=round(val, 2),
                contribution_pct=pct,
                is_elimination=is_elim,
            )
        )
        
    return SegmentContributionResult(
        segments=items,
        total_gross_value=round(gross_total, 2),
        net_value=round(net_total, 2),
        status="SUCCESS",
        label=f"Computed contributions across {len(items)} segments on ₹{denom:,.2f} Cr base",
    )
