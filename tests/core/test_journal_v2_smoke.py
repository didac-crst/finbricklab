"""
Smoke tests for V2 postings model.

These tests verify core invariants:
- Internal transfer cancellation
- Boundary entries never cancel
- Income/interest classification via category/type tags
"""

from datetime import datetime

import pytest

pytestmark = pytest.mark.v2
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
from finbricklab.core.validation import validate_origin_id_uniqueness


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


class TestExpenseRecurring:
    """Test expense_recurring strategy V2 journal entries."""

    def test_expense_entry_structure(self, journal, account_registry, registry):
        """Single month expense produces one CDPair with correct structure."""
        cash_node_id = "a:cash"

        account_registry.register_account(
            Account(
                id=cash_node_id,
                name="Cash",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create expense entry (DR boundary, CR cash)
        expense_entry = JournalEntry(
            id="cp:expense:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=BOUNDARY_NODE_ID,
                    amount=create_amount(500, "EUR"),
                    metadata={
                        "node_id": BOUNDARY_NODE_ID,
                        "category": "expense.recurring",
                    },
                ),
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(-500, "EUR"),
                    metadata={"node_id": cash_node_id, "type": "expense"},
                ),
            ],
            metadata={
                "operation_id": "op:expense:2026-01",
                "parent_id": "fs:expense",
                "sequence": 1,
                "origin_id": "expense1",
                "tags": {"type": "expense"},
                "transaction_type": "expense",
            },
        )
        journal.post(expense_entry)

        # Verify entry structure
        assert len(expense_entry.postings) == 2, "Must have exactly 2 postings"
        assert expense_entry.metadata["transaction_type"] == "expense"
        assert expense_entry.metadata["tags"]["type"] == "expense"

        # Verify boundary posting (DR expense)
        boundary_posting = expense_entry.postings[0]
        assert boundary_posting.metadata.get("node_id") == BOUNDARY_NODE_ID
        assert boundary_posting.metadata.get("category") == "expense.recurring"
        # Note: type_tag is stored as "type" by stamp_posting_metadata, but we're manually creating here
        # The actual strategy will use stamp_posting_metadata which sets "type" from type_tag
        assert boundary_posting.amount.value > 0, "DR expense should be positive"

        # Verify cash posting (CR cash)
        cash_posting = expense_entry.postings[1]
        assert cash_posting.metadata.get("node_id") == cash_node_id
        assert cash_posting.metadata.get("type") == "expense"
        assert cash_posting.amount.value < 0, "CR cash should be negative"

    def test_expense_aggregation_with_cash(self, journal, account_registry, registry):
        """Expense shows as cash_out when cash node is in selection."""
        cash_node_id = "a:cash"

        account_registry.register_account(
            Account(
                id=cash_node_id,
                name="Cash",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create expense entry
        expense_entry = JournalEntry(
            id="cp:expense:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=BOUNDARY_NODE_ID,
                    amount=create_amount(500, "EUR"),
                    metadata={
                        "node_id": BOUNDARY_NODE_ID,
                        "category": "expense.recurring",
                    },
                ),
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(-500, "EUR"),
                    metadata={"node_id": cash_node_id, "type": "expense"},
                ),
            ],
            metadata={
                "operation_id": "op:expense:2026-01",
                "parent_id": "fs:expense",
                "sequence": 1,
                "origin_id": "expense1",
                "tags": {"type": "expense"},
                "transaction_type": "expense",
            },
        )
        journal.post(expense_entry)

        # Aggregate with cash node in selection
        import pandas as pd

        time_index = pd.PeriodIndex([pd.Period("2026-01", freq="M")], freq="M")
        selection = {cash_node_id}

        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.BOUNDARY_ONLY,
        )

        # Expense should show as cash_out (CR cash posting)
        assert df.loc["2026-01", "cash_out"] == 500.0, "Expense should show as cash_out"
        assert df.loc["2026-01", "cash_in"] == 0.0, "No cash_in for expense"

    def test_expense_aggregation_without_cash(
        self, journal, account_registry, registry
    ):
        """Expense shows zero cashflow when cash node is not in selection."""
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

        # Create expense entry
        expense_entry = JournalEntry(
            id="cp:expense:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=BOUNDARY_NODE_ID,
                    amount=create_amount(500, "EUR"),
                    metadata={
                        "node_id": BOUNDARY_NODE_ID,
                        "category": "expense.recurring",
                    },
                ),
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(-500, "EUR"),
                    metadata={"node_id": cash_node_id, "type": "expense"},
                ),
            ],
            metadata={
                "operation_id": "op:expense:2026-01",
                "parent_id": "fs:expense",
                "sequence": 1,
                "origin_id": "expense1",
                "tags": {"type": "expense"},
                "transaction_type": "expense",
            },
        )
        journal.post(expense_entry)

        # Aggregate with ETF node in selection (not cash)
        import pandas as pd

        time_index = pd.PeriodIndex([pd.Period("2026-01", freq="M")], freq="M")
        selection = {etf_node_id}

        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.BOUNDARY_ONLY,
        )

        # Expense should not show (cash node not in selection)
        assert (
            df.loc["2026-01", "cash_out"] == 0.0
        ), "No cashflow when cash not in selection"
        assert df.loc["2026-01", "cash_in"] == 0.0, "No cash_in"


