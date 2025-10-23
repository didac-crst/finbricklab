"""
Example demonstrating the new filtered results functionality.

This example shows how to:
1. Create an entity with multiple bricks and MacroBricks
2. Run a scenario
3. Filter results to show only specific bricks and/or MacroBricks
4. Access filtered data with the same API as full results
"""

from datetime import date

from finbricklab.core.entity import Entity
from finbricklab.core.kinds import K


def main():
    """Demonstrate filtered results functionality."""
    print("=== FinBrickLab Filtered Results Example ===\n")

    # Create entity
    e = Entity(id="demo_entity", name="Demo Entity")

    # Create bricks
    e.new_ABrick("cash", "Cash Account", K.A_CASH, {"initial_balance": 50000.0})
    e.new_ABrick(
        "etf",
        "ETF Investment",
        K.A_SECURITY_UNITIZED,
        {
            "initial_units": 200.0,
            "price_series": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
        },
    )
    e.new_ABrick(
        "property",
        "Real Estate",
        K.A_PROPERTY,
        {"initial_value": 500000.0, "appreciation_pa": 0.03, "fees_pct": 0.05},
    )
    e.new_LBrick(
        "mortgage",
        "Mortgage",
        K.L_LOAN_ANNUITY,
        {"rate_pa": 0.034, "term_months": 300, "principal": 400000.0},
    )
    e.new_FBrick(
        "salary",
        "Salary",
        K.F_INCOME_RECURRING,
        {"amount_monthly": 8000.0}
        # No routing needed - Journal system handles automatically
    )
    e.new_FBrick(
        "expenses",
        "Monthly Expenses",
        K.F_EXPENSE_RECURRING,
        {"amount_monthly": 3000.0}
        # No routing needed - Journal system handles automatically
    )

    # Create MacroBricks
    e.new_MacroBrick("investments", "Investment Portfolio", ["etf"])
    e.new_MacroBrick("real_estate", "Real Estate Holdings", ["property", "mortgage"])

    # Create scenario
    e.create_scenario(
        "demo_scenario",
        "Demo Scenario",
        brick_ids=[
            "cash",
            "etf",
            "property",
            "mortgage",
            "salary",
            "expenses",
            "investments",
            "real_estate",
        ],
        settlement_default_cash_id="cash",
    )

    print("Created scenario with:")
    print("- Cash account")
    print("- ETF investment")
    print("- Real estate property")
    print("- Mortgage")
    print("- Salary income")
    print("- Monthly expenses")
    print("- Investment portfolio MacroBrick (ETF)")
    print("- Real estate MacroBrick (property + mortgage)")
    print()

    # Run scenario
    print("Running scenario for 6 months...")
    results = e.run_scenario("demo_scenario", start=date(2026, 1, 1), months=6)

    # Show full results
    print("\n=== FULL RESULTS ===")
    full_monthly = results["views"].monthly()
    print("Full monthly totals (first 3 months):")
    print(full_monthly.head(3))
    print()

    # Filter to only cash and salary
    print("=== FILTERED: Cash + Salary Only ===")
    cash_salary_view = results["views"].filter(brick_ids=["cash", "salary"])
    cash_salary_monthly = cash_salary_view.monthly()
    print("Cash + Salary monthly totals (first 3 months):")
    print(cash_salary_monthly.head(3))
    print()

    # Filter to investment portfolio MacroBrick
    print("=== FILTERED: Investment Portfolio MacroBrick ===")
    investments_view = results["views"].filter(brick_ids=["investments"])
    investments_monthly = investments_view.monthly()
    print("Investment portfolio monthly totals (first 3 months):")
    print(investments_monthly.head(3))
    print()

    # Filter to real estate MacroBrick
    print("=== FILTERED: Real Estate MacroBrick ===")
    real_estate_view = results["views"].filter(brick_ids=["real_estate"])
    real_estate_monthly = real_estate_view.monthly()
    print("Real estate monthly totals (first 3 months):")
    print(real_estate_monthly.head(3))
    print()

    # Filter to both cash and real estate
    print("=== FILTERED: Cash + Real Estate ===")
    mixed_view = results["views"].filter(brick_ids=["cash", "real_estate"])
    mixed_monthly = mixed_view.monthly()
    print("Cash + Real Estate monthly totals (first 3 months):")
    print(mixed_monthly.head(3))
    print()

    # Show quarterly aggregation on filtered data
    print("=== QUARTERLY AGGREGATION ON FILTERED DATA ===")
    investments_quarterly = investments_view.quarterly()
    print("Investment portfolio quarterly totals:")
    print(investments_quarterly)
    print()

    # Show yearly aggregation on filtered data
    print("=== YEARLY AGGREGATION ON FILTERED DATA ===")
    real_estate_yearly = real_estate_view.yearly()
    print("Real estate yearly totals:")
    print(real_estate_yearly)
    print()

    print("=== SUMMARY ===")
    print("✅ Successfully demonstrated filtered results functionality!")
    print(
        "✅ Filtered views support all time aggregation methods (monthly, quarterly, yearly)"
    )
    print("✅ Can filter by unified brick_ids (bricks and MacroBricks mixed)")
    print("✅ MacroBricks are automatically expanded to their constituent bricks")
    print("✅ Filtered results maintain the same structure as full results")


if __name__ == "__main__":
    main()
