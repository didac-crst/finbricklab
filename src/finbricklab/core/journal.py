"""
Double-entry journal system for FinBrickLab.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import numpy as np

from .accounts import AccountScope
from .currency import Amount


def _norm_ts(ts: Any) -> np.datetime64:
    """
    Normalize timestamp to month-precision numpy datetime64.

    Accepts: str | date | datetime | np.datetime64
    Returns: np.datetime64 with 'M' precision for consistent sorting/comparison
    """
    if isinstance(ts, np.datetime64):
        return ts.astype("datetime64[M]")
    # Convert string, date, or datetime to numpy datetime64
    return np.datetime64(str(ts), "M")


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
        self._validate_two_posting()
        self._validate_zero_sum()

    def _validate_two_posting(self) -> None:
        """Validate that entry has exactly 2 postings (two-posting invariant)."""
        if len(self.postings) != 2:
            raise ValueError(
                f"Entry {self.id} must have exactly 2 postings, got {len(self.postings)}"
            )

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

        # Calculate balance at specific timestamp
        # TODO: Performance - cache sorted entries to avoid re-sorting on every call
        # Sort entries by normalized timestamp to handle out-of-order posting and mixed types
        et_normalized = _norm_ts(at_timestamp)
        sorted_entries = sorted(self.entries, key=lambda e: _norm_ts(e.timestamp))
        balance = Decimal("0")

        for entry in sorted_entries:
            entry_ts_norm = _norm_ts(entry.timestamp)
            if entry_ts_norm <= et_normalized:
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
        # Normalize timestamps for consistent comparison across types
        at_ts_norm = _norm_ts(at_timestamp)
        balances: dict[str, dict[str, Decimal]] = {}

        # Sort by normalized timestamp to handle out-of-order entries
        for entry in sorted(self.entries, key=lambda e: _norm_ts(e.timestamp)):
            entry_ts_norm = _norm_ts(entry.timestamp)
            if entry_ts_norm <= at_ts_norm:
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
                # Entries are sorted, safe to break
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

        # Normalize timestamps for consistent comparison across types
        start_ts_norm = _norm_ts(start_timestamp)
        end_ts_norm = _norm_ts(end_timestamp)

        for entry in self.entries:
            entry_ts_norm = _norm_ts(entry.timestamp)
            if start_ts_norm <= entry_ts_norm <= end_ts_norm:
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
    # Normalize timestamp to month precision to ensure consistent hashing for same month
    try:
        ts_norm = _norm_ts(timestamp)
        timestamp_str = str(ts_norm)
    except Exception:
        timestamp_str = (
            timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
        )

    # Handle None links
    links_str = str(sorted(links.items())) if links else "None"
    content = (
        f"{brick_id}:{timestamp_str}:{str(sorted(spec.items()))}:{links_str}:{sequence}"
    )
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def create_operation_id(
    parent_id: str, timestamp: datetime, hash_suffix: str = ""
) -> str:
    """
    Create operation ID in format: op:<parent_id>:<YYYY-MM>[:hash].

    Args:
        parent_id: Creator node ID (a:/l:/fs:/ts:)
        timestamp: Operation timestamp
        hash_suffix: Optional hash suffix for disambiguation

    Returns:
        Operation ID string
    """
    # Normalize timestamp to month precision
    try:
        ts_norm = _norm_ts(timestamp)
        timestamp_str = str(ts_norm)
        # Extract YYYY-MM from datetime64[M]
        year_month = timestamp_str.split("-")[:2]
        year_month_str = "-".join(year_month)
    except Exception:
        # Fallback to datetime formatting
        year_month_str = (
            timestamp.strftime("%Y-%m")
            if hasattr(timestamp, "strftime")
            else str(timestamp)[:7]
        )

    op_id = f"op:{parent_id}:{year_month_str}"
    if hash_suffix:
        op_id = f"{op_id}:{hash_suffix}"
    return op_id


def create_entry_id(operation_id: str, sequence: int) -> str:
    """
    Create entry ID (CDPair ID) in format: cp:<operation_id>:<sequence>.

    Args:
        operation_id: Operation ID
        sequence: Sequence number within operation (1, 2, ...)

    Returns:
        Entry ID string
    """
    return f"cp:{operation_id}:{sequence}"


def stamp_entry_metadata(
    entry: JournalEntry,
    parent_id: str,
    timestamp: datetime,
    tags: dict[str, Any],
    sequence: int,
    origin_id: str | None = None,
) -> None:
    """
    Stamp required metadata on journal entry.

    Args:
        entry: Journal entry to stamp
        parent_id: Creator node ID (a:/l:/fs:/ts:)
        timestamp: Entry timestamp
        tags: Shared tags dict (e.g., {'type': 'principal'})
        sequence: Sequence number within operation
        origin_id: Optional origin ID (if None, will be generated)
    """
    # Create operation_id and entry_id
    operation_id = create_operation_id(parent_id, timestamp)
    entry_id = create_entry_id(operation_id, sequence)

    # Generate origin_id if not provided
    if origin_id is None:
        # Use a simplified hash based on operation_id and sequence
        content = f"{operation_id}:{sequence}"
        origin_id = hashlib.sha256(content.encode()).hexdigest()[:16]

    # Stamp metadata
    entry.metadata["operation_id"] = operation_id
    entry.metadata["parent_id"] = parent_id
    entry.metadata["sequence"] = sequence
    entry.metadata["origin_id"] = origin_id
    entry.metadata["tags"] = tags.copy()

    # Update entry ID if it doesn't match
    if entry.id != entry_id:
        entry.id = entry_id


def stamp_posting_metadata(
    posting: Posting,
    node_id: str,
    category: str | None = None,
    type_tag: str | None = None,
) -> None:
    """
    Stamp required metadata on posting.

    Args:
        posting: Posting to stamp
        node_id: Logical node ID (a:/l:/b:boundary)
        category: Category for boundary postings (e.g., 'income.salary', 'expense.interest')
        type_tag: Optional type tag (e.g., 'principal', 'interest', 'fee')
    """
    posting.metadata["node_id"] = node_id
    if category:
        posting.metadata["category"] = category
    if type_tag:
        posting.metadata["type"] = type_tag


def validate_entry_metadata(entry: JournalEntry) -> None:
    """
    Validate that entry has all required metadata keys.

    Args:
        entry: Journal entry to validate

    Raises:
        ValueError: If required metadata is missing
    """
    required_keys = ["operation_id", "parent_id", "sequence", "origin_id", "tags"]
    missing_keys = [key for key in required_keys if key not in entry.metadata]
    if missing_keys:
        raise ValueError(
            f"Entry {entry.id} missing required metadata keys: {missing_keys}"
        )

    # Validate types
    if not isinstance(entry.metadata["sequence"], int):
        raise ValueError(f"Entry {entry.id} metadata 'sequence' must be int")
    if not isinstance(entry.metadata["tags"], dict):
        raise ValueError(f"Entry {entry.id} metadata 'tags' must be dict")


def validate_posting_metadata(posting: Posting) -> None:
    """
    Validate that posting has required metadata.

    Args:
        posting: Posting to validate

    Raises:
        ValueError: If required metadata is missing
    """
    if "node_id" not in posting.metadata:
        raise ValueError(
            f"Posting to account {posting.account_id} missing required 'node_id' in metadata"
        )

    # Check if this is a boundary posting (node_id == 'b:boundary')
    node_id = posting.metadata.get("node_id")
    if node_id == "b:boundary":
        if "category" not in posting.metadata:
            raise ValueError(
                f"Boundary posting to account {posting.account_id} missing required 'category' in metadata"
            )
