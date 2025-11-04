"""
One-time expense flow strategy.
"""

from __future__ import annotations

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
        """Validate configuration before simulation."""
        if brick.spec is None:
            raise ConfigError("ExpenseOneTime: spec is required")

        # Required fields
        if "amount" not in brick.spec:
            raise ConfigError("ExpenseOneTime: 'amount' is required")
        if "date" not in brick.spec:
            raise ConfigError("ExpenseOneTime: 'date' (YYYY-MM-DD) is required")

        # Coerce and validate
        try:
            amount = float(brick.spec["amount"])  # arrays are float downstream
        except Exception as e:
            raise ConfigError(f"ExpenseOneTime: invalid amount: {e}") from e
        if amount < 0:
            raise ConfigError("ExpenseOneTime: amount must be >= 0")

        tax_rate = float(brick.spec.get("tax_rate", 0.0))
        if not (0.0 <= tax_rate <= 1.0):
            raise ConfigError("ExpenseOneTime: tax_rate must be in [0,1]")

        # Validate date format
        from datetime import datetime

        try:
            datetime.strptime(str(brick.spec["date"]), "%Y-%m-%d")
        except Exception as e:
            raise ConfigError(
                "ExpenseOneTime: date must be in YYYY-MM-DD format"
            ) from e

    def simulate(self, brick: FBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate one-time expense flow.

        Args:
            brick: The FBrick instance
            ctx: Scenario context

        Returns:
            BrickOutput with cash flow data
        """
        # Extract parameters
        amount = float(brick.spec["amount"])  # ensure float
        date_str = brick.spec["date"]
        tax_deductible = brick.spec.get("tax_deductible", False)
        tax_rate = float(brick.spec.get("tax_rate", 0.0))

        # Parse the date
        from datetime import datetime

        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        # Calculate net amount (with potential tax deduction)
        net_amount = amount * (1 - tax_rate) if tax_deductible else amount

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
