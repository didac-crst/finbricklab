"""
Private equity valuation strategy with deterministic marking.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import numpy as np

from finbricklab.core.bricks import ABrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.errors import ConfigError
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
    """

    def prepare(self, brick: ABrick, ctx: ScenarioContext) -> None:
        """
        Prepare and validate private equity strategy.

        Args:
            brick: The ABrick instance
            ctx: Scenario context

        Raises:
            ConfigError: If required parameters are missing or invalid
        """
        # Validate required parameters
        if "initial_value" not in brick.spec:
            raise ConfigError(f"{brick.id}: Missing required parameter 'initial_value'")
        if "drift_pa" not in brick.spec:
            raise ConfigError(f"{brick.id}: Missing required parameter 'drift_pa'")

        # Validate and coerce initial_value
        initial_value = brick.spec["initial_value"]
        if isinstance(initial_value, (int, float, str)):
            initial_value = Decimal(str(initial_value))
        if initial_value < 0:
            raise ConfigError(
                f"{brick.id}: initial_value must be >= 0, got {initial_value!r}"
            )

        # Validate and coerce drift_pa
        drift_pa = brick.spec["drift_pa"]
        if isinstance(drift_pa, (int, float, str)):
            drift_pa = Decimal(str(drift_pa))
        if drift_pa < 0:
            raise ConfigError(f"{brick.id}: drift_pa must be >= 0, got {drift_pa!r}")

        # Validate nav_series if provided
        nav_series = brick.spec.get("nav_series")
        if nav_series is not None:
            if not isinstance(nav_series, list):
                raise ConfigError(
                    f"{brick.id}: nav_series must be a list, got {type(nav_series).__name__}"
                )
            for i, nav in enumerate(nav_series):
                if isinstance(nav, (int, float, str)):
                    nav_val = Decimal(str(nav))
                else:
                    nav_val = Decimal(str(nav))
                if nav_val < 0:
                    raise ConfigError(
                        f"{brick.id}: nav_series[{i}] must be >= 0, got {nav_val!r}"
                    )

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

        # Optional NAV series override
        nav_series = brick.spec.get("nav_series")

        # Get months from context if not provided
        if months is None:
            months = len(ctx.t_index)

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
                # Use drift-based calculation with monthly compounding
                # Monthly compounding: value_t = initial_value * (1 + drift_m)^t
                # where drift_m = (1 + drift_pa)^(1/12) - 1
                import math

                # Calculate monthly drift rate using float math for fractional exponent
                # then convert back to Decimal
                drift_pa_float = float(drift_pa)
                drift_m_float = math.pow(1.0 + drift_pa_float, 1.0 / 12.0) - 1.0
                drift_m = Decimal(str(drift_m_float))

                # Use integer exponent for Decimal (month_idx is integer)
                value = initial_value * (Decimal("1") + drift_m) ** month_idx

            # Store asset value
            asset_value[month_idx] = float(value)

        return BrickOutput(
            cash_in=np.zeros(months, dtype=float),
            cash_out=np.zeros(months, dtype=float),
            assets=asset_value,
            liabilities=np.zeros(months, dtype=float),
            interest=np.zeros(
                months, dtype=float
            ),  # Private equity doesn't generate regular interest
            events=[],
        )
