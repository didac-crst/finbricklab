"""
One-time income flow strategy.
"""

from __future__ import annotations

from decimal import Decimal

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
        """
        Prepare the one-time income strategy.

        Validates required parameters and coerces numeric values.

        Args:
            brick: The flow brick
            ctx: The simulation context

        Raises:
            ConfigError: If required parameters are missing or invalid
        """
        # Validate required parameters
        if "amount" not in brick.spec:
            raise ConfigError(f"{brick.id}: Missing required parameter 'amount'")

        # Coerce amount to Decimal, then float for numpy arrays
        amount = brick.spec["amount"]
        if not isinstance(amount, (int, float, Decimal, str)):
            raise ConfigError(
                f"{brick.id}: amount must be numeric, got {type(amount).__name__}"
            )
        amount_decimal = Decimal(str(amount))

        # Validate amount is positive
        if amount_decimal <= 0:
            raise ConfigError(
                f"{brick.id}: amount must be positive, got {amount_decimal!r}"
            )

        # Validate tax_rate if provided
        tax_rate = brick.spec.get("tax_rate", 0.0)
        if not isinstance(tax_rate, (int, float, Decimal, str)):
            raise ConfigError(
                f"{brick.id}: tax_rate must be numeric, got {type(tax_rate).__name__}"
            )
        tax_rate_float = float(tax_rate)
        if not 0 <= tax_rate_float <= 1:
            raise ConfigError(
                f"{brick.id}: tax_rate must be in [0, 1], got {tax_rate_float!r}"
            )

        # Store normalized values in spec (as float for numpy compatibility)
        brick.spec["_normalized_amount"] = float(amount_decimal)
        brick.spec["_normalized_tax_rate"] = tax_rate_float

    def simulate(self, brick: FBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate one-time income flow.

        Args:
            brick: The FBrick instance
            ctx: Scenario context

        Returns:
            BrickOutput with cash flow data
        """
        # Extract parameters (use normalized values if available from prepare)
        if "_normalized_amount" in brick.spec:
            amount = brick.spec["_normalized_amount"]
        else:
            amount = float(brick.spec["amount"])

        if "_normalized_tax_rate" in brick.spec:
            tax_rate = brick.spec["_normalized_tax_rate"]
        else:
            tax_rate = float(brick.spec.get("tax_rate", 0.0))

        # Use the brick's start_date for the event date
        if not brick.start_date:
            raise ValueError(
                f"One-time income brick '{brick.id}' must have a start_date"
            )

        event_date = brick.start_date

        # Calculate net amount after tax (all float operations)
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
