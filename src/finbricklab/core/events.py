"""
Event classes for tracking simulation occurrences.
"""

from __future__ import annotations
from typing import NamedTuple, Optional, Dict, Any
import numpy as np


class Event(NamedTuple):
    """
    Time-stamped event record for financial brick simulations.
    
    Events provide a structured way to track important occurrences during
    simulation, with timestamps aligned to the simulation time index.
    
    Attributes:
        t: The month when the event occurred (np.datetime64[M])
        kind: Event type identifier (e.g., 'purchase', 'fees', 'loan_draw', 'payment')
        message: Human-readable description of the event
        meta: Optional dictionary with additional event metadata
    """
    t: np.datetime64          # Month when event occurred
    kind: str                 # Event type identifier
    message: str              # Human-readable description
    meta: Optional[Dict[str, Any]] = None  # Additional metadata
