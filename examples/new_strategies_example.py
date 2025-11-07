#!/usr/bin/env python3
"""
New Strategies Example

This example demonstrates the new financial strategies implemented in FinBrickLab:
- CreditLine: Revolving credit with interest accrual and minimum payments
- CreditFixed: Linear amortization with equal principal payments
- LoanBalloon: Balloon loans with interest-only and linear amortization options
- PrivateEquity: Deterministic marking with drift-based calculation
"""

import sys
from datetime import date
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finbricklab import ABrick, FBrick, LBrick, Scenario
from finbricklab.core.kinds import K


def create_credit_line_example():
    """Create a credit line example."""
    print("=== Credit Line Example ===")

    # Create cash account
    cash = ABrick(
        id="checking",
        name="Checking Account",
        kind=K.A_CASH,
        spec={"initial_balance": 5000.0, "interest_pa": 0.02},
    )

    # Create credit line (revolving credit)
    credit_line = LBrick(
        id="credit_card",
        name="Credit Card",
        kind=K.L_CREDIT_LINE,
        spec={
            "credit_limit": 10000.0,  # €10,000 credit limit
            "rate_pa": 0.18,  # 18% APR
            "min_payment": {
                "type": "percent",
                "percent": 0.02,  # 2% minimum payment
                "floor": 25.0,  # €25 minimum
            },
            "billing_day": 15,  # 15th of each month
            "start_date": "2026-01-01",
        },
    )

    # Create income
    income = FBrick(
        id="salary",
        name="Salary",
        kind=K.F_INCOME_RECURRING,
        spec={"amount_monthly": 3000.0},
    )

    # Create expenses
    expenses = FBrick(
        id="expenses",
        name="Monthly Expenses",
        kind=K.F_EXPENSE_RECURRING,
        spec={"amount_monthly": 2500.0},
    )

    scenario = Scenario(
        id="credit_line_demo",
        name="Credit Line Demo",
        bricks=[cash, credit_line, income, expenses],
    )

    # Run scenario
    results = scenario.run(start=date(2026, 1, 1), months=12)

    # Analyze results
    credit_balance = results["outputs"]["credit_card"]["liabilities"]
    cash_balance = results["outputs"]["checking"]["assets"]

    print(f"Initial credit balance: €{credit_balance[0]:,.2f}")
    print(f"Final credit balance: €{credit_balance[-1]:,.2f}")
    print(f"Final cash balance: €{cash_balance[-1]:,.2f}")
    print()


def create_credit_fixed_example():
    """Create a fixed-term credit example."""
    print("=== Fixed-Term Credit Example ===")

    # Create cash account
    cash = ABrick(
        id="checking",
        name="Checking Account",
        kind=K.A_CASH,
        spec={"initial_balance": 20000.0, "interest_pa": 0.02},
    )

    # Create fixed-term credit (personal loan)
    personal_loan = LBrick(
        id="personal_loan",
        name="Personal Loan",
        kind=K.L_CREDIT_FIXED,
        spec={
            "principal": 15000.0,  # €15,000 loan
            "rate_pa": 0.08,  # 8% interest rate
            "term_months": 36,  # 3 years
            "start_date": "2026-01-01",
        },
    )

    # Create income
    income = FBrick(
        id="salary",
        name="Salary",
        kind=K.F_INCOME_RECURRING,
        spec={"amount_monthly": 4000.0},
    )

    scenario = Scenario(
        id="credit_fixed_demo",
        name="Fixed-Term Credit Demo",
        bricks=[cash, personal_loan, income],
    )

    # Run scenario
    results = scenario.run(start=date(2026, 1, 1), months=36)

    # Analyze results
    loan_balance = results["outputs"]["personal_loan"]["liabilities"]
    cash_balance = results["outputs"]["checking"]["assets"]

    print(f"Initial loan balance: €{loan_balance[0]:,.2f}")
    print(f"Final loan balance: €{loan_balance[-1]:,.2f}")
    print(f"Final cash balance: €{cash_balance[-1]:,.2f}")
    print()


