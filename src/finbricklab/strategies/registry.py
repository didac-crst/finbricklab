"""
Strategy registry setup for FinBrickLab.
"""

from finbricklab.core.bricks import FlowRegistry, ScheduleRegistry, ValuationRegistry
from finbricklab.core.kinds import K

from .flow.expense_onetime import FlowExpenseOneTime
from .flow.expense_recurring import FlowExpenseRecurring
from .flow.income_onetime import FlowIncomeOneTime

# Flow strategies
from .flow.income_recurring import FlowIncomeRecurring
from .schedule.credit_fixed import ScheduleCreditFixed
from .schedule.credit_line import ScheduleCreditLine

# Schedule strategies
from .schedule.loan_annuity import ScheduleLoanAnnuity
from .schedule.loan_balloon import ScheduleLoanBalloon
from .transfer.lumpsum import TransferLumpSum

# Transfer strategies
from .transfer.recurring import TransferRecurring
from .transfer.scheduled import TransferScheduled

# Valuation strategies
from .valuation.cash import ValuationCash
from .valuation.private_equity import ValuationPrivateEquity
from .valuation.property import ValuationProperty
from .valuation.security_unitized import ValuationSecurityUnitized


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
    ValuationRegistry[K.A_PRIVATE_EQUITY] = ValuationPrivateEquity()

    # Register liability schedule strategies
    ScheduleRegistry[K.L_LOAN_ANNUITY] = ScheduleLoanAnnuity()
    ScheduleRegistry[K.L_CREDIT_LINE] = ScheduleCreditLine()
    ScheduleRegistry[K.L_CREDIT_FIXED] = ScheduleCreditFixed()
    ScheduleRegistry[K.L_LOAN_BALLOON] = ScheduleLoanBalloon()

    # Register cash flow strategies
    FlowRegistry[K.F_INCOME_RECURRING] = FlowIncomeRecurring()
    FlowRegistry[K.F_EXPENSE_RECURRING] = FlowExpenseRecurring()
    FlowRegistry[K.F_INCOME_ONE_TIME] = FlowIncomeOneTime()
    FlowRegistry[K.F_EXPENSE_ONE_TIME] = FlowExpenseOneTime()

    # Register transfer strategies
    FlowRegistry[K.T_TRANSFER_RECURRING] = TransferRecurring()
    FlowRegistry[K.T_TRANSFER_LUMP_SUM] = TransferLumpSum()
    FlowRegistry[K.T_TRANSFER_SCHEDULED] = TransferScheduled()
