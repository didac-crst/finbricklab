"""
Tests for journal balance snapshot and out-of-order posting handling.
"""

from decimal import Decimal

import numpy as np
import pytest
from finbricklab.core.currency import create_amount
from finbricklab.core.journal import Journal, JournalEntry, Posting


class TestJournalBalanceSnapshot:
    """Test journal balance calculation with out-of-order and snapshot semantics."""

    def test_out_of_order_posting_consistency(self):
        """Test that balance is consistent regardless of posting order."""
        journal = Journal()

        # Create entries out of order
        entry1 = JournalEntry(
            id="txn1",
            timestamp=np.datetime64("2024-01-15", "M"),
            postings=[
                Posting("asset:cash", create_amount(100, "EUR"), {}),
                Posting("equity:opening", create_amount(-100, "EUR"), {}),
            ],
        )

        entry2 = JournalEntry(
            id="txn2",
            timestamp=np.datetime64("2024-02-15", "M"),
            postings=[
                Posting("asset:cash", create_amount(50, "EUR"), {}),
                Posting("income:salary", create_amount(-50, "EUR"), {}),
            ],
        )

        entry3 = JournalEntry(
            id="txn3",
            timestamp=np.datetime64("2024-03-15", "M"),
            postings=[
                Posting("asset:cash", create_amount(-30, "EUR"), {}),
                Posting("expense:food", create_amount(30, "EUR"), {}),
            ],
        )

        # Post in chronological order
        journal.post(entry1)
        journal.post(entry2)
        journal.post(entry3)

        balance_chronological = journal.balance(
            "asset:cash", "EUR", at_timestamp=np.datetime64("2024-03-20", "M")
        )
        assert balance_chronological == Decimal("120")

        # Now create a new journal and post out of order
        journal_reordered = Journal()
        journal_reordered.post(entry2)  # February first
        journal_reordered.post(entry3)  # March second
        journal_reordered.post(entry1)  # January last

        balance_reordered = journal_reordered.balance(
            "asset:cash", "EUR", at_timestamp=np.datetime64("2024-03-20", "M")
        )

        # Should be identical
        assert balance_reordered == balance_chronological
        assert balance_reordered == Decimal("120")

    def test_balance_snapshot_at_different_times(self):
        """Test balance snapshots at different timestamps."""
        journal = Journal()

        entry1 = JournalEntry(
            id="txn1",
            timestamp=np.datetime64("2024-01-15", "M"),
            postings=[
                Posting("asset:cash", create_amount(100, "EUR"), {}),
                Posting("equity:opening", create_amount(-100, "EUR"), {}),
            ],
        )

        entry2 = JournalEntry(
            id="txn2",
            timestamp=np.datetime64("2024-02-15", "M"),
            postings=[
                Posting("asset:cash", create_amount(50, "EUR"), {}),
                Posting("income:salary", create_amount(-50, "EUR"), {}),
            ],
        )

        entry3 = JournalEntry(
            id="txn3",
            timestamp=np.datetime64("2024-03-15", "M"),
            postings=[
                Posting("asset:cash", create_amount(-30, "EUR"), {}),
                Posting("expense:food", create_amount(30, "EUR"), {}),
            ],
        )

        journal.post(entry1)
        journal.post(entry2)
        journal.post(entry3)

        # Balance at end of January
        jan_balance = journal.balance(
            "asset:cash", "EUR", at_timestamp=np.datetime64("2024-01-31", "M")
        )
        assert jan_balance == Decimal("100")

        # Balance at end of February
        feb_balance = journal.balance(
            "asset:cash", "EUR", at_timestamp=np.datetime64("2024-02-28", "M")
        )
        assert feb_balance == Decimal("150")

        # Balance at end of March
        mar_balance = journal.balance(
            "asset:cash", "EUR", at_timestamp=np.datetime64("2024-03-31", "M")
        )
        assert mar_balance == Decimal("120")

    def test_per_currency_zero_sum_validation(self):
        """Test that every entry is zero-sum per currency."""
        # Valid entry - zero sum in same currency
        valid_entry = JournalEntry(
            id="valid",
            timestamp=np.datetime64("2024-01-15", "M"),
            postings=[
                Posting("asset:cash", create_amount(100, "EUR"), {}),
                Posting("equity:opening", create_amount(-100, "EUR"), {}),
            ],
        )
        journal = Journal()
        journal.post(valid_entry)

        # Invalid entry - not zero sum
        with pytest.raises(ValueError, match="not zero-sum"):
            invalid_entry = JournalEntry(
                id="invalid",
                timestamp=np.datetime64("2024-01-15", "M"),
                postings=[
                    Posting("asset:cash", create_amount(100, "EUR"), {}),
                    Posting("equity:opening", create_amount(-50, "EUR"), {}),
                ],
            )
            journal.post(invalid_entry)

    def test_multi_currency_entry_zero_sum(self):
        """Test entries with multiple currencies are zero-sum per currency."""
        # Entry with two currencies - both must zero-sum independently
        valid_multi = JournalEntry(
            id="multi",
            timestamp=np.datetime64("2024-01-15", "M"),
            postings=[
                Posting("asset:cash_usd", create_amount(100, "USD"), {}),
                Posting("income:salary_usd", create_amount(-100, "USD"), {}),
                Posting("asset:cash_eur", create_amount(50, "EUR"), {}),
                Posting("income:salary_eur", create_amount(-50, "EUR"), {}),
            ],
        )
        journal = Journal()
        journal.post(valid_multi)

        # Invalid multi-currency - EUR doesn't zero-sum
        with pytest.raises(ValueError, match="not zero-sum"):
            invalid_multi = JournalEntry(
                id="invalid_multi",
                timestamp=np.datetime64("2024-01-15", "M"),
                postings=[
                    Posting("asset:cash_usd", create_amount(100, "USD"), {}),
                    Posting("income:salary_usd", create_amount(-100, "USD"), {}),
                    Posting("asset:cash_eur", create_amount(50, "EUR"), {}),
                    Posting(
                        "income:salary_eur", create_amount(-30, "EUR"), {}
                    ),  # Mismatch
                ],
            )
            journal.post(invalid_multi)

    def test_entry_get_currency_totals(self):
        """Test that get_currency_totals returns zero for valid entries."""
        entry = JournalEntry(
            id="test",
            timestamp=np.datetime64("2024-01-15", "M"),
            postings=[
                Posting("asset:cash", create_amount(100, "EUR"), {}),
                Posting("equity:opening", create_amount(-100, "EUR"), {}),
                Posting("asset:cash_usd", create_amount(50, "USD"), {}),
                Posting("income:salary", create_amount(-50, "USD"), {}),
            ],
        )

        totals = entry.get_currency_totals()
        assert totals["EUR"] == Decimal("0")
        assert totals["USD"] == Decimal("0")

    def test_entry_get_accounts(self):
        """Test get_accounts returns all unique accounts."""
        entry = JournalEntry(
            id="test",
            timestamp=np.datetime64("2024-01-15", "M"),
            postings=[
                Posting("asset:cash", create_amount(100, "EUR"), {}),
                Posting("equity:opening", create_amount(-100, "EUR"), {}),
                Posting("asset:cash", create_amount(50, "EUR"), {}),  # Same account
                Posting("income:salary", create_amount(-50, "EUR"), {}),
            ],
        )

        accounts = entry.get_accounts()
        assert accounts == {"asset:cash", "equity:opening", "income:salary"}
