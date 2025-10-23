"""
Tests for German mortgage scenarios with new parameter aliases.
"""

from datetime import date

import numpy as np
from finbricklab.core.bricks import LBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.kinds import K
from finbricklab.strategies.schedule.mortgage_annuity import ScheduleMortgageAnnuity


class TestGermanMortgageScenarios:
    """Test German mortgage scenarios with new parameter aliases."""

    def test_german_mortgage_annuity_math(self):
        """Test German mortgage annuity calculation with exact numbers."""
        principal = 420_000.0
        interest_rate_pa = 0.013  # 1.3%
        amortization_pa = 0.04  # 4%

        mortgage = LBrick(
            id="german_mortgage",
            name="German Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": principal,
                "interest_rate_pa": interest_rate_pa,  # New alias
                "amortization_pa": amortization_pa,  # New alias
            },
        )

        # Create context for full term
        t_index = np.arange("2026-01", "2047-01", dtype="datetime64[M]")  # ~21 years
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleMortgageAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # Expected calculations:
        # term_months ≈ 260 (from term_from_amort)
        # Monthly payment ≈ €1,855
        # First month: interest ≈ €455, principal ≈ €1,400

        debt_balance = result["debt_balance"]
        cash_out = result["cash_out"]

        # Check that term was calculated correctly (should be ~260 months)
        term_months = mortgage.spec["term_months"]
        assert 250 <= term_months <= 270, f"Expected term ~260, got {term_months}"

        # Check monthly payment amount (should be ~€1,854)
        monthly_payment = cash_out[1]  # First payment
        assert (
            1850 <= monthly_payment <= 1860
        ), f"Expected payment ~€1,854, got {monthly_payment:.2f}"

        # Check first month interest and principal breakdown
        first_interest = debt_balance[0] * interest_rate_pa / 12
        first_principal = monthly_payment - first_interest

        assert (
            450 <= first_interest <= 460
        ), f"Expected first interest ~€455, got {first_interest:.2f}"
        assert (
            1395 <= first_principal <= 1405
        ), f"Expected first principal ~€1,399, got {first_principal:.2f}"

    def test_german_mortgage_10_year_balloon(self):
        """Test 10-year German mortgage with balloon payment scenario."""
        principal = 420_000.0
        interest_rate_pa = 0.013  # 1.3%
        amortization_pa = 0.04  # 4%

        mortgage = LBrick(
            id="german_mortgage",
            name="German Mortgage",
            kind=K.L_LOAN_ANNUITY,
            start_date=date(2018, 7, 1),
            end_date=date(2028, 7, 1),  # 10-year credit window
            spec={
                "principal": principal,
                "interest_rate_pa": interest_rate_pa,
                "amortization_pa": amortization_pa,
                "balloon_policy": "refinance",
            },
        )

        # Create context for 10 years
        t_index = np.arange("2018-07", "2028-08", dtype="datetime64[M]")  # 10 years
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleMortgageAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        debt_balance = result["debt_balance"]
        events = result["events"]

        # Check that after 10 years (120 months), residual is ~€240,769
        final_balance = debt_balance[-1]
        assert (
            240_000 <= final_balance <= 241_000
        ), f"Expected residual ~€240,769, got {final_balance:.2f}"

        # Check that balloon_due event was emitted
        balloon_events = [e for e in events if e.kind == "balloon_due"]
        assert len(balloon_events) == 1, "Expected exactly one balloon_due event"
        assert balloon_events[0].t == np.datetime64(
            "2028-07"
        ), "Balloon event should be in July 2028"

    def test_german_mortgage_10_year_payoff(self):
        """Test 10-year German mortgage with payoff policy."""
        principal = 420_000.0
        interest_rate_pa = 0.013  # 1.3%
        amortization_pa = 0.04  # 4%

        mortgage = LBrick(
            id="german_mortgage",
            name="German Mortgage",
            kind=K.L_LOAN_ANNUITY,
            start_date=date(2018, 7, 1),
            end_date=date(2028, 7, 1),  # 10-year credit window
            spec={
                "principal": principal,
                "interest_rate_pa": interest_rate_pa,
                "amortization_pa": amortization_pa,
                "balloon_policy": "payoff",
            },
        )

        # Create context for 10 years
        t_index = np.arange("2018-07", "2028-08", dtype="datetime64[M]")  # 10 years
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleMortgageAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        debt_balance = result["debt_balance"]
        cash_out = result["cash_out"]
        events = result["events"]

        # Check that final debt balance is zero
        final_balance = debt_balance[-1]
        assert (
            abs(final_balance) < 1.0
        ), f"Expected zero final balance, got {final_balance:.2f}"

        # Check that final cash outflow equals the residual
        final_cash_out = cash_out[-1]
        assert (
            242_000 <= final_cash_out <= 243_000
        ), f"Expected final cash out ~€242,623, got {final_cash_out:.2f}"

        # Check that balloon_payoff event was emitted
        balloon_events = [e for e in events if e.kind == "balloon_payoff"]
        assert len(balloon_events) == 1, "Expected exactly one balloon_payoff event"
        assert balloon_events[0].t == np.datetime64(
            "2028-07"
        ), "Balloon event should be in July 2028"

    def test_german_mortgage_with_new_aliases(self):
        """Test German mortgage using all new parameter aliases."""
        principal = 420_000.0

        mortgage = LBrick(
            id="german_mortgage",
            name="German Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": principal,
                "interest_rate_pa": 0.013,  # New alias for rate_pa
                "amortization_rate_pa": 0.04,  # New alias for amortization_pa
                "amortization_term_months": 300,  # New alias for term_months
            },
        )

        # Create context for full term
        t_index = np.arange("2026-01", "2051-01", dtype="datetime64[M]")  # 25 years
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleMortgageAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # Check that aliases were applied correctly
        assert mortgage.spec["rate_pa"] == 0.013
        assert mortgage.spec["amortization_pa"] == 0.04
        assert mortgage.spec["term_months"] == 300

        # Check that mortgage completes in 25 years (within rounding tolerance)
        debt_balance = result["debt_balance"]
        final_balance = debt_balance[-1]
        assert (
            abs(final_balance) < 2000.0
        ), f"Expected near-zero final balance, got {final_balance:.2f}"

    def test_german_mortgage_credit_window_aliases(self):
        """Test German mortgage with credit window aliases."""
        principal = 420_000.0

        mortgage = LBrick(
            id="german_mortgage",
            name="German Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": principal,
                "interest_rate_pa": 0.013,
                "amortization_pa": 0.04,
                "credit_term_months": 120,  # 10-year credit window
                "balloon_policy": "refinance",
            },
        )

        # Create context for 15 years (longer than credit window)
        t_index = np.arange("2018-07", "2033-08", dtype="datetime64[M]")  # 15 years
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleMortgageAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # Check that credit_term_months was applied to duration_m
        assert mortgage.duration_m == 120

        # Check that mortgage becomes inactive after 10 years
        debt_balance = result["debt_balance"]

        # After 10 years (index 120), debt should be outstanding
        balance_at_10_years = debt_balance[120]
        assert (
            240_000 <= balance_at_10_years <= 241_000
        ), f"Expected residual ~€240,769 at 10 years, got {balance_at_10_years:.2f}"

        # Check that balloon_due event was emitted at the right time
        events = result["events"]
        balloon_events = [e for e in events if e.kind == "balloon_due"]
        assert len(balloon_events) == 1, "Expected exactly one balloon_due event"

    def test_german_mortgage_fix_rate_months(self):
        """Test German mortgage with fix_rate_months parameter."""
        principal = 420_000.0

        mortgage = LBrick(
            id="german_mortgage",
            name="German Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": principal,
                "interest_rate_pa": 0.013,
                "amortization_pa": 0.04,
                "fix_rate_months": 120,  # 10-year fix rate period
                "balloon_policy": "refinance",
            },
        )

        # Create context for 15 years
        t_index = np.arange("2018-07", "2033-08", dtype="datetime64[M]")  # 15 years
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleMortgageAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # Check that fix_rate_months was applied to duration_m
        assert mortgage.duration_m == 120

        # Check that mortgage becomes inactive after 10 years
        debt_balance = result["debt_balance"]
        balance_at_10_years = debt_balance[120]
        assert (
            240_000 <= balance_at_10_years <= 241_000
        ), f"Expected residual ~€240,769 at 10 years, got {balance_at_10_years:.2f}"

    def test_zero_interest_edge_case(self):
        """Test German mortgage with zero interest rate."""
        principal = 420_000.0

        mortgage = LBrick(
            id="zero_interest_mortgage",
            name="Zero Interest Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": principal,
                "interest_rate_pa": 0.0,  # Zero interest
                "amortization_pa": 0.04,  # 4% amortization
            },
        )

        # Create context for full term
        t_index = np.arange("2026-01", "2051-01", dtype="datetime64[M]")  # 25 years
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleMortgageAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # With zero interest, term should be 12 / 0.04 = 300 months
        term_months = mortgage.spec["term_months"]
        assert (
            term_months == 300
        ), f"Expected 300 months for zero interest, got {term_months}"

        # Monthly payment should be principal / term_months
        expected_payment = principal / term_months
        cash_out = result["cash_out"]
        actual_payment = cash_out[1]  # First payment
        assert (
            abs(actual_payment - expected_payment) < 1.0
        ), f"Expected linear payment {expected_payment:.2f}, got {actual_payment:.2f}"

        # Final balance should be close to zero (within rounding tolerance)
        debt_balance = result["debt_balance"]
        final_balance = debt_balance[-1]
        assert (
            abs(final_balance) < 2000.0
        ), f"Expected near-zero final balance, got {final_balance:.2f}"
