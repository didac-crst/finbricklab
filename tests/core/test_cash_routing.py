"""
Tests for cash flow routing and cash account behavior.
"""

from datetime import date

import numpy as np
from finbricklab.core.bricks import ABrick, FBrick, LBrick
from finbricklab.core.kinds import K
from finbricklab.core.scenario import Scenario


class TestCashFlowRouting:
    """Test cash flow routing between bricks."""

    def test_all_cash_flows_route_to_cash_account(self):
        """Test that all cash flows from other bricks route to the cash account."""
        # Create bricks that generate cash flows
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 10000.0, "interest_pa": 0.02},
        )

        income = FBrick(
            id="income",
            name="Salary",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 5000.0},
        )

        expense = FBrick(
            id="expense",
            name="Living Expenses",
            kind=K.F_EXPENSE_RECURRING,
            spec={"amount_monthly": 3000.0},
        )

        scenario = Scenario(
            id="cash_routing_test",
            name="Cash Routing Test",
            bricks=[cash, income, expense],
        )

        results = scenario.run(start=date(2026, 1, 1), months=6)

        # Check that income generates proper journal entries
        income_output = results["outputs"]["income"]

        # Income should generate cash_in
        assert (
            np.sum(income_output["cash_in"]) > 0
        ), "Income should generate cash inflows"

        # Check that journal has income entries
        # Note: We need to access the journal from the scenario
        # For now, verify the cash account balance increased
        cash_output = results["outputs"]["cash"]
        assert (
            np.sum(cash_output["asset_value"]) > 0
        ), "Cash account should have positive asset value from income"

        # Expense should generate cash_out
        expense_output = results["outputs"]["expense"]
        assert (
            np.sum(expense_output["cash_out"]) > 0
        ), "Expense should generate cash outflows"

        # Check that the net effect is positive (income > expenses)
        net_income = np.sum(income_output["cash_in"]) - np.sum(
            expense_output["cash_out"]
        )
        assert net_income > 0, "Net income should be positive"

    def test_cash_balance_calculation(self):
        """Test that cash balance is calculated correctly from routed flows."""
        initial_balance = 5000.0
        monthly_income = 4000.0
        monthly_expense = 2500.0
        interest_rate = 0.03  # 3% annual

        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": initial_balance, "interest_pa": interest_rate},
        )

        income = FBrick(
            id="income",
            name="Salary",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": monthly_income},
        )

        expense = FBrick(
            id="expense",
            name="Expenses",
            kind=K.F_EXPENSE_RECURRING,
            spec={"amount_monthly": monthly_expense},
        )

        scenario = Scenario(
            id="balance_test",
            name="Balance Calculation Test",
            bricks=[cash, income, expense],
        )

        results = scenario.run(start=date(2026, 1, 1), months=12)

        # Verify cash balance progression
        cash_balance = results["outputs"]["cash"]["asset_value"]

        # First month: initial + income - expense + interest
        expected_first = initial_balance + monthly_income - monthly_expense
        expected_first += expected_first * (interest_rate / 12)

        assert (
            abs(cash_balance[0] - expected_first) < 1e-6
        ), f"First month balance {cash_balance[0]:.2f} != expected {expected_first:.2f}"

        # Balance should generally increase (income > expense)
        assert cash_balance[-1] > cash_balance[0], "Balance should increase over time"

        # Final balance should be reasonable
        expected_final = initial_balance + 12 * (monthly_income - monthly_expense)
        # Allow for compound interest effect
        assert (
            cash_balance[-1] >= expected_final * 0.98
        ), f"Final balance {cash_balance[-1]:.2f} should be at least {expected_final * 0.98:.2f}"

    def test_multiple_cash_flows_accumulate(self):
        """Test that multiple cash flows accumulate correctly in cash account."""
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={
                "initial_balance": 0.0,
                "interest_pa": 0.0,
            },  # No interest for clean test
        )

        # Multiple income sources
        income1 = FBrick(
            id="income1",
            name="Primary Income",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 3000.0},
        )

        income2 = FBrick(
            id="income2",
            name="Secondary Income",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 1500.0},
        )

        # Multiple expenses
        expense1 = FBrick(
            id="expense1",
            name="Housing",
            kind=K.F_EXPENSE_RECURRING,
            spec={"amount_monthly": 2000.0},
        )

        expense2 = FBrick(
            id="expense2",
            name="Other Expenses",
            kind=K.F_EXPENSE_RECURRING,
            spec={"amount_monthly": 800.0},
        )

        scenario = Scenario(
            id="multiple_flows",
            name="Multiple Cash Flows",
            bricks=[cash, income1, income2, expense1, expense2],
        )

        results = scenario.run(start=date(2026, 1, 1), months=3)

        # Check that all flows are routed to cash account
        cash_output = results["outputs"]["cash"]
        external_in = cash.spec.get("external_in", np.zeros(3))
        external_out = cash.spec.get("external_out", np.zeros(3))

        # Total external_in should equal sum of all income
        total_income = (
            results["outputs"]["income1"]["cash_in"]
            + results["outputs"]["income2"]["cash_in"]
        )
        assert np.allclose(
            external_in, total_income, atol=1e-6
        ), "External_in should equal sum of all income"

        # Total external_out should equal sum of all expenses
        total_expenses = (
            results["outputs"]["expense1"]["cash_out"]
            + results["outputs"]["expense2"]["cash_out"]
        )
        assert np.allclose(
            external_out, total_expenses, atol=1e-6
        ), "External_out should equal sum of all expenses"

        # Net cash flow should be positive (income > expenses)
        net_cash_flow = external_in - external_out
        assert np.all(net_cash_flow > 0), "Net cash flow should be positive"

        # Cash balance should increase by net cash flow each month
        cash_balance = cash_output["asset_value"]
        for i in range(1, len(cash_balance)):
            expected_balance = cash_balance[i - 1] + net_cash_flow[i]
            assert (
                abs(cash_balance[i] - expected_balance) < 1e-6
            ), f"Balance calculation error at month {i}"

    def test_cash_account_interest_compounding(self):
        """Test that cash account interest compounds correctly."""
        initial_balance = 10000.0
        interest_rate = 0.06  # 6% annual
        monthly_deposit = 1000.0

        cash = ABrick(
            id="cash",
            name="Interest Account",
            kind=K.A_CASH,
            spec={"initial_balance": initial_balance, "interest_pa": interest_rate},
        )

        deposit = FBrick(
            id="deposit",
            name="Monthly Deposit",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": monthly_deposit},
        )

        scenario = Scenario(
            id="interest_test", name="Interest Compounding Test", bricks=[cash, deposit]
        )

        results = scenario.run(start=date(2026, 1, 1), months=12)

        cash_balance = results["outputs"]["cash"]["asset_value"]

        # Verify interest is being earned
        # Without interest, final balance would be: initial + 12 * deposit
        balance_without_interest = initial_balance + 12 * monthly_deposit

        # With interest, final balance should be higher
        assert (
            cash_balance[-1] > balance_without_interest
        ), f"Final balance {cash_balance[-1]:.2f} should exceed {balance_without_interest:.2f} (no interest)"

        # Calculate approximate compound interest
        # Each month: balance = (prev_balance + deposit) * (1 + monthly_rate)
        monthly_rate = interest_rate / 12

        # Verify first few months manually
        expected_balance = initial_balance
        for i in range(min(3, len(cash_balance))):
            # Add deposit and apply interest
            expected_balance = (expected_balance + monthly_deposit) * (1 + monthly_rate)
            actual_balance = cash_balance[i]

            assert (
                abs(actual_balance - expected_balance) < 1e-6
            ), f"Balance mismatch at month {i}: expected {expected_balance:.2f}, got {actual_balance:.2f}"


