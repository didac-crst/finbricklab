"""
MacroBrick composite structure for grouping heterogeneous bricks.

A MacroBrick is a named container that groups bricks (A/L/F) and other MacroBricks
into logical structures (e.g., "Bausparkonto", "Rental Property"). It provides
aggregated views without duplicating state - just references and derived calculations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .utils import slugify_name

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

    name: str
    id: str = ""
    members: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Normalize MacroBrick ID from name when omitted."""
        if not self.id:
            if not self.name:
                raise ValueError("MacroBrick must define either an id or a name")
            normalized = slugify_name(self.name)
            if not normalized:
                raise ValueError(
                    f"MacroBrick name '{self.name}' cannot be converted into a valid id"
                )
            self.id = normalized

    def validate_membership(self, registry: Registry) -> None:
        """
        Validate that MacroBrick members are A/L or MacroGroups only (reject F/T/Shell/Boundary).

        Args:
            registry: Registry providing lookup for bricks and MacroBricks

        Raises:
            ConfigError: If F/T/Shell/Boundary found as members
        """
        from .errors import ConfigError

        for member_id in self.members:
            if registry.is_macrobrick(member_id):
                # MacroGroups are valid members (nested groups)
                continue
            elif registry.is_brick(member_id):
                # Check brick family - only A/L allowed
                brick = registry.get_brick(member_id)
                if hasattr(brick, "family"):
                    if brick.family == "f" or brick.family == "t":
                        raise ConfigError(
                            f"MacroBrick '{self.id}' contains invalid member '{member_id}': "
                            f"F/T bricks (FlowShell/TransferShell) are not allowed. "
                            f"Only A/L bricks and other MacroGroups are valid members."
                        )
                    elif brick.family != "a" and brick.family != "l":
                        raise ConfigError(
                            f"MacroBrick '{self.id}' contains invalid member '{member_id}': "
                            f"Unknown brick family '{brick.family}'. "
                            f"Only A/L bricks and MacroGroups are valid members."
                        )
            else:
                raise ConfigError(
                    f"MacroBrick '{self.id}' contains unknown member id '{member_id}'."
                )

    def expand_member_bricks(self, registry: Registry) -> list[str]:
        """
        Resolve to a flat list of brick IDs (transitive), ensuring a DAG (no cycles).

        Validates that members are A/L or MacroGroups only (rejects F/T/Shell/Boundary).

        Args:
            registry: Registry providing lookup for bricks and MacroBricks

        Returns:
            Flat list of unique brick IDs that this MacroBrick contains

        Raises:
            ConfigError: If cycle detected, unknown member ID found, or invalid member type
        """
        from .errors import ConfigError

        # Validate membership first (fail fast)
        self.validate_membership(registry)

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
                # Validate nested macro membership
                macro.validate_membership(registry)
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
