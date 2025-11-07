"""
Brick classes for FinBrickLab financial instruments.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .context import ScenarioContext
from .errors import ConfigError
from .interfaces import (
    IFlowStrategy,
    IScheduleStrategy,
    ITransferStrategy,
    IValuationStrategy,
)
from .results import BrickOutput
from .utils import slugify_name


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
        kind: Dot-separated string discriminator (e.g., 'a.cash', 'l.loan.annuity')
        currency: Currency code for the brick (default: 'EUR')
        spec: Dictionary containing strategy-specific parameters
        links: Dictionary for referencing other bricks (e.g., {'principal': {'from_house': 'house_id'}})
        family: Brick family type ('a' for assets, 'l' for liabilities, 'f' for flows)
        start_date: Optional start date for the brick (default: None = starts at scenario start)

    Note:
        The 'family' attribute is automatically set by subclasses and should not be
        specified manually when creating brick instances.

        The 'start_date' allows bricks to activate at specific times during the simulation,
        enabling scenarios like buying a house in 2028 or starting a new job in 2025.
    """

    name: str
    kind: str  # Dot-separated string discriminator
    currency: str = "EUR"
    spec: dict = None  # Strategy-specific parameters
    links: dict = None  # References to other bricks
    family: str = None  # 'a' | 'l' | 'f' - set automatically in subclasses
    start_date: date | None = None  # When this brick becomes active
    end_date: date | None = None  # When this brick becomes inactive
    duration_m: int | None = None  # Duration in months (alternative to end_date)
    id: str = ""

    def __post_init__(self) -> None:
        """
        Normalize the brick id if it was omitted.

        When an id is not explicitly provided, derive it from the name by lowercasing
        and replacing whitespace with underscores (e.g., "Cash Reserve" -> "cash_reserve").
        """

        if not self.id:
            if not self.name:
                raise ConfigError("FinBrick must define either an id or a name")
            normalized = slugify_name(self.name)
            if not normalized:
                raise ConfigError(
                    f"FinBrick name '{self.name}' cannot be converted into a valid id"
                )
            self.id = normalized

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
        ETF investment: kind='a.security.unitized'
    """

    valuation: IValuationStrategy = None

    def __post_init__(self):
        """Set the family type to 'a' for assets."""
        super().__post_init__()
        self.family = "a"

    def prepare(self, ctx: ScenarioContext) -> None:
        """
        Prepare the asset for simulation.

        Delegates to the associated valuation strategy's prepare method.

        Args:
            ctx: The simulation context containing time index and registry
        """
        if self.valuation is None:
            raise ConfigError(
                f"Asset brick '{self.id}' ({self.kind}) has no valuation strategy configured"
            )
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
        if self.valuation is None:
            raise ConfigError(
                f"Asset brick '{self.id}' ({self.kind}) has no valuation strategy configured"
            )
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
        Mortgage: kind='l.loan.annuity'
        Personal loan: kind='l.loan.personal'
        Credit card: kind='l.credit.card'
    """

    schedule: IScheduleStrategy = None

    def __post_init__(self):
        """Set the family type to 'l' for liabilities."""
        super().__post_init__()
        self.family = "l"

    def prepare(self, ctx: ScenarioContext) -> None:
        """
        Prepare the liability for simulation.

        Delegates to the associated schedule strategy's prepare method.

        Args:
            ctx: The simulation context containing time index and registry
        """
        if self.schedule is None:
            raise ConfigError(
                f"Liability brick '{self.id}' ({self.kind}) has no schedule strategy configured"
            )
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
        if self.schedule is None:
            raise ConfigError(
                f"Liability brick '{self.id}' ({self.kind}) has no schedule strategy configured"
            )
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
        super().__post_init__()
        self.family = "f"

    def prepare(self, ctx: ScenarioContext) -> None:
        """
        Prepare the flow for simulation.

        Delegates to the associated flow strategy's prepare method.

        Args:
            ctx: The simulation context containing time index and registry
        """
        if self.flow is None:
            raise ConfigError(
                f"Flow brick '{self.id}' ({self.kind}) has no flow strategy configured"
            )
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
        if self.flow is None:
            raise ConfigError(
                f"Flow brick '{self.id}' ({self.kind}) has no flow strategy configured"
            )
        return self.flow.simulate(self, ctx)


@dataclass
class TBrick(FinBrickABC):
    """
    Transfer brick for moving money between accounts within the system.

    This class represents internal transfers that move money between
    internal accounts without affecting net worth. The actual behavior
    is determined by the transfer strategy associated with the brick's
    'kind' discriminator.

    Attributes:
        transfer: The transfer strategy object (set automatically by registry)
        transparent: Whether this transfer should be hidden in analysis views by default

    Examples:
        Lump sum transfer: kind='t.transfer.lumpsum'
        Recurring transfer: kind='t.transfer.recurring'
        Scheduled transfer: kind='t.transfer.scheduled'
    """

    transfer: ITransferStrategy = None
    transparent: bool = True  # Default to hidden in analysis views

    def __post_init__(self):
        """Set the family type to 't' for transfers."""
        super().__post_init__()
        self.family = "t"

    def prepare(self, ctx: ScenarioContext) -> None:
        """
        Prepare the transfer for simulation.

        Delegates to the associated transfer strategy's prepare method.

        Args:
            ctx: The simulation context containing time index and registry
        """
        if self.transfer is None:
            raise ConfigError(
                f"Transfer brick '{self.id}' ({self.kind}) has no transfer strategy configured"
            )
        self.transfer.prepare(self, ctx)

    def simulate(self, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the transfer over the time period.

        Delegates to the associated transfer strategy's simulate method.

        Args:
            ctx: The simulation context containing time index and registry

        Returns:
            BrickOutput containing transfer flows and events
        """
        if self.transfer is None:
            raise ConfigError(
                f"Transfer brick '{self.id}' ({self.kind}) has no transfer strategy configured"
            )
        return self.transfer.simulate(self, ctx)


# Global registries mapping kind strings to strategy implementations
ValuationRegistry: dict[str, IValuationStrategy] = {}
ScheduleRegistry: dict[str, IScheduleStrategy] = {}
FlowRegistry: dict[str, IFlowStrategy] = {}


def wire_strategies(bricks: list[FinBrickABC]) -> None:
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
    for brick in bricks:
        if brick.family == "a":
            if brick.kind not in ValuationRegistry:
                raise ConfigError(f"Unknown valuation strategy: {brick.kind}")
            brick.valuation = ValuationRegistry[brick.kind]

        elif brick.family == "l":
            if brick.kind not in ScheduleRegistry:
                raise ConfigError(f"Unknown schedule strategy: {brick.kind}")
            brick.schedule = ScheduleRegistry[brick.kind]

        elif brick.family == "f":
            if brick.kind not in FlowRegistry:
                raise ConfigError(f"Unknown flow strategy: {brick.kind}")
            brick.flow = FlowRegistry[brick.kind]

        elif brick.family == "t":
            if brick.kind not in FlowRegistry:
                raise ConfigError(f"Unknown transfer strategy: {brick.kind}")
            brick.transfer = FlowRegistry[brick.kind]

        else:
            raise ConfigError(f"Unknown brick family: {brick.family}")
