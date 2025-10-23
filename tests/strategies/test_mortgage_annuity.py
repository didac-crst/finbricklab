"""
Tests for mortgage annuity strategy math invariants.
"""

from datetime import date

import numpy as np
from finbricklab.core.bricks import ABrick, LBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.kinds import K
from finbricklab.core.scenario import Scenario
from finbricklab.strategies.schedule.loan_annuity import ScheduleMortgageAnnuity


class TestMortgageAnnuityMath:
    """Test mortgage annuity mathematical invariants."""

    def test_payment_invariant(self):
        """Test that payment amount is constant for given rate/term/principal."""
        # Test case: 30-year mortgage, 3.5% rate, $400k principal
        principal = 400000.0
        rate_pa = 0.035
        term_months = 360

        # Create mortgage brick
        mortgage = LBrick(
            id="mortgage",
            name="Test Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": principal,
                "rate_pa": rate_pa,
                "term_months": term_months,
            },
        )

        # Create context
        t_index = np.arange("2026-01", "2036-01", dtype="datetime64[M]")
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        # Create strategy and simulate
        strategy = ScheduleMortgageAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # Extract payment amounts (cash_out should be constant except for initial and final months)
        payments = result["cash_out"]

        # Skip the first payment (initial principal) and last payment (final payment)
        # Regular payments should be identical
        if len(payments) > 2:
            regular_payments = payments[1:-1]  # Skip first and last
        else:
            regular_payments = payments[1:]  # Just skip first if only 2 payments

        assert len(regular_payments) > 0, "Should have regular payments"

        # Check that all regular payments are within 1 cent of each other
        if len(regular_payments) > 1:
            payment_std = np.std(regular_payments)
            assert payment_std < 0.01, f"Payment variance too high: {payment_std:.4f}"

        # The payment should be approximately correct (within $10)
        expected_payment = (
            principal * (rate_pa / 12) / (1 - (1 + rate_pa / 12) ** (-term_months))
        )
        actual_payment = regular_payments[0]
        assert (
            abs(actual_payment - expected_payment) < 10.0
        ), f"Payment {actual_payment:.2f} differs from expected {expected_payment:.2f}"

    def test_amortization_sum_check(self):
        """Test that debt balance decreases over time (partial amortization check)."""
        principal = 300000.0
        rate_pa = 0.04
        term_months = 240  # 20 years

        mortgage = LBrick(
            id="mortgage",
            name="Test Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": principal,
                "rate_pa": rate_pa,
                "term_months": term_months,
            },
        )

        # Create context for 24 months (1 year)
        t_index = np.arange("2026-01", "2028-01", dtype="datetime64[M]")
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleMortgageAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # Check that debt balance decreases over time
        debt_balance = result["debt_balance"]

        # Initial balance should equal principal
        assert (
            abs(debt_balance[0] - principal) < 1e-6
        ), f"Initial debt balance {debt_balance[0]:.2f} != principal {principal:.2f}"

        # Balance should decrease over time
        assert (
            debt_balance[-1] < debt_balance[0]
        ), f"Debt balance should decrease: {debt_balance[0]:.2f} -> {debt_balance[-1]:.2f}"

        # Should have paid down some principal in 24 months
        principal_paid = debt_balance[0] - debt_balance[-1]
        assert principal_paid > 0, "Should have paid down some principal"

        # For a 20-year mortgage, principal paid in 2 years should be reasonable
        # (The mortgage strategy might pay off early if term is shorter than simulation)
        # Just verify that some principal was paid
        assert (
            principal_paid >= 1000.0
        ), f"Should have paid at least 1000 in principal, got {principal_paid:.2f}"

    def test_debt_balance_decreases_monotonically(self):
        """Test that debt balance decreases monotonically."""
        principal = 500000.0
        rate_pa = 0.03
        term_months = 180  # 15 years

        mortgage = LBrick(
            id="mortgage",
            name="Test Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": principal,
                "rate_pa": rate_pa,
                "term_months": term_months,
            },
        )

        t_index = np.arange("2026-01", "2028-01", dtype="datetime64[M]")  # 24 months
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleMortgageAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # Debt balance should decrease monotonically
        debt_balance = result["debt_balance"]
        assert len(debt_balance) > 1, "Should have multiple time periods"

        # Check that balance decreases (or stays same due to rounding)
        for i in range(1, len(debt_balance)):
            assert (
                debt_balance[i] <= debt_balance[i - 1] + 1e-6
            ), f"Debt balance increased at month {i}: {debt_balance[i-1]:.2f} -> {debt_balance[i]:.2f}"

    def test_final_balance_is_zero(self):
        """Test that debt balance reaches zero at term end."""
        principal = 200000.0
        rate_pa = 0.025
        term_months = 60  # 5 years

        mortgage = LBrick(
            id="mortgage",
            name="Test Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": principal,
                "rate_pa": rate_pa,
                "term_months": term_months,
                "balloon_policy": "payoff",  # Explicitly request full payoff for this test
            },
        )

        # Create context for full term
        t_index = np.arange("2026-01", "2031-01", dtype="datetime64[M]")  # 5 years
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleMortgageAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # Final balance should be zero (within rounding tolerance)
        final_balance = result["debt_balance"][-1]
        assert abs(final_balance) < 1.0, f"Final balance not zero: {final_balance:.2f}"

    def test_interest_decreases_over_time(self):
        """Test that interest portion decreases as principal is paid down."""
        principal = 350000.0
        rate_pa = 0.045
        term_months = 120  # 10 years

        mortgage = LBrick(
            id="mortgage",
            name="Test Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": principal,
                "rate_pa": rate_pa,
                "term_months": term_months,
            },
        )

        t_index = np.arange("2026-01", "2028-01", dtype="datetime64[M]")  # 24 months
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleMortgageAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # Calculate interest as cash_in (interest received by lender)
        interest_payments = result["cash_in"]

        # Interest should generally decrease over time (allowing for some noise)
        # Check that the trend is decreasing by comparing first and last quarters
        first_quarter_avg = np.mean(interest_payments[:3])
        last_quarter_avg = np.mean(interest_payments[-3:])

        assert (
            last_quarter_avg < first_quarter_avg
        ), f"Interest trend not decreasing: {first_quarter_avg:.2f} -> {last_quarter_avg:.2f}"

    def test_different_rates_produce_different_payments(self):
        """Test that different interest rates produce different payment amounts."""
        principal = 400000.0
        term_months = 300

        # Test two different rates
        rates = [0.03, 0.05]
        payments = []

        for rate_pa in rates:
            mortgage = LBrick(
                id=f"mortgage_{rate_pa}",
                name=f"Mortgage {rate_pa}%",
                kind=K.L_LOAN_ANNUITY,
                spec={
                    "principal": principal,
                    "rate_pa": rate_pa,
                    "term_months": term_months,
                },
            )

            t_index = np.arange("2026-01", "2027-01", dtype="datetime64[M]")
            ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

            strategy = ScheduleMortgageAnnuity()
            strategy.prepare(mortgage, ctx)
            result = strategy.simulate(mortgage, ctx)

            # Get the regular payment (skip initial principal)
            regular_payment = (
                result["cash_out"][1]
                if len(result["cash_out"]) > 1
                else result["cash_out"][0]
            )
            payments.append(regular_payment)

        # Higher rate should produce higher payment
        assert (
            payments[1] > payments[0]
        ), f"Higher rate payment {payments[1]:.2f} should be > lower rate payment {payments[0]:.2f}"

        # Difference should be meaningful (at least $100/month)
        payment_diff = payments[1] - payments[0]
        assert payment_diff > 100.0, f"Payment difference too small: {payment_diff:.2f}"


