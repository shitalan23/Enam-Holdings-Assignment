"""Unit tests for deterministic fundamental research calculations (backend/finn/research_math.py).

Tests edge cases: missing figures, zero denominators, negative values, cash burn regimes,
unit normalizations, and segment eliminations without fabricating data.
"""
import pytest
from finn.research_math import (
    calculate_net_debt,
    calculate_cfo_to_pat,
    calculate_cfo_to_ebitda,
    calculate_free_cash_flow,
    calculate_working_capital,
    calculate_working_capital_change,
    calculate_segment_contributions,
)


class TestNetDebtCalculation:
    def test_standard_net_debt(self):
        # Gross Debt 350,000 Cr, Cash 100,000 Cr, Investments 50,000 Cr -> Net Debt = 200,000 Cr
        res = calculate_net_debt(350000.0, 100000.0, 50000.0)
        assert res.net_debt == 200000.0
        assert res.status == "NET_DEBT"
        assert "Net Debt of ₹200,000.00 Cr" in res.label

    def test_net_cash_surplus(self):
        # Gross Debt 50,000 Cr, Cash 80,000 Cr -> Net Cash 30,000 Cr
        res = calculate_net_debt(50000.0, 80000.0, 0.0)
        assert res.net_debt == -30000.0
        assert res.status == "NET_CASH"
        assert "Net Cash surplus of ₹30,000.00 Cr" in res.label

    def test_zero_net_debt(self):
        res = calculate_net_debt(50000.0, 50000.0)
        assert res.net_debt == 0.0
        assert res.status == "ZERO_NET_DEBT"

    def test_missing_debt_or_cash_never_fabricates(self):
        res1 = calculate_net_debt(None, 50000.0)
        assert res1.net_debt is None
        assert res1.status == "MISSING_DATA"

        res2 = calculate_net_debt(50000.0, None)
        assert res2.net_debt is None
        assert res2.status == "MISSING_DATA"

    def test_unit_conversion(self):
        # Debt in Lakhs: 10,000,000 Lakhs = 100,000 Crore; Cash in Million: 500,000 Million = 50,000 Crore
        res = calculate_net_debt(10000000.0, 500000.0, 0.0, debt_unit="lakh", cash_unit="million")
        assert res.gross_debt == 100000.0
        assert res.cash_and_equivalents == 50000.0
        assert res.net_debt == 50000.0
        assert res.status == "NET_DEBT"

    def test_unsupported_unit(self):
        res = calculate_net_debt(1000.0, 500.0, debt_unit="bitcoin")
        assert res.net_debt is None
        assert res.status == "UNIT_MISMATCH"


class TestCfoToPatConversion:
    def test_strong_conversion(self):
        # CFO 32,000 Cr, PAT 25,000 Cr -> Ratio = 1.28 (128%)
        res = calculate_cfo_to_pat(32000.0, 25000.0)
        assert res.ratio == 1.28
        assert res.pct == 128.0
        assert res.status == "STRONG_CONVERSION"
        assert "High earnings quality" in res.label

    def test_moderate_conversion(self):
        # CFO 18,000 Cr, PAT 24,000 Cr -> Ratio = 0.75 (75%)
        res = calculate_cfo_to_pat(18000.0, 24000.0)
        assert res.ratio == 0.75
        assert res.pct == 75.0
        assert res.status == "MODERATE_CONVERSION"

    def test_poor_conversion(self):
        # CFO 8,000 Cr, PAT 20,000 Cr -> Ratio = 0.40 (40%)
        res = calculate_cfo_to_pat(8000.0, 20000.0)
        assert res.ratio == 0.40
        assert res.pct == 40.0
        assert res.status == "POOR_CONVERSION"

    def test_zero_pat_denominator(self):
        res = calculate_cfo_to_pat(10000.0, 0.0)
        assert res.ratio is None
        assert res.status == "ZERO_DENOMINATOR"

    def test_missing_data(self):
        res1 = calculate_cfo_to_pat(None, 10000.0)
        assert res1.ratio is None
        assert res1.status == "MISSING_DATA"

        res2 = calculate_cfo_to_pat(10000.0, None)
        assert res2.ratio is None
        assert res2.status == "MISSING_DATA"

    def test_cash_burn_despite_accounting_profit(self):
        # PAT +15,000 Cr, but CFO -5,000 Cr (severe working capital trap)
        res = calculate_cfo_to_pat(-5000.0, 15000.0)
        assert res.ratio == -0.33
        assert res.status == "CASH_BURN_DESPITE_PROFIT"
        assert "Earnings quality risk" in res.label

    def test_cash_positive_despite_net_loss(self):
        # PAT -4,000 Cr (accounting loss), but CFO +6,000 Cr (high non-cash depreciation)
        res = calculate_cfo_to_pat(6000.0, -4000.0)
        assert res.ratio == -1.5
        assert res.status == "CASH_POSITIVE_DESPITE_LOSS"
        assert "Cash generative despite net loss" in res.label

    def test_both_negative(self):
        # Loss of 5,000 Cr and cash burn of 8,000 Cr
        res = calculate_cfo_to_pat(-8000.0, -5000.0)
        assert res.ratio == 1.6
        assert res.status == "BOTH_NEGATIVE"
        assert "Severe cash burn" in res.label


