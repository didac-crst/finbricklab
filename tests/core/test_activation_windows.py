"""
Tests for activation windows and delayed brick activation.
"""

from datetime import date

import numpy as np
from finbricklab.core.bricks import ABrick, FBrick
from finbricklab.core.kinds import K
from finbricklab.core.scenario import Scenario


class TestActivationWindows:
    """Test activation window functionality."""

    def test_delayed_activation_starts_at_correct_time(self):
        """Test that bricks with start_date activate at the correct time."""
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 10000.0, "interest_pa": 0.02},
        )

        # Income that starts in month 3
        income = FBrick(
            id="income",
            name="Delayed Income",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 4000.0},
            start_date=date(2026, 3, 1),  # Starts in month 3
        )

        scenario = Scenario(
            id="delayed_activation",
            name="Delayed Activation Test",
            bricks=[cash, income],
        )

        results = scenario.run(start=date(2026, 1, 1), months=6)

        # Check that income starts generating cash flows in month 3 (index 2)
        income_output = results["outputs"]["income"]
        cash_in = income_output["cash_in"]

        # First two months should have no cash flows
        assert cash_in[0] == 0, "Month 1 should have no income"
        assert cash_in[1] == 0, "Month 2 should have no income"

        # Month 3 onwards should have income
        assert cash_in[2] == 4000.0, "Month 3 should have income"
        assert cash_in[3] == 4000.0, "Month 4 should have income"
        assert cash_in[4] == 4000.0, "Month 5 should have income"
        assert cash_in[5] == 4000.0, "Month 6 should have income"

    def test_activation_window_with_end_date(self):
        """Test activation window that ends before simulation end."""
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 5000.0},
        )

        # Income that runs for only 3 months (months 2-4)
        income = FBrick(
            id="income",
            name="Temporary Income",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 3000.0},
            start_date=date(2026, 2, 1),
            end_date=date(2026, 4, 30),  # Ends in month 4
        )

        scenario = Scenario(
            id="temporary_income", name="Temporary Income Test", bricks=[cash, income]
        )

        results = scenario.run(start=date(2026, 1, 1), months=6)

        # Check activation window
        income_output = results["outputs"]["income"]
        cash_in = income_output["cash_in"]

        # Month 1: no income
        assert cash_in[0] == 0, "Month 1 should have no income"

        # Months 2-4: should have income
        assert cash_in[1] == 3000.0, "Month 2 should have income"
        assert cash_in[2] == 3000.0, "Month 3 should have income"
        assert cash_in[3] == 3000.0, "Month 4 should have income"

        # Months 5-6: no income (ended)
        assert cash_in[4] == 0, "Month 5 should have no income"
        assert cash_in[5] == 0, "Month 6 should have no income"

    def test_duration_based_activation_window(self):
        """Test activation window using duration instead of end_date."""
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 8000.0},
        )

        # Expense that runs for 4 months starting in month 2
        expense = FBrick(
            id="expense",
            name="Temporary Expense",
            kind=K.F_EXPENSE_RECURRING,
            spec={"amount_monthly": 2000.0},
            start_date=date(2026, 2, 1),
            duration_m=4,  # Runs for 4 months
        )

        scenario = Scenario(
            id="duration_expense", name="Duration-Based Expense", bricks=[cash, expense]
        )

        results = scenario.run(start=date(2026, 1, 1), months=8)

        # Check duration-based window
        expense_output = results["outputs"]["expense"]
        cash_out = expense_output["cash_out"]

        # Month 1: no expense
        assert cash_out[0] == 0, "Month 1 should have no expense"

        # Months 2-5: should have expense (4 months duration)
        assert cash_out[1] == 2000.0, "Month 2 should have expense"
        assert cash_out[2] == 2000.0, "Month 3 should have expense"
        assert cash_out[3] == 2000.0, "Month 4 should have expense"
        assert cash_out[4] == 2000.0, "Month 5 should have expense"

        # Months 6-8: no expense (duration ended)
        assert cash_out[5] == 0, "Month 6 should have no expense"
        assert cash_out[6] == 0, "Month 7 should have no expense"
        assert cash_out[7] == 0, "Month 8 should have no expense"

    def test_equity_neutral_activation_window(self):
        """Test that activation windows apply equity-neutral masking."""
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 15000.0, "interest_pa": 0.02},
        )

        # Asset that starts in month 2 and ends in month 5
        asset = ABrick(
            id="asset",
            name="Temporary Asset",
            kind=K.A_PROPERTY,
            spec={
                "initial_value": 100000.0,
                "fees_pct": 0.05,
                "appreciation_pa": 0.05,
                "sell_on_window_end": True,  # Auto-sell when window ends
            },
            start_date=date(2026, 2, 1),
            end_date=date(2026, 5, 31),
        )

        scenario = Scenario(
            id="equity_neutral_asset",
            name="Equity-Neutral Asset Window",
            bricks=[cash, asset],
        )

        results = scenario.run(start=date(2026, 1, 1), months=8)

        # Check asset behavior during window
        asset_output = results["outputs"]["asset"]
        asset_value = asset_output["assets"]

        # Month 1: no asset value (not active)
        assert asset_value[0] == 0, "Month 1 should have no asset value"

        # Months 2-4: asset should have value
        assert asset_value[1] > 0, "Month 2 should have asset value"
        assert asset_value[2] > 0, "Month 3 should have asset value"
        assert asset_value[3] > 0, "Month 4 should have asset value"

        # Month 5: asset sold at end of window, so end-of-month value is 0
        assert asset_value[4] == 0, "Month 5 should have 0 asset value after sale"

        # Check that sale proceeds were received in month 5
        cash_output = results["outputs"]["asset"]
        cash_in = cash_output["cash_in"]
        assert cash_in[4] > 0, "Month 5 should have cash inflow from asset sale"

        # Month 6+: asset value should be 0 (window ended, auto-sold)
        assert asset_value[5] == 0, "Month 6 should have no asset value (sold)"
        assert asset_value[6] == 0, "Month 7 should have no asset value (sold)"
        assert asset_value[7] == 0, "Month 8 should have no asset value (sold)"

        # Check that auto-sell generates cash inflow in month 5 (proceeds from sale)
        # Note: sales generate cash_in (proceeds), not cash_out (costs)

        # Check cash flows - property purchase happens when it becomes active
        cash_out = asset_output["cash_out"]
        assert cash_out[0] == 0, "Month 1 should have no cash flows (not active)"
        assert cash_out[1] > 0, "Month 2 should have cash outflow (property purchase)"
        assert cash_out[2] == 0, "Month 3 should have no additional cash flows"
        assert cash_out[3] == 0, "Month 4 should have no additional cash flows"
        assert cash_out[5] == 0, "Month 6 should have no cash flows (sold)"

    def test_multiple_overlapping_windows(self):
        """Test multiple bricks with overlapping activation windows."""
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 20000.0},
        )

        # Income that runs months 2-6
        income = FBrick(
            id="income",
            name="Contract Income",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 5000.0},
            start_date=date(2026, 2, 1),
            end_date=date(2026, 6, 30),
        )

        # Expense that runs months 4-8 (overlaps with income)
        expense = FBrick(
            id="expense",
            name="Project Expense",
            kind=K.F_EXPENSE_RECURRING,
            spec={"amount_monthly": 3000.0},
            start_date=date(2026, 4, 1),
            end_date=date(2026, 8, 31),
        )

        scenario = Scenario(
            id="overlapping_windows",
            name="Overlapping Windows Test",
            bricks=[cash, income, expense],
        )

        results = scenario.run(start=date(2026, 1, 1), months=10)

        # Check income window (months 2-6)
        income_output = results["outputs"]["income"]
        income_cash_in = income_output["cash_in"]

        assert income_cash_in[0] == 0, "Month 1: no income"
        assert income_cash_in[1] == 5000.0, "Month 2: income starts"
        assert income_cash_in[2] == 5000.0, "Month 3: income continues"
        assert income_cash_in[3] == 5000.0, "Month 4: income continues"
        assert income_cash_in[4] == 5000.0, "Month 5: income continues"
        assert income_cash_in[5] == 5000.0, "Month 6: income ends"
        assert income_cash_in[6] == 0, "Month 7: no income"

        # Check expense window (months 4-8)
        expense_output = results["outputs"]["expense"]
        expense_cash_out = expense_output["cash_out"]

        assert expense_cash_out[0] == 0, "Month 1: no expense"
        assert expense_cash_out[1] == 0, "Month 2: no expense"
        assert expense_cash_out[2] == 0, "Month 3: no expense"
        assert expense_cash_out[3] == 3000.0, "Month 4: expense starts"
        assert expense_cash_out[4] == 3000.0, "Month 5: expense continues"
        assert expense_cash_out[5] == 3000.0, "Month 6: expense continues"
        assert expense_cash_out[6] == 3000.0, "Month 7: expense continues"
        assert expense_cash_out[7] == 3000.0, "Month 8: expense ends"
        assert expense_cash_out[8] == 0, "Month 9: no expense"

        # Check overlap period (months 4-6): both income and expense active
        for month in [3, 4, 5]:  # indices for months 4-6
            assert (
                income_cash_in[month] > 0
            ), f"Month {month+1}: income should be active"
            assert (
                expense_cash_out[month] > 0
            ), f"Month {month+1}: expense should be active"

    def test_window_end_event_generation(self):
        """Test that window end events are generated correctly."""
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 10000.0},
        )

        # Asset with defined end date
        asset = ABrick(
            id="asset",
            name="Temporary Asset",
            kind=K.A_PROPERTY,
            spec={
                "initial_value": 50000.0,
                "fees_pct": 0.03,
                "appreciation_pa": 0.03,
                "sell_on_window_end": False,
            },
            start_date=date(2026, 2, 1),
            duration_m=3,  # Runs for 3 months
        )

        scenario = Scenario(
            id="window_events", name="Window End Events Test", bricks=[cash, asset]
        )

        results = scenario.run(start=date(2026, 1, 1), months=6)

        # Check that window end event is generated
        asset_output = results["outputs"]["asset"]
        events = asset_output["events"]

        # Should have exactly one window_end event
        window_end_events = [e for e in events if e.kind == "window_end"]
        assert len(window_end_events) == 1, "Should have exactly one window_end event"

        event = window_end_events[0]
        assert event.message == "Brick 'Temporary Asset' window ended"
        assert "brick_id" in event.meta
        assert event.meta["brick_id"] == "asset"

        # Event should occur in month 3 (April 2026) - last month of 3-month duration
        # start=2026-02-01, duration_m=3 => Feb, Mar, Apr are active
        event_time = event.t
        expected_time = np.datetime64("2026-04", "M")  # April 2026 (last active month)
        assert (
            event_time == expected_time
        ), f"Event time {event_time} != expected {expected_time}"

    def test_activation_window_validation_passes(self):
        """Test that scenarios with activation windows pass validation."""
        cash = ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 25000.0}
        )

        income = FBrick(
            id="income",
            name="Income",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 4000.0},
            start_date=date(2026, 2, 1),
            duration_m=6,
        )

        expense = FBrick(
            id="expense",
            name="Expense",
            kind=K.F_EXPENSE_RECURRING,
            spec={"amount_monthly": 2000.0},
            start_date=date(2026, 3, 1),
            end_date=date(2026, 7, 31),
        )

        scenario = Scenario(
            id="window_validation_test",
            name="Window Validation Test",
            bricks=[cash, income, expense],
        )

        results = scenario.run(start=date(2026, 1, 1), months=8)

        # Validation should not raise any exceptions
        from finbricklab.core.scenario import validate_run

        validate_run(results, mode="warn")  # Should not raise