class TestTransferRecurring:
    """Test transfer_recurring strategy V2 journal entries."""

    def test_transfer_entry_structure(self, journal, account_registry, registry):
        """Single month transfer produces one CDPair with correct structure."""
        from_node_id = "a:savings"
        to_node_id = "a:checking"

        account_registry.register_account(
            Account(
                id=from_node_id,
                name="Savings",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )
        account_registry.register_account(
            Account(
                id=to_node_id,
                name="Checking",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create internal transfer entry (DR destination, CR source)
        transfer_entry = JournalEntry(
            id="cp:transfer:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=to_node_id,
                    amount=create_amount(1000, "EUR"),
                    metadata={"node_id": to_node_id, "type": "transfer"},
                ),
                Posting(
                    account_id=from_node_id,
                    amount=create_amount(-1000, "EUR"),
                    metadata={"node_id": from_node_id, "type": "transfer"},
                ),
            ],
            metadata={
                "operation_id": "op:transfer:2026-01",
                "parent_id": "ts:transfer",
                "sequence": 1,
                "origin_id": "transfer1",
                "tags": {"type": "transfer"},
                "transaction_type": "transfer",
            },
        )
        journal.post(transfer_entry)

        # Verify entry structure
        assert len(transfer_entry.postings) == 2, "Must have exactly 2 postings"
        assert transfer_entry.metadata["transaction_type"] == "transfer"
        assert transfer_entry.metadata["tags"]["type"] == "transfer"

        # Verify destination posting (DR destination)
        dest_posting = transfer_entry.postings[0]
        assert dest_posting.metadata.get("node_id") == to_node_id
        assert dest_posting.metadata.get("type") == "transfer"
        assert dest_posting.amount.value > 0, "DR destination should be positive"

        # Verify source posting (CR source)
        source_posting = transfer_entry.postings[1]
        assert source_posting.metadata.get("node_id") == from_node_id
        assert source_posting.metadata.get("type") == "transfer"
        assert source_posting.amount.value < 0, "CR source should be negative"

    def test_transfer_aggregation_with_both_nodes(
        self, journal, account_registry, registry
    ):
        """Internal transfer cancels when both nodes are in selection."""
        from_node_id = "a:savings"
        to_node_id = "a:checking"

        account_registry.register_account(
            Account(
                id=from_node_id,
                name="Savings",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )
        account_registry.register_account(
            Account(
                id=to_node_id,
                name="Checking",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create internal transfer entry
        transfer_entry = JournalEntry(
            id="cp:transfer:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=to_node_id,
                    amount=create_amount(1000, "EUR"),
                    metadata={"node_id": to_node_id, "type": "transfer"},
                ),
                Posting(
                    account_id=from_node_id,
                    amount=create_amount(-1000, "EUR"),
                    metadata={"node_id": from_node_id, "type": "transfer"},
                ),
            ],
            metadata={
                "operation_id": "op:transfer:2026-01",
                "parent_id": "ts:transfer",
                "sequence": 1,
                "origin_id": "transfer1",
                "tags": {"type": "transfer"},
                "transaction_type": "transfer",
            },
        )
        journal.post(transfer_entry)

        # Aggregate with both nodes in selection
        import pandas as pd

        time_index = pd.PeriodIndex([pd.Period("2026-01", freq="M")], freq="M")
        selection = {from_node_id, to_node_id}

        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.BOUNDARY_ONLY,
        )

        # Internal transfer should cancel (no net cashflow)
        assert df.loc["2026-01", "cash_in"] == 0.0, "Internal transfer should cancel"
        assert df.loc["2026-01", "cash_out"] == 0.0, "Internal transfer should cancel"

    def test_transfer_aggregation_with_one_node(
        self, journal, account_registry, registry
    ):
        """Transfer shows as inflow/outflow when only one node is in selection."""
        from_node_id = "a:savings"
        to_node_id = "a:checking"

        account_registry.register_account(
            Account(
                id=from_node_id,
                name="Savings",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )
        account_registry.register_account(
            Account(
                id=to_node_id,
                name="Checking",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create internal transfer entry
        transfer_entry = JournalEntry(
            id="cp:transfer:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=to_node_id,
                    amount=create_amount(1000, "EUR"),
                    metadata={"node_id": to_node_id, "type": "transfer"},
                ),
                Posting(
                    account_id=from_node_id,
                    amount=create_amount(-1000, "EUR"),
                    metadata={"node_id": from_node_id, "type": "transfer"},
                ),
            ],
            metadata={
                "operation_id": "op:transfer:2026-01",
                "parent_id": "ts:transfer",
                "sequence": 1,
                "origin_id": "transfer1",
                "tags": {"type": "transfer"},
                "transaction_type": "transfer",
            },
        )
        journal.post(transfer_entry)

        # Aggregate with only destination node in selection
        import pandas as pd

        time_index = pd.PeriodIndex([pd.Period("2026-01", freq="M")], freq="M")
        selection = {to_node_id}

        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.ALL,
        )

        # Should show as inflow (DR destination)
        assert df.loc["2026-01", "cash_in"] == 1000.0, "Transfer should show as inflow"
        assert df.loc["2026-01", "cash_out"] == 0.0, "No outflow for destination"

        # Aggregate with only source node in selection
        selection = {from_node_id}

        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.ALL,
        )

        # Should show as outflow (CR source)
        assert df.loc["2026-01", "cash_in"] == 0.0, "No inflow for source"
        assert (
            df.loc["2026-01", "cash_out"] == 1000.0
        ), "Transfer should show as outflow"

    def test_transfer_visibility_modes(self, journal, account_registry, registry):
        """Test TransferVisibility modes for internal transfers."""
        from_node_id = "a:savings"
        to_node_id = "a:checking"
        cash_node_id = "a:cash"

        account_registry.register_account(
            Account(
                id=from_node_id,
                name="Savings",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )
        account_registry.register_account(
            Account(
                id=to_node_id,
                name="Checking",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )
        account_registry.register_account(
            Account(
                id=cash_node_id,
                name="Cash",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create internal transfer entry
        transfer_entry = JournalEntry(
            id="cp:transfer:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=to_node_id,
                    amount=create_amount(1000, "EUR"),
                    metadata={"node_id": to_node_id, "type": "transfer"},
                ),
                Posting(
                    account_id=from_node_id,
                    amount=create_amount(-1000, "EUR"),
                    metadata={"node_id": from_node_id, "type": "transfer"},
                ),
            ],
            metadata={
                "operation_id": "op:transfer:2026-01",
                "parent_id": "ts:transfer",
                "sequence": 1,
                "origin_id": "transfer1",
                "tags": {"type": "transfer"},
                "transaction_type": "transfer",
            },
        )
        journal.post(transfer_entry)

        # Create income entry for comparison
        income_entry = JournalEntry(
            id="cp:income:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(5000, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
                Posting(
                    account_id=BOUNDARY_NODE_ID,
                    amount=create_amount(-5000, "EUR"),
                    metadata={"node_id": BOUNDARY_NODE_ID, "category": "income.salary"},
                ),
            ],
            metadata={
                "operation_id": "op:income:2026-01",
                "parent_id": "fs:salary",
                "sequence": 1,
                "origin_id": "income1",
                "tags": {"type": "income"},
                "transaction_type": "income",
            },
        )
        journal.post(income_entry)

        import pandas as pd

        time_index = pd.PeriodIndex([pd.Period("2026-01", freq="M")], freq="M")
        selection = {from_node_id, to_node_id, cash_node_id}

        # Test OFF: hide internal transfers
        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.OFF,
        )
        assert df.loc["2026-01", "cash_in"] == 5000.0, "Income should show"
        assert (
            df.loc["2026-01", "cash_out"] == 0.0
        ), "Internal transfer should be hidden"

        # Test ONLY: show only transfer entries
        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.ONLY,
        )
        assert df.loc["2026-01", "cash_in"] == 1000.0, "Transfer should show"
        assert df.loc["2026-01", "cash_out"] == 1000.0, "Transfer should show"
        # Note: With both nodes in selection, transfer cancels to 0, but with ONLY mode,
        # we're showing the transfer entries themselves. This depends on implementation.
        # For now, we'll verify the behavior is consistent.

        # Test BOUNDARY_ONLY: show only boundary-touching entries
        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.BOUNDARY_ONLY,
        )
        assert df.loc["2026-01", "cash_in"] == 5000.0, "Income should show"
        assert (
            df.loc["2026-01", "cash_out"] == 0.0
        ), "Internal transfer should be hidden"

        # Test ALL: show everything
        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.ALL,
        )
        # With both nodes in selection, transfer cancels to 0 net
        assert df.loc["2026-01", "cash_in"] == 5000.0, "Income should show"
        assert df.loc["2026-01", "cash_out"] == 0.0, "Internal transfer cancels"


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


