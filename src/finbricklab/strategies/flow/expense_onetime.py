"""
One-time expense flow strategy.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np

from finbricklab.core.bricks import FBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.errors import ConfigError
from finbricklab.core.interfaces import IFlowStrategy
from finbricklab.core.results import BrickOutput


class FlowExpenseOneTime(IFlowStrategy):
    """
    One-time expense flow strategy (kind: 'f.expense.onetime').

    This strategy models a single one-time expense event.
    Commonly used for major purchases, emergency expenses,
    one-time fees, or other irregular cash outflows.

    Required Parameters:
        - amount: The one-time expense amount
        - date: The date when the expense occurs (YYYY-MM-DD format)

    Optional Parameters:
        - tax_deductible: Whether this expense is tax deductible (default: False)
        - tax_rate: Tax rate for deduction (default: 0.0)
    """

    def prepare(self, brick: FBrick, ctx: ScenarioContext) -> None:
        """
        Prepare the one-time expense strategy.

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

        if "date" not in brick.spec:
            raise ConfigError(f"{brick.id}: Missing required parameter 'date'")

        # Coerce amount to Decimal
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
        tax_deductible = brick.spec.get("tax_deductible", False)
        if tax_deductible:
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

        # Store normalized values in spec
        brick.spec["_normalized_amount"] = float(amount_decimal)

    def simulate(self, brick: FBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate one-time expense flow.

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

        date_str = brick.spec["date"]
        tax_deductible = brick.spec.get("tax_deductible", False)
        tax_rate = float(brick.spec.get("tax_rate", 0.0))

        # Parse the date
        from datetime import datetime

        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        # Calculate net amount (with potential tax deduction)
        if tax_deductible:
            net_amount = amount * (1 - tax_rate)
        else:
            net_amount = amount

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
                cash_out[month_idx] = net_amount
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
