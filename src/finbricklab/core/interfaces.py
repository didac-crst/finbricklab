"""
Strategy interface protocols for FinBrickLab.
"""

from __future__ import annotations
from typing import Protocol
from .context import ScenarioContext
from .results import BrickOutput


class IValuationStrategy(Protocol):
    """
    Protocol for asset valuation strategies.
    
    This protocol defines the interface that all asset valuation strategies must implement.
    Asset strategies handle the valuation and cash flow generation for assets like cash,
    property, investments, etc.
    
    Methods:
        prepare: Initialize the strategy with brick parameters and context
        simulate: Generate the simulation results for the asset
    """
    
    def prepare(self, brick: "ABrick", ctx: ScenarioContext) -> None:
        """
        Prepare the strategy for simulation.
        
        This method is called once before simulation begins to validate parameters,
        perform any necessary calculations, and set up the strategy state.
        
        Args:
            brick: The asset brick being simulated
            ctx: The simulation context containing time index and registry
        """
        ...
    
    def simulate(self, brick: "ABrick", ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the asset over the entire time period.
        
        This method generates the complete simulation results for the asset,
        including cash flows, asset values, and any relevant events.
        
        Args:
            brick: The asset brick being simulated
            ctx: The simulation context containing time index and registry
            
        Returns:
            BrickOutput containing cash flows, asset values, and events
        """
        ...


class IScheduleStrategy(Protocol):
    """
    Protocol for liability scheduling strategies.
    
    This protocol defines the interface that all liability scheduling strategies must implement.
    Liability strategies handle the payment schedules and balance tracking for debts like
    mortgages, loans, credit cards, etc.
    
    Methods:
        prepare: Initialize the strategy with brick parameters and context
        simulate: Generate the simulation results for the liability
    """
    
    def prepare(self, brick: "LBrick", ctx: ScenarioContext) -> None:
        """
        Prepare the strategy for simulation.
        
        This method is called once before simulation begins to validate parameters,
        perform any necessary calculations, and set up the strategy state.
        
        Args:
            brick: The liability brick being simulated
            ctx: The simulation context containing time index and registry
        """
        ...
    
    def simulate(self, brick: "LBrick", ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the liability over the entire time period.
        
        This method generates the complete simulation results for the liability,
        including payment schedules, debt balances, and any relevant events.
        
        Args:
            brick: The liability brick being simulated
            ctx: The simulation context containing time index and registry
            
        Returns:
            BrickOutput containing cash flows, debt balances, and events
        """
        ...


class IFlowStrategy(Protocol):
    """
    Protocol for cash flow strategies.
    
    This protocol defines the interface that all cash flow strategies must implement.
    Flow strategies handle the generation of cash flows for income, expenses,
    transfers, and other cash flow events.
    
    Methods:
        prepare: Initialize the strategy with brick parameters and context
        simulate: Generate the simulation results for the flow
    """
    
    def prepare(self, brick: "FBrick", ctx: ScenarioContext) -> None:
        """
        Prepare the strategy for simulation.
        
        This method is called once before simulation begins to validate parameters,
        perform any necessary calculations, and set up the strategy state.
        
        Args:
            brick: The flow brick being simulated
            ctx: The simulation context containing time index and registry
        """
        ...
    
    def simulate(self, brick: "FBrick", ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the flow over the entire time period.
        
        This method generates the complete simulation results for the flow,
        including cash inflows/outflows and any relevant events.
        
        Args:
            brick: The flow brick being simulated
            ctx: The simulation context containing time index and registry
            
        Returns:
            BrickOutput containing cash flows and events
        """
        ...
