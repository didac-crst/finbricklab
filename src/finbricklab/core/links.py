"""
Link classes for defining relationships between bricks.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StartLink:
    """Link to define when a brick starts based on another brick's lifecycle."""

    on_end_of: str | None = None  # brick_id - start when brick ends
    on_fix_end_of: str | None = (
        None  # brick_id - start when brick's fixed rate period ends
    )
    offset_m: int = 0  # months offset from the reference point


@dataclass
class PrincipalLink:
    """Link to define how a mortgage gets its principal amount."""

    from_house: str | None = (
        None  # brick_id of A_PROPERTY - price - down_payment - fees
    )
    remaining_of: str | None = None  # brick_id of L_MORT_ANN - take remaining balance
    share: float | None = None  # 0..1, for remaining_of - take this fraction
    nominal: float | None = None  # explicit amount or None
    fill_remaining: bool = False  # absorbs residual of the settlement bucket
