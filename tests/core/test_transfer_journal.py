"""
Tests for TBrick and Journal functionality.
"""

from datetime import date
from decimal import Decimal

import pytest
from finbricklab.core.accounts import (
    Account,
    AccountRegistry,
    AccountScope,
    AccountType,
)
from finbricklab.core.bricks import TBrick
from finbricklab.core.compiler import BrickCompiler
from finbricklab.core.context import ScenarioContext
from finbricklab.core.currency import create_amount
from finbricklab.core.journal import Journal, JournalEntry, Posting
from finbricklab.core.kinds import K


class TestTBrickJournal:
    """Test TBrick and Journal integration."""

    def test_tbrick_creation(self):
        """Test TBrick creation and basic properties."""
        tbrick = TBrick(
            id="transfer_1",
            name="Test Transfer",
            kind=K.T_TRANSFER_LUMP_SUM,
            spec={"amount": 1000.0, "currency": "EUR"},
            links={"from": "savings", "to": "checking"},
            start_date=date(2026, 1, 15),
        )

        assert tbrick.id == "transfer_1"
        assert tbrick.name == "Test Transfer"
        assert tbrick.kind == K.T_TRANSFER_LUMP_SUM
        assert tbrick.family == "t"
        assert tbrick.spec["amount"] == 1000.0
        assert tbrick.links["from"] == "savings"
        assert tbrick.links["to"] == "checking"
        assert tbrick.start_date == date(2026, 1, 15)

    def test_journal_entry_creation(self):
        """Test Journal entry creation and validation."""
        # Create postings
        postings = [
            Posting("savings", create_amount(-1000, "EUR"), {"type": "transfer_out"}),
            Posting("checking", create_amount(1000, "EUR"), {"type": "transfer_in"}),
        ]

        # Create journal entry
        entry = JournalEntry(
            id="txn_001",
            timestamp=date(2026, 1, 15),
            postings=postings,
            metadata={"brick_id": "transfer_1"},
        )

        assert entry.id == "txn_001"
        assert len(entry.postings) == 2
        assert entry.get_currency_totals()["EUR"] == Decimal("0")  # Zero-sum validation

    def test_journal_zero_sum_validation(self):
        """Test that journal entries must be zero-sum."""
        # Valid zero-sum entry
        postings = [
            Posting("savings", create_amount(-1000, "EUR")),
            Posting("checking", create_amount(1000, "EUR")),
        ]
        entry = JournalEntry(
            id="txn_001", timestamp=date(2026, 1, 15), postings=postings
        )
        # Should not raise exception

        # Invalid non-zero-sum entry
        postings = [
            Posting("savings", create_amount(-1000, "EUR")),
            Posting("checking", create_amount(500, "EUR")),  # Not zero-sum
        ]
        with pytest.raises(ValueError, match="not zero-sum"):
            JournalEntry(id="txn_002", timestamp=date(2026, 1, 15), postings=postings)

    def test_journal_balance_tracking(self):
        """Test journal balance tracking functionality."""
        journal = Journal()

        # Create and post entry
        postings = [
            Posting("savings", create_amount(-1000, "EUR")),
            Posting("checking", create_amount(1000, "EUR")),
        ]
        entry = JournalEntry(
            id="txn_001", timestamp=date(2026, 1, 15), postings=postings
        )

        journal.post(entry)

        # Check balances
        assert journal.balance("savings", "EUR") == Decimal("-1000")
        assert journal.balance("checking", "EUR") == Decimal("1000")

        # Check trial balance
        trial_balance = journal.trial_balance()
        assert trial_balance["savings"]["EUR"] == Decimal("-1000")
        assert trial_balance["checking"]["EUR"] == Decimal("1000")

    def test_compiler_tbrick_compilation(self):
        """Test TBrick compilation to journal entries."""
        # Create account registry
        account_registry = AccountRegistry()
        account_registry.register_account(
            Account("savings", "Savings", AccountScope.INTERNAL, AccountType.ASSET)
        )
        account_registry.register_account(
            Account("checking", "Checking", AccountScope.INTERNAL, AccountType.ASSET)
        )

        # Create compiler
        compiler = BrickCompiler(account_registry)

        # Create TBrick
        tbrick = TBrick(
            id="transfer_1",
            name="Test Transfer",
            kind=K.T_TRANSFER_LUMP_SUM,
            spec={"amount": 1000.0, "currency": "EUR"},
            links={"from": "savings", "to": "checking"},
            start_date=date(2026, 1, 15),
        )

        # Create mock context
        import numpy as np
        from finbricklab.core.registry import Registry

        t_index = np.array([date(2026, 1, 1), date(2026, 1, 15), date(2026, 2, 1)])
        registry = Registry(bricks={}, macrobricks={})
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry=registry)

        # Compile TBrick
        entries = compiler.compile_tbrick(tbrick, ctx)

        assert len(entries) == 1
        entry = entries[0]
        assert len(entry.postings) == 2
        assert entry.get_currency_totals()["EUR"] == Decimal("0")

        # Check posting details
        savings_posting = next(p for p in entry.postings if p.account_id == "savings")
        checking_posting = next(p for p in entry.postings if p.account_id == "checking")

        assert savings_posting.amount.value == Decimal("-1000")
        assert checking_posting.amount.value == Decimal("1000")

    def test_compiler_tbrick_with_fees(self):
        """Test TBrick compilation with fees."""
        # Create account registry
        account_registry = AccountRegistry()
        account_registry.register_account(
            Account("savings", "Savings", AccountScope.INTERNAL, AccountType.ASSET)
        )
        account_registry.register_account(
            Account("checking", "Checking", AccountScope.INTERNAL, AccountType.ASSET)
        )
        account_registry.register_account(
            Account(
                "Expenses:BankFees",
                "Bank Fees",
                AccountScope.BOUNDARY,
                AccountType.EXPENSE,
            )
        )

        # Create compiler
        compiler = BrickCompiler(account_registry)

        # Create TBrick with fees
        tbrick = TBrick(
            id="transfer_1",
            name="Test Transfer",
            kind=K.T_TRANSFER_LUMP_SUM,
            spec={
                "amount": 1000.0,
                "currency": "EUR",
                "fees": {"amount": 5.0, "account": "Expenses:BankFees"},
            },
            links={"from": "savings", "to": "checking"},
            start_date=date(2026, 1, 15),
        )

        # Create mock context
        import numpy as np
        from finbricklab.core.registry import Registry

        t_index = np.array([date(2026, 1, 1), date(2026, 1, 15), date(2026, 2, 1)])
        registry = Registry(bricks={}, macrobricks={})
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry=registry)

        # Compile TBrick
        entries = compiler.compile_tbrick(tbrick, ctx)

        assert len(entries) == 1
        entry = entries[0]
        assert len(entry.postings) == 4  # 2 for transfer + 2 for fees

        # Check that entry is still zero-sum
        assert entry.get_currency_totals()["EUR"] == Decimal("0")

    def test_account_scope_validation(self):
        """Test account scope validation for transfers."""
        account_registry = AccountRegistry()

        # Register internal accounts
        account_registry.register_account(
            Account("savings", "Savings", AccountScope.INTERNAL, AccountType.ASSET)
        )
        account_registry.register_account(
            Account("checking", "Checking", AccountScope.INTERNAL, AccountType.ASSET)
        )

        # Register boundary account
        account_registry.register_account(
            Account(
                "Income:Salary", "Salary", AccountScope.BOUNDARY, AccountType.INCOME
            )
        )

        # Valid internal transfer
        account_registry.validate_transfer_accounts("savings", "checking")

        # Invalid transfer with boundary account
        with pytest.raises(ValueError, match="must be internal"):
            account_registry.validate_transfer_accounts("savings", "Income:Salary")

        with pytest.raises(ValueError, match="must be internal"):
            account_registry.validate_transfer_accounts("Income:Salary", "checking")

    def test_currency_precision(self):
        """Test currency precision handling."""
        # Test EUR precision (2 decimal places)
        amount_eur = create_amount(1000.123, "EUR")
        assert amount_eur.value == Decimal("1000.12")  # Rounded to 2 decimal places

        # Test JPY precision (0 decimal places)
        amount_jpy = create_amount(1000.7, "JPY")
        assert amount_jpy.value == Decimal("1001")  # Rounded to 0 decimal places

        # Test amount arithmetic
        amount1 = create_amount(100, "EUR")
        amount2 = create_amount(50.5, "EUR")
        result = amount1 + amount2
        assert result.value == Decimal("150.50")

        # Test different currencies (should raise error)
        with pytest.raises(ValueError, match="different currencies"):
            amount1 + create_amount(50, "USD")
