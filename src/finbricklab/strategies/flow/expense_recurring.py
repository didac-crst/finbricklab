"""
Fixed monthly expense flow strategy.
"""

from __future__ import annotations

import numpy as np

from finbricklab.core.bricks import FBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.interfaces import IFlowStrategy
from finbricklab.core.results import BrickOutput


class FlowExpenseRecurring(IFlowStrategy):
    """
    Fixed monthly expense flow strategy (kind: 'f.expense.recurring').

    This strategy models a regular monthly expense with a constant amount.
    Commonly used for living expenses, insurance, subscriptions, or other
    regular recurring costs.

    Required Parameters:
        - amount_monthly: The monthly expense amount

    Note:
        This strategy generates the same cash outflow every month throughout
        the simulation period.
    """

    def prepare(self, brick: FBrick, ctx: ScenarioContext) -> None:
        """
        Prepare the fixed expense strategy.

        Validates that the amount_monthly parameter is present.

        Args:
            brick: The expense flow brick
            ctx: The simulation context

        Raises:
            AssertionError: If amount_monthly parameter is missing
        """
        assert (
            "amount_monthly" in brick.spec
        ), "Missing required parameter: amount_monthly"

    def simulate(self, brick: FBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the fixed monthly expense.

        Generates a constant monthly cash outflow throughout the simulation period.

        Args:
            brick: The expense flow brick
            ctx: The simulation context

        Returns:
            BrickOutput with constant monthly cash outflows and no events
        """
        T = len(ctx.t_index)
        cash_out = np.full(T, float(brick.spec["amount_monthly"]))

        return BrickOutput(
            cash_in=np.zeros(T),
            cash_out=cash_out,
            assets=np.zeros(T),
            liabilities=np.zeros(T),
            events=[],  # No events for regular expense flows
        )
