"""Unit tests for deterministic financial results calculations and validations."""
from datetime import date
import pytest
from finn.results_math import (
    calculate_derived_ebitda,
    calculate_metric_change,
    get_comparison_period_dates,
    get_indian_fiscal_period,
    normalize_to_crore,
    normalize_unit_name,
    validate_not_cumulative_ytd,
)


class TestUnitNormalization:
    def test_unit_name_normalization(self):
        assert normalize_unit_name("₹ in Crores") == "crore"
        assert normalize_unit_name("Crores") == "crore"
        assert normalize_unit_name("Rs. in Lakhs") == "lakh"
        assert normalize_unit_name("Millions") == "million"
        assert normalize_unit_name("in billion") == "billion"
        assert normalize_unit_name("thousands") == "thousand"

    def test_value_conversion_to_crore(self):
        # 1 Crore = 1.0 Crore
        assert normalize_to_crore(100.0, "crore") == 100.0
        # 100 Lakh = 1.0 Crore
        assert normalize_to_crore(100.0, "lakh") == 1.0
        # 10 Million = 1.0 Crore
        assert normalize_to_crore(10.0, "million") == 1.0
        # 1 Billion = 100.0 Crore
        assert normalize_to_crore(1.0, "billion") == 100.0
        # 10,000 Thousand = 1.0 Crore
        assert normalize_to_crore(10000.0, "thousand") == 1.0
        # None value returns None
        assert normalize_to_crore(None, "crore") is None


class TestMetricComparison:
    def test_standard_positive_growth(self):
        res = calculate_metric_change(115.0, 100.0, "crore", "crore")
        assert res.status == "GROWTH"
        assert res.pct_change == 15.0
        assert res.label == "+15.0%"
        assert res.absolute_change == 15.0

    def test_standard_decline(self):
        res = calculate_metric_change(85.0, 100.0, "crore", "crore")
        assert res.status == "DECLINE"
        assert res.pct_change == -15.0
        assert res.label == "-15.0%"
        assert res.absolute_change == -15.0

    def test_flat_performance(self):
        res = calculate_metric_change(100.0, 100.0, "crore", "crore")
        assert res.status == "FLAT"
        assert res.pct_change == 0.0
        assert res.label == "0.0%"
        assert res.absolute_change == 0.0

    def test_zero_base_with_positive_current(self):
        # Division by zero safeguard
        res = calculate_metric_change(50.0, 0.0, "crore", "crore")
        assert res.status == "NOT_APPLICABLE"
        assert res.pct_change is None
        assert "base 0" in res.label
        assert res.absolute_change == 50.0

    def test_both_zero(self):
        res = calculate_metric_change(0.0, 0.0, "crore", "crore")
        assert res.status == "FLAT"
        assert res.pct_change == 0.0
        assert res.label == "0.0%"

    def test_turnaround_loss_to_profit(self):
        # Base was loss (-50), current is profit (+20). Never output misleading positive percentage!
        res = calculate_metric_change(20.0, -50.0, "crore", "crore")
        assert res.status == "TURNAROUND"
        assert res.pct_change is None
        assert res.label == "Turnaround"
        assert res.absolute_change == 70.0

    def test_swing_to_loss(self):
        # Base was profit (+50), current is loss (-20)
        res = calculate_metric_change(-20.0, 50.0, "crore", "crore")
        assert res.status == "SWING_TO_LOSS"
        assert res.pct_change is None
        assert res.label == "Swing to Loss"
        assert res.absolute_change == -70.0

    def test_loss_narrowed(self):
        # Base was -100 loss, current is -60 loss (loss narrowed by 40%)
        res = calculate_metric_change(-60.0, -100.0, "crore", "crore")
        assert res.status == "LOSS_NARROWED"
        assert res.pct_change == 40.0
        assert res.label == "Loss narrowed 40.0%"
        assert res.absolute_change == 40.0

    def test_loss_widened(self):
        # Base was -50 loss, current is -75 loss (loss widened by 50%)
        res = calculate_metric_change(-75.0, -50.0, "crore", "crore")
        assert res.status == "LOSS_WIDENED"
        assert res.pct_change == 50.0
        assert res.label == "Loss widened 50.0%"
        assert res.absolute_change == -25.0

    def test_unit_conversion_during_comparison(self):
        # Current is 10,000 Lakhs (= 100 Crore), Base is 80 Crore
        res = calculate_metric_change(10000.0, 80.0, "lakh", "crore")
        assert res.status == "GROWTH"
        assert res.pct_change == 25.0
        assert res.label == "+25.0%"
        assert res.absolute_change == 20.0

    def test_missing_values(self):
        res1 = calculate_metric_change(None, 100.0)
        assert res1.status == "UNAVAILABLE"
        assert res1.label == "Unavailable"

        res2 = calculate_metric_change(100.0, None)
        assert res2.status == "UNAVAILABLE"
        assert res2.label == "Unavailable"


class TestEbitdaDistinction:
    def test_derived_operating_ebitda_calculation(self):
        # PBT: 100, Finance costs: 20, Depreciation: 30, Other income: 10
        # Derived Operating EBITDA = 100 + 20 + 30 - 10 = 140
        val, method = calculate_derived_ebitda(
            pbt=100.0,
            pbt_before_exceptional=100.0,
            exceptional_items=0.0,
            finance_costs=20.0,
            depreciation=30.0,
            other_income=10.0,
        )
        assert val == 140.0
        assert "PBT (core) ₹100.00" in method
        assert "+ Finance Costs ₹20.00" in method
        assert "+ Depreciation ₹30.00" in method
        assert "- Other Income ₹10.00" in method

    def test_derived_ebitda_with_exceptional_items(self):
        # Reported PBT: 120 (including exceptional gain of 20). Core PBT = 100
        val, method = calculate_derived_ebitda(
            pbt=120.0,
            pbt_before_exceptional=None,
            exceptional_items=20.0,
            finance_costs=15.0,
            depreciation=25.0,
            other_income=0.0,
        )
        assert val == 140.0
        assert "PBT (core) ₹100.00" in method

    def test_derived_ebitda_unavailable_when_components_missing(self):
        val, method = calculate_derived_ebitda(
            pbt=100.0,
            pbt_before_exceptional=100.0,
            exceptional_items=0.0,
            finance_costs=None,  # missing finance cost
            depreciation=30.0,
            other_income=10.0,
        )
        assert val is None
        assert method is None


class TestIndianFiscalMapping:
    def test_quarter_end_mapping(self):
        assert get_indian_fiscal_period("2026-06-30")["label"] == "Q1 FY27"
        assert get_indian_fiscal_period("2026-09-30")["label"] == "Q2 FY27"
        assert get_indian_fiscal_period("2026-12-31")["label"] == "Q3 FY27"
        assert get_indian_fiscal_period("2027-03-31")["label"] == "Q4 FY27"

    def test_comparison_dates_generation(self):
        dates = get_comparison_period_dates("2026-09-30")
        assert dates["current"] == "2026-09-30"
        assert dates["prev_quarter"] == "2026-06-30"
        assert dates["yoy_quarter"] == "2025-09-30"


class TestYtdValidation:
    def test_detects_cumulative_ytd_figure(self):
        # Q1 was 100, Q2 was 120, H1 cumulative is 220
        # If candidate is 220, reject as cumulative YTD!
        ok, reason = validate_not_cumulative_ytd(220.0, 100.0, 220.0)
        assert not ok
        assert "cumulative" in reason.lower()

    def test_accepts_valid_quarterly_figure(self):
        ok, reason = validate_not_cumulative_ytd(120.0, 100.0, 220.0)
        assert ok
