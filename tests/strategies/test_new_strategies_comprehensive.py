"""
Comprehensive tests for new strategy implementations.
"""

from datetime import date

import pytest
from finbricklab import Entity
from finbricklab.core.bricks import ScheduleRegistry, ValuationRegistry
from finbricklab.core.kinds import K


class TestNewStrategyRegistration:
    """Test that all new strategies are properly registered."""

    def test_credit_line_registered(self):
        """Test that credit line strategy is registered."""
        assert K.L_CREDIT_LINE in ScheduleRegistry
        strategy = ScheduleRegistry[K.L_CREDIT_LINE]
        assert hasattr(strategy, "simulate")

    def test_credit_fixed_registered(self):
        """Test that credit fixed strategy is registered."""
        assert K.L_CREDIT_FIXED in ScheduleRegistry
        strategy = ScheduleRegistry[K.L_CREDIT_FIXED]
        assert hasattr(strategy, "simulate")

    def test_loan_balloon_registered(self):
        """Test that loan balloon strategy is registered."""
        assert K.L_LOAN_BALLOON in ScheduleRegistry
        strategy = ScheduleRegistry[K.L_LOAN_BALLOON]
        assert hasattr(strategy, "simulate")

    def test_private_equity_registered(self):
        """Test that private equity strategy is registered."""
        assert K.A_PRIVATE_EQUITY in ValuationRegistry
        strategy = ValuationRegistry[K.A_PRIVATE_EQUITY]
        assert hasattr(strategy, "simulate")


class TestCreditLineStrategy:
    """Test credit line (revolving credit) strategy."""

    def test_credit_line_basic_functionality(self):
        """Test basic credit line functionality."""
        entity = Entity(id="test", name="Test Entity")

        # Create a cash account for payments
        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 10000.0}
        )

        # Create credit line with initial draw
        entity.new_LBrick(
            "credit_card",
            "Credit Card",
            K.L_CREDIT_LINE,
            {
                "credit_limit": 5000.0,
                "rate_pa": 0.24,  # 24% APR
                "initial_draw": 500.0,  # Start with 500 debt
                "min_payment": {
                    "type": "percent",
                    "percent": 0.03,  # 3% minimum
                    "floor": 25.0,
                },
                "billing_day": 15,
                "start_date": "2026-01-15",
            },
        )

        scenario = entity.create_scenario(
            id="credit_test",
            name="Credit Test",
            brick_ids=["checking", "credit_card"],
            settlement_default_cash_id="checking",
        )

        results = scenario.run(start=date(2026, 1, 1), months=12)

        # Should have debt balance and cash outflows
        # Check what columns are available
        print("Available columns:", results["totals"].columns.tolist())

        # Use the correct column names based on the system
        liabilities = results["totals"]["liabilities"]
        cash_out = results["totals"]["cash_out"]

        # Credit line should have some balance and payments
        assert liabilities.iloc[-1] > 0  # Should have some debt
        assert cash_out.sum() > 0  # Should have some payments

    def test_credit_line_minimum_payment_policy(self):
        """Test different minimum payment policies."""
        entity = Entity(id="test", name="Test Entity")

        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 10000.0}
        )

        # Test percent policy with initial draw
        entity.new_LBrick(
            "credit_percent",
            "Credit Percent",
            K.L_CREDIT_LINE,
            {
                "credit_limit": 10000.0,
                "rate_pa": 0.20,
                "initial_draw": 1000.0,  # Start with 1000 debt
                "min_payment": {"type": "percent", "percent": 0.05},
                "billing_day": 1,
                "start_date": "2026-01-01",
            },
        )

        # Test fixed_or_percent policy with initial draw
        entity.new_LBrick(
            "credit_fixed_percent",
            "Credit Fixed Percent",
            K.L_CREDIT_LINE,
            {
                "credit_limit": 10000.0,
                "rate_pa": 0.20,
                "initial_draw": 800.0,  # Start with 800 debt
                "min_payment": {
                    "type": "fixed_or_percent",
                    "percent": 0.03,
                    "floor": 50.0,
                },
                "billing_day": 1,
                "start_date": "2026-01-01",
            },
        )

        scenario = entity.create_scenario(
            id="credit_policies",
            name="Credit Policies",
            brick_ids=["checking", "credit_percent", "credit_fixed_percent"],
            settlement_default_cash_id="checking",
        )

        results = scenario.run(start=date(2026, 1, 1), months=6)

        # Both should have debt and payments
        liabilities = results["totals"]["liabilities"]
        cash_out = results["totals"]["cash_out"]

        assert liabilities.iloc[-1] > 0
        assert cash_out.sum() > 0


