"""
Double-entry journal system for FinBrickLab.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from .accounts import AccountScope
from .currency import Amount


@dataclass
class Posting:
    """
    A single posting in a journal entry.

    Attributes:
        account_id: Account identifier
        amount: Monetary amount (positive for debit, negative for credit)
        metadata: Optional metadata for the posting
    """

    account_id: str
    amount: Amount
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate posting after initialization."""
        if not isinstance(self.amount, Amount):
            raise ValueError("Amount must be an Amount object")

    def is_debit(self) -> bool:
        """Check if posting is a debit (positive amount)."""
        return self.amount.value > 0

    def is_credit(self) -> bool:
        """Check if posting is a credit (negative amount)."""
        return self.amount.value < 0

    def __str__(self) -> str:
        return f"{self.account_id}: {self.amount}"

    def __repr__(self) -> str:
        return f"Posting(account_id='{self.account_id}', amount={self.amount})"


@dataclass
class JournalEntry:
    """
    A double-entry journal entry.

    Attributes:
        id: Unique transaction identifier
        timestamp: Entry timestamp
        postings: List of postings in this entry
        metadata: Optional metadata for the entry
    """

    id: str
    timestamp: datetime
    postings: list[Posting]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate entry after initialization."""
        self._validate_zero_sum()

    def _validate_zero_sum(self) -> None:
        """Validate that entry is zero-sum by currency."""
        currency_totals: dict[str, Decimal] = {}

        for posting in self.postings:
            currency = posting.amount.currency.code
            amount = posting.amount.value

            if currency not in currency_totals:
                currency_totals[currency] = Decimal("0")
            currency_totals[currency] += amount

        # Check zero-sum for each currency
        for currency, total in currency_totals.items():
            if total != 0:
                raise ValueError(
                    f"Entry {self.id} is not zero-sum for currency {currency}: {total}"
                )

    def get_currency_totals(self) -> dict[str, Decimal]:
        """Get total amounts by currency."""
        currency_totals: dict[str, Decimal] = {}

        for posting in self.postings:
            currency = posting.amount.currency.code
            amount = posting.amount.value

            if currency not in currency_totals:
                currency_totals[currency] = Decimal("0")
            currency_totals[currency] += amount

        return currency_totals

    def get_accounts(self) -> set[str]:
        """Get all account IDs in this entry."""
        return {posting.account_id for posting in self.postings}

    def __str__(self) -> str:
        lines = [f"Entry {self.id} @ {self.timestamp}"]
        for posting in self.postings:
            lines.append(f"  {posting}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"JournalEntry(id='{self.id}', timestamp={self.timestamp}, postings={len(self.postings)})"


class Journal:
    """
    Double-entry journal for recording financial transactions.

    Attributes:
        entries: List of journal entries
        account_registry: Registry for account information
    """

    def __init__(self, account_registry: Optional[Any] = None):
        self.entries: list[JournalEntry] = []
        self.account_registry = account_registry
        self._balances: dict[
            str, dict[str, Decimal]
        ] = {}  # account_id -> currency -> balance

    def post(self, entry: JournalEntry) -> None:
        """
        Post a journal entry to the journal.

        Args:
            entry: Journal entry to post

        Raises:
            ValueError: If entry is not zero-sum or has validation errors
        """
        # Validate entry
        entry._validate_zero_sum()

        # Check for duplicate transaction ID
        if any(e.id == entry.id for e in self.entries):
            raise ValueError(f"Duplicate transaction ID: {entry.id}")

        # Add entry
        self.entries.append(entry)

        # Update balances
        self._update_balances(entry)

    def _update_balances(self, entry: JournalEntry) -> None:
        """Update account balances from journal entry."""
        for posting in entry.postings:
            account_id = posting.account_id
            currency = posting.amount.currency.code
            amount = posting.amount.value

            if account_id not in self._balances:
                self._balances[account_id] = {}
            if currency not in self._balances[account_id]:
                self._balances[account_id][currency] = Decimal("0")

            self._balances[account_id][currency] += amount

    def balance(
        self, account_id: str, currency: str, at_timestamp: Optional[datetime] = None
    ) -> Decimal:
        """
        Get account balance at a specific time.

        Args:
            account_id: Account identifier
            currency: Currency code
            at_timestamp: Timestamp to calculate balance at (None for current)

        Returns:
            Account balance in specified currency
        """
        if at_timestamp is None:
            # Return current balance
            return self._balances.get(account_id, {}).get(currency, Decimal("0"))

        # Normalize timestamp to month precision for comparison
        try:
            import numpy as np
            from typing import Any

            et_normalized_np: Any = np.datetime64(at_timestamp, "M")
        except (ImportError, TypeError, ValueError):
            et_normalized_np = at_timestamp

        # Calculate balance at specific timestamp
        # TODO: Performance - cache sorted entries to avoid re-sorting on every call
        # Sort entries by timestamp to handle out-of-order posting
        sorted_entries = sorted(self.entries, key=lambda e: e.timestamp)
        balance = Decimal("0")

        for entry in sorted_entries:
            try:
                import numpy as np
                from typing import Any

                entry_timestamp_np: Any = np.datetime64(entry.timestamp, "M")
            except (ImportError, TypeError, ValueError):
                entry_timestamp_np = entry.timestamp

            if entry_timestamp_np <= et_normalized_np:
                for posting in entry.postings:
                    if (
                        posting.account_id == account_id
                        and posting.amount.currency.code == currency
                    ):
                        balance += posting.amount.value

        return balance

    def trial_balance(
        self, at_timestamp: Optional[datetime] = None
    ) -> dict[str, dict[str, Decimal]]:
        """
        Get trial balance for all accounts.

        Args:
            at_timestamp: Timestamp to calculate balance at (None for current)

        Returns:
            Dictionary of account_id -> currency -> balance
        """
        if at_timestamp is None:
            return self._balances.copy()

        # Calculate balances at specific timestamp
        balances: dict[str, dict[str, Decimal]] = {}

        for entry in self.entries:
            if entry.timestamp <= at_timestamp:
                for posting in entry.postings:
                    account_id = posting.account_id
                    currency = posting.amount.currency.code
                    amount = posting.amount.value

                    if account_id not in balances:
                        balances[account_id] = {}
                    if currency not in balances[account_id]:
                        balances[account_id][currency] = Decimal("0")

                    balances[account_id][currency] += amount
            else:
                break

        return balances

    def cashflow(
        self,
        start_timestamp: datetime,
        end_timestamp: datetime,
        by_scope: Optional[AccountScope] = None,
    ) -> dict[str, Decimal]:
        """
        Calculate cash flow for a time period.

        Args:
            start_timestamp: Start of period
            end_timestamp: End of period
            by_scope: Filter by account scope (None for all)

        Returns:
            Dictionary of currency -> net cash flow
        """
        cashflow: dict[str, Decimal] = {}

        for entry in self.entries:
            if start_timestamp <= entry.timestamp <= end_timestamp:
                for posting in entry.postings:
                    # Filter by scope if specified
                    if by_scope and self.account_registry:
                        account = self.account_registry.get_account(posting.account_id)
                        if account and account.scope != by_scope:
                            continue

                    currency = posting.amount.currency.code
                    amount = posting.amount.value

                    if currency not in cashflow:
                        cashflow[currency] = Decimal("0")
                    cashflow[currency] += amount

        return cashflow

    def validate_invariants(self, account_registry: Optional[Any] = None) -> list[str]:
        """
        Validate journal invariants.

        Args:
            account_registry: Account registry for scope validation

        Returns:
            List of validation errors (empty if all valid)
        """
        errors = []

        # Check zero-sum for each entry
        for entry in self.entries:
            try:
                entry._validate_zero_sum()
            except ValueError as e:
                errors.append(f"Entry {entry.id}: {e}")

        # Check for orphan accounts if registry provided
        if account_registry:
            for entry in self.entries:
                for posting in entry.postings:
                    if not account_registry.has_account(posting.account_id):
                        errors.append(
                            f"Entry {entry.id}: Orphan account {posting.account_id}"
                        )

        return errors

    def get_entries_by_account(self, account_id: str) -> list[JournalEntry]:
        """Get all entries affecting a specific account."""
        return [
            entry
            for entry in self.entries
            if any(posting.account_id == account_id for posting in entry.postings)
        ]

    def get_entries_by_time_range(
        self, start: datetime, end: datetime
    ) -> list[JournalEntry]:
        """Get entries within a time range."""
        return [entry for entry in self.entries if start <= entry.timestamp <= end]

    def __len__(self) -> int:
        """Get number of entries in journal."""
        return len(self.entries)

    def __str__(self) -> str:
        return f"Journal({len(self.entries)} entries)"

    def __repr__(self) -> str:
        return f"Journal(entries={len(self.entries)})"


def generate_transaction_id(
    brick_id: str,
    timestamp: datetime,
    spec: dict[str, Any],
    links: dict[str, Any],
    sequence: int = 0,
) -> str:
    """
    Generate deterministic transaction ID.

    Args:
        brick_id: Brick identifier
        timestamp: Transaction timestamp
        spec: Brick specification
        links: Brick links
        sequence: Sequence number for tie-breaking

    Returns:
        Deterministic transaction ID
    """
    # Create deterministic hash
    # Handle numpy datetime64 objects
    if hasattr(timestamp, "isoformat"):
        timestamp_str = timestamp.isoformat()
    else:
        # Convert numpy datetime64 to string
        timestamp_str = str(timestamp)

    # Handle None links
    links_str = str(sorted(links.items())) if links else "None"
    content = (
        f"{brick_id}:{timestamp_str}:{str(sorted(spec.items()))}:{links_str}:{sequence}"
    )
    return hashlib.sha256(content.encode()).hexdigest()[:16]
