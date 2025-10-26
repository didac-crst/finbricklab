"""
Property-based tests using Hypothesis for FX transfers and accounting identities.

These tests are optional and will be skipped if Hypothesis is not installed.
Run `pip install hypothesis` to enable them.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

# Try to import Hypothesis
try:
    from hypothesis import assume, given
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

    # Dummy decorator for when Hypothesis is not available
    def given(*args, **kwargs):
        def decorator(func):
            func._hypothesis_internal_skip = True
            return func

        return decorator

    assume = None
    st = None

from finbricklab import Entity
from finbricklab.core.kinds import K
from finbricklab.core.transfer_visibility import TransferVisibility

# Skip entire module if Hypothesis is not available
pytestmark = pytest.mark.skipif(
    not HAS_HYPOTHESIS,
    reason="Hypothesis not installed - run 'pip install hypothesis' to enable property tests",
)


if HAS_HYPOTHESIS:
    # Hypothesis strategies
    fx_rate_strategy = st.floats(
        min_value=0.01, max_value=1000.0, allow_infinity=False, allow_nan=False
    ).map(lambda x: round(x, 6))

    monetary_amount_strategy = st.floats(
        min_value=1.0, max_value=1000000.0, allow_infinity=False, allow_nan=False
    ).map(lambda x: round(x, 2))

    class TestFXPropertyBased:
        """Property-based tests for FX transfer per-currency zero-sum."""

        @given(
            source_amount=monetary_amount_strategy,
            fx_rate=fx_rate_strategy,
            currencies=st.sampled_from(
                [("EUR", "USD"), ("USD", "EUR"), ("USD", "JPY"), ("EUR", "GBP")]
            ),
        )
        def test_fx_transfer_per_currency_zero_sum(
            self, source_amount, fx_rate, currencies
        ):
            """Property test: FX transfers maintain per-currency zero-sum for any amount and rate."""
            source_currency, dest_currency = currencies

            entity = Entity(id="test", name="Test Entity")

            # Create cash accounts in different currencies
            entity.new_ABrick(
                "cash_source",
                "Source Cash",
                K.A_CASH,
                {"initial_balance": source_amount},
            )
            entity.new_ABrick(
                "cash_dest", "Dest Cash", K.A_CASH, {"initial_balance": 0.0}
            )

            # Create FX transfer
            entity.new_TBrick(
                "fx_transfer",
                "FX Transfer",
                K.T_TRANSFER_LUMP_SUM,
                {
                    "amount": source_amount,
                    "currency": source_currency,
                    "fx": {
                        "rate": fx_rate,
                        "pair": f"{source_currency}/{dest_currency}",
                        "pnl_account": "P&L:FX",
                    },
                },
                links={"from": "cash_source", "to": "cash_dest"},
            )

            scenario = entity.create_scenario(
                id="fx_test",
                name="FX Test",
                brick_ids=["cash_source", "cash_dest", "fx_transfer"],
                settlement_default_cash_id="cash_source",
            )

            results = scenario.run(start="2024-01-01", months=1)
            journal = results["journal"]

            # Find FX transfer entries
            fx_entries = [
                e
                for e in journal.entries
                if e.metadata.get("transaction_type") in {"transfer", "fx_transfer"}
            ]

            # Verify each FX entry is per-currency zero-sum
            for entry in fx_entries:
                currency_totals = entry.get_currency_totals()
                for currency, total in currency_totals.items():
                    assert abs(total) < Decimal("0.01"), (
                        f"FX entry {entry.id} violates per-currency zero-sum "
                        f"for {currency}: {total} (amount={source_amount}, rate={fx_rate})"
                    )

    class TestAccountingIdentitiesPropertyBased:
        """Property-based tests for accounting identity preservation."""

        @given(
            salary_amount=monetary_amount_strategy,
            transfer_amount=monetary_amount_strategy,
            initial_balance=monetary_amount_strategy,
        )
        def test_identities_preserved_across_scenarios(
            self, salary_amount, transfer_amount, initial_balance
        ):
            """Property test: Accounting identities hold for any combination of amounts."""
            assume(
                initial_balance >= transfer_amount
            )  # Can't transfer more than available

            entity = Entity(id="test", name="Test Entity")

            # Create boundary income (salary)
            entity.new_FBrick(
                "salary",
                "Salary",
                K.F_INCOME_RECURRING,
                {"amount_monthly": salary_amount},
                links={"route": {"to": "checking"}},
            )

            # Create cash accounts
            entity.new_ABrick(
                "checking", "Checking", K.A_CASH, {"initial_balance": initial_balance}
            )
            entity.new_ABrick("savings", "Savings", K.A_CASH, {"initial_balance": 0.0})

            # Create internal transfer
            entity.new_TBrick(
                "transfer",
                "Transfer to Savings",
                K.T_TRANSFER_RECURRING,
                {"amount": transfer_amount, "frequency": "MONTHLY"},
                links={"from": "checking", "to": "savings"},
            )

            scenario = entity.create_scenario(
                id="identity_test",
                name="Identity Test",
                brick_ids=["salary", "checking", "savings", "transfer"],
                settlement_default_cash_id="checking",
            )

            results = scenario.run(start="2024-01-01", months=3)

            # Test identities for each visibility mode
            for visibility in [
                TransferVisibility.OFF,
                TransferVisibility.ONLY,
                TransferVisibility.ALL,
            ]:
                monthly_data = results["views"].monthly(transfer_visibility=visibility)

                for idx in range(len(monthly_data)):
                    # Identity: assets == cash + non_cash
                    assets = monthly_data.iloc[idx]["assets"]
                    cash = monthly_data.iloc[idx]["cash"]
                    non_cash = monthly_data.iloc[idx]["non_cash"]
                    assert abs(assets - cash - non_cash) < 0.01, (
                        f"Identity violation: assets != cash + non_cash at {idx} "
                        f"(visibility={visibility.value}, salary={salary_amount}, "
                        f"transfer={transfer_amount}, init={initial_balance})"
                    )

                    # Identity: equity == assets - liabilities
                    equity = monthly_data.iloc[idx]["equity"]
                    assets = monthly_data.iloc[idx]["assets"]
                    liabilities = monthly_data.iloc[idx]["liabilities"]
                    assert abs(equity - (assets - liabilities)) < 0.01, (
                        f"Identity violation: equity != assets - liabilities at {idx} "
                        f"(visibility={visibility.value})"
                    )

    class TestTransferWindowProperty:
        """Property-based tests for transfer window logic."""

        @given(
            transfer_date_offset=st.integers(min_value=-2, max_value=25),
            transfer_amount=monetary_amount_strategy,
        )
        def test_scheduled_transfer_window_boundary(
            self, transfer_date_offset, transfer_amount
        ):
            """Property test: Scheduled transfers outside window produce zero postings."""
            # Scenario runs from 2024-01-01 for 12 months
            scenario_start = date(2024, 1, 1)
            transfer_date = scenario_start + timedelta(days=30 * transfer_date_offset)

            entity = Entity(id="test", name="Test Entity")

            entity.new_ABrick(
                "cash_a", "Cash A", K.A_CASH, {"initial_balance": 10000.0}
            )
            entity.new_ABrick("cash_b", "Cash B", K.A_CASH, {"initial_balance": 0.0})

            entity.new_TBrick(
                "transfer",
                "Scheduled Transfer",
                K.T_TRANSFER_SCHEDULED,
                {
                    "schedule": [
                        {"date": transfer_date.isoformat(), "amount": transfer_amount}
                    ]
                },
                links={"from": "cash_a", "to": "cash_b"},
            )

            scenario = entity.create_scenario(
                id="window_test",
                name="Window Test",
                brick_ids=["cash_a", "cash_b", "transfer"],
                settlement_default_cash_id="cash_a",
            )

            results = scenario.run(start=scenario_start.isoformat(), months=12)
            journal = results["journal"]

            # Find transfer entries
            transfer_entries = [
                e
                for e in journal.entries
                if e.metadata.get("transaction_type") in {"transfer"}
            ]

            # If transfer date is outside scenario window, there should be no transfer postings
            # (outside window = before month 0 or after month 11)
            is_in_window = 0 <= transfer_date_offset <= 11

            if not is_in_window:
                # Transfer outside window should produce zero cash flows
                for entry in transfer_entries:
                    for posting in entry.postings:
                        if posting.account_id in {"asset:cash_a", "asset:cash_b"}:
                            assert abs(posting.amount.value) < Decimal("0.01"), (
                                f"Transfer outside window produced non-zero posting: "
                                f"date={transfer_date}, offset={transfer_date_offset}, "
                                f"amount={transfer_amount}"
                            )
