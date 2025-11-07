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

## Selection-Based Aggregation (V2)

### Select by Specific Node IDs

```python
# Select only the cash account (salary inflows appear on the cash node)
cash_only_monthly = results["views"].monthly(selection={"a:cash"})

print("Cash-only monthly totals:")
print(cash_only_monthly.head())
```

### Select by MacroBricks

```python
# Select investment portfolio MacroBrick (expanded to A/L nodes)
investments_monthly = results["views"].monthly(selection={"investments"})

print("Investment portfolio monthly totals:")
print(investments_monthly.head())
```

### Mixed Selection

```python
# Select both cash and real estate MacroBrick
mixed_monthly = results["views"].monthly(selection={"a:cash", "housing"})

print("Cash + Real Estate monthly totals:")
print(mixed_monthly.head())
```

### Time Aggregation with Selection

```python
# Quarterly aggregation with selection
investments_quarterly = results["views"].to_freq("Q", selection={"investments"})
print("Investment portfolio quarterly totals:")
print(investments_quarterly)

# Yearly aggregation with selection
housing_yearly = results["views"].to_freq("Y", selection={"housing"})
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

### 5. **Filtered Results (V2)**
- Filter by specific bricks or MacroBricks using journal-first aggregation
- **Sticky defaults**: Selection, visibility, and `include_cash` settings persist in filtered views
- Filtered views remember their selection/visibility for subsequent `monthly()` calls unless explicitly overridden
- Only A/L bricks produce selection node IDs; F/T bricks are ignored for selection
- MacroBricks are expanded recursively using cached expansion
- Unknown brick IDs warn and return zeros
- `include_cash=False` persists across visibility changes (sticky on filtered views)
- Support for all time aggregation methods (monthly, quarterly, yearly)
- Maintains same structure as full results

**Example:**
```python
# Filter to cash account only
cash_view = results["views"].filter(brick_ids=["cash"])

# Selection is preserved (sticky) - changing visibility still respects cash selection
cash_all = cash_view.monthly(transfer_visibility=TransferVisibility.ALL)
cash_boundary = cash_view.monthly(transfer_visibility=TransferVisibility.BOUNDARY_ONLY)
# Default call uses the stored selection + visibility
cash_default = cash_view.monthly()  # Uses stored selection and visibility

# Filter to MacroBrick (automatically expanded)
investments_view = results["views"].filter(brick_ids=["investments"])

# include_cash=False persists across visibility changes (sticky)
no_cash_view = results["views"].filter(brick_ids=["cash"], include_cash=False)
assert "cash" not in no_cash_view.monthly(transfer_visibility=TransferVisibility.ALL).columns
assert "cash" not in no_cash_view.monthly().columns  # Sticky default applies

# Override defaults by passing explicit parameters
override_view = no_cash_view.monthly(selection={"a:other_account"})  # Temporarily overrides stored selection
```

### 6. **MacroBrick Aggregation**
- Automatic calculation of MacroBrick totals
- Access via `results["by_struct"][macrobrick_id]`
- Proper handling of overlapping bricks

### 7. **Enhanced Journal System** 🆕
- **Complete transaction-level detail** for all financial activities
- **Double-entry bookkeeping** with proper account tracking
- **Time-series analysis** of financial flows throughout simulation
- **Account-level reconciliation** and debugging capabilities
- **Filtered journal analysis** for specific components
- **Transaction type classification** and comprehensive audit trail

## Journal Analysis Examples

### Basic Journal Access

```python
# Get complete journal of all transactions
journal_df = results["views"].journal()
print(f"Total transactions: {len(journal_df)}")
print(f"Date range: {journal_df['timestamp'].min()} to {journal_df['timestamp'].max()}")

# Show sample transactions
print(journal_df.head())
```

### Account-Specific Transactions

```python
# Get all transactions for a specific account
checking_txns = results["views"].transactions("checking")
savings_txns = results["views"].transactions("savings")

