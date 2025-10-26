"""
Strategy implementations for FinBrickLab.

This module contains all the concrete strategy implementations for the FinBrickLab system.
Strategies implement the actual behavior for different types of financial instruments
based on their 'kind' discriminator.

Strategy Categories:
- Valuation Strategies: Handle asset valuation and cash flow generation
- Schedule Strategies: Handle liability payment schedules and balance tracking
- Flow Strategies: Handle cash flow events like income, expenses, and transfers

Registry System:
The module automatically registers all default strategies in the global registries,
making them available for use by bricks with matching kind discriminators.
"""

from .flow import (
    FlowExpenseOneTime,
    FlowExpenseRecurring,
    FlowIncomeOneTime,
    FlowIncomeRecurring,
)
from .registry import register_defaults
from .schedule import (
    ScheduleLoanAnnuity,
)
from .valuation import (
    ValuationCash,
    ValuationProperty,
    ValuationSecurityUnitized,
)

# Register all default strategies when module is imported
register_defaults()

__all__ = [
    # Valuation strategies
    "ValuationCash",
    "ValuationProperty",
    "ValuationSecurityUnitized",
    # Schedule strategies
    "ScheduleLoanAnnuity",
    # Flow strategies
    "FlowIncomeRecurring",
    "FlowExpenseRecurring",
    "FlowIncomeOneTime",
    "FlowExpenseOneTime",
    # Registry
    "register_defaults",
]