class TestOriginIdUniqueness:
    """Test that origin_id is unique per currency."""

    def test_origin_id_uniqueness(self, journal, account_registry):
        """Origin_id must be unique per currency."""
        cash_node_id = "a:cash"

        account_registry.register_account(
            Account(
                id=cash_node_id,
                name="Cash",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create first entry with origin_id "test1"
        entry1 = JournalEntry(
            id="cp:test:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(100, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(-100, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
            ],
            metadata={
                "operation_id": "op:test:2026-01",
                "parent_id": "a:test",
                "sequence": 1,
                "origin_id": "test1",
                "tags": {"type": "transfer"},
            },
        )
        journal.post(entry1)

        # Create second entry with same origin_id (should fail)
        entry2 = JournalEntry(
            id="cp:test:2",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(200, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(-200, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
            ],
            metadata={
                "operation_id": "op:test2:2026-01",
                "parent_id": "a:test2",
                "sequence": 1,
                "origin_id": "test1",  # Same origin_id
                "tags": {"type": "transfer"},
            },
        )
        journal.post(entry2)

        # Validation should fail with duplicate origin_id
        with pytest.raises(ValueError, match="Duplicate origin_id"):
            validate_origin_id_uniqueness(journal)

    def test_origin_id_different_currencies(self, journal, account_registry):
        """Origin_id can be same across different currencies."""
        cash_node_id = "a:cash"

        account_registry.register_account(
            Account(
                id=cash_node_id,
                name="Cash",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create EUR entry with origin_id "test1"
        entry1 = JournalEntry(
            id="cp:test:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(100, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(-100, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
            ],
            metadata={
                "operation_id": "op:test:2026-01",
                "parent_id": "a:test",
                "sequence": 1,
                "origin_id": "test1",
                "tags": {"type": "transfer"},
            },
        )
        journal.post(entry1)

        # Create USD entry with same origin_id (should pass - different currency)
        entry2 = JournalEntry(
            id="cp:test:2",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(200, "USD"),
                    metadata={"node_id": cash_node_id},
                ),
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(-200, "USD"),
                    metadata={"node_id": cash_node_id},
                ),
            ],
            metadata={
                "operation_id": "op:test2:2026-01",
                "parent_id": "a:test2",
                "sequence": 1,
                "origin_id": "test1",  # Same origin_id, different currency
                "tags": {"type": "transfer"},
            },
        )
        journal.post(entry2)

        # Validation should pass (different currencies)
        validate_origin_id_uniqueness(journal)


