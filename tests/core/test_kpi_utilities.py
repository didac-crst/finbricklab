"""
Tests for KPI utility functions.
"""

import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, "src")

from finbricklab.kpi import (  # noqa: E402
    breakeven_month,
    dsti,
    effective_tax_rate,
    fee_drag_cum,
    interest_paid_cum,
    liquidity_runway,
    ltv,
    max_drawdown,
    savings_rate,
    tax_burden_cum,
)


class TestKPIUtilities:
    """Test KPI utility functions."""

    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame with canonical schema."""
        dates = pd.date_range(start="2026-01-31", periods=12, freq="ME")
        return pd.DataFrame(
            {
                "date": dates,
                "cash": [10000, 11000, 12000, 13000, 14000, 15000] * 2,
                "liquid_assets": [5000, 5500, 6000, 6500, 7000, 7500] * 2,
                "illiquid_assets": [100000, 101000, 102000, 103000, 104000, 105000] * 2,
                "liabilities": [80000, 79000, 78000, 77000, 76000, 75000] * 2,
                "inflows": [3000, 3000, 3000, 3000, 3000, 3000] * 2,
                "outflows": [2000, 2000, 2000, 2000, 2000, 2000] * 2,
                "taxes": [300, 300, 300, 300, 300, 300] * 2,
                "fees": [100, 100, 100, 100, 100, 100] * 2,
                "interest": [200, 190, 180, 170, 160, 150] * 2,
                "principal": [100, 110, 120, 130, 140, 150] * 2,
                "mortgage_balance": [80000, 79000, 78000, 77000, 76000, 75000] * 2,
                "property_value": [100000, 101000, 102000, 103000, 104000, 105000] * 2,
                "net_income": [1000, 1000, 1000, 1000, 1000, 1000] * 2,
            }
        )

    def test_liquidity_runway(self, sample_df):
        """Test liquidity runway calculation."""
        runway = liquidity_runway(sample_df)

        assert len(runway) == len(sample_df)
        assert runway.name == "liquidity_runway_months"
        assert not runway.isna().any()
        assert (runway > 0).all()  # Should always be positive

        # Test with custom parameters
        runway_custom = liquidity_runway(
            sample_df, lookback_months=3, essential_share=0.8
        )
        assert len(runway_custom) == len(sample_df)

    def test_max_drawdown(self, sample_df):
        """Test maximum drawdown calculation."""
        # Test with Series
        net_worth_series = (
            sample_df["cash"]
            + sample_df["liquid_assets"]
            + sample_df["illiquid_assets"]
            - sample_df["liabilities"]
        )
        dd_series = max_drawdown(net_worth_series)

        assert isinstance(dd_series, pd.Series)
        assert dd_series.name == "max_drawdown"
        assert len(dd_series) == 1  # Single value for Series

        # Test with DataFrame
        df_subset = sample_df[["cash", "liquid_assets"]]
        dd_df = max_drawdown(df_subset)

        assert isinstance(dd_df, pd.Series)
        assert len(dd_df) == 2  # One per column
        assert set(dd_df.index) == {"cash", "liquid_assets"}

    def test_fee_drag_cum(self, sample_df):
        """Test cumulative fee drag calculation."""
        fee_drag = fee_drag_cum(sample_df)

        assert len(fee_drag) == len(sample_df)
        assert fee_drag.name == "fee_drag_cum"
        assert not fee_drag.isna().any()
        assert (fee_drag >= 0).all()  # Should be non-negative

        # Should be constant since fees and inflows are constant
        assert abs(fee_drag.iloc[-1] - fee_drag.iloc[0]) < 0.01

    def test_tax_burden_cum(self, sample_df):
        """Test cumulative tax burden calculation."""
        tax_burden = tax_burden_cum(sample_df)

        assert len(tax_burden) == len(sample_df)
        assert tax_burden.name == "tax_burden_cum"
        assert not tax_burden.isna().any()
        assert (tax_burden >= 0).all()  # Should be non-negative

        # Should be constant since taxes and inflows are constant
        assert abs(tax_burden.iloc[-1] - tax_burden.iloc[0]) < 0.01

    def test_effective_tax_rate(self, sample_df):
        """Test effective tax rate calculation."""
        # Should be same as tax_burden_cum
        tax_rate = effective_tax_rate(sample_df)
        tax_burden = tax_burden_cum(sample_df)

        pd.testing.assert_series_equal(tax_rate, tax_burden)

    def test_interest_paid_cum(self, sample_df):
        """Test cumulative interest paid calculation."""
        interest_cum = interest_paid_cum(sample_df)

        assert len(interest_cum) == len(sample_df)
        assert interest_cum.name == "interest_paid_cum"
        assert not interest_cum.isna().any()

        # Should be increasing over time
        assert interest_cum.iloc[-1] > interest_cum.iloc[0]

    def test_interest_paid_cum_missing_column(self):
        """Test interest_paid_cum with missing interest column."""
        df_no_interest = pd.DataFrame(
            {
                "date": pd.date_range("2026-01-31", periods=3, freq="ME"),
                "cash": [1000, 1100, 1200],
            }
        )

        interest_cum = interest_paid_cum(df_no_interest)
        assert (interest_cum == 0.0).all()

    def test_dsti(self, sample_df):
        """Test DSTI calculation."""
        dsti_ratio = dsti(sample_df)

        assert len(dsti_ratio) == len(sample_df)
        assert dsti_ratio.name == "dsti"
        assert not dsti_ratio.isna().any()
        assert (dsti_ratio > 0).all()  # Should be positive

        # Test with missing columns
        df_no_dsti = sample_df.drop(columns=["interest", "principal", "net_income"])
        dsti_missing = dsti(df_no_dsti)
        assert dsti_missing.isna().all()

    def test_ltv(self, sample_df):
        """Test LTV calculation."""
        ltv_ratio = ltv(sample_df)

        assert len(ltv_ratio) == len(sample_df)
        assert ltv_ratio.name == "ltv"
        assert not ltv_ratio.isna().any()
        assert (ltv_ratio > 0).all()  # Should be positive

        # Test fallback to proxy LTV
        df_proxy = sample_df.drop(columns=["mortgage_balance", "property_value"]).copy()
        df_proxy["total_assets"] = (
            df_proxy["cash"] + df_proxy["liquid_assets"] + df_proxy["illiquid_assets"]
        )
        ltv_proxy = ltv(df_proxy)
        assert ltv_proxy.name == "ltv_proxy"  # Uses proxy name
        assert not ltv_proxy.isna().any()

    def test_ltv_missing_all_columns(self):
        """Test LTV with no suitable columns."""
        df_minimal = pd.DataFrame(
            {
                "date": pd.date_range("2026-01-31", periods=3, freq="ME"),
                "cash": [1000, 1100, 1200],
            }
        )

        ltv_missing = ltv(df_minimal)
        assert ltv_missing.isna().all()

    def test_breakeven_month(self, sample_df):
        """Test breakeven month calculation."""
        # Create two scenarios with different net worth progression
        baseline = sample_df.copy()
        baseline["net_worth"] = 50000  # Constant

        scenario = sample_df.copy()
        scenario["net_worth"] = [
            45000,
            47000,
            49000,
            51000,
            53000,
            55000,
        ] * 2  # Increasing

        breakeven = breakeven_month(scenario, baseline)
        assert breakeven == 4  # Month 4 (1-based) where scenario exceeds baseline

        # Test no breakeven case
        scenario_lower = sample_df.copy()
        scenario_lower["net_worth"] = [
            40000,
            41000,
            42000,
            43000,
            44000,
            45000,
        ] * 2  # Always lower

        breakeven_none = breakeven_month(scenario_lower, baseline)
        assert breakeven_none is None

    def test_savings_rate(self, sample_df):
        """Test savings rate calculation."""
        savings = savings_rate(sample_df)

        assert len(savings) == len(sample_df)
        assert savings.name == "savings_rate"
        assert not savings.isna().any()

        # With inflows=3000, outflows=2000, net_income=1000, savings_rate should be 1000/3000 ≈ 0.33
        expected_savings_rate = 1000 / 3000
        assert abs(savings.iloc[0] - expected_savings_rate) < 0.01

    def test_savings_rate_zero_inflows(self):
        """Test savings rate with zero inflows."""
        df_zero_inflows = pd.DataFrame(
            {
                "date": pd.date_range("2026-01-31", periods=3, freq="ME"),
                "inflows": [0, 0, 0],
                "outflows": [1000, 1000, 1000],
            }
        )

        savings = savings_rate(df_zero_inflows)
        assert savings.isna().all()

    def test_edge_cases(self):
        """Test edge cases for various functions."""
        # DataFrame with minimal required columns
        minimal_df = pd.DataFrame(
            {
                "cash": [],
                "outflows": [],
                "inflows": [],
                "taxes": [],
                "fees": [],
            }
        )

        # Should handle empty DataFrame gracefully
        runway = liquidity_runway(minimal_df)
        assert len(runway) == 0

        # DataFrame with all zeros
        zero_df = pd.DataFrame(
            {
                "cash": [0, 0, 0],
                "outflows": [0, 0, 0],
                "inflows": [0, 0, 0],
                "taxes": [0, 0, 0],
                "fees": [0, 0, 0],
            }
        )

        runway_zero = liquidity_runway(zero_df)
        assert (runway_zero == np.inf).all()  # Infinite runway with no outflows

        fee_drag_zero = fee_drag_cum(zero_df)
        assert (fee_drag_zero == 0.0).all()  # No fees, no drag
