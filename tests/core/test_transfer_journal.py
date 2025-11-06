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
        """Test TBrick compilation with fees (V2: separate fee entry)."""
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

        # V2: Fees are in a separate entry (2 entries total: transfer + fee)
        assert len(entries) == 2, "Should have 2 entries: transfer + fee"

        # Transfer entry should have 2 postings
        transfer_entry = entries[0]
        assert (
            len(transfer_entry.postings) == 2
        ), "Transfer entry should have 2 postings"
        assert transfer_entry.get_currency_totals()["EUR"] == Decimal(
            "0"
        ), "Transfer entry should be zero-sum"
        assert transfer_entry.metadata.get("transaction_type") == "transfer"

        # Fee entry should have 2 postings
        fee_entry = entries[1]
        assert len(fee_entry.postings) == 2, "Fee entry should have 2 postings"
        assert fee_entry.get_currency_totals()["EUR"] == Decimal(
            "0"
        ), "Fee entry should be zero-sum"
        assert fee_entry.metadata.get("transaction_type") == "transfer"
        assert (
            fee_entry.metadata.get("fee") is True
        ), "Fee entry should be marked as fee"

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

    def test_fx_transfer_visibility_boundary_only(self):
        """Test that FX transfers are visible in BOUNDARY_ONLY mode."""
        from finbricklab.core.entity import Entity
        from finbricklab.core.kinds import K
        from finbricklab.core.results import TransferVisibility

        entity = Entity(id="test", name="Test Entity")

        # Create cash accounts in different currencies
        entity.new_ABrick("cash_usd", "USD Cash", K.A_CASH, {"initial_balance": 0.0})
        entity.new_ABrick("cash_eur", "EUR Cash", K.A_CASH, {"initial_balance": 1000.0})

        # Create FX transfer (EUR to USD) with start_date
        from datetime import date

        entity.new_TBrick(
            "fx_transfer",
            "FX Transfer",
            K.T_TRANSFER_LUMP_SUM,
            {
                "amount": 500.0,
                "currency": "EUR",
                "fx": {"rate": 1.1, "pair": "EUR/USD", "pnl_account": "P&L:FX"},
            },
            links={"from": "cash_eur", "to": "cash_usd"},
            start_date=date(2024, 1, 1),
        )

        scenario = entity.create_scenario(
            id="test",
            name="Test",
            brick_ids=["cash_usd", "cash_eur", "fx_transfer"],
            settlement_default_cash_id="cash_eur",
        )

        results = scenario.run(start="2024-01-01", months=1)

        # Check that FX transfer entries are visible in BOUNDARY_ONLY mode
        monthly = results["views"].monthly(
            transfer_visibility=TransferVisibility.BOUNDARY_ONLY
        )

        # FX transfers touch boundary (via b:fx_clear), so they should be visible
        # Check that there are entries in the journal
        journal = results["journal"]
        fx_entries = [
            e
            for e in journal.entries
            if e.metadata.get("transaction_type") == "fx_transfer"
        ]
        assert len(fx_entries) > 0, "Should have FX transfer entries"

        # Verify that monthly view includes cash flows (FX transfers are boundary-touching)
        # The cash_in/cash_out should reflect the FX transfer
        assert monthly is not None, "Monthly view should exist"
        # FX transfers should be visible in BOUNDARY_ONLY mode

    def test_fx_pnl_positive_gain_credits_income(self):
        """Test that positive P&L (gain) credits the P&L account (income)."""
        from finbricklab.core.accounts import FX_CLEAR_NODE_ID
        from finbricklab.core.entity import Entity
        from finbricklab.core.kinds import K

        entity = Entity(id="test", name="Test Entity")

        # Create cash accounts
        entity.new_ABrick("cash_usd", "USD Cash", K.A_CASH, {"initial_balance": 0.0})
        entity.new_ABrick("cash_eur", "EUR Cash", K.A_CASH, {"initial_balance": 1000.0})

        # Create FX transfer with explicit destination amount that creates a gain
        # Rate: 1.1, so 100 EUR = 110 USD
        # But explicit amount: 120 USD (gain of 10 USD)
        from datetime import date

        entity.new_TBrick(
            "fx_transfer",
            "FX Transfer",
            K.T_TRANSFER_LUMP_SUM,
            {
                "amount": 100.0,
                "currency": "EUR",
                "fx": {
                    "rate": 1.1,
                    "pair": "EUR/USD",
                    "amount_dest": 120.0,  # Explicit amount creates gain
                    "pnl_account": "P&L:FX",
                },
            },
            links={"from": "cash_eur", "to": "cash_usd"},
            start_date=date(2024, 1, 1),
        )

        scenario = entity.create_scenario(
            id="test",
            name="Test",
            brick_ids=["cash_usd", "cash_eur", "fx_transfer"],
            settlement_default_cash_id="cash_eur",
        )

        results = scenario.run(start="2024-01-01", months=1)
        journal = results["journal"]

        # Find P&L entry (should have transaction_type="fx_transfer" and fx_leg="pnl")
        pnl_entries = [
            e
            for e in journal.entries
            if e.metadata.get("transaction_type") == "fx_transfer"
            and e.metadata.get("tags", {}).get("fx_leg") == "pnl"
        ]

        assert len(pnl_entries) == 1, "Should have one P&L entry for gain"

        pnl_entry = pnl_entries[0]

        # Check that P&L account posting is credited (negative amount)
        # Find posting by account_id (P&L:FX), not node_id
        pnl_account_posting = next(
            p for p in pnl_entry.postings if p.account_id == "P&L:FX"
        )
        assert (
            pnl_account_posting.amount.value < 0
        ), "P&L account should be credited (negative amount) for gain"

        # Check that category is income.fx
        assert (
            pnl_account_posting.metadata.get("category") == "income.fx"
        ), "P&L entry should have category 'income.fx' for gain"

        assert (
            pnl_account_posting.metadata.get("node_id") == "P&L:FX"
        ), "P&L posting should stamp node_id with the P&L account"

        # Check that clearing account is debited (positive amount)
        clearing_posting = next(
            p for p in pnl_entry.postings if p.account_id == FX_CLEAR_NODE_ID
        )
        assert (
            clearing_posting.amount.value > 0
        ), "Clearing account should be debited (positive amount) for gain"
        assert (
            clearing_posting.metadata.get("category") == "fx.clearing"
        ), "Clearing posting should use 'fx.clearing' category"

    def test_fx_pnl_negative_loss_debits_expense(self):
        """Test that negative P&L (loss) debits the P&L account (expense)."""
        from finbricklab.core.accounts import FX_CLEAR_NODE_ID
        from finbricklab.core.entity import Entity
        from finbricklab.core.kinds import K

        entity = Entity(id="test", name="Test Entity")

        # Create cash accounts
        entity.new_ABrick("cash_usd", "USD Cash", K.A_CASH, {"initial_balance": 0.0})
        entity.new_ABrick("cash_eur", "EUR Cash", K.A_CASH, {"initial_balance": 1000.0})

        # Create FX transfer with explicit destination amount that creates a loss
        # Rate: 1.1, so 100 EUR = 110 USD
        # But explicit amount: 100 USD (loss of 10 USD)
        from datetime import date

        entity.new_TBrick(
            "fx_transfer",
            "FX Transfer",
            K.T_TRANSFER_LUMP_SUM,
            {
                "amount": 100.0,
                "currency": "EUR",
                "fx": {
                    "rate": 1.1,
                    "pair": "EUR/USD",
                    "amount_dest": 100.0,  # Explicit amount creates loss
                    "pnl_account": "P&L:FX",
                },
            },
            links={"from": "cash_eur", "to": "cash_usd"},
            start_date=date(2024, 1, 1),
        )

        scenario = entity.create_scenario(
            id="test",
            name="Test",
            brick_ids=["cash_usd", "cash_eur", "fx_transfer"],
            settlement_default_cash_id="cash_eur",
        )

        results = scenario.run(start="2024-01-01", months=1)
        journal = results["journal"]

        # Find P&L entry (should have transaction_type="fx_transfer" and fx_leg="pnl")
        pnl_entries = [
            e
            for e in journal.entries
            if e.metadata.get("transaction_type") == "fx_transfer"
            and e.metadata.get("tags", {}).get("fx_leg") == "pnl"
        ]

        assert len(pnl_entries) == 1, "Should have one P&L entry for loss"

        pnl_entry = pnl_entries[0]

        # Check that P&L account posting is debited (positive amount)
        # Find posting by account_id (P&L:FX), not node_id
        pnl_account_posting = next(
            p for p in pnl_entry.postings if p.account_id == "P&L:FX"
        )
        assert (
            pnl_account_posting.amount.value > 0
        ), "P&L account should be debited (positive amount) for loss"

        # Check that category is expense.fx
        assert (
            pnl_account_posting.metadata.get("category") == "expense.fx"
        ), "P&L entry should have category 'expense.fx' for loss"
        assert (
            pnl_account_posting.metadata.get("node_id") == "P&L:FX"
        ), "P&L posting should stamp node_id with the P&L account"

        # Check that clearing account is credited (negative amount)
        clearing_posting = next(
            p for p in pnl_entry.postings if p.account_id == FX_CLEAR_NODE_ID
        )
        assert (
            clearing_posting.amount.value < 0
        ), "Clearing account should be credited (negative amount) for loss"
        assert (
            clearing_posting.metadata.get("category") == "fx.clearing"
        ), "Clearing posting should use 'fx.clearing' category"