class TestDuplicateEntryId:
    """Test that duplicate entry.id is rejected."""

    def test_duplicate_entry_id(self, journal, account_registry):
        """Journal.post should reject duplicate entry.id."""
        cash_node_id = "a:cash"

        account_registry.register_account(
            Account(
                id=cash_node_id,
                name="Cash",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create first entry
        entry1 = JournalEntry(
            id="cp:test:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(100, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(-100, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
            ],
            metadata={},
        )
        journal.post(entry1)

        # Try to post entry with same id (should fail)
        entry2 = JournalEntry(
            id="cp:test:1",  # Same ID
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(200, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(-200, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
            ],
            metadata={},
        )

        with pytest.raises(ValueError, match="Duplicate transaction ID"):
            journal.post(entry2)


class TestTransferVisibility:
    """Test TransferVisibility modes (OFF/ONLY/BOUNDARY_ONLY/ALL)."""

    def test_transfer_visibility_off(self, journal, account_registry, registry):
        """OFF: Hide internal transfers, show boundary transfers."""
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

        # Create internal transfer entry
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
                "transaction_type": "transfer",
            },
        )
        journal.post(transfer_entry)

        # Create income entry (boundary)
        income_entry = JournalEntry(
            id="cp:income:1",
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
                "operation_id": "op:income:2026-01",
                "parent_id": "fs:income",
                "sequence": 1,
                "origin_id": "income1",
                "tags": {"type": "income"},
                "transaction_type": "income",
            },
        )
        journal.post(income_entry)

        # Aggregate with OFF visibility
        import pandas as pd

        time_index = pd.PeriodIndex([pd.Period("2026-01", freq="M")], freq="M")
        selection = {cash_node_id, etf_node_id}

        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.OFF,
        )

        # Internal transfer should be hidden (no cashflow)
        # Income should show (boundary)
        assert df.loc["2026-01", "cash_in"] == 1000.0, "Income should show"
        assert (
            df.loc["2026-01", "cash_out"] == 0.0
        ), "Internal transfer should be hidden"

    def test_transfer_visibility_only(self, journal, account_registry, registry):
        """ONLY: Show only transfers (for debugging)."""
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

        # Create internal transfer entry
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
                "transaction_type": "transfer",
            },
        )
        journal.post(transfer_entry)

        # Create income entry (not a transfer)
        income_entry = JournalEntry(
            id="cp:income:1",
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
                "operation_id": "op:income:2026-01",
                "parent_id": "fs:income",
                "sequence": 1,
                "origin_id": "income1",
                "tags": {"type": "income"},
                "transaction_type": "income",
            },
        )
        journal.post(income_entry)

        # Aggregate with ONLY visibility
        import pandas as pd

        time_index = pd.PeriodIndex([pd.Period("2026-01", freq="M")], freq="M")
        selection = {cash_node_id, etf_node_id}

        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.ONLY,
        )

        # Only transfer should show (income should be hidden)
        # Transfer is internal, so it cancels (no net cashflow)
        assert df.loc["2026-01", "cash_in"] == 0.0, "Only transfers should show"
        assert df.loc["2026-01", "cash_out"] == 0.0, "Internal transfer cancels"

    def test_transfer_visibility_boundary_only(
        self, journal, account_registry, registry
    ):
        """BOUNDARY_ONLY: Show only boundary-crossing transfers."""
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

        # Create internal transfer entry
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
                "transaction_type": "transfer",
            },
        )
        journal.post(transfer_entry)

        # Create income entry (boundary)
        income_entry = JournalEntry(
            id="cp:income:1",
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
                "operation_id": "op:income:2026-01",
                "parent_id": "fs:income",
                "sequence": 1,
                "origin_id": "income1",
                "tags": {"type": "income"},
                "transaction_type": "income",
            },
        )
        journal.post(income_entry)

        # Aggregate with BOUNDARY_ONLY visibility
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

        # Internal transfer should be hidden (no boundary)
        # Income should show (boundary)
        assert df.loc["2026-01", "cash_in"] == 1000.0, "Income should show"
        assert (
            df.loc["2026-01", "cash_out"] == 0.0
        ), "Internal transfer should be hidden"

    def test_transfer_visibility_all(self, journal, account_registry, registry):
        """ALL: Show all transfers."""
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

        # Create internal transfer entry
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
                "transaction_type": "transfer",
            },
        )
        journal.post(transfer_entry)

        # Create income entry (boundary)
        income_entry = JournalEntry(
            id="cp:income:1",
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
                "operation_id": "op:income:2026-01",
                "parent_id": "fs:income",
                "sequence": 1,
                "origin_id": "income1",
                "tags": {"type": "income"},
                "transaction_type": "income",
            },
        )
        journal.post(income_entry)

        # Aggregate with ALL visibility
        import pandas as pd

        time_index = pd.PeriodIndex([pd.Period("2026-01", freq="M")], freq="M")
        selection = {cash_node_id, etf_node_id}

        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.ALL,
        )

        # Both should show, but internal transfer cancels
        assert df.loc["2026-01", "cash_in"] == 1000.0, "Income should show"
        assert df.loc["2026-01", "cash_out"] == 0.0, "Internal transfer cancels"


