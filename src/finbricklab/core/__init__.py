"""
Core module for FinBrickLab.

This module contains the fundamental building blocks for the financial scenario modeling system.
"""

from .bricks import (
    ABrick,
    FBrick,
    FinBrickABC,
    FlowRegistry,
    LBrick,
    ScheduleRegistry,
    TBrick,
    ValuationRegistry,
    wire_strategies,
)
from .context import ScenarioContext
from .errors import ConfigError
from .events import Event
from .interfaces import IFlowStrategy, IScheduleStrategy, IValuationStrategy
from .links import PrincipalLink, StartLink
from .macrobrick import MacroBrick
from .registry import Registry
from .results import (
    BrickOutput,
    NumpyEncoder,
    ScenarioResults,
    aggregate_totals,
    finalize_totals,
)
from .scenario import Scenario, export_ledger_csv, export_run_json, validate_run
from .specs import LMortgageSpec, term_from_amort
from .transfer_visibility import TransferVisibility
from .utils import (
    _apply_window_equity_neutral,
    active_mask,
    month_range,
    resolve_prepayments_to_month_idx,
)
from .validation import DisjointReport, ValidationReport

__all__ = [
    # Errors
    "ConfigError",
    # Links
    "StartLink",
    "PrincipalLink",
    # Specs
    "LMortgageSpec",
    "term_from_amort",
    # Events and Results
    "Event",
    "BrickOutput",
    "ScenarioResults",
    "NumpyEncoder",
    "aggregate_totals",
    "finalize_totals",
    # Context
    "ScenarioContext",
    # Interfaces
    "IValuationStrategy",
    "IScheduleStrategy",
    "IFlowStrategy",
    # Bricks
    "FinBrickABC",
    "ABrick",
    "LBrick",
    "FBrick",
    "TBrick",
    # Registries
    "ValuationRegistry",
    "ScheduleRegistry",
    "FlowRegistry",
    "wire_strategies",
    # Scenario
    "Scenario",
    "validate_run",
    "export_run_json",
    "export_ledger_csv",
    # MacroBrick and Registry
    "MacroBrick",
    "Registry",
    # Validation
    "ValidationReport",
    "DisjointReport",
    # Utils
    "month_range",
    "active_mask",
    "_apply_window_equity_neutral",
    "resolve_prepayments_to_month_idx",
    # Transfer Visibility
    "TransferVisibility",
]
