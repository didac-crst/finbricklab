"""
Context classes for FinBrickLab simulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .bricks import FinBrickABC


@dataclass
class ScenarioContext:
    """
    Context object passed to all brick strategies during simulation.

    This dataclass contains the shared context information that all strategies
    need access to during the simulation process, including the time index,
    currency, and registry of all bricks in the scenario.

    Attributes:
        t_index: Array of monthly datetime64 objects representing the simulation timeline
        currency: Base currency for the scenario (e.g., 'EUR', 'USD')
        registry: Dictionary mapping brick IDs to brick instances for cross-references

    Note:
        The registry allows bricks to reference other bricks through the links mechanism,
        enabling complex interdependencies like mortgages that auto-calculate from property values.
    """

    t_index: np.ndarray
    currency: str
    registry: dict[str, FinBrickABC]  # id -> brick mapping
