# FinBrickLab Examples - Updated Architecture

Comprehensive examples demonstrating FinBrickLab's new architecture with unified brick handling, new strategies, and improved kind taxonomy.

## Table of Contents

* [Basic Scenarios](#basic-scenarios)
* [New Strategy Examples](#new-strategy-examples)
* [Entity and MacroBrick Usage](#entity-and-macrobrick-usage)
* [Filtered Results](#filtered-results)
* [Advanced Patterns](#advanced-patterns)

---

## Basic Scenarios

### Simple Cash Account

```python
from datetime import date
from finbricklab import Scenario, ABrick
from finbricklab.core.kinds import K

# Create a cash account with interest
cash = ABrick(
    id="savings",
    name="High-Yield Savings",
    kind=K.A_CASH,
    spec={
        "initial_balance": 10000.0,
        "interest_pa": 0.025
    }
)

# Create and run scenario
scenario = Scenario(id="simple_savings", name="Simple Savings", bricks=[cash])
results = scenario.run(start=date(2026, 1, 1), months=12)

print(f"Final balance: €{results['totals']['assets'].iloc[-1]:,.2f}")
```

### Investment Portfolio

```python
from finbricklab import Scenario, ABrick, FBrick
from finbricklab.core.kinds import K

# Cash account
cash = ABrick(
    id="checking",
    name="Checking Account",
    kind=K.A_CASH,
    spec={"initial_balance": 50000.0, "interest_pa": 0.02}
)

# ETF investment
etf = ABrick(
    id="etf",
    name="Stock ETF",
    kind=K.A_SECURITY_UNITIZED,
    spec={
        "initial_units": 200.0,
        "price0": 100.0,
        "drift_pa": 0.08,
        "volatility_pa": 0.15
    }
)

# Real estate
property = ABrick(
    id="property",
    name="Investment Property",
    kind=K.A_PROPERTY,
    spec={
        "initial_value": 300000.0,
        "appreciation_pa": 0.03,
        "fees_pct": 0.06
    }
)

# Mortgage
mortgage = LBrick(
    id="mortgage",
    name="Property Mortgage",
    kind=K.L_LOAN_ANNUITY,
    spec={
        "principal": 240000.0,
        "rate_pa": 0.04,
        "term_months": 300
    }
)

# Income
salary = FBrick(
    id="salary",
    name="Monthly Salary",
    kind=K.F_INCOME_RECURRING,
    spec={"amount_monthly": 6000.0}
)

# Expenses
expenses = FBrick(
    id="expenses",
    name="Monthly Expenses",
    kind=K.F_EXPENSE_RECURRING,
    spec={"amount_monthly": 3000.0}
)

# Create scenario
scenario = Scenario(
    id="investment_portfolio",
    name="Investment Portfolio",
    bricks=[cash, etf, property, mortgage, salary, expenses]
)

# Run scenario
results = scenario.run(start=date(2026, 1, 1), months=60)

# Analyze results
print(f"Final net worth: €{results['totals']['equity'].iloc[-1]:,.2f}")
print(f"Total assets: €{results['totals']['assets'].iloc[-1]:,.2f}")
print(f"Total liabilities: €{results['totals']['liabilities'].iloc[-1]:,.2f}")
```

---

## New Strategy Examples

### Credit Line (Revolving Credit)

```python
from finbricklab import Scenario, ABrick, LBrick, FBrick
from finbricklab.core.kinds import K

# Cash account
cash = ABrick(
    id="checking",
    name="Checking Account",
    kind=K.A_CASH,
    spec={"initial_balance": 5000.0, "interest_pa": 0.02}
)

# Credit line
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
    }
)

# Income
salary = FBrick(
    id="salary",
    name="Salary",
    kind=K.F_INCOME_RECURRING,
    spec={"amount_monthly": 3000.0}
)

# Expenses
expenses = FBrick(
    id="expenses",
    name="Monthly Expenses",
    kind=K.F_EXPENSE_RECURRING,
    spec={"amount_monthly": 2500.0}
)

scenario = Scenario(
    id="credit_line_demo",
    name="Credit Line Demo",
    bricks=[cash, credit_line, salary, expenses]
)

results = scenario.run(start=date(2026, 1, 1), months=12)

# Analyze credit line usage
credit_balance = results["outputs"]["credit_card"]["liabilities"]
print(f"Initial credit balance: €{credit_balance[0]:,.2f}")
print(f"Final credit balance: €{credit_balance[-1]:,.2f}")
```

### Fixed-Term Credit (Personal Loan)

```python
# Personal loan with linear amortization
personal_loan = LBrick(
    id="personal_loan",
    name="Personal Loan",
    kind=K.L_CREDIT_FIXED,
    spec={
        "principal": 15000.0,  # €15,000 loan
        "rate_pa": 0.08,  # 8% interest rate
        "term_months": 36,  # 3 years
        "start_date": "2026-01-01",
    }
)

# The loan will be paid off with equal principal payments plus interest
```

### Balloon Loan

```python
# Business loan with balloon payment
balloon_loan = LBrick(
    id="business_loan",
    name="Business Loan",
    kind=K.L_LOAN_BALLOON,
    spec={
        "principal": 500000.0,  # €500,000 loan
        "rate_pa": 0.06,  # 6% interest rate
        "term_months": 60,  # 5 years
        "amortization": {
            "type": "interest_only",  # Interest-only for first 4 years
            "amort_months": 0,
        },
        "balloon_at_maturity": "full",  # Full balloon payment
        "start_date": "2026-01-01",
    }
)
```

### Private Equity Investment

```python
# Private equity fund investment
pe_investment = ABrick(
    id="pe_fund",
    name="Private Equity Fund",
    kind=K.A_PRIVATE_EQUITY,
    spec={
        "initial_value": 50000.0,  # €50,000 initial investment
        "drift_pa": 0.12,  # 12% annual growth
        "valuation_frequency": "annual",  # Annual valuations
    }
)
```

---

## Entity and MacroBrick Usage

### Unified Brick Selection

```python
from finbricklab import Entity
from finbricklab.core.kinds import K

# Create entity
entity = Entity(id="demo", name="Demo Entity")

# Create individual bricks
entity.new_ABrick("cash", "Cash", K.A_CASH, {"initial_balance": 10000.0})
entity.new_ABrick("etf", "ETF", K.A_SECURITY_UNITIZED, {"initial_units": 100.0, "price0": 100.0})
entity.new_LBrick("mortgage", "Mortgage", K.L_LOAN_ANNUITY, {"principal": 200000.0, "rate_pa": 0.04})

# Create MacroBricks
entity.new_MacroBrick("investments", "Investment Portfolio", ["etf"])
entity.new_MacroBrick("housing", "Housing", ["mortgage"])

# Create scenario with unified brick selection
# MacroBricks are automatically expanded to their constituent bricks
scenario = entity.create_scenario(
    id="demo_scenario",
    name="Demo Scenario",
    brick_ids=["cash", "investments", "housing"]  # Mix of bricks and MacroBricks
)

# Run scenario
results = entity.run_scenario("demo_scenario", start=date(2026, 1, 1), months=12)
```

### MacroBrick Aggregation

```python
# Access MacroBrick aggregates
housing_totals = results["by_struct"]["housing"]
investment_totals = results["by_struct"]["investments"]

# MacroBrick totals are automatically calculated
print(f"Housing assets: €{housing_totals['asset_value'][-1]:,.2f}")
print(f"Investment assets: €{investment_totals['asset_value'][-1]:,.2f}")
```

---

## Filtered Results

### Filter by Specific Bricks

```python
# Filter to show only cash and salary
cash_salary_view = results["views"].filter(brick_ids=["cash", "salary"])
cash_salary_monthly = cash_salary_view.monthly()

print("Cash + Salary monthly totals:")
print(cash_salary_monthly.head())
```

### Filter by MacroBricks

```python
# Filter to show only investment portfolio
investments_view = results["views"].filter(brick_ids=["investments"])
investments_monthly = investments_view.monthly()

print("Investment portfolio monthly totals:")
print(investments_monthly.head())
```

### Mixed Filtering

```python
# Filter to show cash + real estate MacroBrick
mixed_view = results["views"].filter(brick_ids=["cash", "housing"])
mixed_monthly = mixed_view.monthly()

print("Cash + Real Estate monthly totals:")
print(mixed_monthly.head())
```

### Time Aggregation on Filtered Data

```python
# Quarterly aggregation on filtered data
investments_quarterly = investments_view.quarterly()
print("Investment portfolio quarterly totals:")
print(investments_quarterly)

# Yearly aggregation on filtered data
housing_yearly = housing_view.yearly()
print("Housing yearly totals:")
print(housing_yearly)
```

---

## Advanced Patterns

### Multi-Strategy Investment Comparison

```python
from finbricklab import Entity

def create_investment_scenario(name: str, stock_allocation: float, bond_allocation: float):
    """Create an investment scenario with given allocation."""

    # Cash
    cash = ABrick(
        id=f"{name}_cash",
        name="Cash",
        kind=K.A_CASH,
        spec={"initial_balance": 100000.0 * (1 - stock_allocation - bond_allocation), "interest_pa": 0.02}
    )

    # Stocks
    stocks = ABrick(
        id=f"{name}_stocks",
        name="Stock ETF",
        kind=K.A_SECURITY_UNITIZED,
        spec={
            "initial_units": (100000.0 * stock_allocation) / 100.0,
            "price0": 100.0,
            "drift_pa": 0.08,
            "volatility_pa": 0.20
        }
    )

    # Bonds
    bonds = ABrick(
        id=f"{name}_bonds",
        name="Bond ETF",
        kind=K.A_SECURITY_UNITIZED,
        spec={
            "initial_units": (100000.0 * bond_allocation) / 50.0,
            "price0": 50.0,
            "drift_pa": 0.04,
            "volatility_pa": 0.05
        }
    )

    return Scenario(
        id=name,
        name=name,
        bricks=[cash, stocks, bonds]
    )

# Create different strategies
aggressive = create_investment_scenario("aggressive", 0.8, 0.2)
balanced = create_investment_scenario("balanced", 0.6, 0.3)
conservative = create_investment_scenario("conservative", 0.4, 0.4)

# Create entity
entity = Entity(
    id="investment_comparison",
    name="Investment Strategy Comparison",
    scenarios=[aggressive, balanced, conservative]
)

# Run all scenarios
for scenario in entity.scenarios:
    scenario.run(start=date(2026, 1, 1), months=120)

# Compare results
comparison_df = entity.compare()
print("Final net worth by strategy:")
final_net_worth = comparison_df.groupby("scenario_name")["net_worth"].last()
print(final_net_worth)
```

### Real Estate Investment with Multiple Properties

```python
def create_property_scenario(property_id: str, property_value: float, mortgage_rate: float):
    """Create a property investment scenario."""

    # Property
    property = ABrick(
        id=f"{property_id}_property",
        name=f"Property {property_id}",
        kind=K.A_PROPERTY,
        spec={
            "initial_value": property_value,
            "appreciation_pa": 0.03,
            "fees_pct": 0.06
        }
    )

    # Mortgage
    mortgage = LBrick(
        id=f"{property_id}_mortgage",
        name=f"Mortgage {property_id}",
        kind=K.L_LOAN_ANNUITY,
        spec={
            "principal": property_value * 0.8,  # 80% LTV
            "rate_pa": mortgage_rate,
            "term_months": 300
        }
    )

    # Cash for down payment
    cash = ABrick(
        id=f"{property_id}_cash",
        name=f"Cash {property_id}",
        kind=K.A_CASH,
        spec={"initial_balance": property_value * 0.2, "interest_pa": 0.02}
    )

    return Scenario(
        id=property_id,
        name=f"Property {property_id}",
        bricks=[property, mortgage, cash]
    )

# Create multiple property scenarios
property1 = create_property_scenario("property1", 300000.0, 0.04)
property2 = create_property_scenario("property2", 400000.0, 0.035)
property3 = create_property_scenario("property3", 250000.0, 0.045)

# Create entity
property_entity = Entity(
    id="property_portfolio",
    name="Property Portfolio",
    scenarios=[property1, property2, property3]
)

# Run all scenarios
for scenario in property_entity.scenarios:
    scenario.run(start=date(2026, 1, 1), months=60)

# Compare results
comparison_df = property_entity.compare()
print("Property investment comparison:")
final_results = comparison_df.groupby("scenario_name")["net_worth"].last()
print(final_results)
```

---

## Key Features Demonstrated

### 1. **Unified Brick Selection**
- Single `brick_ids` parameter accepts both brick IDs and MacroBrick IDs
- MacroBricks are automatically expanded to their constituent bricks
- No need for separate `macrobrick_ids` parameter

### 2. **New Financial Strategies**
- **CreditLine**: Revolving credit with interest accrual and minimum payments
- **CreditFixed**: Linear amortization with equal principal payments
- **LoanBalloon**: Balloon loans with interest-only and linear amortization options
- **PrivateEquity**: Deterministic marking with drift-based calculation

### 3. **Improved Kind Taxonomy**
- Behavior-centric naming (e.g., `K.A_SECURITY_UNITIZED` for unitized securities)
- Clear separation between assets, liabilities, flows, and transfers
- Extensible design for future financial instruments

### 4. **Enhanced Column Names**
- `assets` instead of `asset_value`
- `liabilities` instead of `debt_balance`
- Consistent naming across all output formats

### 5. **Filtered Results**
- Filter by specific bricks or MacroBricks
- Support for all time aggregation methods (monthly, quarterly, yearly)
- Maintains same structure as full results

### 6. **MacroBrick Aggregation**
- Automatic calculation of MacroBrick totals
- Access via `results["by_struct"][macrobrick_id]`
- Proper handling of overlapping bricks

This new architecture provides a more intuitive and powerful way to model complex financial scenarios while maintaining backward compatibility where possible.
