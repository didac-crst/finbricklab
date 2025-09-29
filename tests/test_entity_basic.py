"""
Basic tests for Entity functionality.
"""

import sys
from datetime import date

import numpy as np

sys.path.insert(0, "src")

from finbricklab.core.bricks import ABrick  # noqa: E402
from finbricklab.core.entity import Entity  # noqa: E402
from finbricklab.core.kinds import K  # noqa: E402
from finbricklab.core.scenario import Scenario  # noqa: E402


class TestEntityBasic:
    """Basic tests for Entity functionality."""

    def test_entity_creation(self):
        """Test basic Entity creation."""
        entity = Entity(id="test_entity", name="Test Entity", base_currency="EUR")

        assert entity.id == "test_entity"
        assert entity.name == "Test Entity"
        assert entity.base_currency == "EUR"
        assert entity.scenarios == []
        assert entity.assumptions == {}
        assert entity.benchmarks == {}

    def test_scenario_to_canonical_frame(self):
        """Test Scenario.to_canonical_frame() method."""
        # Create a simple scenario
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 1000.0},
        )

        scenario = Scenario(
            id="test_scenario", name="Test Scenario", bricks=[cash], currency="EUR"
        )

        # Run scenario
        scenario.run(start=date(2026, 1, 1), months=3)

        # Get canonical frame
        canonical_df = scenario.to_canonical_frame()

        # Check required columns
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

        for col in required_columns:
            assert col in canonical_df.columns, f"Missing required column: {col}"

        # Check data types
        assert canonical_df["cash"].dtype == np.float64
        assert canonical_df["liquid_assets"].dtype == np.float64
        assert canonical_df["illiquid_assets"].dtype == np.float64
        assert canonical_df["liabilities"].dtype == np.float64
        assert canonical_df["inflows"].dtype == np.float64
        assert canonical_df["outflows"].dtype == np.float64
        assert canonical_df["taxes"].dtype == np.float64
        assert canonical_df["fees"].dtype == np.float64
        assert canonical_df["total_assets"].dtype == np.float64
        assert canonical_df["net_worth"].dtype == np.float64

        # Check length
        assert len(canonical_df) == 3  # 3 months

        # Check basic values
        assert canonical_df["cash"].iloc[0] == 1000.0
        assert canonical_df["total_assets"].iloc[0] == 1000.0
        assert canonical_df["net_worth"].iloc[0] == 1000.0

    def test_entity_compare(self):
        """Test Entity.compare() method."""
        # Create two scenarios
        cash1 = ABrick(
            id="cash1",
            name="Cash Account 1",
            kind=K.A_CASH,
            spec={"initial_balance": 1000.0},
        )

        cash2 = ABrick(
            id="cash2",
            name="Cash Account 2",
            kind=K.A_CASH,
            spec={"initial_balance": 2000.0},
        )

        scenario1 = Scenario(
            id="scenario1", name="Scenario 1", bricks=[cash1], currency="EUR"
        )

        scenario2 = Scenario(
            id="scenario2", name="Scenario 2", bricks=[cash2], currency="EUR"
        )

        # Run scenarios
        scenario1.run(start=date(2026, 1, 1), months=3)
        scenario2.run(start=date(2026, 1, 1), months=3)

        # Create entity
        entity = Entity(
            id="test_entity", name="Test Entity", scenarios=[scenario1, scenario2]
        )

        # Compare scenarios
        comparison_df = entity.compare(["scenario1", "scenario2"])

        # Check structure
        expected_columns = [
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
            "scenario_id",
            "scenario_name",
        ]

        for col in expected_columns:
            assert col in comparison_df.columns, f"Missing column: {col}"

        # Check length (2 scenarios × 3 months = 6 rows)
        assert len(comparison_df) == 6

        # Check scenario names
        assert set(comparison_df["scenario_name"]) == {"Scenario 1", "Scenario 2"}

        # Check that scenario1 has lower cash values
        scenario1_data = comparison_df[comparison_df["scenario_id"] == "scenario1"]
        scenario2_data = comparison_df[comparison_df["scenario_id"] == "scenario2"]

        assert scenario1_data["cash"].iloc[0] == 1000.0
        assert scenario2_data["cash"].iloc[0] == 2000.0

    def test_entity_breakeven_table(self):
        """Test Entity.breakeven_table() method."""
        # Create scenarios with different growth rates
        cash1 = ABrick(
            id="cash1",
            name="Cash Account 1",
            kind=K.A_CASH,
            spec={"initial_balance": 1000.0},
        )

        cash2 = ABrick(
            id="cash2",
            name="Cash Account 2",
            kind=K.A_CASH,
            spec={"initial_balance": 500.0},
        )

        scenario1 = Scenario(
            id="baseline", name="Baseline", bricks=[cash1], currency="EUR"
        )

        scenario2 = Scenario(
            id="alternative", name="Alternative", bricks=[cash2], currency="EUR"
        )

        # Run scenarios
        scenario1.run(start=date(2026, 1, 1), months=12)
        scenario2.run(start=date(2026, 1, 1), months=12)

        # Create entity
        entity = Entity(
            id="test_entity", name="Test Entity", scenarios=[scenario1, scenario2]
        )

        # Calculate breakeven table
        breakeven_df = entity.breakeven_table("baseline")

        # Check structure
        expected_columns = ["scenario_id", "scenario_name", "breakeven_month"]
        for col in expected_columns:
            assert col in breakeven_df.columns, f"Missing column: {col}"

        # Should have one row for the alternative scenario
        assert len(breakeven_df) == 1
        assert breakeven_df["scenario_id"].iloc[0] == "alternative"

        # Alternative scenario should never break even (lower starting value)
        assert breakeven_df["breakeven_month"].iloc[0] is None

    def test_entity_fees_taxes_summary(self):
        """Test Entity.fees_taxes_summary() method."""
        # Create scenario
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 1000.0},
        )

        scenario = Scenario(
            id="test_scenario", name="Test Scenario", bricks=[cash], currency="EUR"
        )

        # Run scenario
        scenario.run(start=date(2026, 1, 1), months=12)

        # Create entity
        entity = Entity(id="test_entity", name="Test Entity", scenarios=[scenario])

        # Calculate fees/taxes summary
        summary_df = entity.fees_taxes_summary(horizons=[6, 12])

        # Check structure
        expected_columns = [
            "scenario_id",
            "scenario_name",
            "horizon_months",
            "cumulative_fees",
            "cumulative_taxes",
        ]

        for col in expected_columns:
            assert col in summary_df.columns, f"Missing column: {col}"

        # Should have 2 rows (2 horizons)
        assert len(summary_df) == 2

        # Check horizon values
        assert set(summary_df["horizon_months"]) == {6, 12}

        # Fees and taxes should be zero (not tracked in basic cash scenario)
        assert summary_df["cumulative_fees"].sum() == 0.0
        assert summary_df["cumulative_taxes"].sum() == 0.0

    def test_entity_liquidity_runway(self):
        """Test Entity.liquidity_runway() method."""
        # Create scenario
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 1000.0},
        )

        scenario = Scenario(
            id="test_scenario", name="Test Scenario", bricks=[cash], currency="EUR"
        )

        # Run scenario
        scenario.run(start=date(2026, 1, 1), months=12)

        # Create entity
        entity = Entity(id="test_entity", name="Test Entity", scenarios=[scenario])

        # Calculate liquidity runway
        runway_df = entity.liquidity_runway(lookback_months=3, essential_share=0.5)

        # Check structure
        expected_columns = [
            "scenario_id",
            "scenario_name",
            "date",
            "cash",
            "essential_outflows",
            "liquidity_runway_months",
        ]

        for col in expected_columns:
            assert col in runway_df.columns, f"Missing column: {col}"

        # Should have 12 rows (12 months)
        assert len(runway_df) == 12

        # Check that liquidity runway is calculated
        assert runway_df["liquidity_runway_months"].notna().all()

        # Since outflows are zero, runway should be infinite
        assert np.isinf(runway_df["liquidity_runway_months"]).all()
