"""
Tests for Journal system invariants and validation.
"""

from datetime import date
from decimal import Decimal

import numpy as np
import pytest
from finbricklab import Entity
from finbricklab.core.accounts import (
    Account,
    AccountRegistry,
    AccountScope,
    AccountType,
)
from finbricklab.core.currency import create_amount
from finbricklab.core.journal import Journal, JournalEntry, Posting
from finbricklab.core.kinds import K


class TestJournalInvariants:
    """Test Journal system invariants and validation."""

    def test_zero_sum_entries(self):
        """Test that journal entries are zero-sum."""
        registry = AccountRegistry()
        journal = Journal(registry)

        # Register accounts
        registry.register_account(
            Account("cash", "Cash", AccountScope.INTERNAL, AccountType.ASSET)
        )
        registry.register_account(
            Account("income", "Income", AccountScope.BOUNDARY, AccountType.INCOME)
        )

        # Create a valid zero-sum entry
        entry = JournalEntry(
            id="test_entry",
            timestamp=date(2026, 1, 1),
            postings=[
                Posting("income", create_amount(-1000, "EUR"), {"type": "income"}),
                Posting("cash", create_amount(1000, "EUR"), {"type": "cash_in"}),
            ],
            metadata={"type": "income"},
        )

        # Should not raise an error
        journal.post(entry)
        assert len(journal.entries) == 1

        # Test invalid non-zero-sum entry
        with pytest.raises(ValueError, match="not zero-sum"):
            invalid_entry = JournalEntry(
                id="invalid_entry",
                timestamp=date(2026, 1, 1),
                postings=[
                    Posting("income", create_amount(-1000, "EUR"), {"type": "income"}),
                    Posting(
                        "cash", create_amount(500, "EUR"), {"type": "cash_in"}
                    ),  # Not zero-sum
                ],
                metadata={"type": "income"},
            )

    def test_account_balance_calculation(self):
        """Test that account balances are calculated correctly."""
        registry = AccountRegistry()
        journal = Journal(registry)

        # Register accounts
        registry.register_account(
            Account("cash", "Cash", AccountScope.INTERNAL, AccountType.ASSET)
        )
        registry.register_account(
            Account("income", "Income", AccountScope.BOUNDARY, AccountType.INCOME)
        )

        # Post income entry
        income_entry = JournalEntry(
            id="income_entry",
            timestamp=date(2026, 1, 1),
            postings=[
                Posting("income", create_amount(-1000, "EUR"), {"type": "income"}),
                Posting("cash", create_amount(1000, "EUR"), {"type": "cash_in"}),
            ],
            metadata={"type": "income"},
        )
        journal.post(income_entry)

        # Check balances
        cash_balance = journal.balance("cash", "EUR")
        income_balance = journal.balance("income", "EUR")

        assert cash_balance == Decimal("1000.00")
        assert income_balance == Decimal("-1000.00")

        # Post expense entry
        expense_entry = JournalEntry(
            id="expense_entry",
            timestamp=date(2026, 1, 2),
            postings=[
                Posting("cash", create_amount(-500, "EUR"), {"type": "cash_out"}),
                Posting("income", create_amount(500, "EUR"), {"type": "expense"}),
            ],
            metadata={"type": "expense"},
        )
        journal.post(expense_entry)

        # Check updated balances
        cash_balance = journal.balance("cash", "EUR")
        income_balance = journal.balance("income", "EUR")

        assert cash_balance == Decimal("500.00")
        assert income_balance == Decimal("-500.00")

    def test_trial_balance(self):
        """Test that trial balance is calculated correctly."""
        registry = AccountRegistry()
        journal = Journal(registry)

        # Register accounts
        registry.register_account(
            Account("cash", "Cash", AccountScope.INTERNAL, AccountType.ASSET)
        )
        registry.register_account(
            Account("income", "Income", AccountScope.BOUNDARY, AccountType.INCOME)
        )
        registry.register_account(
            Account("expense", "Expense", AccountScope.BOUNDARY, AccountType.EXPENSE)
        )

        # Post entries
        income_entry = JournalEntry(
            id="income_entry",
            timestamp=date(2026, 1, 1),
            postings=[
                Posting("income", create_amount(-1000, "EUR"), {"type": "income"}),
                Posting("cash", create_amount(1000, "EUR"), {"type": "cash_in"}),
            ],
            metadata={"type": "income"},
        )
        journal.post(income_entry)

        expense_entry = JournalEntry(
            id="expense_entry",
            timestamp=date(2026, 1, 2),
            postings=[
                Posting("cash", create_amount(-300, "EUR"), {"type": "cash_out"}),
                Posting("expense", create_amount(300, "EUR"), {"type": "expense"}),
            ],
            metadata={"type": "expense"},
        )
        journal.post(expense_entry)

        # Check trial balance
        trial_balance = journal.trial_balance()

        assert trial_balance["cash"]["EUR"] == Decimal("700.00")
        assert trial_balance["income"]["EUR"] == Decimal("-1000.00")
        assert trial_balance["expense"]["EUR"] == Decimal("300.00")

        # Total should be zero (balanced)
        total = sum(
            balances.get("EUR", Decimal("0")) for balances in trial_balance.values()
        )
        assert total == Decimal("0.00")

    def test_currency_precision(self):
        """Test that currency precision is maintained."""
        registry = AccountRegistry()
        journal = Journal(registry)

        # Register accounts
        registry.register_account(
            Account("cash", "Cash", AccountScope.INTERNAL, AccountType.ASSET)
        )
        registry.register_account(
            Account("income", "Income", AccountScope.BOUNDARY, AccountType.INCOME)
        )

        # Test with precise amounts
        entry = JournalEntry(
            id="precision_test",
            timestamp=date(2026, 1, 1),
            postings=[
                Posting("income", create_amount(-1234.56, "EUR"), {"type": "income"}),
                Posting("cash", create_amount(1234.56, "EUR"), {"type": "cash_in"}),
            ],
            metadata={"type": "income"},
        )
        journal.post(entry)

        # Check that precision is maintained
        cash_balance = journal.balance("cash", "EUR")
        assert cash_balance == Decimal("1234.56")

        # Test with JPY (no decimal places)
        jpy_entry = JournalEntry(
            id="jpy_test",
            timestamp=date(2026, 1, 1),
            postings=[
                Posting("income", create_amount(-1000, "JPY"), {"type": "income"}),
                Posting("cash", create_amount(1000, "JPY"), {"type": "cash_in"}),
            ],
            metadata={"type": "income"},
        )
        journal.post(jpy_entry)

        jpy_balance = journal.balance("cash", "JPY")
        assert jpy_balance == Decimal("1000")

    def test_scenario_journal_integration(self):
        """Test that scenario simulation creates valid journal entries."""
        entity = Entity("test", "Test")

        # Create simple scenario
        cash = entity.new_ABrick("cash", "Cash", K.A_CASH, {"initial_balance": 1000.0})
        income = entity.new_FBrick(
            "income", "Salary", K.F_INCOME_RECURRING, {"amount_monthly": 2000.0}
        )
        expense = entity.new_FBrick(
            "expense", "Rent", K.F_EXPENSE_RECURRING, {"amount_monthly": 800.0}
        )

        scenario = entity.create_scenario("test", "Test", ["cash", "income", "expense"])
        results = scenario.run(start=date(2026, 1, 1), months=3)

        # Check that scenario completed successfully
        assert "outputs" in results
        assert "cash" in results["outputs"]
        assert "income" in results["outputs"]
        assert "expense" in results["outputs"]

        # Check that cash balance is reasonable
        cash_balance = results["outputs"]["cash"]["asset_value"]
        assert len(cash_balance) == 3
        assert cash_balance[0] > 0  # Should have positive balance

        # Check that income and expense are generating flows
        income_flows = results["outputs"]["income"]["cash_in"]
        expense_flows = results["outputs"]["expense"]["cash_out"]

        assert np.sum(income_flows) > 0
        assert np.sum(expense_flows) > 0
