"""
Strategy registry setup for FinBrickLab.
"""

from finbricklab.core.bricks import ValuationRegistry, ScheduleRegistry, FlowRegistry
from finbricklab.core.kinds import K
from .valuation import ValuationCash, ValuationPropertyDiscrete, ValuationETFUnitized
from .schedule import ScheduleMortgageAnnuity
from .flow import FlowTransferLumpSum, FlowIncomeFixed, FlowExpenseFixed


def register_defaults():
    """
    Register all default strategy implementations in the global registries.
    
    This function populates the global strategy registries with the default
    implementations provided by FinBrickLab. These strategies are automatically
    available for use by bricks with matching kind discriminators.
    
    Registered Strategies:
        Assets:
            - 'a.cash': Cash account with interest
            - 'a.property_discrete': Real estate with appreciation
            - 'a.etf_unitized': ETF investment with unitized pricing
            
        Liabilities:
            - 'l.mortgage.annuity': Fixed-rate mortgage with annuity payments
            
        Flows:
            - 'f.transfer.lumpsum': One-time lump sum transfer
            - 'f.income.fixed': Fixed recurring income
            - 'f.expense.fixed': Fixed recurring expense
            
    Note:
        This function is automatically called when the module is imported.
        Additional strategies can be registered by calling the registry
        dictionaries directly.
    """
    # Register asset valuation strategies
    ValuationRegistry[K.A_CASH]              = ValuationCash()
    ValuationRegistry[K.A_PROPERTY_DISCRETE] = ValuationPropertyDiscrete()
    ValuationRegistry[K.A_ETF_UNITIZED]      = ValuationETFUnitized()
    
    # Register liability schedule strategies
    ScheduleRegistry[K.L_MORT_ANN]           = ScheduleMortgageAnnuity()
    
    # Register cash flow strategies
    FlowRegistry[K.F_TRANSFER_LUMP_SUM]      = FlowTransferLumpSum()
    FlowRegistry[K.F_INCOME_FIXED]           = FlowIncomeFixed()
    FlowRegistry[K.F_EXPENSE_FIXED]          = FlowExpenseFixed()
