"""
Tests for Journal-based multi-cash account routing functionality.
"""

from datetime import date
from decimal import Decimal

import numpy as np
from finbricklab import Entity
from finbricklab.core.accounts import (
    Account,
    AccountRegistry,
    AccountScope,
    AccountType,
)
from finbricklab.core.compiler import BrickCompiler
from finbricklab.core.context import ScenarioContext
from finbricklab.core.currency import create_amount
from finbricklab.core.journal import Journal, JournalEntry, Posting
from finbricklab.core.kinds import K


class TestJournalRouting:
    """Test Journal-based routing functionality."""

    def test_split_income_two_cash_accounts(self):
        """Test that income can be split between multiple cash accounts using Journal."""
        entity = Entity("test", "Test")

        # Create two cash accounts
        checking = entity.new_ABrick(
            "checking",
            "Checking",
            K.A_CASH,
            {"initial_balance": 0.0, "interest_pa": 0.0},
        )
        savings = entity.new_ABrick(
            "savings", "Savings", K.A_CASH, {"initial_balance": 0.0, "interest_pa": 0.0}
        )

        # Create income that splits 70% to checking, 30% to savings
        income = entity.new_FBrick(
            "income", "Salary", K.F_INCOME_RECURRING, {"amount_monthly": 3000.0}
        )

        # Create expense paid from checking only
        expense = entity.new_FBrick(
            "expense", "Living", K.F_EXPENSE_RECURRING, {"amount_monthly": 1000.0}
        )

        scenario = entity.create_scenario(
            "multi-cash",
            "Multi-cash routing",
            ["checking", "savings", "income", "expense"],
        )
        results = scenario.run(start=date(2026, 1, 1), months=3)

        # Check that income generates flows
        income_flows = results["outputs"]["income"]["cash_in"]
        assert np.sum(income_flows) > 0

        # Check that expense generates flows
        expense_flows = results["outputs"]["expense"]["cash_out"]
        assert np.sum(expense_flows) > 0

        # Check that both cash accounts receive flows (default routing to all cash accounts)
        checking_flows = results["outputs"]["checking"]["assets"]
        savings_flows = results["outputs"]["savings"]["assets"]

        # Both should have positive balances from income
        assert np.sum(checking_flows) > 0
        assert np.sum(savings_flows) > 0

    def test_default_routing_when_no_links(self):
        """Test that flows default to all cash accounts when no explicit routing."""
        entity = Entity("test", "Test")

        # Create two cash accounts
        main = entity.new_ABrick("main", "Main", K.A_CASH, {"initial_balance": 0.0})
        side = entity.new_ABrick("side", "Side", K.A_CASH, {"initial_balance": 0.0})

        # Create income and expense with no explicit routing
        income = entity.new_FBrick(
            "income", "Salary", K.F_INCOME_RECURRING, {"amount_monthly": 500.0}
        )
        expense = entity.new_FBrick(
            "expense", "Rent", K.F_EXPENSE_RECURRING, {"amount_monthly": 200.0}
        )

        scenario = entity.create_scenario(
            "defaults", "Defaults", ["main", "side", "income", "expense"]
        )
        results = scenario.run(start=date(2026, 1, 1), months=2)

        # Check that both cash accounts receive flows (default routing)
        main_flows = results["outputs"]["main"]["assets"]
        side_flows = results["outputs"]["side"]["assets"]

        # Both should have positive balances from income
        assert np.sum(main_flows) > 0
        assert np.sum(side_flows) > 0

    def test_journal_compilation_with_multiple_accounts(self):
        """Test that Journal compilation works with multiple cash accounts."""
        # Create account registry
        registry = AccountRegistry()
        journal = Journal(registry)
        compiler = BrickCompiler(registry)

        # Register cash accounts
        registry.register_account(
            Account("checking", "Checking", AccountScope.INTERNAL, AccountType.ASSET)
        )
        registry.register_account(
            Account("savings", "Savings", AccountScope.INTERNAL, AccountType.ASSET)
        )
        registry.register_account(
            Account(
                "Income:Salary", "Salary", AccountScope.BOUNDARY, AccountType.INCOME
            )
        )

        # Create mock context
        from finbricklab.core.bricks import FBrick

        income_brick = FBrick(
            id="income",
            name="Salary",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 1000.0},
            links={"to": "checking"},  # Route to checking only
        )

        # Create mock context
        import numpy as np

        ctx = ScenarioContext(
            t_index=np.array(["2026-01"], dtype="datetime64[M]"),
            currency="EUR",
            registry={"income": income_brick},
        )

        # Compile the income brick
        entries = compiler.compile_fbrick(income_brick, ctx)

        # Should create one entry
        assert len(entries) == 1
        entry = entries[0]

        # Should have two postings: income (negative) and checking (positive)
        assert len(entry.postings) == 2

        # Check postings
        income_posting = next(
            p for p in entry.postings if p.account_id == "Income:Salary"
        )
        checking_posting = next(p for p in entry.postings if p.account_id == "checking")

        assert income_posting.amount.value == Decimal("-1000.00")
        assert checking_posting.amount.value == Decimal("1000.00")

    def test_journal_validation_with_multiple_accounts(self):
        """Test that Journal validation works with multiple accounts."""
        registry = AccountRegistry()
        journal = Journal(registry)

        # Register accounts
        registry.register_account(
            Account("checking", "Checking", AccountScope.INTERNAL, AccountType.ASSET)
        )
        registry.register_account(
            Account("savings", "Savings", AccountScope.INTERNAL, AccountType.ASSET)
        )
        registry.register_account(
            Account(
                "Income:Salary", "Salary", AccountScope.BOUNDARY, AccountType.INCOME
            )
        )

        # Create valid entry
        entry = JournalEntry(
            id="income_entry",
            timestamp=date(2026, 1, 1),
            postings=[
                Posting(
                    "Income:Salary", create_amount(-1000, "EUR"), {"type": "income"}
                ),
                Posting("checking", create_amount(700, "EUR"), {"type": "checking_in"}),
                Posting("savings", create_amount(300, "EUR"), {"type": "savings_in"}),
            ],
            metadata={"type": "income_split"},
        )

        # Should not raise validation errors
        journal.post(entry)
        errors = journal.validate_invariants(registry)
        assert len(errors) == 0

        # Check balances
        checking_balance = journal.balance("checking", "EUR")
        savings_balance = journal.balance("savings", "EUR")
        income_balance = journal.balance("Income:Salary", "EUR")

        assert checking_balance == Decimal("700.00")
        assert savings_balance == Decimal("300.00")
        assert income_balance == Decimal("-1000.00")

    def test_currency_precision_with_routing(self):
        """Test that currency precision is maintained with routing."""
        registry = AccountRegistry()
        journal = Journal(registry)

        # Register accounts
        registry.register_account(
            Account("checking", "Checking", AccountScope.INTERNAL, AccountType.ASSET)
        )
        registry.register_account(
            Account("savings", "Savings", AccountScope.INTERNAL, AccountType.ASSET)
        )
        registry.register_account(
            Account(
                "Income:Salary", "Salary", AccountScope.BOUNDARY, AccountType.INCOME
            )
        )

        # Test with precise amounts
        entry = JournalEntry(
            id="precision_test",
            timestamp=date(2026, 1, 1),
            postings=[
                Posting(
                    "Income:Salary", create_amount(-1234.56, "EUR"), {"type": "income"}
                ),
                Posting(
                    "checking", create_amount(864.19, "EUR"), {"type": "checking_in"}
                ),  # 70%
                Posting(
                    "savings", create_amount(370.37, "EUR"), {"type": "savings_in"}
                ),  # 30%
            ],
            metadata={"type": "income_split"},
        )

        journal.post(entry)

        # Check that precision is maintained
        checking_balance = journal.balance("checking", "EUR")
        savings_balance = journal.balance("savings", "EUR")

        assert checking_balance == Decimal("864.19")
        assert savings_balance == Decimal("370.37")

        # Total should equal income
        total_internal = checking_balance + savings_balance
        income_balance = journal.balance("Income:Salary", "EUR")
        assert total_internal == -income_balance

    def test_scenario_with_multiple_cash_accounts(self):
        """Test complete scenario with multiple cash accounts."""
        entity = Entity("test", "Test")

        # Create multiple cash accounts
        checking = entity.new_ABrick(
            "checking",
            "Checking",
            K.A_CASH,
            {"initial_balance": 1000.0, "interest_pa": 0.02},
        )
        savings = entity.new_ABrick(
            "savings",
            "Savings",
            K.A_CASH,
            {"initial_balance": 5000.0, "interest_pa": 0.03},
        )
        investment = entity.new_ABrick(
            "investment",
            "Investment",
            K.A_CASH,
            {"initial_balance": 0.0, "interest_pa": 0.01},
        )

        # Create various flows
        salary = entity.new_FBrick(
            "salary", "Salary", K.F_INCOME_RECURRING, {"amount_monthly": 5000.0}
        )
        bonus = entity.new_FBrick(
            "bonus", "Bonus", K.F_INCOME_RECURRING, {"amount_monthly": 1000.0}
        )
        rent = entity.new_FBrick(
            "rent", "Rent", K.F_EXPENSE_RECURRING, {"amount_monthly": 2000.0}
        )
        groceries = entity.new_FBrick(
            "groceries", "Groceries", K.F_EXPENSE_RECURRING, {"amount_monthly": 800.0}
        )

        scenario = entity.create_scenario(
            "multi-account",
            "Multi-account scenario",
            [
                "checking",
                "savings",
                "investment",
                "salary",
                "bonus",
                "rent",
                "groceries",
            ],
        )
        results = scenario.run(start=date(2026, 1, 1), months=6)

        # Check that all accounts have reasonable balances
        checking_balance = results["outputs"]["checking"]["assets"]
        savings_balance = results["outputs"]["savings"]["assets"]
        investment_balance = results["outputs"]["investment"]["assets"]

        # All should have positive balances
        assert np.sum(checking_balance) > 0
        assert np.sum(savings_balance) > 0
        assert np.sum(investment_balance) > 0

        # Check that flows are generating
        salary_flows = results["outputs"]["salary"]["cash_in"]
        rent_flows = results["outputs"]["rent"]["cash_out"]

        assert np.sum(salary_flows) > 0
        assert np.sum(rent_flows) > 0

        # Check that balances are growing over time (income > expenses)
        assert checking_balance[-1] > checking_balance[0]
        assert savings_balance[-1] > savings_balance[0]

    def test_journal_entries_with_different_currencies(self):
        """Test Journal entries with different currencies."""
        registry = AccountRegistry()
        journal = Journal(registry)

        # Register accounts
        registry.register_account(
            Account("checking", "Checking", AccountScope.INTERNAL, AccountType.ASSET)
        )
        registry.register_account(
            Account(
                "Income:Salary", "Salary", AccountScope.BOUNDARY, AccountType.INCOME
            )
        )

        # Test EUR entry
        eur_entry = JournalEntry(
            id="eur_entry",
            timestamp=date(2026, 1, 1),
            postings=[
                Posting(
                    "Income:Salary", create_amount(-1000, "EUR"), {"type": "income"}
                ),
                Posting("checking", create_amount(1000, "EUR"), {"type": "cash_in"}),
            ],
            metadata={"type": "income"},
        )
        journal.post(eur_entry)

        # Test USD entry
        usd_entry = JournalEntry(
            id="usd_entry",
            timestamp=date(2026, 1, 2),
            postings=[
                Posting(
                    "Income:Salary", create_amount(-1200, "USD"), {"type": "income"}
                ),
                Posting("checking", create_amount(1200, "USD"), {"type": "cash_in"}),
            ],
            metadata={"type": "income"},
        )
        journal.post(usd_entry)

        # Check balances in different currencies
        eur_balance = journal.balance("checking", "EUR")
        usd_balance = journal.balance("checking", "USD")

        assert eur_balance == Decimal("1000.00")
        assert usd_balance == Decimal("1200.00")

        # Check that trial balance handles multiple currencies
        trial_balance = journal.trial_balance()
        assert "EUR" in trial_balance["checking"]
        assert "USD" in trial_balance["checking"]