class TestCfoToEbitdaConversion:
    def test_strong_operating_conversion(self):
        # CFO 55,000 Cr, Operating EBITDA 60,000 Cr -> Ratio = 0.92 (91.7%)
        res = calculate_cfo_to_ebitda(55000.0, 60000.0)
        assert res.ratio == 0.92
        assert res.pct == 91.7
        assert res.status == "STRONG_CONVERSION"

    def test_moderate_operating_conversion(self):
        # CFO 36,000 Cr, EBITDA 60,000 Cr -> Ratio = 0.60 (60%)
        res = calculate_cfo_to_ebitda(36000.0, 60000.0)
        assert res.ratio == 0.60
        assert res.pct == 60.0
        assert res.status == "MODERATE_CONVERSION"

    def test_poor_operating_conversion(self):
        # CFO 15,000 Cr, EBITDA 50,000 Cr -> Ratio = 0.30 (30%)
        res = calculate_cfo_to_ebitda(15000.0, 50000.0)
        assert res.ratio == 0.30
        assert res.pct == 30.0
        assert res.status == "POOR_CONVERSION"

    def test_zero_ebitda_denominator(self):
        res = calculate_cfo_to_ebitda(5000.0, 0.0)
        assert res.ratio is None
        assert res.status == "ZERO_DENOMINATOR"

    def test_missing_ebitda(self):
        res = calculate_cfo_to_ebitda(10000.0, None)
        assert res.ratio is None
        assert res.status == "MISSING_DATA"

    def test_ebitda_positive_cfo_negative(self):
        res = calculate_cfo_to_ebitda(-2000.0, 10000.0)
        assert res.status == "CASH_BURN_DESPITE_PROFIT"


class TestFreeCashFlowCalculation:
    def test_positive_free_cash_flow(self):
        # CFO 45,000 Cr, Capex 25,000 Cr -> FCF = 20,000 Cr
        res = calculate_free_cash_flow(45000.0, 25000.0)
        assert res.fcf == 20000.0
        assert res.status == "POSITIVE_FCF"
        assert "Positive Free Cash Flow of ₹20,000.00 Cr" in res.label

    def test_negative_free_cash_flow_due_to_high_capex(self):
        # CFO 30,000 Cr, Capex 50,000 Cr -> FCF = -20,000 Cr
        res = calculate_free_cash_flow(30000.0, 50000.0)
        assert res.fcf == -20000.0
        assert res.status == "NEGATIVE_FCF"
        assert "Negative Free Cash Flow of ₹-20,000.00 Cr" in res.label

    def test_negative_capex_input_handled_as_magnitude(self):
        # In Cash Flow statements Capex is often reported as negative cash outflow: -35,000 Cr
        res = calculate_free_cash_flow(50000.0, -35000.0)
        assert res.capex == 35000.0
        assert res.fcf == 15000.0
        assert res.status == "POSITIVE_FCF"

    def test_breakeven_fcf(self):
        res = calculate_free_cash_flow(20000.0, 20000.0)
        assert res.fcf == 0.0
        assert res.status == "BREAKEVEN_FCF"

    def test_missing_capex_never_assumed_zero(self):
        # Never fabricate missing capex as zero
        res = calculate_free_cash_flow(30000.0, None)
        assert res.fcf is None
        assert res.status == "MISSING_DATA"

    def test_unit_conversion(self):
        # CFO in Crore (1000 Cr), Capex in Millions (5000 Mn = 500 Cr) -> FCF = 500 Cr
        res = calculate_free_cash_flow(1000.0, 5000.0, cfo_unit="crore", capex_unit="million")
        assert res.cfo == 1000.0
        assert res.capex == 500.0
        assert res.fcf == 500.0