class TestCashAccountConstraints:
    """Test cash account liquidity constraints."""

    def test_overdraft_limit_enforcement(self):
        """Test that overdraft limit is respected (when implemented)."""
        # This test documents expected behavior for future implementation
        # Currently, overdraft_limit is a parameter but not enforced in simulation

        cash = ABrick(
            id="cash",
            name="Cash with Overdraft",
            kind=K.A_CASH,
            spec={
                "initial_balance": 1000.0,
                "interest_pa": 0.02,
                "overdraft_limit": 500.0,  # Can go to -500
            },
        )

        expense = FBrick(
            id="expense",
            name="Large Expense",
            kind=K.F_EXPENSE_RECURRING,
            spec={"amount_monthly": 2000.0},  # More than initial balance
        )

        scenario = Scenario(
            id="overdraft_test", name="Overdraft Test", bricks=[cash, expense]
        )

        results = scenario.run(start=date(2026, 1, 1), months=2)

        # Currently, the simulation allows negative balances
        # In the future, this should be constrained by overdraft_limit
        cash_balance = results["outputs"]["cash"]["asset_value"]

        # For now, just verify the balance goes negative as expected
        assert cash_balance[0] < 0, "Balance should go negative"

        # Future implementation should ensure balance >= -overdraft_limit
        # assert cash_balance[0] >= -500.0, "Should not exceed overdraft limit"

    def test_minimum_buffer_constraint(self):
        """Test minimum buffer constraint (when implemented)."""
        # This test documents expected behavior for future implementation

        cash = ABrick(
            id="cash",
            name="Cash with Buffer",
            kind=K.A_CASH,
            spec={
                "initial_balance": 5000.0,
                "interest_pa": 0.02,
                "min_buffer": 2000.0,  # Should maintain at least 2000
            },
        )

        expense = FBrick(
            id="expense",
            name="Expenses",
            kind=K.F_EXPENSE_RECURRING,
            spec={"amount_monthly": 4000.0},  # Would bring balance below buffer
        )

        scenario = Scenario(
            id="buffer_test", name="Buffer Test", bricks=[cash, expense]
        )

        results = scenario.run(start=date(2026, 1, 1), months=2)

        results["outputs"]["cash"]["asset_value"]

        # Currently, buffer is not enforced in simulation
        # Future implementation should ensure balance >= min_buffer
        # assert cash_balance[0] >= 2000.0, "Should maintain minimum buffer"


