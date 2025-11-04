"""
Validation and reporting utilities for FinBrickLab.

Provides structured validation reports and disjointness checking for scenarios.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .accounts import BOUNDARY_NODE_ID, AccountRegistry, AccountScope, get_node_scope
from .journal import JournalEntry, Posting


@dataclass
class ValidationReport:
    """
    Structured validation report for scenario configuration.

    Provides machine-readable validation results with clear error/warning
    categorization for CI/CD integration and user feedback.
    """

    unknown_ids: list[str] = None
    cycles: list[list[str]] = None
    empty_macrobricks: list[str] = None
    id_conflicts: list[str] = None
    overlaps_global: dict[str, list[str]] = None

    def __post_init__(self):
        """Initialize default empty lists/dicts."""
        if self.unknown_ids is None:
            self.unknown_ids = []
        if self.cycles is None:
            self.cycles = []
        if self.empty_macrobricks is None:
            self.empty_macrobricks = []
        if self.id_conflicts is None:
            self.id_conflicts = []
        if self.overlaps_global is None:
            self.overlaps_global = {}

    def has_errors(self) -> bool:
        """Check if there are any hard errors (unknown IDs, cycles, conflicts)."""
        return bool(self.unknown_ids or self.cycles or self.id_conflicts)

    def has_warnings(self) -> bool:
        """Check if there are any warnings (empty MacroBricks, overlaps)."""
        return bool(self.empty_macrobricks or self.overlaps_global)

    def is_valid(self) -> bool:
        """Check if validation passed (no errors, warnings are OK)."""
        return not self.has_errors()

    def get_exit_code(self) -> int:
        """
        Get appropriate CLI exit code.

        Returns:
            0: Valid (no errors)
            1: Errors present
            2: Warnings only
        """
        if self.has_errors():
            return 1
        elif self.has_warnings():
            return 2
        else:
            return 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "unknown_ids": self.unknown_ids,
            "cycles": self.cycles,
            "empty_macrobricks": self.empty_macrobricks,
            "id_conflicts": self.id_conflicts,
            "overlaps_global": self.overlaps_global,
            "has_errors": self.has_errors(),
            "has_warnings": self.has_warnings(),
            "is_valid": self.is_valid(),
            "exit_code": self.get_exit_code(),
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        lines = []

        if self.is_valid():
            lines.append("✅ Validation passed")
        else:
            lines.append("❌ Validation failed")

        if self.unknown_ids:
            lines.append(f"Unknown IDs: {', '.join(self.unknown_ids)}")

        if self.cycles:
            for cycle in self.cycles:
                lines.append(f"Cycle detected: {' → '.join(cycle)} → {cycle[0]}")

        if self.id_conflicts:
            lines.append(f"ID conflicts: {', '.join(self.id_conflicts)}")

        if self.empty_macrobricks:
            lines.append(f"Empty MacroBricks: {', '.join(self.empty_macrobricks)}")

        if self.overlaps_global:
            for brick_id, owners in self.overlaps_global.items():
                lines.append(f"Brick '{brick_id}' shared by: {', '.join(owners)}")

        return "\n".join(lines)


@dataclass
class DisjointReport:
    """
    Report on disjointness check for MacroBricks.

    Provides detailed information about whether a set of MacroBricks
    share any bricks, with specific conflict details.
    """

    is_disjoint: bool
    conflicts: list[dict[str, Any]] = None

    def __post_init__(self):
        """Initialize default empty list."""
        if self.conflicts is None:
            self.conflicts = []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {"is_disjoint": self.is_disjoint, "conflicts": self.conflicts}

    def __str__(self) -> str:
        """Human-readable string representation."""
        if self.is_disjoint:
            return "✅ MacroBricks are disjoint (no shared bricks)"
        else:
            lines = ["❌ MacroBricks are not disjoint:"]
            for conflict in self.conflicts:
                if isinstance(conflict, dict):
                    lines.append(
                        f"  '{conflict['macrobrick1']}' and '{conflict['macrobrick2']}' "
                        f"share: {', '.join(conflict['shared_bricks'])}"
                    )
                else:
                    lines.append(f"  {conflict}")
            return "\n".join(lines)


def validate_entry_structure(entry: JournalEntry) -> None:
    """
    Validate that entry has exactly 2 postings and zero-sum per currency.

    Args:
        entry: Journal entry to validate

    Raises:
        ValueError: If entry structure is invalid
    """
    # Check two-posting invariant (already enforced in JournalEntry.__post_init__)
    if len(entry.postings) != 2:
        raise ValueError(
            f"Entry {entry.id} must have exactly 2 postings, got {len(entry.postings)}"
        )

    # Zero-sum validation is already done in JournalEntry.__post_init__
    # But we can re-validate here for explicit checks
    entry._validate_zero_sum()


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
    if node_id == BOUNDARY_NODE_ID:
        if "category" not in posting.metadata:
            raise ValueError(
                f"Boundary posting to account {posting.account_id} missing required 'category' in metadata"
            )


def validate_transfer_entry(entry: JournalEntry, registry: AccountRegistry) -> None:
    """
    Validate that transfer entry has both postings hit INTERNAL nodes.

    Args:
        entry: Journal entry to validate
        registry: Account registry for scope checking

    Raises:
        ValueError: If entry is not a valid transfer entry
    """
    validate_entry_structure(entry)
    validate_entry_metadata(entry)

    # Check both postings hit INTERNAL nodes
    for posting in entry.postings:
        validate_posting_metadata(posting)
        node_id = posting.metadata.get("node_id")
        scope = get_node_scope(node_id, registry)
        if scope != AccountScope.INTERNAL:
            raise ValueError(
                f"Transfer entry {entry.id}: posting to {node_id} must be INTERNAL, got {scope.value}"
            )


def validate_flow_entry(entry: JournalEntry, registry: AccountRegistry) -> None:
    """
    Validate that flow entry has exactly one BOUNDARY posting and one INTERNAL posting.

    Args:
        entry: Journal entry to validate
        registry: Account registry for scope checking

    Raises:
        ValueError: If entry is not a valid flow entry
    """
    validate_entry_structure(entry)
    validate_entry_metadata(entry)

    # Check exactly one BOUNDARY posting
    boundary_count = 0
    internal_count = 0

    for posting in entry.postings:
        validate_posting_metadata(posting)
        node_id = posting.metadata.get("node_id")
        scope = get_node_scope(node_id, registry)
        if scope == AccountScope.BOUNDARY:
            boundary_count += 1
        elif scope == AccountScope.INTERNAL:
            internal_count += 1

    if boundary_count != 1:
        raise ValueError(
            f"Flow entry {entry.id} must have exactly 1 BOUNDARY posting, got {boundary_count}"
        )
    if internal_count != 1:
        raise ValueError(
            f"Flow entry {entry.id} must have exactly 1 INTERNAL posting, got {internal_count}"
        )


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


def validate_origin_id_uniqueness(journal) -> None:
    """
    Validate that origin_id is unique per currency in the journal.

    Args:
        journal: Journal to validate

    Raises:
        ValueError: If duplicate origin_id found
    """
    seen: dict[tuple[str, str], str] = {}  # (origin_id, currency) -> entry_id

    for entry in journal.entries:
        origin_id = entry.metadata.get("origin_id")
        if origin_id is None:
            continue  # Skip entries without origin_id (legacy)

        # Check each currency in the entry
        for posting in entry.postings:
            currency = posting.amount.currency.code
            key = (origin_id, currency)
            if key in seen:
                raise ValueError(
                    f"Duplicate origin_id '{origin_id}' for currency '{currency}': "
                    f"entry {entry.id} conflicts with {seen[key]}"
                )
            seen[key] = entry.id
