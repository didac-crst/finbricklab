"""
Lump sum transfer flow strategy.
"""

from __future__ import annotations
import numpy as np
from finbricklab.core.interfaces import IFlowStrategy
from finbricklab.core.bricks import FBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.results import BrickOutput
from finbricklab.core.events import Event


class FlowTransferLumpSum(IFlowStrategy):
    """
    Lump sum transfer flow strategy (kind: 'f.transfer.lumpsum').
    
    This strategy models a one-time cash transfer that occurs at t=0.
    Commonly used for initial capital injections, windfalls, or large
    one-time payments.
    
    Required Parameters:
        - amount: The lump sum amount to transfer at t=0
        
    Note:
        This strategy generates a single cash inflow at the beginning
        of the simulation period.
    """
    
    def prepare(self, brick: FBrick, ctx: ScenarioContext) -> None:
        """
        Prepare the lump sum transfer strategy.
        
        Validates that the amount parameter is present.
        
        Args:
            brick: The transfer flow brick
            ctx: The simulation context
            
        Raises:
            AssertionError: If amount parameter is missing
        """
        assert "amount" in brick.spec, "Missing required parameter: amount"

    def simulate(self, brick: FBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the lump sum transfer.
        
        Generates a single cash inflow at t=0 with the specified amount.
        
        Args:
            brick: The transfer flow brick
            ctx: The simulation context
            
        Returns:
            BrickOutput with single cash inflow at t=0 and transfer event
        """
        T = len(ctx.t_index)
        cash_in = np.zeros(T)
        cash_in[0] = float(brick.spec["amount"])
        
        return BrickOutput(
            cash_in=cash_in, 
            cash_out=np.zeros(T),
            asset_value=np.zeros(T), 
            debt_balance=np.zeros(T), 
            events=[Event(ctx.t_index[0], "transfer", f"Lump sum transfer: €{cash_in[0]:,.2f}", 
                          {"amount": cash_in[0]})]
        )
