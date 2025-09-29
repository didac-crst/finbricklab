"""
Tests for basic scenario functionality.
"""

from datetime import date

from finbricklab import ABrick, LBrick, Scenario


class TestScenarioBasics:
    """Test basic scenario creation and functionality."""

    def test_scenario_creation(self):
        """Test creating a scenario with bricks."""
        cash = ABrick(
            id="cash",
            name="Main Cash",
            kind="a.cash",
            spec={"initial_balance": 1000.0, "interest_pa": 0.02},
        )

        scenario = Scenario(id="test", name="Test Scenario", bricks=[cash])

        assert scenario.id == "test"
        assert scenario.name == "Test Scenario"
        assert len(scenario.bricks) == 1
        assert scenario.bricks[0].id == "cash"

    def test_scenario_run_basic(self):
        """Test running a basic scenario."""
        cash = ABrick(
            id="cash",
            name="Main Cash",
            kind="a.cash",
            spec={"initial_balance": 1000.0, "interest_pa": 0.02},
        )

        scenario = Scenario(id="test", name="Test Scenario", bricks=[cash])

        # Run for 12 months
        results = scenario.run(start=date(2026, 1, 1), months=12)

        assert "outputs" in results
        assert "totals" in results
        assert "cash" in results["outputs"]

        # Check that cash balance grows with interest
        cash_balance = results["outputs"]["cash"]["asset_value"]
        assert cash_balance[0] > 1000.0  # Initial balance plus interest
        assert cash_balance[-1] > cash_balance[0]  # Balance grows over time

    def test_scenario_with_property_and_mortgage(self):
        """Test a more complex scenario with property and mortgage."""
        cash = ABrick(
            id="cash",
            name="Main Cash",
            kind="a.cash",
            spec={"initial_balance": 50000.0, "interest_pa": 0.02},
        )

        house = ABrick(
            id="house",
            name="Property",
            kind="a.property_discrete",
            spec={
                "initial_value": 400000.0,
                "fees_pct": 0.095,
                "appreciation_pa": 0.02,
                "down_payment": 40000.0,
            },
        )

        mortgage = LBrick(
            id="mortgage",
            name="Home Loan",
            kind="l.mortgage.annuity",
            links={"principal": {"from_house": "house"}},
            spec={"rate_pa": 0.034, "term_months": 300},
        )

        scenario = Scenario(
            id="house_purchase",
            name="House Purchase Scenario",
            bricks=[cash, house, mortgage],
        )

        # Run for 12 months
        results = scenario.run(start=date(2026, 1, 1), months=12)

        assert "outputs" in results
        assert "totals" in results

        # Check that all bricks are present
        assert "cash" in results["outputs"]
        assert "house" in results["outputs"]
        assert "mortgage" in results["outputs"]

        # Check that property value appreciates (before auto-dispose)
        house_value = results["outputs"]["house"]["asset_value"]
        assert house_value[0] > 0  # Property has value
        # Find the last non-zero value (before auto-dispose)
        non_zero_values = house_value[house_value > 0]
        if len(non_zero_values) > 1:
            assert non_zero_values[-1] > non_zero_values[0]  # Value appreciates

        # Check that mortgage balance decreases
        mortgage_balance = results["outputs"]["mortgage"]["debt_balance"]
        assert mortgage_balance[0] > 0  # Initial mortgage balance
        assert mortgage_balance[-1] < mortgage_balance[0]  # Balance decreases

    def test_scenario_validation(self):
        """Test scenario validation."""
        cash = ABrick(
            id="cash",
            name="Main Cash",
            kind="a.cash",
            spec={"initial_balance": 1000.0, "interest_pa": 0.02},
        )

        scenario = Scenario(id="test", name="Test Scenario", bricks=[cash])

        # Run scenario
        scenario.run(start=date(2026, 1, 1), months=12)

        # Validate results (should not raise)
        scenario.validate()

        # Test with warning mode
        scenario.validate(mode="warn")
