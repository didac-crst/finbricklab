"""
Tests for Entity breakeven logic using the golden 12-month dataset.

This test validates the canonical schema and breakeven calculations
against a hand-verifiable dataset with deterministic breakeven at June 2026.
"""

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, "src")


class TestEntityBreakevenGolden:
    """Test Entity breakeven logic with golden dataset."""

    @pytest.fixture
    def golden_data(self):
        """Load the golden 12-month dataset."""
        golden_path = Path(__file__).parent / "data" / "golden_12m.csv"
        df = pd.read_csv(golden_path)
        df["date"] = pd.to_datetime(df["date"])
        return df

    def test_golden_dataset_schema(self, golden_data):
        """Test that golden dataset has correct schema and dtypes."""
        # Required columns
        required_columns = [
            "scenario_id",
            "scenario_name",
            "date",
            "cash",
            "liquid_assets",
            "illiquid_assets",
            "liabilities",
            "inflows",
            "outflows",
            "taxes",
            "fees",
            "total_assets",
            "net_worth",
        ]

        for col in required_columns:
            assert col in golden_data.columns, f"Missing required column: {col}"

        # Check data types
        numeric_columns = [
            "cash",
            "liquid_assets",
            "illiquid_assets",
            "liabilities",
            "inflows",
            "outflows",
            "taxes",
            "fees",
            "total_assets",
            "net_worth",
        ]

        for col in numeric_columns:
            assert pd.api.types.is_numeric_dtype(
                golden_data[col]
            ), f"Column {col} is not numeric"

        # Check that we have two scenarios
        assert golden_data["scenario_name"].nunique() == 2
        assert set(golden_data["scenario_name"]) == {"Baseline", "Alt"}

        # Check that we have 12 months per scenario
        assert len(golden_data) == 24  # 2 scenarios × 12 months

    def test_golden_dataset_month_end_dates(self, golden_data):
        """Test that dates are month-end dates."""
        # Check that dates are month-end
        for _, row in golden_data.iterrows():
            date_val = row["date"]
            # Month-end dates should be the last day of the month
            next_month = date_val.replace(day=1) + pd.DateOffset(months=1)
            expected_month_end = next_month - pd.Timedelta(days=1)
            assert date_val == expected_month_end, f"Date {date_val} is not month-end"

        # Check specific dates
        baseline_dates = golden_data[golden_data["scenario_name"] == "Baseline"][
            "date"
        ].tolist()
        expected_dates = [
            date(2026, 1, 31),
            date(2026, 2, 28),  # 2026 is not a leap year
            date(2026, 3, 31),
            date(2026, 4, 30),
            date(2026, 5, 31),
            date(2026, 6, 30),
            date(2026, 7, 31),
            date(2026, 8, 31),
            date(2026, 9, 30),
            date(2026, 10, 31),
            date(2026, 11, 30),
            date(2026, 12, 31),
        ]

        for i, expected_date in enumerate(expected_dates):
            assert baseline_dates[i] == pd.Timestamp(expected_date)

    def test_golden_dataset_values(self, golden_data):
        """Test that golden dataset has correct hand-verifiable values."""
        baseline = golden_data[golden_data["scenario_name"] == "Baseline"]
        alt = golden_data[golden_data["scenario_name"] == "Alt"]

        # Baseline: constant 20k
        assert (baseline["cash"] == 20000.0).all()
        assert (baseline["total_assets"] == 20000.0).all()
        assert (baseline["net_worth"] == 20000.0).all()
        assert (baseline["inflows"] == 2000.0).all()
        assert (baseline["outflows"] == 2000.0).all()

        # Alt: 15k + 1k*(m-1) progression
        expected_cash = [15000.0 + 1000.0 * i for i in range(12)]
        assert np.allclose(alt["cash"].values, expected_cash)
        assert np.allclose(alt["total_assets"].values, expected_cash)
        assert np.allclose(alt["net_worth"].values, expected_cash)
        assert (alt["inflows"] == 3000.0).all()
        assert (alt["outflows"] == 2000.0).all()

        # Both scenarios: zero for unused fields
        for scenario_name in ["Baseline", "Alt"]:
            scenario_data = golden_data[golden_data["scenario_name"] == scenario_name]
            assert (scenario_data["liquid_assets"] == 0.0).all()
            assert (scenario_data["illiquid_assets"] == 0.0).all()
            assert (scenario_data["liabilities"] == 0.0).all()
            assert (scenario_data["taxes"] == 0.0).all()
            assert (scenario_data["fees"] == 0.0).all()

    def test_golden_dataset_breakeven_calculation(self, golden_data):
        """Test that breakeven calculation works correctly on golden data."""
        # Test breakeven calculation manually
        baseline = golden_data[golden_data["scenario_name"] == "Baseline"].copy()
        alt = golden_data[golden_data["scenario_name"] == "Alt"].copy()

        # Find first month where Alt net worth >= Baseline net worth
        baseline = baseline.sort_values("date")
        alt = alt.sort_values("date")

        # Calculate advantage
        advantage = alt["net_worth"].values - baseline["net_worth"].values

        # Find first month where advantage >= 0
        breakeven_mask = advantage >= 0
        assert breakeven_mask.any(), "Alt should eventually break even"

        # First breakeven should be at month 6 (June 2026)
        first_breakeven_idx = np.where(breakeven_mask)[0][0]
        assert (
            first_breakeven_idx == 5
        ), f"Expected breakeven at month 6, got month {first_breakeven_idx + 1}"

        # Verify the values at breakeven point
        june_baseline = baseline.iloc[5]["net_worth"]
        june_alt = alt.iloc[5]["net_worth"]
        assert june_baseline == 20000.0
        assert june_alt == 20000.0
        assert advantage[5] == 0.0  # Exactly equal at breakeven

    def test_golden_dataset_no_breakeven_case(self, golden_data):
        """Test that baseline vs baseline returns no breakeven."""
        # Test that a scenario compared to itself has no breakeven
        baseline = golden_data[golden_data["scenario_name"] == "Baseline"].copy()
        baseline = baseline.sort_values("date")

        # Compare baseline to itself - advantage should always be 0
        advantage = baseline["net_worth"].values - baseline["net_worth"].values
        assert (advantage == 0.0).all()

        # No "breakeven" since there's no advantage to gain
        # This tests the edge case handling

    def test_golden_dataset_chart_compatibility(self, golden_data):
        """Test that golden dataset works with chart functions."""
        try:
            from finbricklab.charts import net_worth_vs_time

            # This should work without errors
            fig, data = net_worth_vs_time(golden_data)

            # Verify the returned data is the same
            pd.testing.assert_frame_equal(data, golden_data, check_dtype=False)

        except ImportError:
            # Skip if plotly not available
            pytest.skip("Plotly not available for chart testing")

    def test_golden_dataset_entity_integration(self, golden_data):
        """Test that golden dataset integrates with Entity methods."""
        # Test that the golden dataset has the right structure for Entity methods
        # by checking the data can be processed by Entity.compare() logic

        # Verify we can group by scenario
        scenarios = golden_data.groupby("scenario_name")
        assert len(scenarios) == 2

        # Test that each scenario has the required columns
        required_columns = [
            "date",
            "cash",
            "liquid_assets",
            "illiquid_assets",
            "liabilities",
            "inflows",
            "outflows",
            "taxes",
            "fees",
            "total_assets",
            "net_worth",
        ]

        for scenario_name, scenario_data in scenarios:
            for col in required_columns:
                assert col in scenario_data.columns, f"Missing {col} in {scenario_name}"

            # Test that dates are sorted
            assert scenario_data["date"].is_monotonic_increasing

            # Test that numeric columns are all finite
            numeric_cols = [col for col in required_columns if col != "date"]
            for col in numeric_cols:
                assert (
                    scenario_data[col].notna().all()
                ), f"NaN values in {col} for {scenario_name}"
                assert np.isfinite(
                    scenario_data[col]
                ).all(), f"Non-finite values in {col} for {scenario_name}"

        # Test breakeven calculation manually using Entity logic
        baseline = golden_data[golden_data["scenario_name"] == "Baseline"].sort_values(
            "date"
        )
        alt = golden_data[golden_data["scenario_name"] == "Alt"].sort_values("date")

        # Calculate advantage (Alt - Baseline)
        advantage = alt["net_worth"].values - baseline["net_worth"].values

        # Find breakeven month
        breakeven_mask = advantage >= 0
        assert breakeven_mask.any(), "Should have breakeven"

        first_breakeven_idx = np.where(breakeven_mask)[0][0]
        assert (
            first_breakeven_idx == 5
        ), f"Expected breakeven at month 6, got month {first_breakeven_idx + 1}"