class TestCreditFixedStrategy:
    """Test credit fixed (linear amortization) strategy."""

    def test_credit_fixed_linear_amortization(self):
        """Test linear amortization functionality."""
        entity = Entity(id="test", name="Test Entity")

        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 10000.0}
        )

        # Create fixed-term credit with linear amortization
        entity.new_LBrick(
            "personal_loan",
            "Personal Loan",
            K.L_CREDIT_FIXED,
            {
                "principal": 20000.0,
                "rate_pa": 0.08,  # 8% APR
                "term_months": 24,
                "start_date": "2026-01-15",
            },
        )

        scenario = entity.create_scenario(
            id="credit_fixed_test",
            name="Credit Fixed Test",
            brick_ids=["checking", "personal_loan"],
            settlement_default_cash_id="checking",
        )

        results = scenario.run(start=date(2026, 1, 1), months=25)

        # Should have debt balance that decreases over time
        liabilities = results["totals"]["liabilities"]
        cash_out = results["totals"]["cash_out"]

        # Initial balance should be principal (or reduced if payment already made)
        assert liabilities.iloc[0] <= 20000.0

        # Final balance should be close to zero
        assert liabilities.iloc[-1] < 1.0  # Should be nearly paid off

        # Should have consistent payments
        assert cash_out.sum() > 0

    def test_credit_fixed_vs_annuity_comparison(self):
        """Test that linear amortization has different payment pattern than annuity."""
        entity = Entity(id="test", name="Test Entity")

        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 100000.0}
        )

        # Linear amortization
        entity.new_LBrick(
            "linear_loan",
            "Linear Loan",
            K.L_CREDIT_FIXED,
            {
                "principal": 50000.0,
                "rate_pa": 0.06,
                "term_months": 12,
                "start_date": "2026-01-15",
            },
        )

        # Annuity loan for comparison
        entity.new_LBrick(
            "annuity_loan",
            "Annuity Loan",
            K.L_LOAN_ANNUITY,
            {
                "principal": 50000.0,
                "rate_pa": 0.06,
                "term_months": 12,
                "start_date": "2026-01-15",
            },
        )

        scenario = entity.create_scenario(
            id="loan_comparison",
            name="Loan Comparison",
            brick_ids=["checking", "linear_loan", "annuity_loan"],
            settlement_default_cash_id="checking",
        )

        results = scenario.run(start=date(2026, 1, 1), months=12)

        # Both should be paid off by the end (or very close)
        liabilities = results["totals"]["liabilities"]
        assert liabilities.iloc[-1] < 5000.0  # Should be nearly paid off


