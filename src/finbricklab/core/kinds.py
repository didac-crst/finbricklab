"""
FinBrickLab Kind Constants (behavior-centric, extensible).
"""


class K:
    # === Assets (value-producing or appreciating) ===
    A_CASH = "a.cash"
    A_SECURITY_UNITIZED = (
        "a.security.unitized"  # ETFs, stocks, bonds, REITs (unitized positions)
    )
    A_PROPERTY = "a.property"  # Real estate & discrete illiquid assets
    A_PRIVATE_EQUITY = "a.private_equity"  # (placeholder for later)

    # === Liabilities (obligations & amortization) ===
    L_LOAN_ANNUITY = "l.loan.annuity"  # Mortgages, car loans — fixed annuity
    L_LOAN_BALLOON = "l.loan.balloon"  # Balloon structures (future)
    L_CREDIT_LINE = "l.credit.line"  # Revolving credit, HELOCs
    L_CREDIT_FIXED = "l.credit.fixed"  # Fixed-term credit (non-annuity)

    # === External flows (in/out from the world) ===
    F_INCOME_RECURRING = "f.income.recurring"  # Salary, recurring dividends, rent-in
    F_INCOME_ONE_TIME = "f.income.onetime"  # Bonus, inheritance
    F_EXPENSE_RECURRING = "f.expense.recurring"  # Rent, utilities, subscriptions
    F_EXPENSE_ONE_TIME = "f.expense.onetime"  # One-offs

    # === Internal transfers (between your accounts) ===
    T_TRANSFER_RECURRING = "t.transfer.recurring"
    T_TRANSFER_LUMP_SUM = "t.transfer.lumpsum"
    T_TRANSFER_SCHEDULED = "t.transfer.scheduled"

    @classmethod
    def all_kinds(cls) -> list[str]:
        """Enumerate all known kinds (for validation and docs)."""
        return [
            # assets
            cls.A_CASH,
            cls.A_SECURITY_UNITIZED,
            cls.A_PROPERTY,
            cls.A_PRIVATE_EQUITY,
            # liabilities
            cls.L_LOAN_ANNUITY,
            cls.L_LOAN_BALLOON,
            cls.L_CREDIT_LINE,
            cls.L_CREDIT_FIXED,
            # flows
            cls.F_INCOME_RECURRING,
            cls.F_INCOME_ONE_TIME,
            cls.F_EXPENSE_RECURRING,
            cls.F_EXPENSE_ONE_TIME,
            # transfers
            cls.T_TRANSFER_RECURRING,
            cls.T_TRANSFER_LUMP_SUM,
            cls.T_TRANSFER_SCHEDULED,
        ]
