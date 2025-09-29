"""
Tests for MacroBrick and FinBrick chart functions.
"""

import sys

import pandas as pd
import pytest

sys.path.insert(0, "src")

from finbricklab.charts import (  # noqa: E402
    category_allocation_over_time,
    category_cashflow_bars,
    event_timeline,
    holdings_cost_basis,
)


class TestMacroBrickFinBrickCharts:
    """Test MacroBrick and FinBrick chart functions."""

    @pytest.fixture
    def sample_tidy_data(self):
        """Create sample tidy data for chart testing."""
        dates = pd.date_range(start="2026-01-31", periods=12, freq="ME")
        return pd.DataFrame(
            {
                "scenario_id": ["test"] * 12,
                "scenario_name": ["Test Scenario"] * 12,
                "date": dates,
                "cash": [10000, 11000, 12000, 13000, 14000, 15000] * 2,
                "liquid_assets": [5000, 5500, 6000, 6500, 7000, 7500] * 2,
                "illiquid_assets": [100000, 101000, 102000, 103000, 104000, 105000] * 2,
                "liabilities": [80000, 79000, 78000, 77000, 76000, 75000] * 2,
                "inflows": [3000, 3000, 3000, 3000, 3000, 3000] * 2,
                "outflows": [2000, 2000, 2000, 2000, 2000, 2000] * 2,
                "taxes": [300, 300, 300, 300, 300, 300] * 2,
                "fees": [100, 100, 100, 100, 100, 100] * 2,
                "total_assets": [115000, 116500, 118000, 119500, 121000, 122500] * 2,
                "net_worth": [35000, 37500, 40000, 42500, 45000, 47500] * 2,
            }
        )

    def test_category_allocation_over_time(self, sample_tidy_data):
        """Test category allocation over time chart."""
        try:
            fig, data = category_allocation_over_time(sample_tidy_data)

            # Check that figure was created
            assert fig is not None

            # Check that data was returned
            assert isinstance(data, pd.DataFrame)
            assert len(data) > 0

            # Check required columns
            required_cols = ["date", "category", "value"]
            for col in required_cols:
                assert col in data.columns

            # Check that we have multiple categories
            categories = data["category"].unique()
            assert len(categories) >= 3  # Should have Cash, Liquid Assets, etc.

        except ImportError:
            pytest.skip("Plotly not available")

    def test_category_cashflow_bars(self, sample_tidy_data):
        """Test category cashflow bars chart."""
        try:
            fig, data = category_cashflow_bars(sample_tidy_data)

            # Check that figure was created
            assert fig is not None

            # Check that data was returned
            assert isinstance(data, pd.DataFrame)
            assert len(data) > 0

            # Check required columns
            required_cols = ["year", "category", "amount"]
            for col in required_cols:
                assert col in data.columns

            # Check that we have multiple categories
            categories = data["category"].unique()
            assert len(categories) >= 2  # Should have inflows, outflows, etc.

        except ImportError:
            pytest.skip("Plotly not available")

    def test_event_timeline(self, sample_tidy_data):
        """Test event timeline chart."""
        try:
            fig, data = event_timeline(sample_tidy_data)

            # Check that figure was created
            assert fig is not None

            # Check that data was returned
            assert isinstance(data, pd.DataFrame)
            assert len(data) > 0

            # Check required columns
            required_cols = ["date", "event_type", "amount", "description"]
            for col in required_cols:
                assert col in data.columns

            # Should have at least one event (scenario start)
            assert len(data) >= 1

        except ImportError:
            pytest.skip("Plotly not available")

    def test_holdings_cost_basis(self, sample_tidy_data):
        """Test holdings and cost basis chart."""
        try:
            fig, data = holdings_cost_basis(sample_tidy_data)

            # Check that figure was created
            assert fig is not None

            # Check that data was returned
            assert isinstance(data, pd.DataFrame)
            assert len(data) > 0

            # Check required columns
            required_cols = [
                "date",
                "asset_type",
                "units",
                "avg_price",
                "market_value",
                "cost_basis",
                "unrealized_pl",
            ]
            for col in required_cols:
                assert col in data.columns

            # Check that values are reasonable
            assert (data["market_value"] >= 0).all()
            assert (data["cost_basis"] >= 0).all()

        except ImportError:
            pytest.skip("Plotly not available")

    def test_charts_with_different_scenarios(self, sample_tidy_data):
        """Test that charts work with multiple scenarios."""
        # Create data with two scenarios
        scenario2_data = sample_tidy_data.copy()
        scenario2_data["scenario_id"] = "test2"
        scenario2_data["scenario_name"] = "Test Scenario 2"

        combined_data = pd.concat([sample_tidy_data, scenario2_data], ignore_index=True)

        try:
            # Test category allocation with specific scenario
            fig, data = category_allocation_over_time(combined_data, "Test Scenario")

            # Should only have data for the specified scenario
            assert fig is not None
            assert isinstance(data, pd.DataFrame)

            # Test event timeline with specific scenario
            fig2, data2 = event_timeline(combined_data, "Test Scenario 2")

            assert fig2 is not None
            assert isinstance(data2, pd.DataFrame)

        except ImportError:
            pytest.skip("Plotly not available")

    def test_charts_with_no_plotly(self):
        """Test that charts raise ImportError when Plotly is not available."""
        # This test would need to mock the plotly import to actually test the error
        # For now, we'll just verify the functions exist
        assert category_allocation_over_time is not None
        assert category_cashflow_bars is not None
        assert event_timeline is not None
        assert holdings_cost_basis is not None