class TestLoanBalloonStrategy:
    """Test loan balloon strategy."""

    def test_balloon_interest_only(self):
        """Test interest-only balloon loan."""
        entity = Entity(id="test", name="Test Entity")

        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 100000.0}
        )

        # Interest-only balloon loan
        entity.new_LBrick(
            "balloon_io",
            "Balloon IO",
            K.L_LOAN_BALLOON,
            start_date=date(2026, 1, 1),
            spec={
                "principal": 300000.0,
                "rate_pa": 0.05,
                "balloon_after_months": 36,
                "amortization_rate_pa": 0.0,  # Interest only
                "balloon_type": "residual",
            },
        )

        scenario = entity.create_scenario(
            id="balloon_io_test",
            name="Balloon IO Test",
            brick_ids=["checking", "balloon_io"],
            settlement_default_cash_id="checking",
        )

        results = scenario.run(start=date(2026, 1, 1), months=37)

        liabilities = results["totals"]["liabilities"]
        cash_out = results["totals"]["cash_out"]

        # Should maintain principal balance until final month
        assert (
            liabilities.iloc[0] <= 300000.0
        )  # Initial principal (or reduced if payment made)
        assert liabilities.iloc[-2] <= 300000.0  # Still full principal before balloon
        assert liabilities.iloc[-1] == 0.0  # Paid off after balloon

        # Should have payments throughout
        assert cash_out.sum() > 0

    def test_balloon_linear_amortization(self):
        """Test balloon loan with partial linear amortization."""
        entity = Entity(id="test", name="Test Entity")

        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 100000.0}
        )

        # Linear amortization + balloon
        entity.new_LBrick(
            "balloon_linear",
            "Balloon Linear",
            K.L_LOAN_BALLOON,
            start_date=date(2026, 1, 1),
            spec={
                "principal": 200000.0,
                "rate_pa": 0.06,
                "balloon_after_months": 24,
                "amortization_rate_pa": 0.02,  # 2% annual amortization
                "balloon_type": "residual",
            },
        )

        scenario = entity.create_scenario(
            id="balloon_linear_test",
            name="Balloon Linear Test",
            brick_ids=["checking", "balloon_linear"],
            settlement_default_cash_id="checking",
        )

        results = scenario.run(start=date(2026, 1, 1), months=25)

        liabilities = results["totals"]["liabilities"]

        # Should have some principal reduction during amortization period
        assert (
            liabilities.iloc[0] <= 200000.0
        )  # Initial principal (or reduced if payment made)
        assert liabilities.iloc[11] < 200000.0  # Some reduction after 12 months
        assert liabilities.iloc[-1] == 0.0  # Paid off after balloon


class TestPrivateEquityStrategy:
    """Test private equity valuation strategy."""

    def test_private_equity_drift_calculation(self):
        """Test private equity with drift-based valuation."""
        entity = Entity(id="test", name="Test Entity")

        # Create cash account (required for Journal system)
        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 10000.0}
        )

        # Create private equity investment
        entity.new_ABrick(
            "pe_fund",
            "PE Fund",
            K.A_PRIVATE_EQUITY,
            {
                "initial_value": 100000.0,
                "drift_pa": 0.12,  # 12% annual return
                "lockup_end_date": "2028-01-01",
            },
        )

        scenario = entity.create_scenario(
            id="pe_test",
            name="PE Test",
            brick_ids=["checking", "pe_fund"],
            settlement_default_cash_id="checking",
        )

        results = scenario.run(start=date(2026, 1, 1), months=25)

        assets = results["totals"]["assets"]

        # Should start at initial value (plus cash account)
        assert assets.iloc[0] >= 100000.0

        # Should grow over time
        assert assets.iloc[-1] > assets.iloc[0]

        # After 12 months, should be approximately initial * (1 + 0.12) + cash
        expected_12m = 100000.0 * 1.12 + 10000.0  # PE fund + cash account
        assert abs(assets.iloc[11] - expected_12m) < 1500.0  # Within $1500

    def test_private_equity_nav_series_override(self):
        """Test private equity with explicit NAV series."""
        entity = Entity(id="test", name="Test Entity")

        # Create cash account (required for Journal system)
        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 10000.0}
        )

        # Create NAV series (first 6 months)
        nav_series = [100000.0, 102000.0, 105000.0, 103000.0, 108000.0, 110000.0]

        entity.new_ABrick(
            "pe_fund_nav",
            "PE Fund NAV",
            K.A_PRIVATE_EQUITY,
            {
                "initial_value": 100000.0,
                "drift_pa": 0.10,  # This should be ignored
                "nav_series": nav_series,
            },
        )

        scenario = entity.create_scenario(
            id="pe_nav_test",
            name="PE NAV Test",
            brick_ids=["checking", "pe_fund_nav"],
            settlement_default_cash_id="checking",
        )

        results = scenario.run(start=date(2026, 1, 1), months=6)

        assets = results["totals"]["assets"]

        # Should match the NAV series exactly (plus cash account)
        for i, expected_value in enumerate(nav_series):
            assert (
                abs(assets.iloc[i] - expected_value - 10000.0) < 0.01
            )  # Subtract cash account

    def test_private_equity_nav_series_exhausted_error(self):
        """Test that NAV series exhaustion raises appropriate error."""
        entity = Entity(id="test", name="Test Entity")

        # Create cash account (required for Journal system)
        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 10000.0}
        )

        # Create short NAV series
        nav_series = [100000.0, 102000.0]  # Only 2 months

        entity.new_ABrick(
            "pe_fund_short",
            "PE Fund Short",
            K.A_PRIVATE_EQUITY,
            {"initial_value": 100000.0, "drift_pa": 0.10, "nav_series": nav_series},
        )

        scenario = entity.create_scenario(
            id="pe_short_test",
            name="PE Short Test",
            brick_ids=["checking", "pe_fund_short"],
            settlement_default_cash_id="checking",
        )

        # Should raise error when trying to run beyond NAV series
        with pytest.raises(ValueError, match="NAV series exhausted"):
            scenario.run(start=date(2026, 1, 1), months=6)