class TestTransferVisibilitySingleNode:
    """Test TransferVisibility with single-node selection (shows transfers)."""

    def test_single_node_selection_with_all(self, journal, account_registry, registry):
        """Single-node selection with ALL visibility shows transfers."""
        from_node_id = "a:savings"
        to_node_id = "a:checking"

        account_registry.register_account(
            Account(
                id=from_node_id,
                name="Savings",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )
        account_registry.register_account(
            Account(
                id=to_node_id,
                name="Checking",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create internal transfer entry
        transfer_entry = JournalEntry(
            id="cp:transfer:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=to_node_id,
                    amount=create_amount(1000, "EUR"),
                    metadata={"node_id": to_node_id, "type": "transfer"},
                ),
                Posting(
                    account_id=from_node_id,
                    amount=create_amount(-1000, "EUR"),
                    metadata={"node_id": from_node_id, "type": "transfer"},
                ),
            ],
            metadata={
                "operation_id": "op:transfer:2026-01",
                "parent_id": "ts:transfer",
                "sequence": 1,
                "origin_id": "transfer1",
                "tags": {"type": "transfer"},
                "transaction_type": "transfer",
            },
        )
        journal.post(transfer_entry)

        import pandas as pd

        time_index = pd.PeriodIndex([pd.Period("2026-01", freq="M")], freq="M")

        # Aggregate with only destination node in selection + ALL visibility
        selection = {to_node_id}
        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.ALL,
        )

        # Should show as inflow (DR destination)
        assert df.loc["2026-01", "cash_in"] == 1000.0, "Transfer should show as inflow"
        assert df.loc["2026-01", "cash_out"] == 0.0, "No outflow for destination"

        # Aggregate with only source node in selection + ALL visibility
        selection = {from_node_id}
        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.ALL,
        )

        # Should show as outflow (CR source)
        assert df.loc["2026-01", "cash_in"] == 0.0, "No inflow for source"
        assert (
            df.loc["2026-01", "cash_out"] == 1000.0
        ), "Transfer should show as outflow"

    def test_single_node_selection_with_only(self, journal, account_registry, registry):
        """Single-node selection with ONLY visibility shows transfers."""
        from_node_id = "a:savings"
        to_node_id = "a:checking"
        cash_node_id = "a:cash"

        account_registry.register_account(
            Account(
                id=from_node_id,
                name="Savings",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )
        account_registry.register_account(
            Account(
                id=to_node_id,
                name="Checking",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )
        account_registry.register_account(
            Account(
                id=cash_node_id,
                name="Cash",
                scope=AccountScope.INTERNAL,
                account_type=AccountType.ASSET,
            )
        )

        # Create internal transfer entry
        transfer_entry = JournalEntry(
            id="cp:transfer:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=to_node_id,
                    amount=create_amount(1000, "EUR"),
                    metadata={"node_id": to_node_id, "type": "transfer"},
                ),
                Posting(
                    account_id=from_node_id,
                    amount=create_amount(-1000, "EUR"),
                    metadata={"node_id": from_node_id, "type": "transfer"},
                ),
            ],
            metadata={
                "operation_id": "op:transfer:2026-01",
                "parent_id": "ts:transfer",
                "sequence": 1,
                "origin_id": "transfer1",
                "tags": {"type": "transfer"},
                "transaction_type": "transfer",
            },
        )
        journal.post(transfer_entry)

        # Create income entry (not a transfer)
        income_entry = JournalEntry(
            id="cp:income:1",
            timestamp=datetime(2026, 1, 1),
            postings=[
                Posting(
                    account_id=cash_node_id,
                    amount=create_amount(5000, "EUR"),
                    metadata={"node_id": cash_node_id},
                ),
                Posting(
                    account_id=BOUNDARY_NODE_ID,
                    amount=create_amount(-5000, "EUR"),
                    metadata={"node_id": BOUNDARY_NODE_ID, "category": "income.salary"},
                ),
            ],
            metadata={
                "operation_id": "op:income:2026-01",
                "parent_id": "fs:income",
                "sequence": 1,
                "origin_id": "income1",
                "tags": {"type": "income"},
                "transaction_type": "income",
            },
        )
        journal.post(income_entry)

        import pandas as pd

        time_index = pd.PeriodIndex([pd.Period("2026-01", freq="M")], freq="M")

        # Aggregate with only destination node + ONLY visibility
        selection = {to_node_id}
        df = _aggregate_journal_monthly(
            journal=journal,
            registry=registry,
            time_index=time_index,
            selection=selection,
            transfer_visibility=TransferVisibility.ONLY,
        )

        # Should show transfer (income hidden)
        assert df.loc["2026-01", "cash_in"] == 1000.0, "Transfer should show"
        assert df.loc["2026-01", "cash_out"] == 0.0, "No outflow"


