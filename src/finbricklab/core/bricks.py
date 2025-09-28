"""
Brick classes for FinBrickLab financial instruments.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import date

from .interfaces import IValuationStrategy, IScheduleStrategy, IFlowStrategy
from .context import ScenarioContext
from .results import BrickOutput


@dataclass
class FinBrickABC:
    """
    Abstract base class for all financial instruments in FinBrickLab.
    
    This class defines the common interface and structure for all financial bricks.
    It serves as the foundation for the strategy pattern implementation, where
    the actual behavior is determined by the 'kind' discriminator and associated
    strategy objects.
    
    Attributes:
        id: Unique identifier for the brick within a scenario
        name: Human-readable name for the brick
        kind: Dot-separated string discriminator (e.g., 'a.cash', 'l.mortgage.annuity')
        currency: Currency code for the brick (default: 'EUR')
        spec: Dictionary containing strategy-specific parameters
        links: Dictionary for referencing other bricks (e.g., {'auto_principal_from': 'house_id'})
        family: Brick family type ('a' for assets, 'l' for liabilities, 'f' for flows)
        start_date: Optional start date for the brick (default: None = starts at scenario start)
        
    Note:
        The 'family' attribute is automatically set by subclasses and should not be
        specified manually when creating brick instances.
        
        The 'start_date' allows bricks to activate at specific times during the simulation,
        enabling scenarios like buying a house in 2028 or starting a new job in 2025.
    """
    id: str
    name: str
    kind: str             # Dot-separated string discriminator
    currency: str = "EUR"
    spec: dict = None     # Strategy-specific parameters
    links: dict = None    # References to other bricks
    family: str = None    # 'a' | 'l' | 'f' - set automatically in subclasses
    start_date: Optional[date] = None  # When this brick becomes active
    end_date: Optional[date] = None    # When this brick becomes inactive
    duration_m: Optional[int] = None   # Duration in months (alternative to end_date)

    def prepare(self, ctx: ScenarioContext) -> None:
        """
        Prepare the brick for simulation.
        
        This method is called once before simulation begins to validate parameters
        and perform any necessary setup. The actual implementation is delegated
        to the appropriate strategy object.
        
        Args:
            ctx: The simulation context containing time index and registry
            
        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError
    
    def simulate(self, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the brick over the entire time period.
        
        This method generates the complete simulation results for the brick.
        The actual implementation is delegated to the appropriate strategy object.
        
        Args:
            ctx: The simulation context containing time index and registry
            
        Returns:
            BrickOutput containing cash flows, values, and events
            
        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError


@dataclass
class ABrick(FinBrickABC):
    """
    Asset brick for representing financial assets.
    
    This class represents assets such as cash accounts, real estate, investments,
    vehicles, and other valuable items. The actual behavior is determined by
    the valuation strategy associated with the brick's 'kind' discriminator.
    
    Attributes:
        valuation: The valuation strategy object (set automatically by registry)
        
    Examples:
        Cash account: kind='a.cash'
        Real estate: kind='a.property'  
        ETF investment: kind='a.invest.etf'
    """
    valuation: IValuationStrategy = None
    
    def __post_init__(self):
        """Set the family type to 'a' for assets."""
        self.family = 'a'
    
    def prepare(self, ctx: ScenarioContext) -> None:
        """
        Prepare the asset for simulation.
        
        Delegates to the associated valuation strategy's prepare method.
        
        Args:
            ctx: The simulation context containing time index and registry
        """
        self.valuation.prepare(self, ctx)
    
    def simulate(self, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the asset over the time period.
        
        Delegates to the associated valuation strategy's simulate method.
        
        Args:
            ctx: The simulation context containing time index and registry
            
        Returns:
            BrickOutput containing asset values, cash flows, and events
        """
        return self.valuation.simulate(self, ctx)


@dataclass
class LBrick(FinBrickABC):
    """
    Liability brick for representing financial debts and obligations.
    
    This class represents liabilities such as mortgages, loans, credit cards,
    and other debt instruments. The actual behavior is determined by
    the schedule strategy associated with the brick's 'kind' discriminator.
    
    Attributes:
        schedule: The schedule strategy object (set automatically by registry)
        
    Examples:
        Mortgage: kind='l.mortgage.annuity'
        Personal loan: kind='l.loan.personal'
        Credit card: kind='l.credit.card'
    """
    schedule: IScheduleStrategy = None
    
    def __post_init__(self):
        """Set the family type to 'l' for liabilities."""
        self.family = 'l'
    
    def prepare(self, ctx: ScenarioContext) -> None:
        """
        Prepare the liability for simulation.
        
        Delegates to the associated schedule strategy's prepare method.
        
        Args:
            ctx: The simulation context containing time index and registry
        """
        self.schedule.prepare(self, ctx)
    
    def simulate(self, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the liability over the time period.
        
        Delegates to the associated schedule strategy's simulate method.
        
        Args:
            ctx: The simulation context containing time index and registry
            
        Returns:
            BrickOutput containing debt balances, payment flows, and events
        """
        return self.schedule.simulate(self, ctx)


@dataclass
class FBrick(FinBrickABC):
    """
    Flow brick for representing cash flow events.
    
    This class represents cash flow events such as income, expenses, transfers,
    and other monetary flows. The actual behavior is determined by
    the flow strategy associated with the brick's 'kind' discriminator.
    
    Attributes:
        flow: The flow strategy object (set automatically by registry)
        
    Examples:
        Salary income: kind='f.income.salary'
        Living expenses: kind='f.expense.living'
        Lump sum transfer: kind='f.transfer.lumpsum'
    """
    flow: IFlowStrategy = None
    
    def __post_init__(self):
        """Set the family type to 'f' for flows."""
        self.family = 'f'
    
    def prepare(self, ctx: ScenarioContext) -> None:
        """
        Prepare the flow for simulation.
        
        Delegates to the associated flow strategy's prepare method.
        
        Args:
            ctx: The simulation context containing time index and registry
        """
        self.flow.prepare(self, ctx)
    
    def simulate(self, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the flow over the time period.
        
        Delegates to the associated flow strategy's simulate method.
        
        Args:
            ctx: The simulation context containing time index and registry
            
        Returns:
            BrickOutput containing cash flows and events
        """
        return self.flow.simulate(self, ctx)


# Global registries mapping kind strings to strategy implementations
ValuationRegistry: Dict[str, IValuationStrategy] = {}
ScheduleRegistry:  Dict[str, IScheduleStrategy]  = {}
FlowRegistry:      Dict[str, IFlowStrategy]      = {}


def wire_strategies(bricks: List[FinBrickABC]) -> None:
    """
    Wire strategy objects to bricks based on their kind discriminators.
    
    This function automatically assigns the appropriate strategy objects to each brick
    based on their 'kind' attribute and the global registries. It must be called
    before running any scenario to ensure all bricks have their strategies properly
    configured.
    
    Args:
        bricks: List of bricks to wire with strategies
        
    Raises:
        ConfigError: If a brick's kind is not found in any registry
    """
    from .errors import ConfigError
    
    for brick in bricks:
        if brick.family == 'a':
            if brick.kind not in ValuationRegistry:
                raise ConfigError(f"Unknown valuation strategy: {brick.kind}")
            brick.valuation = ValuationRegistry[brick.kind]
            
        elif brick.family == 'l':
            if brick.kind not in ScheduleRegistry:
                raise ConfigError(f"Unknown schedule strategy: {brick.kind}")
            brick.schedule = ScheduleRegistry[brick.kind]
            
        elif brick.family == 'f':
            if brick.kind not in FlowRegistry:
                raise ConfigError(f"Unknown flow strategy: {brick.kind}")
            brick.flow = FlowRegistry[brick.kind]
            
        else:
            raise ConfigError(f"Unknown brick family: {brick.family}")