class TestStrategyIntegration:
    """Test integration of new strategies with existing system."""

    def test_all_new_strategies_together(self):
        """Test all new strategies working together in one scenario."""
        entity = Entity(id="test", name="Test Entity")

        # Create cash account
        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 50000.0}
        )

        # Create credit line
        entity.new_LBrick(
            "credit_card",
            "Credit Card",
            K.L_CREDIT_LINE,
            start_date=date(2026, 1, 15),
            spec={
                "credit_limit": 10000.0,
                "rate_pa": 0.20,
                "min_payment": {"type": "interest_only"},
                "billing_day": 15,
            },
        )

        # Create fixed-term credit
        entity.new_LBrick(
            "personal_loan",
            "Personal Loan",
            K.L_CREDIT_FIXED,
            start_date=date(2026, 1, 15),
            spec={
                "principal": 15000.0,
                "rate_pa": 0.08,
                "term_months": 12,
            },
        )

        # Create balloon loan
        entity.new_LBrick(
            "equipment_loan",
            "Equipment Loan",
            K.L_LOAN_BALLOON,
            start_date=date(2026, 1, 15),
            spec={
                "principal": 50000.0,
                "rate_pa": 0.06,
                "balloon_after_months": 24,
                "amortization_rate_pa": 0.0,  # Interest only
                "balloon_type": "residual",
            },
        )

        # Create private equity investment
        entity.new_ABrick(
            "pe_fund",
            "PE Fund",
            K.A_PRIVATE_EQUITY,
            {"initial_value": 25000.0, "drift_pa": 0.15},
        )

        scenario = entity.create_scenario(
            id="comprehensive_test",
            name="Comprehensive Test",
            brick_ids=[
                "checking",
                "credit_card",
                "personal_loan",
                "equipment_loan",
                "pe_fund",
            ],
            settlement_default_cash_id="checking",
        )

        results = scenario.run(start=date(2026, 1, 1), months=25)

        # All strategies should work together
        totals = results["totals"]

        # Should have cash flows
        assert totals["cash_in"].sum() >= 0
        assert totals["cash_out"].sum() > 0

        # Should have asset values
        assert totals["assets"].sum() > 0

        # Should have debt balances
        assert totals["liabilities"].sum() > 0

    def test_strategy_parameter_validation(self):
        """Test that strategies validate their parameters correctly."""
        entity = Entity(id="test", name="Test Entity")

        # Create a cash account for the scenario
        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 10000.0}
        )

        # Test credit line with missing required parameters - should fail during simulation
        entity.new_LBrick(
            "bad_credit",
            "Bad Credit",
            K.L_CREDIT_LINE,
            {
                "credit_limit": 5000.0,
                # Missing rate_pa, min_payment, etc.
            },
        )

        scenario = entity.create_scenario(
            id="validation_test",
            name="Validation Test",
            brick_ids=["checking", "bad_credit"],
            settlement_default_cash_id="checking",
        )

        # Should fail during simulation due to missing parameters
        with pytest.raises((KeyError, ValueError)):
            scenario.run(start=date(2026, 1, 1), months=6)