class TestParallelScenarios:
    """Test that scenarios with boundary entries don't interfere with each other."""

    def test_parallel_scenarios_independent(self):
        """Two scenarios with boundary entries validate independently."""
        from datetime import date

        import pandas as pd

        from finbricklab.core.scenario import Scenario
        from finbricklab.core.bricks import ABrick, FBrick

        # Scenario 1: income flow
        cash1 = ABrick(
            id="cash1",
            name="Cash 1",
            kind="a.cash",
            spec={"initial_balance": 0.0, "interest_pa": 0.0},
        )
        income1 = FBrick(
            id="income1",
            name="Income 1",
            kind="f.income.recurring",
            spec={"amount_monthly": 1000.0},
        )
        scenario1 = Scenario(
            id="scenario1",
            name="Scenario 1",
            bricks=[cash1, income1],
            currency="EUR",
        )

        # Scenario 2: expense flow
        cash2 = ABrick(
            id="cash2",
            name="Cash 2",
            kind="a.cash",
            spec={"initial_balance": 0.0, "interest_pa": 0.0},
        )
        expense2 = FBrick(
            id="expense2",
            name="Expense 2",
            kind="f.expense.recurring",
            spec={"amount_monthly": 500.0},
        )
        scenario2 = Scenario(
            id="scenario2",
            name="Scenario 2",
            bricks=[cash2, expense2],
            currency="USD",
        )

        # Run both scenarios
        results1 = scenario1.run(start=date(2026, 1, 1), months=12)
        results2 = scenario2.run(start=date(2026, 1, 1), months=12)

        # Both should have journals
        assert results1.journal is not None, "Scenario 1 should have journal"
        assert results2.journal is not None, "Scenario 2 should have journal"

        # Both journals should have boundary entries
        boundary_entries_1 = [
            e
            for e in results1.journal.entries
            if any(
                p.metadata.get("node_id") == BOUNDARY_NODE_ID for p in e.postings
            )
        ]
        boundary_entries_2 = [
            e
            for e in results2.journal.entries
            if any(
                p.metadata.get("node_id") == BOUNDARY_NODE_ID for p in e.postings
            )
        ]

        assert len(boundary_entries_1) > 0, "Scenario 1 should have boundary entries"
        assert len(boundary_entries_2) > 0, "Scenario 2 should have boundary entries"

        # Both should validate independently
        from finbricklab.core.validation import validate_origin_id_uniqueness

        validate_origin_id_uniqueness(results1.journal)
        validate_origin_id_uniqueness(results2.journal)

        # Both should aggregate correctly
        monthly1 = results1.monthly()
        monthly2 = results2.monthly()

        # Scenario 1: income should show as cash_in
        assert monthly1.loc["2026-01", "cash_in"] == 1000.0, "Scenario 1 income"
        # Scenario 2: expense should show as cash_out
        assert monthly2.loc["2026-01", "cash_out"] == 500.0, "Scenario 2 expense"

        # Journals should be independent (different currencies, different entries)
        assert results1.journal.account_registry is not results2.journal.account_registry
        assert len(results1.journal.entries) != len(results2.journal.entries)
