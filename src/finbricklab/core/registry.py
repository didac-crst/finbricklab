"""
Registry for indexing and validating bricks and MacroBricks.

Provides unified lookup and validation for the scenario execution engine.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bricks import FinBrickABC
    from .macrobrick import MacroBrick
    from .validation import ValidationReport


class Registry:
    """
    Unified registry for bricks and MacroBricks with validation.

    The Registry class provides centralized lookup and validation for all financial
    instruments in a scenario. It ensures structural integrity (no cycles, all
    references exist) and precomputes member expansions for efficient execution.

    **Use Cases:**
    - Centralized brick and MacroBrick lookup during scenario execution
    - Validation of scenario structure before simulation
    - Efficient expansion of MacroBrick members
    - Dependency resolution and cycle detection

    **Example Usage:**
        ```python
        from finbricklab.core.registry import Registry
        from finbricklab.core.bricks import ABrick, FBrick

        # Create individual bricks
        cash = ABrick(id="cash", name="Savings", kind="a.cash", spec={"initial_balance": 10000})
        salary = FBrick(id="salary", name="Salary", kind="f.income.fixed", spec={"amount_monthly": 3000})

        # Create registry
        registry = Registry(
            bricks={"cash": cash, "salary": salary},
            macrobricks={}
        )

        # Lookup bricks
        brick = registry.get_brick("cash")
        all_bricks = registry.bricks()
        ```

    **Key Features:**
    - Provides lookup methods and validates the structure graph (no cycles, all members exist)
    - Precomputes struct member expansions for efficient access during scenario execution
    - Automatic validation on construction
    """

    def __init__(
        self, bricks: dict[str, FinBrickABC], macrobricks: dict[str, MacroBrick]
    ):
        """
        Initialize registry with bricks and MacroBricks.

        Args:
            bricks: Dictionary mapping brick ID to FinBrickABC instance
            macrobricks: Dictionary mapping MacroBrick ID to MacroBrick instance
        """
        self._bricks = bricks.copy()
        self._macrobricks = macrobricks.copy()
        self._struct_flat_members: dict[str, frozenset[str]] = {}

        # Validate the registry on construction and precompute caches
        self._precompute_struct_cache()
        self.validate()

    def is_brick(self, id: str) -> bool:
        """Check if the given ID refers to a brick."""
        return id in self._bricks

    def is_macrobrick(self, id: str) -> bool:
        """Check if the given ID refers to a MacroBrick."""
        return id in self._macrobricks

    def get_brick(self, id: str) -> FinBrickABC:
        """Get brick by ID."""
        if id not in self._bricks:
            from .errors import ConfigError

            raise ConfigError(f"Brick '{id}' not found in registry")
        return self._bricks[id]

    def get_macrobrick(self, id: str) -> MacroBrick:
        """Get MacroBrick by ID."""
        if id not in self._macrobricks:
            from .errors import ConfigError

            raise ConfigError(f"MacroBrick '{id}' not found in registry")
        return self._macrobricks[id]

    def iter_bricks(self) -> Iterator[tuple[str, FinBrickABC]]:
        """Iterate over all bricks (id, brick) pairs."""
        return iter(self._bricks.items())

    def iter_macrobricks(self) -> Iterator[tuple[str, MacroBrick]]:
        """Iterate over all MacroBricks (id, macrobrick) pairs."""
        return iter(self._macrobricks.items())

    def get_all_brick_ids(self) -> set[str]:
        """Get set of all brick IDs."""
        return set(self._bricks.keys())

    def get_all_macrobrick_ids(self) -> set[str]:
        """Get set of all MacroBrick IDs."""
        return set(self._macrobricks.keys())

    def get_struct_flat_members(self, struct_id: str) -> frozenset[str]:
        """
        Get the flat list of brick IDs for a MacroBrick (cached).

        Args:
            struct_id: MacroBrick ID

        Returns:
            Frozenset of brick IDs that this MacroBrick contains

        Raises:
            ConfigError: If struct_id not found
        """
        if struct_id not in self._struct_flat_members:
            from .errors import ConfigError

            raise ConfigError(f"MacroBrick '{struct_id}' not found in registry")
        return self._struct_flat_members[struct_id]

    def _precompute_struct_cache(self) -> None:
        """Precompute flat member expansions for all MacroBricks."""
        for struct_id, macrobrick in self._macrobricks.items():
            # Use the existing expand_member_bricks method to compute the flat set
            flat_members = macrobrick.expand_member_bricks(self)
            self._struct_flat_members[struct_id] = frozenset(flat_members)

    def validate(self) -> ValidationReport:
        """
        Validate the registry structure and return structured report.

        Checks:
        - All MacroBrick members exist (either as bricks or other MacroBricks)
        - No cycles in MacroBrick membership graph
        - No duplicate IDs between bricks and MacroBricks

        Returns:
            ValidationReport with validation results

        Raises:
            ConfigError: If validation fails (for backward compatibility)
        """
        from .errors import ConfigError
        from .validation import ValidationReport

        report = ValidationReport()

        # Check for reserved prefix usage
        reserved_prefixes = ["b:", "mb:"]
        for brick_id in self._bricks.keys():
            for prefix in reserved_prefixes:
                if brick_id.startswith(prefix):
                    report.id_conflicts.append(
                        f"Brick ID '{brick_id}' uses reserved prefix '{prefix}'"
                    )

        for macrobrick_id in self._macrobricks.keys():
            for prefix in reserved_prefixes:
                if macrobrick_id.startswith(prefix):
                    report.id_conflicts.append(
                        f"MacroBrick ID '{macrobrick_id}' uses reserved prefix '{prefix}'"
                    )

        # Check for ID conflicts between bricks and MacroBricks
        brick_ids = set(self._bricks.keys())
        macrobrick_ids = set(self._macrobricks.keys())
        conflicts = brick_ids & macrobrick_ids

        if conflicts:
            report.id_conflicts.extend(
                [f"ID conflict: '{id}'" for id in sorted(conflicts)]
            )
            # Still raise for backward compatibility
            raise ConfigError(
                f"ID conflicts between bricks and MacroBricks: {sorted(conflicts)}"
            )

        # Validate each MacroBrick
        for macrobrick_id, macrobrick in self._macrobricks.items():
            try:
                # This will raise ConfigError if there are cycles or unknown members
                macrobrick.expand_member_bricks(self)
            except ConfigError as e:
                # Parse the error to extract unknown IDs or cycles
                error_msg = str(e)
                if "Unknown member id" in error_msg:
                    # Extract the unknown ID from the error message
                    import re

                    match = re.search(r"'([^']+)'", error_msg)
                    if match:
                        report.unknown_ids.append(match.group(1))
                elif "Cycle detected" in error_msg:
                    # For now, we'll detect cycles during expansion
                    # A more sophisticated approach would track the cycle path
                    report.cycles.append([macrobrick_id, "cycle_detected"])

                # Still raise for backward compatibility
                raise ConfigError(
                    f"Validation failed for MacroBrick '{macrobrick_id}': {e}"
                ) from e

        # Check for empty MacroBricks (warning, not error)
        for macrobrick_id, macrobrick in self._macrobricks.items():
            if not macrobrick.members:
                report.empty_macrobricks.append(macrobrick_id)

        # Compute global overlaps
        self._compute_global_overlaps(report)

        return report

    def _compute_global_overlaps(self, report: ValidationReport) -> None:
        """Compute global overlaps between all MacroBricks."""

        brick_to_macrobricks: dict[str, list[str]] = {}

        for struct_id, _macrobrick in self._macrobricks.items():
            members = self.get_struct_flat_members(struct_id)
            for brick_id in members:
                brick_to_macrobricks.setdefault(brick_id, []).append(struct_id)

        for brick_id, owners in brick_to_macrobricks.items():
            if len(owners) > 1:
                report.overlaps_global[brick_id] = sorted(owners)

    def __len__(self) -> int:
        """Total number of registered items (bricks + MacroBricks)."""
        return len(self._bricks) + len(self._macrobricks)

    def __str__(self) -> str:
        return f"Registry(bricks={len(self._bricks)}, macrobricks={len(self._macrobricks)})"

    def __repr__(self) -> str:
        return f"Registry(bricks={list(self._bricks.keys())}, macrobricks={list(self._macrobricks.keys())})"