class TestWorkingCapitalCalculation:
    def test_operating_working_capital(self):
        # Current Assets 120,000 Cr (Cash 20,000 Cr), Current Liab 70,000 Cr (Short debt 10,000 Cr)
        # Operating CA = 100,000 Cr, Operating CL = 60,000 Cr -> Net Working Capital = 40,000 Cr
        wc = calculate_working_capital(120000.0, 70000.0, cash_and_equivalents=20000.0, short_term_borrowings=10000.0)
        assert wc == 40000.0

    def test_working_capital_expansion_absorbs_cash(self):
        # Current WC 45,000 Cr, Prior WC 30,000 Cr -> Change = +15,000 Cr (absorbed cash)
        res = calculate_working_capital_change(45000.0, 30000.0)
        assert res.wc_change == 15000.0
        assert res.status == "CASH_ABSORBED"
        assert "Working capital expansion" in res.label

    def test_working_capital_reduction_releases_cash(self):
        # Current WC 25,000 Cr, Prior WC 35,000 Cr -> Change = -10,000 Cr (released cash)
        res = calculate_working_capital_change(25000.0, 35000.0)
        assert res.wc_change == -10000.0
        assert res.status == "CASH_RELEASED"
        assert "Working capital optimization released" in res.label

    def test_unchanged_working_capital(self):
        res = calculate_working_capital_change(30000.0, 30000.0)
        assert res.wc_change == 0.0
        assert res.status == "UNCHANGED"

    def test_missing_wc_values(self):
        res = calculate_working_capital_change(None, 20000.0)
        assert res.wc_change is None
        assert res.status == "MISSING_DATA"


class TestSegmentContributions:
    def test_dict_input_with_eliminations(self):
        segments = {
            "Oil to Chemicals (O2C)": 150000.0,
            "Retail": 90000.0,
            "Digital Services / Jio": 35000.0,
            "Oil and Gas": 6000.0,
            "Others": 4000.0,
            "Less: Inter-segment transfers": -15000.0,
        }
        res = calculate_segment_contributions(segments)
        assert res.status == "SUCCESS"
        # Gross denominator = 150000 + 90000 + 35000 + 6000 + 4000 = 285,000 Cr
        assert res.total_gross_value == 285000.0
        # Net value after eliminations = 285,000 - 15,000 = 270,000 Cr
        assert res.net_value == 270000.0

        o2c = next(s for s in res.segments if "O2C" in s.name)
        assert o2c.contribution_pct == round((150000.0 / 285000.0) * 100, 2)  # ~52.63%
        assert not o2c.is_elimination

        retail = next(s for s in res.segments if "Retail" in s.name)
        assert retail.contribution_pct == round((90000.0 / 285000.0) * 100, 2)  # ~31.58%

        elim = next(s for s in res.segments if "Inter-segment" in s.name)
        assert elim.is_elimination is True

    def test_list_input(self):
        segments = [
            {"name": "Segment A", "revenue": 600.0},
            {"name": "Segment B", "revenue": 400.0},
        ]
        res = calculate_segment_contributions(segments)
        assert res.status == "SUCCESS"
        assert res.total_gross_value == 1000.0
        seg_a = next(s for s in res.segments if s.name == "Segment A")
        assert seg_a.contribution_pct == 60.0

    def test_empty_or_missing_segments(self):
        res1 = calculate_segment_contributions({})
        assert res1.status == "EMPTY_SEGMENTS"
        assert res1.segments == []

        res2 = calculate_segment_contributions({"A": None, "B": None})
        assert res2.status == "MISSING_DATA"

    def test_zero_total_segments(self):
        res = calculate_segment_contributions({"A": 0.0, "B": 0.0})
        assert res.status == "ZERO_TOTAL"
        assert res.segments[0].contribution_pct == 0.0