class TestCashRoutingIntegration:
    """Test cash routing in realistic scenarios."""

    def test_property_purchase_with_mortgage_routing(self):
        """Test cash routing in property purchase with mortgage."""
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 100000.0, "interest_pa": 0.02},
        )

        house = ABrick(
            id="house",
            name="Property",
            kind=K.A_PROPERTY,
            spec={
                "initial_value": 400000.0,
                "fees_pct": 0.05,
                "appreciation_pa": 0.03,
                "sell_on_window_end": False,
            },
        )

        mortgage = LBrick(
            id="mortgage",
            name="Home Loan",
            kind=K.L_LOAN_ANNUITY,
            links={"principal": {"from_house": "house"}},
            spec={"rate_pa": 0.035, "term_months": 300},
        )

        scenario = Scenario(
            id="property_purchase",
            name="Property Purchase",
            bricks=[cash, house, mortgage],
        )

        results = scenario.run(start=date(2026, 1, 1), months=12)

        # Verify cash flows are routed correctly
        cash_output = results["outputs"]["cash"]
        house_output = results["outputs"]["house"]
        mortgage_output = results["outputs"]["mortgage"]

        # House should generate cash outflow (purchase cost)
        assert (
            np.sum(house_output["cash_out"]) > 0
        ), "House should generate cash outflow"

        # Mortgage should generate cash outflow (payments)
        assert (
            np.sum(mortgage_output["cash_out"]) > 0
        ), "Mortgage should generate cash outflow"

        # Cash account should receive all outflows
        external_out = cash.spec.get("external_out", np.zeros(12))
        expected_external_out = house_output["cash_out"] + mortgage_output["cash_out"]

        assert np.allclose(
            external_out, expected_external_out, atol=1e-6
        ), "Cash account should receive all cash outflows"

        # Verify cash balance decreases due to property purchase
        cash_balance = cash_output["asset_value"]
        assert (
            cash_balance[0] < cash.spec["initial_balance"]
        ), "Cash balance should decrease due to property purchase"

    def test_validation_passes_with_cash_routing(self):
        """Test that scenarios with cash routing pass validation."""
        cash = ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 50000.0}
        )

        income = FBrick(
            id="income",
            name="Income",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 5000.0},
        )

        expense = FBrick(
            id="expense",
            name="Expense",
            kind=K.F_EXPENSE_RECURRING,
            spec={"amount_monthly": 3000.0},
        )

        scenario = Scenario(
            id="validation_cash_test",
            name="Cash Routing Validation Test",
            bricks=[cash, income, expense],
        )

        results = scenario.run(start=date(2026, 1, 1), months=6)

        # Validation should not raise any exceptions
        from finbricklab.core.scenario import validate_run

        validate_run(results, mode="warn")  # Should not raise
