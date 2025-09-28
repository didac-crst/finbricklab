"""
FinBrickLab Kind Constants

This module provides centralized constants for all brick kind discriminators,
preventing typos and providing a single source of truth for kind strings.
"""

class K:
    """
    Kind constants for all FinBrickLab brick types.
    
    These constants should be used instead of hardcoded strings to prevent
    typos and ensure consistency across the codebase.
    """
    
    # Asset kinds
    A_CASH = "a.cash"
    A_PROPERTY_DISCRETE = "a.property_discrete"
    A_ETF_UNITIZED = "a.etf_unitized"
    
    # Liability kinds
    L_MORT_ANN = "l.mortgage.annuity"
    
    # Flow kinds
    F_TRANSFER_LUMP_SUM = "f.transfer.lumpsum"
    F_INCOME_FIXED = "f.income.fixed"
    F_EXPENSE_FIXED = "f.expense.fixed"
    
    # Validation: ensure all registered kinds are covered
    @classmethod
    def all_kinds(cls) -> list[str]:
        """Return all defined kind constants."""
        return [
            cls.A_CASH,
            cls.A_PROPERTY_DISCRETE, 
            cls.A_ETF_UNITIZED,
            cls.L_MORT_ANN,
            cls.F_TRANSFER_LUMP_SUM,
            cls.F_INCOME_FIXED,
            cls.F_EXPENSE_FIXED,
        ]
