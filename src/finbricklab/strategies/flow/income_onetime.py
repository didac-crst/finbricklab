"""
One-time income flow strategy.
"""

from __future__ import annotations

import numpy as np

from finbricklab.core.bricks import FBrick
from finbricklab.core.context import ScenarioContext
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
        - date: The date when the income occurs (YYYY-MM-DD format)

    Optional Parameters:
        - tax_rate: Tax rate on this income (default: 0.0)
    """

    def simulate(
        self, brick: FBrick, ctx: ScenarioContext, months: int
    ) -> BrickOutput:
        """
        Simulate one-time income flow.

        Args:
            brick: The FBrick instance
            ctx: Scenario context
            months: Number of months to simulate

        Returns:
            BrickOutput with cash flow data
        """
        # Extract parameters
        amount = brick.spec["amount"]
        date_str = brick.spec["date"]
        tax_rate = brick.spec.get("tax_rate", 0.0)
        
        # Parse the date
        from datetime import datetime
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # Calculate net amount after tax
        net_amount = amount * (1 - tax_rate)
        
        # Initialize arrays
        cash_in = np.zeros(months, dtype=float)
        cash_out = np.zeros(months, dtype=float)
        
        # Find the month when this event occurs
        start_date = ctx.start_date
        for month_idx in range(months):
            current_date = start_date.replace(day=1) + np.timedelta64(month_idx, 'M')
            current_date = current_date.astype(datetime).date()
            
            # Check if this is the month of the event
            if (current_date.year == event_date.year and 
                current_date.month == event_date.month):
                cash_in[month_idx] = net_amount
                break
        
        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            asset_value=np.zeros(months, dtype=float),
            liability_value=np.zeros(months, dtype=float),
            non_cash=np.zeros(months, dtype=float),
            equity=np.zeros(months, dtype=float),
            cash=np.zeros(months, dtype=float),
        )
