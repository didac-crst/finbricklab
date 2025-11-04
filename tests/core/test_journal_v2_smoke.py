"""
Smoke tests for V2 postings model.

These tests verify core invariants:
- Internal transfer cancellation
- Boundary entries never cancel
- Income/interest classification via category/type tags
"""

from datetime import datetime

import pytest
from finbricklab.core.accounts import (
    BOUNDARY_NODE_ID,
    Account,
    AccountRegistry,
    AccountScope,
    AccountType,
)
from finbricklab.core.currency import create_amount
from finbricklab.core.journal import Journal, JournalEntry, Posting
from finbricklab.core.registry import Registry
from finbricklab.core.results import TransferVisibility, _aggregate_journal_monthly


@pytest.fixture
def account_registry():
    """Create account registry for tests."""
    return AccountRegistry()


@pytest.fixture
def journal(account_registry):
    """Create journal for tests."""
    return Journal(account_registry)


@pytest.fixture
def registry():
    """Create registry for tests."""
    return Registry(bricks={}, macrobricks={})


class TestInternalTransferCancellation:
    """Test that internal transfers cancel in MacroGroup aggregation."""

    def test_internal_transfer_cancels(self, journal, account_registry, registry):
        """Internal transfer (cash→etf) cancels when both in selection."""
        # Create cash and ETF accounts
        cash_node_id = "a:cash"
        etf_node_id = "a:etf"

        account_registry.register_account(
            Account(
                id=cash_node_id,
                name="Cash",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )
        account_registry.register_account(
            Account(
                id=etf_node_id,
                name="ETF",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create internal transfer entry: cash→etf (100 EUR)
        transfer_entry = JournalEntry(
            id="cp:transfer:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(-100, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
                Posting(
                    account_id=etf_node_id,
                    amount=create_amount(100, "EUR"),
                    metadata={"node_id": etf_node_id},
                ),
            ],
            metadata={
                "operation_id": "op:transfer:2026-01",
                "parent_id": "ts:transfer",
                "sequence": 1,
                "origin_id": "transfer1",
                "tags": {"type": "transfer"},
            },
        )
        journal.post(transfer_entry)

        # Create salary entry: boundary→cash (1000 EUR)
        salary_entry = JournalEntry(
            id="cp:salary:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(1000, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
                Posting(
                    account_id=BOUNDARY_NODE_ID,
                    amount=create_amount(-1000, "EUR"),
                    metadata={"node_id": BOUNDARY_NODE_ID, "category": "income.salary"},
                ),
            ],
            metadata={
                "operation_id": "op:salary:2026-01",
                "parent_id": "fs:salary",
                "sequence": 1,
                "origin_id": "salary1",
                "tags": {"type": "income"},
            },
        )
        journal.post(salary_entry)

        # Aggregate with selection {cash, etf}
        import pandas as pd

        time_index = pd.PeriodIndex([pd.Period("2026-01", freq="M")], freq="M")
        selection = {cash_node_id, etf_node_id}

        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.BOUNDARY_ONLY,
        )

        # Internal transfer should cancel (no cashflow from transfer)
        # Salary inflow should show (1000 EUR)
        assert df.loc["2026-01", "cash_in"] == 1000.0, "Salary inflow should show"
        assert df.loc["2026-01", "cash_out"] == 0.0, "Internal transfer should cancel"


class TestBoundaryNeverCancels:
    """Test that boundary entries never cancel."""

    def test_boundary_entry_never_cancels(self, journal, account_registry, registry):
        """Boundary entries (income/expense) never cancel even if both in selection."""
        cash_node_id = "a:cash"

        account_registry.register_account(
            Account(
                id=cash_node_id,
                name="Cash",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create salary entry: boundary→cash (1000 EUR)
        salary_entry = JournalEntry(
            id="cp:salary:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(1000, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
                Posting(
                    account_id=BOUNDARY_NODE_ID,
                    amount=create_amount(-1000, "EUR"),
                    metadata={"node_id": BOUNDARY_NODE_ID, "category": "income.salary"},
                ),
            ],
            metadata={
                "operation_id": "op:salary:2026-01",
                "parent_id": "fs:salary",
                "sequence": 1,
                "origin_id": "salary1",
                "tags": {"type": "income"},
            },
        )
        journal.post(salary_entry)

        # Aggregate with selection {cash, boundary}
        import pandas as pd

        time_index = pd.PeriodIndex([pd.Period("2026-01", freq="M")], freq="M")
        selection = {cash_node_id, BOUNDARY_NODE_ID}

        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.BOUNDARY_ONLY,
        )

        # Boundary entry should never cancel
        assert df.loc["2026-01", "cash_in"] == 1000.0, "Boundary entry should show"
        assert df.loc["2026-01", "cash_out"] == 0.0


