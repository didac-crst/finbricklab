"""
Meta-tests for journal zero-sum invariants and accounting identities.
"""

from decimal import Decimal

from finbricklab import Entity
from finbricklab.core.kinds import K
from finbricklab.core.transfer_visibility import TransferVisibility


class TestJournalZeroSumMeta:
    """Meta-tests to verify per-currency zero-sum for all journal entries."""

    def test_all_journal_entries_zero_sum_per_currency(self):
        """Test that every journal entry is zero-sum per currency."""
        entity = Entity(id="test", name="Test Entity")

        # Create simple scenario with multiple bricks
        entity.new_ABrick("cash", "Cash Account", K.A_CASH, {"initial_balance": 1000.0})

        entity.new_FBrick(
            "salary",
            "Salary",
            K.F_INCOME_RECURRING,
            {"amount_monthly": 5000.0},
            links={"route": {"to": "cash"}},
        )

        entity.new_LBrick(
            "loan",
            "Loan",
            K.L_LOAN_ANNUITY,
            {"principal": 10000.0, "rate_pa": 0.05, "term_months": 12},
            links={"route": {"to": "cash"}},
        )

        scenario = entity.create_scenario(
            id="test",
            name="Test",
            brick_ids=["cash", "salary", "loan"],
            settlement_default_cash_id="cash",
        )

        results = scenario.run(start="2024-01-01", months=3)

        # Get journal from results
        journal = results["journal"]

        # Verify every entry is zero-sum per currency
        for entry in journal.entries:
            currency_totals = entry.get_currency_totals()

            for currency, total in currency_totals.items():
                assert total == Decimal(
                    "0"
                ), f"Entry {entry.id} is not zero-sum for currency {currency}: {total}"

    def test_identities_after_transfer_visibility_filtering(self):
        """Test that accounting identities hold after transfer visibility filtering."""
        entity = Entity(id="test", name="Test Entity")

        entity.new_ABrick(
            "cash1", "Cash Account 1", K.A_CASH, {"initial_balance": 1000.0}
        )
        entity.new_ABrick(
            "cash2", "Cash Account 2", K.A_CASH, {"initial_balance": 500.0}
        )

        entity.new_TBrick(
            "transfer",
            "Monthly Transfer",
            K.T_TRANSFER_RECURRING,
            {"amount": 200.0, "frequency": "MONTHLY"},
            links={"from": "cash1", "to": "cash2"},
        )

        entity.new_FBrick(
            "income",
            "Income",
            K.F_INCOME_RECURRING,
            {"amount_monthly": 3000.0},
            links={"route": {"to": "cash1"}},
        )

        scenario = entity.create_scenario(
            id="test",
            name="Test",
            brick_ids=["cash1", "cash2", "transfer", "income"],
            settlement_default_cash_id="cash1",
        )

        results = scenario.run(start="2024-01-01", months=3)

        # Test identities for each visibility mode
        for visibility in [
            TransferVisibility.OFF,
            TransferVisibility.ONLY,
            TransferVisibility.ALL,
            TransferVisibility.BOUNDARY_ONLY,
        ]:
            monthly_data = results["views"].monthly(transfer_visibility=visibility)

            # Identity: assets == cash + non_cash (if both present)
            if "cash" in monthly_data.columns and "non_cash" in monthly_data.columns:
                for idx in monthly_data.index:
                    assets = monthly_data.loc[idx, "assets"]
                    cash = monthly_data.loc[idx, "cash"]
                    non_cash = monthly_data.loc[idx, "non_cash"]
                    assert (
                        abs(assets - cash - non_cash) < 0.01
                    ), f"assets != cash + non_cash for {idx} in {visibility.value} mode"

            # Identity: equity == assets - liabilities
            if "equity" in monthly_data.columns:
                for idx in monthly_data.index:
                    equity = monthly_data.loc[idx, "equity"]
                    assets = monthly_data.loc[idx, "assets"]
                    liabilities = monthly_data.loc[idx, "liabilities"]
                    assert (
                        abs(equity - (assets - liabilities)) < 0.01
                    ), f"equity != assets - liabilities for {idx} in {visibility.value} mode"

            # Identity: net_cf == cash_in - cash_out
            if "net_cf" in monthly_data.columns:
                for idx in monthly_data.index:
                    net_cf = monthly_data.loc[idx, "net_cf"]
                    cash_in = monthly_data.loc[idx, "cash_in"]
                    cash_out = monthly_data.loc[idx, "cash_out"]
                    assert (
                        abs(net_cf - (cash_in - cash_out)) < 0.01
                    ), f"net_cf != cash_in - cash_out for {idx} in {visibility.value} mode"

    def test_fx_entry_per_currency_zero_sum(self):
        """Test that FX transfer entries maintain per-currency zero-sum."""
        entity = Entity(id="test", name="Test Entity")

        entity.new_ABrick("cash_usd", "USD Cash", K.A_CASH, {"initial_balance": 0.0})
        entity.new_ABrick("cash_eur", "EUR Cash", K.A_CASH, {"initial_balance": 1000.0})

        # Create FX transfer (EUR to USD)
        entity.new_TBrick(
            "fx_transfer",
            "FX Transfer",
            K.T_TRANSFER_LUMP_SUM,
            {
                "amount": 500.0,
                "currency": "EUR",
                "fx": {"rate": 1.1, "pair": "EUR/USD"},
                "to": "cash_usd",
            },
            links={"from": "cash_eur", "to": "cash_usd"},
        )

        scenario = entity.create_scenario(
            id="test",
            name="Test",
            brick_ids=["cash_usd", "cash_eur", "fx_transfer"],
            settlement_default_cash_id="cash_eur",
        )

        results = scenario.run(start="2024-01-01", months=1)

        journal = results["journal"]

        # Find FX transfer entry
        fx_entries = [
            e
            for e in journal.entries
            if e.metadata.get("kind") == K.T_TRANSFER_LUMP_SUM
        ]
        assert len(fx_entries) > 0, "No FX transfer entry found"

        # Verify per-currency zero-sum for FX entry
        for entry in fx_entries:
            currency_totals = entry.get_currency_totals()

            # EUR and USD should independently zero-sum
            assert currency_totals.get("EUR", Decimal("0")) == Decimal(
                "0"
            ), f"EUR legs don't sum to zero in FX entry {entry.id}"
            assert currency_totals.get("USD", Decimal("0")) == Decimal(
                "0"
            ), f"USD legs don't sum to zero in FX entry {entry.id}"

    def test_maturity_transfer_entry_zero_sum(self):
        """Test that maturity transfer entries are zero-sum."""
        entity = Entity(id="test", name="Test Entity")

        entity.new_ABrick(
            "source",
            "Source Account",
            K.A_CASH,
            {"initial_balance": 5000.0, "interest_pa": 0.02},
            start_date="2024-01-01",
            end_date="2024-03-01",
            links={"route": {"to": "dest"}},
        )

        entity.new_ABrick(
            "dest", "Destination Account", K.A_CASH, {"initial_balance": 0.0}
        )

        scenario = entity.create_scenario(
            id="test",
            name="Test",
            brick_ids=["source", "dest"],
            settlement_default_cash_id="source",
        )

        results = scenario.run(start="2024-01-01", months=4)

        journal = results["journal"]

        # Find maturity transfer entry
        maturity_entries = [
            e
            for e in journal.entries
            if e.metadata.get("transaction_type") == "maturity_transfer"
        ]

        assert len(maturity_entries) > 0, "No maturity transfer entry found"

        # Verify zero-sum
        for entry in maturity_entries:
            currency_totals = entry.get_currency_totals()
            assert all(
                total == Decimal("0") for total in currency_totals.values()
            ), f"Maturity transfer entry {entry.id} is not zero-sum"
