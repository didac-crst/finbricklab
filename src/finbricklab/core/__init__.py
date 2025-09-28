"""
Core module for FinBrickLab.

This module contains the fundamental building blocks for the financial scenario modeling system.
"""

from .errors import ConfigError
from .links import StartLink, PrincipalLink
from .specs import LMortgageSpec, term_from_amort
from .events import Event
from .results import BrickOutput, ScenarioResults, NumpyEncoder, aggregate_totals, finalize_totals
from .context import ScenarioContext
from .interfaces import IValuationStrategy, IScheduleStrategy, IFlowStrategy
from .bricks import FinBrickABC, ABrick, LBrick, FBrick, ValuationRegistry, ScheduleRegistry, FlowRegistry, wire_strategies
from .scenario import Scenario, validate_run, export_run_json, export_ledger_csv
from .utils import month_range, active_mask, _apply_window_equity_neutral, resolve_prepayments_to_month_idx

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
    
    # Utils
    "month_range",
    "active_mask",
    "_apply_window_equity_neutral",
    "resolve_prepayments_to_month_idx",
]
