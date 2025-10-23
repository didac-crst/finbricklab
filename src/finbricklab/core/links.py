"""
Link classes for defining relationships between bricks.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "StartLink",
    "PrincipalLink",
    "RouteLink",
]


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
    remaining_of: str | None = (
        None  # brick_id of L_LOAN_ANNUITY - take remaining balance
    )
    share: float | None = None  # 0..1, for remaining_of - take this fraction
    nominal: float | None = None  # explicit amount or None
    fill_remaining: bool = False  # absorbs residual of the settlement bucket


@dataclass
class RouteLink:
    """
    Route cash flows to/from specific cash accounts.

    links = {
      "route": {
        "to": "checking" | {"checking": 0.7, "savings": 0.3},
        "from": "checking" | {"checking": 1.0}
      }
    }

    Notes:
      - If omitted, default cash is used.
      - Dict weights are normalized; <=0 total falls back to default cash.
    """

    to: dict[str, float] | str | None = None
    from_: dict[str, float] | str | None = None  # stored as 'from_' to avoid keyword
