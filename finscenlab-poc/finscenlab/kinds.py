"""
FinScenLab Kind Constants

This module provides centralized constants for all brick kind discriminators,
preventing typos and providing a single source of truth for kind strings.
"""

class K:
    """
    Kind constants for all FinScenLab brick types.
    
    These constants should be used instead of hardcoded strings to prevent
    typos and ensure consistency across the codebase.
    """
    
    # Asset kinds
    A_CASH = "a.cash"
    A_PROPERTY = "a.property"
    A_INV_ETF = "a.invest.etf"
    
    # Liability kinds
    L_MORT_ANN = "l.mortgage.annuity"
    
    # Flow kinds
    F_TRANSFER = "f.transfer.lumpsum"
    F_INCOME = "f.income.salary"
    F_EXP_LIVING = "f.expense.living"
    
    # Validation: ensure all registered kinds are covered
    @classmethod
    def all_kinds(cls) -> list[str]:
        """Return all defined kind constants."""
        return [
            cls.A_CASH,
            cls.A_PROPERTY, 
            cls.A_INV_ETF,
            cls.L_MORT_ANN,
            cls.F_TRANSFER,
            cls.F_INCOME,
            cls.F_EXP_LIVING,
        ]
