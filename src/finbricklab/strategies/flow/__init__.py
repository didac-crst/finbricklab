"""
Flow strategies for cash flow bricks.
"""

from .expense import FlowExpenseFixed
from .income import FlowIncomeFixed

__all__ = [
    "FlowIncomeFixed",
    "FlowExpenseFixed",
]