print("Checking account transactions:")
print(checking_txns[['timestamp', 'amount', 'metadata']].head())
```

### Filtered Journal Analysis (V2)

```python
# Filter journal by category (income sources)
journal_df = results["views"].journal()
income_journal = journal_df[journal_df["metadata"].apply(lambda m: m.get("category", "").startswith("income."))]

# Filter journal by brick_id or transaction type
investment_journal = journal_df[
    journal_df["brick_id"].isin(["investment_strategy", "etf"]) |
    journal_df["metadata"].apply(lambda m: m.get("transaction_type", "") in {"transfer", "dividend"})
]

print(f"Income transactions: {len(income_journal)}")
print(f"Investment transactions: {len(investment_journal)}")
```

### Advanced Journal Analysis

```python
# Monthly transaction analysis
monthly_stats = journal_df.groupby('timestamp').agg({
    'record_id': 'count',
    'amount': 'sum'
}).rename(columns={'record_id': 'transactions', 'amount': 'net_amount'})

# Account balance analysis
account_stats = journal_df.groupby('account_id').agg({
    'amount': ['count', 'sum']
}).round(2)

# Transaction type analysis
transaction_types = journal_df['metadata'].apply(lambda x: x.get('type', 'unknown')).value_counts()

# Double-entry validation
entry_balances = journal_df.groupby('record_id')['amount'].sum()
unbalanced_entries = entry_balances[entry_balances.abs() > 1e-6]
print(f"Unbalanced entries: {len(unbalanced_entries)}")
```

### Canonical Journal Structure

The enhanced journal system now provides a canonical structure for better analysis:

```python
# Get journal with canonical structure
journal_df = results["views"].journal()

# New canonical columns:
print("Canonical columns:", list(journal_df.columns))
# ['record_id', 'brick_id', 'brick_type', 'account_id', 'timestamp', 'amount', 'currency', 'metadata', 'entry_metadata']

# Example canonical record:
print("Sample record:")
print(journal_df.iloc[0])
```

**Canonical Structure Benefits:**
- **record_id**: `"flow:income:salary:checking:0"` - Clean, self-documenting unique ID
- **brick_id**: `"salary"` - Primary column for filtering
- **brick_type**: `"flow"` - Type of financial instrument
- **account_id**: `"Asset:checking"` - Where money flows (standardized format)
- **posting_side**: `"credit"` or `"debit"` - Double-entry bookkeeping side
- **metadata**: Rich transaction information

**Example Queries:**
```python
# Filter by brick
salary_transactions = journal_df[journal_df['brick_id'] == 'salary']

# Filter by brick type
flow_transactions = journal_df[journal_df['brick_type'] == 'flow']

# Filter by account type (standardized format)
asset_transactions = journal_df[journal_df['account_id'].str.startswith('Asset:')]
income_transactions = journal_df[journal_df['account_id'].str.startswith('Income:')]
liability_transactions = journal_df[journal_df['account_id'].str.startswith('Liability:')]

# Filter by posting side (double-entry bookkeeping)
debit_transactions = journal_df[journal_df['posting_side'] == 'debit']
credit_transactions = journal_df[journal_df['posting_side'] == 'credit']

# Parse record_id for complex analysis
journal_df['parsed_record'] = journal_df['record_id'].str.split(':')
```

### Journal Benefits

- **🔍 Complete Audit Trail**: Every financial transaction is recorded
- **📊 Account Reconciliation**: Track all account balance changes
- **⏰ Time-Series Analysis**: Analyze financial flows over time
- **🔧 Debugging Support**: Identify issues in financial logic
- **📋 Compliance**: Meet accounting and regulatory requirements
- **🎯 Filtered Analysis**: Focus on specific components or time periods

This new architecture provides a more intuitive and powerful way to model complex financial scenarios while maintaining backward compatibility where possible.
