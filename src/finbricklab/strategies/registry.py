"""
Strategy registry setup for FinBrickLab.
"""

from finbricklab.core.bricks import FlowRegistry, ScheduleRegistry, ValuationRegistry
from finbricklab.core.kinds import K

from .flow import (
    FlowExpenseFixed as FlowExpenseRecurring,
)
from .flow import (
    FlowIncomeFixed as FlowIncomeRecurring,
)
from .schedule import ScheduleMortgageAnnuity as ScheduleLoanAnnuity
from .valuation import (
    ValuationCash,
)
from .valuation import (
    ValuationETFUnitized as ValuationSecurityUnitized,
)
from .valuation import (
    ValuationPropertyDiscrete as ValuationProperty,
)


def register_defaults():
    """
    Register all default strategy implementations in the global registries.

    This function populates the global strategy registries with the default
    implementations provided by FinBrickLab. These strategies are automatically
    available for use by bricks with matching kind discriminators.

    Registered Strategies:
        Assets:
            - 'a.cash': Cash account with interest
            - 'a.property': Real estate with appreciation
            - 'a.security.unitized': ETF investment with unitized pricing

        Liabilities:
            - 'l.loan.annuity': Fixed-rate mortgage with annuity payments

        Flows:
            - 'f.income.recurring': Recurring income
            - 'f.expense.recurring': Recurring expense

    Note:
        This function is automatically called when the module is imported.
        Additional strategies can be registered by calling the registry
        dictionaries directly.
    """
    # Register asset valuation strategies
    ValuationRegistry[K.A_CASH] = ValuationCash()
    ValuationRegistry[K.A_PROPERTY] = ValuationProperty()
    ValuationRegistry[K.A_SECURITY_UNITIZED] = ValuationSecurityUnitized()

    # Register liability schedule strategies
    ScheduleRegistry[K.L_LOAN_ANNUITY] = ScheduleLoanAnnuity()

    # Register cash flow strategies
    FlowRegistry[K.F_INCOME_RECURRING] = FlowIncomeRecurring()
    FlowRegistry[K.F_EXPENSE_RECURRING] = FlowExpenseRecurring()
