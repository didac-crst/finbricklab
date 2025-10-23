"""
Private equity valuation strategy with deterministic marking.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import numpy as np

from finbricklab.core.bricks import ABrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.interfaces import IValuationStrategy
from finbricklab.core.results import BrickOutput


class ValuationPrivateEquity(IValuationStrategy):
    """
    Private equity valuation strategy (kind: 'a.private_equity').

    Models private equity investments with deterministic marking.
    Supports both drift-based valuation and explicit NAV series override.

    Required Parameters:
        - initial_value: Initial investment value
        - drift_pa: Annual drift rate for deterministic marking

    Optional Parameters:
        - nav_series: List of monthly NAV values (overrides drift calculation)
        - lockup_end_date: Lockup end date for analytics (YYYY-MM-DD format)
    """

    def simulate(
        self, brick: ABrick, ctx: ScenarioContext, months: int | None = None
    ) -> BrickOutput:
        """
        Simulate private equity valuation with deterministic marking.

        Args:
            brick: The ABrick instance
            ctx: Scenario context
            months: Number of months to simulate

        Returns:
            BrickOutput with asset values
        """
        # Extract parameters
        initial_value = Decimal(str(brick.spec["initial_value"]))
        drift_pa = Decimal(str(brick.spec["drift_pa"]))

        # Optional parameters
        nav_series = brick.spec.get("nav_series")
        lockup_end_date = brick.spec.get("lockup_end_date")

        # Get months from context if not provided
        if months is None:
            months = len(ctx.t_index)

        # Parse lockup end date if provided
        if lockup_end_date:
            lockup_date = datetime.strptime(lockup_end_date, "%Y-%m-%d").date()
        else:
            lockup_date = None

        # Initialize arrays
        asset_value = np.zeros(months, dtype=float)

        for month_idx in range(months):
            # Get the date for this month - convert from numpy datetime64 to Python date
            month_date = ctx.t_index[month_idx].astype("datetime64[D]").astype(date)

            # Calculate value for this month
            if nav_series and month_idx < len(nav_series):
                # Use explicit NAV series
                value = Decimal(str(nav_series[month_idx]))
            elif nav_series and month_idx >= len(nav_series):
                # NAV series exhausted - raise error
                raise ValueError(
                    f"NAV series exhausted at month {month_idx}. "
                    f"Series length: {len(nav_series)}, requested month: {month_idx}"
                )
            else:
                # Use drift-based calculation
                # value_t = initial_value * (1 + drift_pa)^(t/12)
                months_elapsed = Decimal(str(month_idx))
                drift_factor = (Decimal("1") + drift_pa) ** (
                    months_elapsed / Decimal("12")
                )
                value = initial_value * drift_factor

            # Store asset value
            asset_value[month_idx] = float(value)

        return BrickOutput(
            cash_in=np.zeros(months, dtype=float),
            cash_out=np.zeros(months, dtype=float),
            assets=asset_value,
            liabilities=np.zeros(months, dtype=float),
            events=[],
        )

    def _is_locked_up(self, month_date: date, lockup_date: date | None) -> bool:
        """Check if the investment is still in lockup period."""
        if lockup_date is None:
            return False
        return month_date < lockup_date
