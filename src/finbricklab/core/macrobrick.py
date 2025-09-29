"""
MacroBrick composite structure for grouping heterogeneous bricks.

A MacroBrick is a named container that groups bricks (A/L/F) and other MacroBricks
into logical structures (e.g., "Bausparkonto", "Rental Property"). It provides
aggregated views without duplicating state - just references and derived calculations.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import Registry
    from .errors import ConfigError

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
    members: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def expand_member_bricks(self, registry: "Registry") -> List[str]:
        """
        Resolve to a flat list of brick IDs (transitive), ensuring a DAG (no cycles).
        
        Args:
            registry: Registry providing lookup for bricks and MacroBricks
            
        Returns:
            Flat list of unique brick IDs that this MacroBrick contains
            
        Raises:
            ConfigError: If cycle detected or unknown member ID found
        """
        flat: List[str] = []
        seen: Set[str] = set()

        def dfs(node_id: str):
            if node_id in seen:
                from .errors import ConfigError
                raise ConfigError(f"Cycle detected in MacroBrick membership at '{node_id}'.")
            seen.add(node_id)
            
            if registry.is_macrobrick(node_id):
                # Recursively expand nested MacroBrick
                for member_id in registry.get_macrobrick(node_id).members:
                    dfs(member_id)
            elif registry.is_brick(node_id):
                # Found a brick - add to flat list
                flat.append(node_id)
            else:
                from .errors import ConfigError
                raise ConfigError(f"Unknown member id '{node_id}' in MacroBrick '{self.id}'.")

        for member_id in self.members:
            dfs(member_id)
            
        return flat

    def __str__(self) -> str:
        return f"MacroBrick(id='{self.id}', name='{self.name}', members={len(self.members)})"

    def __repr__(self) -> str:
        return f"MacroBrick(id='{self.id}', name='{self.name}', members={self.members}, tags={self.tags})"