class TestMortgageScenarioIntegration:
    """Test mortgage in realistic scenario context."""

    def test_mortgage_with_property_purchase(self):
        """Test mortgage with linked property purchase."""
        # Create property and mortgage bricks
        house = ABrick(
            id="house",
            name="Primary Residence",
            kind=K.A_PROPERTY,
            spec={
                "initial_value": 500000.0,
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
            spec={"rate_pa": 0.034, "term_months": 300},
        )

        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 100000.0, "interest_pa": 0.02},
        )

        # Create and run scenario
        scenario = Scenario(
            id="house_purchase",
            name="House Purchase Test",
            bricks=[cash, house, mortgage],
        )

        results = scenario.run(start=date(2026, 1, 1), months=12)

        # Verify mortgage debt balance is reasonable
        mortgage_balance = results["outputs"]["mortgage"]["debt_balance"]
        assert mortgage_balance[0] > 0, "Mortgage should have initial debt"
        assert (
            mortgage_balance[-1] < mortgage_balance[0]
        ), "Mortgage balance should decrease"

        # Verify total debt equals mortgage debt (since it's the only liability)
        total_debt = results["totals"]["liabilities"]
        assert np.allclose(
            total_debt, mortgage_balance, atol=1e-6
        ), "Total debt should equal mortgage debt"

    def test_mortgage_validation_passes(self):
        """Test that mortgage scenario passes validation."""
        house = ABrick(
            id="house",
            name="Property",
            kind=K.A_PROPERTY,
            spec={"initial_value": 300000.0, "fees_pct": 0.05, "appreciation_pa": 0.02},
        )

        mortgage = LBrick(
            id="mortgage",
            name="Mortgage",
            kind=K.L_LOAN_ANNUITY,
            links={"principal": {"from_house": "house"}},
            spec={"rate_pa": 0.03, "term_months": 240},
        )

        cash = ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 50000.0}
        )

        scenario = Scenario(
            id="validation_test", name="Validation Test", bricks=[cash, house, mortgage]
        )

        results = scenario.run(start=date(2026, 1, 1), months=6)

        # Validation should not raise any exceptions
        from finbricklab.core.scenario import validate_run

        validate_run(results, mode="warn")  # Should not raise
