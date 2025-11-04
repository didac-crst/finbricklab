"""
One-time income flow strategy.
"""

from __future__ import annotations

import numpy as np

from finbricklab.core.bricks import FBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.errors import ConfigError
from finbricklab.core.interfaces import IFlowStrategy
from finbricklab.core.results import BrickOutput


class FlowIncomeOneTime(IFlowStrategy):
    """
    One-time income flow strategy (kind: 'f.income.onetime').

    This strategy models a single one-time income event.
    Commonly used for bonuses, inheritance, tax refunds, or other
    one-time cash inflows.

    Required Parameters:
        - amount: The one-time income amount
        - start_date: The date when the income occurs (set on the brick)

    Optional Parameters:
        - tax_rate: Tax rate on this income (default: 0.0)
    """

    def prepare(self, brick: FBrick, ctx: ScenarioContext) -> None:
        """Validate configuration before simulation."""
        if brick.spec is None:
            raise ConfigError("IncomeOneTime: spec is required")
        if "amount" not in brick.spec:
            raise ConfigError("IncomeOneTime: 'amount' is required")
        try:
            amt = float(brick.spec["amount"])  # arrays are float downstream
        except Exception as e:
            raise ConfigError(f"IncomeOneTime: invalid amount: {e}") from e
        if amt < 0:
            raise ConfigError("IncomeOneTime: amount must be >= 0")
        tax_rate = float(brick.spec.get("tax_rate", 0.0))
        if not (0.0 <= tax_rate <= 1.0):
            raise ConfigError("IncomeOneTime: tax_rate must be in [0,1]")
        # Requires start_date on brick; check presence
        if not brick.start_date:
            raise ConfigError("IncomeOneTime: start_date must be set on the brick")

    def simulate(self, brick: FBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate one-time income flow.

        Args:
            brick: The FBrick instance
            ctx: Scenario context

        Returns:
            BrickOutput with cash flow data
        """
        # Extract parameters
        amount = float(brick.spec["amount"])  # ensure float
        tax_rate = float(brick.spec.get("tax_rate", 0.0))

        # Use the brick's start_date for the event date
        if not brick.start_date:
            raise ConfigError(
                f"One-time income brick '{brick.id}' must have a start_date"
            )

        event_date = brick.start_date

        # Calculate net amount after tax
        net_amount = amount * (1 - tax_rate)

        # Get the number of months from the context
        months = len(ctx.t_index)

        # Initialize arrays
        cash_in = np.zeros(months, dtype=float)
        cash_out = np.zeros(months, dtype=float)

        # Find the month when this event occurs
        # Convert the event date to a string format that matches the time index
        event_month_str = event_date.strftime("%Y-%m")

        for month_idx in range(months):
            # Convert the time index to string format for comparison
            current_month_str = str(ctx.t_index[month_idx])

            # Check if this is the month of the event
            if current_month_str == event_month_str:
                cash_in[month_idx] = net_amount
                break

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            assets=np.zeros(months, dtype=float),
            liabilities=np.zeros(months, dtype=float),
            interest=np.zeros(
                months, dtype=float
            ),  # Flow bricks don't generate interest
            events=[],
        )
