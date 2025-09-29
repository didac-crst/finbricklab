"""
MacroBrick composite structure for grouping heterogeneous bricks.

A MacroBrick is a named container that groups bricks (A/L/F) and other MacroBricks
into logical structures (e.g., "Bausparkonto", "Rental Property"). It provides
aggregated views without duplicating state - just references and derived calculations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import Registry


@dataclass
class MacroBrick:
    """
    A composite structure that groups bricks and other MacroBricks.

    MacroBricks form a DAG (Directed Acyclic Graph) - no cycles allowed.
    They provide aggregated views by summing member outputs after simulation.

    Attributes:
        id: Unique identifier for this MacroBrick
        name: Human-readable name for display
        members: List of brick IDs or MacroBrick IDs (can be nested)
        tags: Optional tags for UI grouping and filtering
    """

    id: str
    name: str
    members: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def expand_member_bricks(self, registry: Registry) -> list[str]:
        """
        Resolve to a flat list of brick IDs (transitive), ensuring a DAG (no cycles).

        Args:
            registry: Registry providing lookup for bricks and MacroBricks

        Returns:
            Flat list of unique brick IDs that this MacroBrick contains

        Raises:
            ConfigError: If cycle detected or unknown member ID found
        """
        from .errors import ConfigError

        flat: list[str] = []
        macros_seen: set[
            str
        ] = set()  # Track visited macros (can be revisited in different paths)
        bricks_seen: set[str] = set()  # Track visited bricks (prevent duplicates)

        def dfs_macro(macro_id: str, stack: set[str]):
            """DFS for macro expansion with proper cycle detection."""
            # Check for cycle in current path
            if macro_id in stack:
                raise ConfigError(
                    f"Cycle detected in MacroBrick membership: {' -> '.join(stack)} -> {macro_id}"
                )

            # Skip if already processed this macro
            if macro_id in macros_seen:
                return

            macros_seen.add(macro_id)
            stack.add(macro_id)

            try:
                macro = registry.get_macrobrick(macro_id)
                for member_id in macro.members:
                    if registry.is_macrobrick(member_id):
                        dfs_macro(member_id, stack)
                    elif registry.is_brick(member_id):
                        add_brick(member_id)
                    else:
                        raise ConfigError(
                            f"Unknown member id '{member_id}' in MacroBrick '{macro_id}'."
                        )
            finally:
                stack.remove(macro_id)

        def add_brick(brick_id: str):
            """Add brick to flat list if not already present."""
            if brick_id not in bricks_seen:
                bricks_seen.add(brick_id)
                flat.append(brick_id)

        # Process each member of this MacroBrick
        for member_id in self.members:
            if registry.is_macrobrick(member_id):
                dfs_macro(member_id, set())
            elif registry.is_brick(member_id):
                add_brick(member_id)
            else:
                raise ConfigError(
                    f"Unknown member id '{member_id}' in MacroBrick '{self.id}'."
                )

        return flat

    def __str__(self) -> str:
        return f"MacroBrick(id='{self.id}', name='{self.name}', members={len(self.members)})"

    def __repr__(self) -> str:
        return f"MacroBrick(id='{self.id}', name='{self.name}', members={self.members}, tags={self.tags})"