def create_balloon_loan_example():
    """Create a balloon loan example."""
    print("=== Balloon Loan Example ===")

    # Create cash account
    cash = ABrick(
        id="checking",
        name="Checking Account",
        kind=K.A_CASH,
        spec={"initial_balance": 100000.0, "interest_pa": 0.02},
    )

    # Create balloon loan (business loan)
    balloon_loan = LBrick(
        id="business_loan",
        name="Business Loan",
        kind=K.L_LOAN_BALLOON,
        spec={
            "principal": 500000.0,  # €500,000 loan
            "rate_pa": 0.06,  # 6% interest rate
            "balloon_after_months": 60,  # Balloon payment after 5 years
            "amortization_rate_pa": 0.06,  # Same as interest rate for interest-only
            "balloon_type": "residual",  # Pay remaining principal
            "start_date": "2026-01-01",
        },
    )

    # Create income
    income = FBrick(
        id="business_income",
        name="Business Income",
        kind=K.F_INCOME_RECURRING,
        spec={"amount_monthly": 15000.0},
    )

    scenario = Scenario(
        id="balloon_loan_demo",
        name="Balloon Loan Demo",
        bricks=[cash, balloon_loan, income],
    )

    # Run scenario
    results = scenario.run(start=date(2026, 1, 1), months=60)

    # Analyze results
    loan_balance = results["outputs"]["business_loan"]["liabilities"]
    cash_balance = results["outputs"]["checking"]["assets"]

    print(f"Initial loan balance: €{loan_balance[0]:,.2f}")
    print(f"Final loan balance: €{loan_balance[-1]:,.2f}")
    print(f"Final cash balance: €{cash_balance[-1]:,.2f}")
    print()


def create_private_equity_example():
    """Create a private equity example."""
    print("=== Private Equity Example ===")

    # Create cash account
    cash = ABrick(
        id="checking",
        name="Checking Account",
        kind=K.A_CASH,
        spec={"initial_balance": 100000.0, "interest_pa": 0.02},
    )

    # Create private equity investment
    pe_investment = ABrick(
        id="pe_fund",
        name="Private Equity Fund",
        kind=K.A_PRIVATE_EQUITY,
        spec={
            "initial_value": 50000.0,  # €50,000 initial investment
            "drift_pa": 0.12,  # 12% annual growth
            "valuation_frequency": "annual",  # Annual valuations
        },
    )

    # Create income
    income = FBrick(
        id="salary",
        name="Salary",
        kind=K.F_INCOME_RECURRING,
        spec={"amount_monthly": 8000.0},
    )

    scenario = Scenario(
        id="pe_demo",
        name="Private Equity Demo",
        bricks=[cash, pe_investment, income],
    )

    # Run scenario
    results = scenario.run(start=date(2026, 1, 1), months=24)

    # Analyze results
    pe_value = results["outputs"]["pe_fund"]["assets"]
    cash_balance = results["outputs"]["checking"]["assets"]

    print(f"Initial PE value: €{pe_value[0]:,.2f}")
    print(f"Final PE value: €{pe_value[-1]:,.2f}")
    print(f"Final cash balance: €{cash_balance[-1]:,.2f}")
    print()


def main():
    """Run all new strategy examples."""
    print("🚀 FinBrickLab New Strategies Demo")
    print("=" * 50)
    print()

    # Run all examples
    create_credit_line_example()
    create_credit_fixed_example()
    create_balloon_loan_example()
    create_private_equity_example()

    print("✅ All new strategy examples completed successfully!")
    print()
    print("📊 Summary of new strategies:")
    print("- CreditLine: Revolving credit with interest accrual")
    print("- CreditFixed: Linear amortization with equal principal payments")
    print("- LoanBalloon: Balloon loans with interest-only periods")
    print("- PrivateEquity: Deterministic marking with drift-based calculation")


if __name__ == "__main__":
    main()
