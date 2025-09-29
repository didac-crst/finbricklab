"""
Validation and reporting utilities for FinBrickLab.

Provides structured validation reports and disjointness checking for scenarios.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