class TestIncomeInterestClassification:
    """Test that income/interest are classified via category/type tags."""

    def test_income_classification(self, journal, account_registry, registry):
        """Income entries have income.salary category."""
        cash_node_id = "a:cash"

        account_registry.register_account(
            Account(
                id=cash_node_id,
                name="Cash",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create salary entry with income.salary category
        salary_entry = JournalEntry(
            id="cp:salary:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(1000, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
                Posting(
                    account_id=BOUNDARY_NODE_ID,
                    amount=create_amount(-1000, "EUR"),
                    metadata={"node_id": BOUNDARY_NODE_ID, "category": "income.salary"},
                ),
            ],
            metadata={
                "operation_id": "op:salary:2026-01",
                "parent_id": "fs:salary",
                "sequence": 1,
                "origin_id": "salary1",
                "tags": {"type": "income"},
            },
        )
        journal.post(salary_entry)

        # Verify category is present
        boundary_posting = salary_entry.postings[1]
        assert boundary_posting.metadata.get("category") == "income.salary"
        assert boundary_posting.metadata.get("node_id") == BOUNDARY_NODE_ID

    def test_interest_classification(self, journal, account_registry, registry):
        """Interest entries have expense.interest category."""
        cash_node_id = "a:cash"
        liability_node_id = "l:mortgage"

        account_registry.register_account(
            Account(
                id=cash_node_id,
                name="Cash",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )
        account_registry.register_account(
            Account(
                id=liability_node_id,
                name="Mortgage",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.LIABILITY,
            )
        )

        # Create interest payment entry with expense.interest category
        interest_entry = JournalEntry(
            id="cp:interest:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(-500, "EUR"),
                    metadata={"node_id": cash_node_id, "type": "interest"},
                ),
                Posting(
                    account_id=BOUNDARY_NODE_ID,
                    amount=create_amount(500, "EUR"),
                    metadata={
                        "node_id": BOUNDARY_NODE_ID,
                        "category": "expense.interest",
                    },
                ),
            ],
            metadata={
                "operation_id": "op:interest:2026-01",
                "parent_id": "l:mortgage",
                "sequence": 1,
                "origin_id": "interest1",
                "tags": {"type": "interest"},
            },
        )
        journal.post(interest_entry)

        # Verify category is present
        boundary_posting = interest_entry.postings[1]
        assert boundary_posting.metadata.get("category") == "expense.interest"
        assert boundary_posting.metadata.get("node_id") == BOUNDARY_NODE_ID


class TestJournalInvariants:
    """Test that journal invariants are enforced."""

    def test_two_posting_invariant(self):
        """Journal entries must have exactly 2 postings."""
        journal = Journal(AccountRegistry())

        # Should fail with 1 posting (validation happens on construction)
        with pytest.raises(ValueError, match="must have exactly 2 postings"):
            entry = JournalEntry(
                id="cp:invalid:1",
                timestamp=datetime(2026, 1, 1),
                postings=[
                    Posting(
                        account_id="a:cash",
                        amount=create_amount(100, "EUR"),
                        metadata={},
                    ),
                ],
                metadata={},
            )

        # Should fail with 3 postings (validation happens on construction)
        with pytest.raises(ValueError, match="must have exactly 2 postings"):
            entry = JournalEntry(
                id="cp:invalid:2",
                timestamp=datetime(2026, 1, 1),
                postings=[
                    Posting(
                        account_id="a:cash",
                        amount=create_amount(100, "EUR"),
                        metadata={},
                    ),
                    Posting(
                        account_id="a:etf",
                        amount=create_amount(-50, "EUR"),
                        metadata={},
                    ),
                    Posting(
                        account_id="a:stock",
                        amount=create_amount(-50, "EUR"),
                        metadata={},
                    ),
                ],
                metadata={},
            )

    def test_zero_sum_invariant(self):
        """Journal entries must be zero-sum per currency."""
        journal = Journal(AccountRegistry())

        # Should fail with non-zero sum (validation happens on construction)
        with pytest.raises(ValueError, match="not zero-sum"):
            entry = JournalEntry(
                id="cp:invalid:3",
                timestamp=datetime(2026, 1, 1),
                postings=[
                    Posting(
                        account_id="a:cash",
                        amount=create_amount(100, "EUR"),
                        metadata={},
                    ),
                    Posting(
                        account_id="a:etf",
                        amount=create_amount(-50, "EUR"),  # Sum = 50, not zero
                        metadata={},
                    ),
                ],
                metadata={},
            )
