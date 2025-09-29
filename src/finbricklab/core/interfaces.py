"""
Strategy interface protocols for FinBrickLab.
Defines the contracts that all strategies must satisfy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .context import ScenarioContext
from .results import BrickOutput

if TYPE_CHECKING:
    # Only imported for type checking to avoid runtime cycles
    from .bricks import ABrick, FBrick, LBrick


@runtime_checkable
class IValuationStrategy(Protocol):
    """
    Contract for ASSET valuation strategies (family='a').
    Responsibilities: produce asset values over time and any internal cash flows.
    """

    def prepare(self, brick: ABrick, ctx: ScenarioContext) -> None:
        """
        Validate inputs, compute derived params, and initialize any internal state.
        Called exactly once before simulation.
        """
        ...

    def simulate(self, brick: ABrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Run the full-period simulation for this asset brick.

        Returns:
            BrickOutput with fields:
              - cash_in:    np.ndarray[T]
              - cash_out:   np.ndarray[T]
              - asset_value: np.ndarray[T]
              - debt_balance: np.ndarray[T] (usually zeros for assets)
              - events:     list[Event]
        """
        ...


@runtime_checkable
class IScheduleStrategy(Protocol):
    """
    Contract for LIABILITY schedule strategies (family='l').
    Responsibilities: produce debt balances and payment schedules over time.
    """

    def prepare(self, brick: LBrick, ctx: ScenarioContext) -> None:
        """Validate inputs and initialize internal state prior to simulate()."""
        ...

    def simulate(self, brick: LBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Run the full-period schedule simulation.

        Returns:
            BrickOutput (same schema). For liabilities, debt_balance is populated;
            asset_value is typically zeros.
        """
        ...


@runtime_checkable
class IFlowStrategy(Protocol):
    """
    Contract for CASH FLOW strategies (family='f').
    Responsibilities: generate external cash inflows/outflows over time.
    """

    def prepare(self, brick: FBrick, ctx: ScenarioContext) -> None:
        """Validate inputs and initialize internal state prior to simulate()."""
        ...

    def simulate(self, brick: FBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Run the full-period flow simulation.

        Returns:
            BrickOutput (same schema). For pure flows, asset_value/debt_balance are zeros.
        """
        ...


__all__ = ["IValuationStrategy", "IScheduleStrategy", "IFlowStrategy"]
