"""
Tests for German mortgage scenarios with new parameter aliases.
"""

from datetime import date

import numpy as np
from finbricklab.core.accounts import AccountRegistry
from finbricklab.core.bricks import LBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.journal import Journal
from finbricklab.core.kinds import K
from finbricklab.strategies.schedule.loan_annuity import ScheduleLoanAnnuity


class TestGermanMortgageScenarios:
    """Test German mortgage scenarios with new parameter aliases."""

    def test_german_loan_annuity_math(self):
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

        # Create context for full term (V2: requires journal)
        t_index = np.arange("2026-01", "2047-01", dtype="datetime64[M]")  # ~21 years
        account_registry = AccountRegistry()
        journal = Journal(account_registry)
        # Register cash and liability accounts for settlement
        from finbricklab.core.accounts import (
            Account,
            AccountScope,
            AccountType,
            get_node_id,
        )

        cash_node_id = get_node_id("cash", "a")
        liability_node_id = get_node_id(mortgage.id, "l")
        account_registry.register_account(
            Account(cash_node_id, "Cash", AccountScope.INTERNAL, AccountType.ASSET)
        )
        account_registry.register_account(
            Account(
                liability_node_id,
                "Liability",
                AccountScope.INTERNAL,
                AccountType.LIABILITY,
            )
        )
        ctx = ScenarioContext(
            t_index=t_index,
            currency="EUR",
            registry={},
            journal=journal,
            settlement_default_cash_id="cash",
        )

        strategy = ScheduleLoanAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # Expected calculations:
        # term_months ≈ 260 (from term_from_amort)
        # Monthly payment ≈ €1,855
        # First month: interest ≈ €455, principal ≈ €1,400

        debt_balance = result["liabilities"]

        # V2: Check monthly payment amount from journal entries (not cash_out array)
        # Find first month payment entries (principal + interest = total monthly payment)
        # First payment month is at index 1 (first_payment_offset = 1)
        import pandas as pd

        first_payment_month = pd.Timestamp(t_index[1]).to_pydatetime()
        payment_entries_first_month = [
            e
            for e in journal.entries
            if e.metadata.get("transaction_type") == "payment"
            and e.timestamp == first_payment_month
            and any(
                p.metadata.get("node_id") == liability_node_id
                or p.metadata.get("node_id") == cash_node_id
                for p in e.postings
            )
        ]
        # Sum principal and interest payments for total monthly payment
        monthly_payment = 0.0
        for entry in payment_entries_first_month:
            cash_posting = next(
                (p for p in entry.postings if p.account_id.startswith("a:")),
                None,
            )
            if cash_posting:
                monthly_payment += abs(float(cash_posting.amount.value))
        assert (
            len(payment_entries_first_month) > 0
        ), "Expected payment entries for first month"
        assert (
            monthly_payment > 0
        ), f"Expected positive monthly payment, got {monthly_payment}"
        assert (
            1850 <= monthly_payment <= 1860
        ), f"Expected payment ~€1,854, got {monthly_payment:.2f}"

        # Check that term was calculated correctly (should be ~260 months)
        term_months = mortgage.spec["term_months"]
        assert 250 <= term_months <= 270, f"Expected term ~260, got {term_months}"

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

        # Create context for 10 years (V2: requires journal)
        t_index = np.arange("2018-07", "2028-08", dtype="datetime64[M]")  # 10 years
        account_registry = AccountRegistry()
        journal = Journal(account_registry)
        # Register cash and liability accounts for settlement
        from finbricklab.core.accounts import (
            Account,
            AccountScope,
            AccountType,
            get_node_id,
        )

        cash_node_id = get_node_id("cash", "a")
        liability_node_id = get_node_id(mortgage.id, "l")
        account_registry.register_account(
            Account(cash_node_id, "Cash", AccountScope.INTERNAL, AccountType.ASSET)
        )
        account_registry.register_account(
            Account(
                liability_node_id,
                "Liability",
                AccountScope.INTERNAL,
                AccountType.LIABILITY,
            )
        )
        ctx = ScenarioContext(
            t_index=t_index,
            currency="EUR",
            registry={},
            journal=journal,
            settlement_default_cash_id="cash",
        )

        strategy = ScheduleLoanAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        debt_balance = result["liabilities"]
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

        # Create context for 10 years (V2: requires journal)
        t_index = np.arange("2018-07", "2028-08", dtype="datetime64[M]")  # 10 years
        account_registry = AccountRegistry()
        journal = Journal(account_registry)
        # Register cash and liability accounts for settlement
        from finbricklab.core.accounts import (
            Account,
            AccountScope,
            AccountType,
            get_node_id,
        )

        cash_node_id = get_node_id("cash", "a")
        liability_node_id = get_node_id(mortgage.id, "l")
        account_registry.register_account(
            Account(cash_node_id, "Cash", AccountScope.INTERNAL, AccountType.ASSET)
        )
        account_registry.register_account(
            Account(
                liability_node_id,
                "Liability",
                AccountScope.INTERNAL,
                AccountType.LIABILITY,
            )
        )
        ctx = ScenarioContext(
            t_index=t_index,
            currency="EUR",
            registry={},
            journal=journal,
            settlement_default_cash_id="cash",
        )

        strategy = ScheduleLoanAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        debt_balance = result["liabilities"]
        events = result["events"]

        # Check that final debt balance is zero
        final_balance = debt_balance[-1]
        assert (
            abs(final_balance) < 1.0
        ), f"Expected zero final balance, got {final_balance:.2f}"

        # V2: Check that balloon_payoff event was emitted with correct residual
        # The balloon payment should have been created, but if not (due to guard or other reasons),
        # the event will still indicate the residual amount
        balloon_events = [e for e in events if e.kind == "balloon_payoff"]
        assert len(balloon_events) == 1, "Expected exactly one balloon_payoff event"
        # Event is a NamedTuple with fields: t, kind, message, meta
        event_meta = (
            balloon_events[0].meta
            if hasattr(balloon_events[0], "meta")
            else balloon_events[0][-1]
            if len(balloon_events[0]) > 3
            else {}
        )
        expected_residual = (
            event_meta.get("residual", 0) if isinstance(event_meta, dict) else 0
        )
        # Residual is ~€240,769 (slightly less than €242,623 due to amortization calculations)
        assert (
            240_000 <= expected_residual <= 243_000
        ), f"Expected residual ~€240,769, got {expected_residual:.2f}"
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

        # Create context for full term (V2: requires journal)
        t_index = np.arange("2026-01", "2051-01", dtype="datetime64[M]")  # 25 years
        account_registry = AccountRegistry()
        journal = Journal(account_registry)
        # Register cash and liability accounts for settlement
        from finbricklab.core.accounts import (
            Account,
            AccountScope,
            AccountType,
            get_node_id,
        )

        cash_node_id = get_node_id("cash", "a")
        liability_node_id = get_node_id(mortgage.id, "l")
        account_registry.register_account(
            Account(cash_node_id, "Cash", AccountScope.INTERNAL, AccountType.ASSET)
        )
        account_registry.register_account(
            Account(
                liability_node_id,
                "Liability",
                AccountScope.INTERNAL,
                AccountType.LIABILITY,
            )
        )
        ctx = ScenarioContext(
            t_index=t_index,
            currency="EUR",
            registry={},
            journal=journal,
            settlement_default_cash_id="cash",
        )

        strategy = ScheduleLoanAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # Check that aliases were applied correctly
        assert mortgage.spec["rate_pa"] == 0.013
        assert mortgage.spec["amortization_pa"] == 0.04
        assert mortgage.spec["term_months"] == 300

        # Check that mortgage completes in 25 years (within rounding tolerance)
        debt_balance = result["liabilities"]
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

        # Create context for 15 years (longer than credit window) (V2: requires journal)
        t_index = np.arange("2018-07", "2033-08", dtype="datetime64[M]")  # 15 years
        account_registry = AccountRegistry()
        journal = Journal(account_registry)
        # Register cash and liability accounts for settlement
        from finbricklab.core.accounts import (
            Account,
            AccountScope,
            AccountType,
            get_node_id,
        )

        cash_node_id = get_node_id("cash", "a")
        liability_node_id = get_node_id(mortgage.id, "l")
        account_registry.register_account(
            Account(cash_node_id, "Cash", AccountScope.INTERNAL, AccountType.ASSET)
        )
        account_registry.register_account(
            Account(
                liability_node_id,
                "Liability",
                AccountScope.INTERNAL,
                AccountType.LIABILITY,
            )
        )
        ctx = ScenarioContext(
            t_index=t_index,
            currency="EUR",
            registry={},
            journal=journal,
            settlement_default_cash_id="cash",
        )

        strategy = ScheduleLoanAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # Check that credit_term_months was applied to duration_m
        assert mortgage.duration_m == 120

        # Check that mortgage becomes inactive after 10 years
        debt_balance = result["liabilities"]

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

        # Create context for 15 years (V2: requires journal)
        t_index = np.arange("2018-07", "2033-08", dtype="datetime64[M]")  # 15 years
        account_registry = AccountRegistry()
        journal = Journal(account_registry)
        # Register cash and liability accounts for settlement
        from finbricklab.core.accounts import (
            Account,
            AccountScope,
            AccountType,
            get_node_id,
        )

        cash_node_id = get_node_id("cash", "a")
        liability_node_id = get_node_id(mortgage.id, "l")
        account_registry.register_account(
            Account(cash_node_id, "Cash", AccountScope.INTERNAL, AccountType.ASSET)
        )
        account_registry.register_account(
            Account(
                liability_node_id,
                "Liability",
                AccountScope.INTERNAL,
                AccountType.LIABILITY,
            )
        )
        ctx = ScenarioContext(
            t_index=t_index,
            currency="EUR",
            registry={},
            journal=journal,
            settlement_default_cash_id="cash",
        )

        strategy = ScheduleLoanAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # Check that fix_rate_months was applied to duration_m
        assert mortgage.duration_m == 120

        # Check that mortgage becomes inactive after 10 years
        debt_balance = result["liabilities"]
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

        # Create context for full term (V2: requires journal)
        t_index = np.arange("2026-01", "2051-01", dtype="datetime64[M]")  # 25 years
        account_registry = AccountRegistry()
        journal = Journal(account_registry)
        # Register cash and liability accounts for settlement
        from finbricklab.core.accounts import (
            Account,
            AccountScope,
            AccountType,
            get_node_id,
        )

        cash_node_id = get_node_id("cash", "a")
        liability_node_id = get_node_id(mortgage.id, "l")
        account_registry.register_account(
            Account(cash_node_id, "Cash", AccountScope.INTERNAL, AccountType.ASSET)
        )
        account_registry.register_account(
            Account(
                liability_node_id,
                "Liability",
                AccountScope.INTERNAL,
                AccountType.LIABILITY,
            )
        )
        ctx = ScenarioContext(
            t_index=t_index,
            currency="EUR",
            registry={},
            journal=journal,
            settlement_default_cash_id="cash",
        )

        strategy = ScheduleLoanAnnuity()
        strategy.prepare(mortgage, ctx)
        result = strategy.simulate(mortgage, ctx)

        # With zero interest, term should be 12 / 0.04 = 300 months
        term_months = mortgage.spec["term_months"]
        assert (
            term_months == 300
        ), f"Expected 300 months for zero interest, got {term_months}"

        # V2: Monthly payment should be principal / term_months (check from journal entries)
        expected_payment = principal / term_months
        # Find first month payment entries (principal only for zero interest)
        # First payment month is at index 1 (first_payment_offset = 1)
        import pandas as pd

        first_payment_month = pd.Timestamp(t_index[1]).to_pydatetime()
        payment_entries_first_month = [
            e
            for e in journal.entries
            if e.metadata.get("transaction_type") == "payment"
            and e.timestamp == first_payment_month
            and any(p.metadata.get("node_id") == liability_node_id for p in e.postings)
        ]
        assert (
            len(payment_entries_first_month) > 0
        ), "Expected payment entries for first month"
        # For zero interest, there should be only principal payments
        first_principal_entry = payment_entries_first_month[0]
        cash_posting = next(
            (
                p
                for p in first_principal_entry.postings
                if p.account_id.startswith("a:")
            ),
            None,
        )
        assert cash_posting is not None, "Expected cash posting in payment entry"
        actual_payment = abs(float(cash_posting.amount.value))
        assert (
            abs(actual_payment - expected_payment) < 1.0
        ), f"Expected linear payment {expected_payment:.2f}, got {actual_payment:.2f}"

        # Final balance should be close to zero (within rounding tolerance)
        debt_balance = result["liabilities"]
        final_balance = debt_balance[-1]
        assert (
            abs(final_balance) < 2000.0
        ), f"Expected near-zero final balance, got {final_balance:.2f}"
