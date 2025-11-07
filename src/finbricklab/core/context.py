"""
Context classes for FinBrickLab simulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .bricks import FinBrickABC
    from .journal import Journal


@dataclass
class ScenarioContext:
    """
    Context object passed to all brick strategies during simulation.

    This dataclass contains the shared context information that all strategies
    need access to during the simulation process, including the time index,
    currency, registry of all bricks in the scenario, and journal for posting entries.

    Attributes:
        t_index: Array of monthly datetime64 objects representing the simulation timeline
        currency: Base currency for the scenario (e.g., 'EUR', 'USD')
        registry: Dictionary mapping brick IDs to brick instances for cross-references
        journal: Journal instance for strategies to write entries directly

    Note:
        The registry allows bricks to reference other bricks through the links mechanism,
        enabling complex interdependencies like mortgages that auto-calculate from property values.
        The journal allows strategies to create journal entries (CDPairs) directly during simulation.
    """

    t_index: np.ndarray
    currency: str
    registry: dict[str, FinBrickABC]  # id -> brick mapping
    journal: Journal | None = None  # Journal for strategies to write entries
    settlement_default_cash_id: str | None = None  # Default cash account for routing
