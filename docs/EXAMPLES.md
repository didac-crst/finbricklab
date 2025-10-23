# FinBrickLab Examples

Comprehensive examples demonstrating FinBrickLab capabilities.

## Table of Contents

* [Basic Scenarios](#basic-scenarios)
* [Journal System Examples](#journal-system-examples)
* [Entity Comparisons](#entity-comparisons)
* [Advanced Patterns](#advanced-patterns)
* [Visualization Examples](#visualization-examples)
* [Custom Strategies](#custom-strategies)
* [Real-World Scenarios](#real-world-scenarios)

---

## Basic Scenarios

### Simple Cash Account

```python
from datetime import date
from finbricklab import Scenario, ABrick

# Create a cash account with interest
cash = ABrick(
    id="savings",
    name="High-Yield Savings",
    kind="a.cash",
    spec={
        "initial_balance": 10000.0,
        "interest_pa": 0.025
    }
)

# Create and run scenario
scenario = Scenario(id="simple_savings", name="Simple Savings", bricks=[cash])
results = scenario.run(start=date(2026, 1, 1), months=12)

print(f"Final balance: ${results['totals']['cash'].iloc[-1]:,.2f}")
```

### Buy vs Rent Analysis

```python
from finbricklab import Scenario, ABrick, LBrick, FBrick

# Renting scenario
rent_cash = ABrick(
    id="rent_cash",
    name="Rent Cash",
    kind="a.cash",
    spec={"initial_balance": 50000.0, "interest_pa": 0.03}
)

rent_expense = FBrick(
    id="rent",
    name="Monthly Rent",
    kind="f.expense.recurring",
    links={"from": {"from_cash": "rent_cash"}},
    spec={
        "amount_monthly": 2500.0,
        "activation_window": {"start_date": "2026-01-01", "end_date": "2036-01-01"}
    }
)

rent_scenario = Scenario(id="rent", name="Rent Forever", bricks=[rent_cash, rent_expense])

# Buying scenario
house = ABrick(
    id="house",
    name="Family Home",
    kind="a.property",
    spec={
        "initial_value": 500000.0,
        "appreciation_pa": 0.025,
        "fees_pct": 0.06
    }
)

mortgage = LBrick(
    id="mortgage",
    name="Home Loan",
    kind="l.loan.annuity",
    links={"principal": {"from_house": "house"}},
    spec={"rate_pa": 0.035, "term_months": 360}
)

buy_cash = ABrick(
    id="buy_cash",
    name="Buy Cash",
    kind="a.cash",
    spec={"initial_balance": 100000.0, "interest_pa": 0.03}
)

down_payment = FBrick(
    id="down_payment",
    name="Down Payment",
    kind="f.transfer.lumpsum",
    links={
        "to": {"to_house": "house"},
        "from": {"from_cash": "buy_cash"}
    },
    spec={
        "amount": -100000.0,
        "activation_window": {"start_date": "2026-01-01", "duration_m": 1}
    }
)

buy_scenario = Scenario(
    id="buy",
    name="Buy Home",
    bricks=[house, mortgage, buy_cash, down_payment]
)

# Run both scenarios
rent_results = rent_scenario.run(start=date(2026, 1, 1), months=120)
buy_results = buy_scenario.run(start=date(2026, 1, 1), months=120)

# Compare results
rent_net_worth = rent_results['totals']['cash'].iloc[-1]
buy_net_worth = buy_results['totals']['assets'].iloc[-1] - buy_results['totals']['liabilities'].iloc[-1]

print(f"Rent net worth: ${rent_net_worth:,.2f}")
print(f"Buy net worth: ${buy_net_worth:,.2f}")
print(f"Buy advantage: ${buy_net_worth - rent_net_worth:,.2f}")
```

---

## Journal System Examples

### Basic Journal Usage

```python
from finbricklab import Entity
from finbricklab.core.kinds import K

# Create entity with Journal-based system
entity = Entity('person', 'John Doe')

# Create cash accounts
checking = entity.new_ABrick('checking', 'Checking', K.A_CASH, {'initial_balance': 5000.0})
savings = entity.new_ABrick('savings', 'Savings', K.A_CASH, {'initial_balance': 10000.0})

# Create income and expense flows
salary = entity.new_FBrick('salary', 'Salary', K.F_INCOME_FIXED, {'amount_monthly': 6000.0})
rent = entity.new_FBrick('rent', 'Rent', K.F_EXPENSE_FIXED, {'amount_monthly': 2000.0})

# Create internal transfer
monthly_save = entity.new_TBrick(
    'monthly_save',
    'Monthly Savings',
    K.T_TRANSFER_RECURRING,
    {'amount': 1000.0, 'currency': 'EUR', 'freq': 'MONTHLY', 'day': 1},
    {'from': 'checking', 'to': 'savings'}
)

# Create scenario
scenario = entity.create_scenario('journal_demo', 'Journal Demo',
                                ['checking', 'savings', 'salary', 'rent', 'monthly_save'])
results = scenario.run(start=date(2026, 1, 1), months=12)

# Check results
print(f"Final checking balance: {results['outputs']['checking']['asset_value'][-1]:.2f}")
print(f"Final savings balance: {results['outputs']['savings']['asset_value'][-1]:.2f}")
```

### Multi-Currency Journal

```python
from finbricklab.core.currency import create_amount, EUR, USD

# Create multi-currency scenario
entity = Entity('international', 'International Person')

# EUR accounts
eur_cash = entity.new_ABrick('eur_cash', 'EUR Cash', K.A_CASH, {'initial_balance': 10000.0})

# USD accounts
usd_cash = entity.new_ABrick('usd_cash', 'USD Cash', K.A_CASH, {'initial_balance': 5000.0})

# EUR income
eur_salary = entity.new_FBrick('eur_salary', 'EUR Salary', K.F_INCOME_FIXED,
                              {'amount_monthly': 5000.0, 'currency': 'EUR'})

# USD income
usd_salary = entity.new_FBrick('usd_salary', 'USD Salary', K.F_INCOME_FIXED,
                              {'amount_monthly': 3000.0, 'currency': 'USD'})

# Cross-currency transfer
fx_transfer = entity.new_TBrick(
    'fx_transfer',
    'FX Transfer',
    K.T_TRANSFER_LUMP_SUM,
    {'amount': 1000.0, 'currency': 'USD'},
    {'from': 'usd_cash', 'to': 'eur_cash'}
)

scenario = entity.create_scenario('multi_currency', 'Multi-Currency',
                                ['eur_cash', 'usd_cash', 'eur_salary', 'usd_salary', 'fx_transfer'])
results = scenario.run(start=date(2026, 1, 1), months=6)
```

### Journal Validation

```python
from finbricklab.core.accounts import Account, AccountRegistry, AccountScope, AccountType
from finbricklab.core.journal import Journal, JournalEntry, Posting
from finbricklab.core.currency import create_amount

# Create account registry
registry = AccountRegistry()
journal = Journal(registry)

# Register accounts
registry.register_account(Account("cash", "Cash", AccountScope.INTERNAL, AccountType.ASSET))
registry.register_account(Account("income", "Income", AccountScope.BOUNDARY, AccountType.INCOME))

# Create valid entry
entry = JournalEntry(
    id="income_entry",
    timestamp=date(2026, 1, 1),
    postings=[
        Posting("income", create_amount(-1000, "EUR"), {"type": "income"}),
        Posting("cash", create_amount(1000, "EUR"), {"type": "cash_in"})
    ],
    metadata={"type": "income"}
)

# Post entry
journal.post(entry)

# Validate invariants
errors = journal.validate_invariants(registry)
if errors:
    print(f"Validation errors: {errors}")
else:
    print("Journal is valid!")

# Check balances
cash_balance = journal.balance("cash", "EUR")
income_balance = journal.balance("income", "EUR")
print(f"Cash balance: {cash_balance}")
print(f"Income balance: {income_balance}")
```

### Transfer Brick Examples

```python
# One-time transfer
emergency_transfer = entity.new_TBrick(
    'emergency_transfer',
    'Emergency Transfer',
    K.T_TRANSFER_LUMP_SUM,
    {'amount': 2000.0, 'currency': 'EUR'},
    {'from': 'savings', 'to': 'checking'}
)

# Recurring transfer
monthly_investment = entity.new_TBrick(
    'monthly_investment',
    'Monthly Investment',
    K.T_TRANSFER_RECURRING,
    {'amount': 500.0, 'currency': 'EUR', 'freq': 'MONTHLY', 'day': 15},
    {'from': 'checking', 'to': 'investment'}
)

# Scheduled transfers
bonus_transfers = entity.new_TBrick(
    'bonus_transfers',
    'Bonus Transfers',
    K.T_TRANSFER_SCHEDULED,
    {
        'schedule': [
            {'date': '2026-06-01', 'amount': 5000.0, 'currency': 'EUR'},
            {'date': '2026-12-01', 'amount': 3000.0, 'currency': 'EUR'}
        ]
    },
    {'from': 'checking', 'to': 'savings'}
)
```

---

## Entity Comparisons

### Multi-Strategy Investment Comparison

```python
from finbricklab import Entity, Scenario, ABrick, FBrick

# Conservative strategy
conservative_cash = ABrick(
    id="conservative_cash",
    name="Conservative Cash",
    kind="a.cash",
    spec={"initial_balance": 100000.0, "interest_pa": 0.03}
)

conservative_scenario = Scenario(
    id="conservative",
    name="Conservative Strategy",
    bricks=[conservative_cash]
)

# Aggressive strategy
aggressive_cash = ABrick(
    id="aggressive_cash",
    name="Aggressive Cash",
    kind="a.cash",
    spec={"initial_balance": 0.0, "interest_pa": 0.03}
)

aggressive_etf = ABrick(
    id="aggressive_etf",
    name="Stock ETF",
    kind="a.security.unitized",
    spec={
        "initial_units": 1000.0,
        "initial_price": 100.0,
        "drift_pa": 0.10,
        "volatility_pa": 0.25
    }
)

aggressive_scenario = Scenario(
    id="aggressive",
    name="Aggressive Strategy",
    bricks=[aggressive_cash, aggressive_etf]
)

# Balanced strategy
balanced_cash = ABrick(
    id="balanced_cash",
    name="Balanced Cash",
    kind="a.cash",
    spec={"initial_balance": 50000.0, "interest_pa": 0.03}
)

balanced_etf = ABrick(
    id="balanced_etf",
    name="Balanced ETF",
    kind="a.security.unitized",
    spec={
        "initial_units": 500.0,
        "initial_price": 100.0,
        "drift_pa": 0.08,
        "volatility_pa": 0.15
    }
)

balanced_scenario = Scenario(
    id="balanced",
    name="Balanced Strategy",
    bricks=[balanced_cash, balanced_etf]
)

# Create entity and run scenarios
entity = Entity(
    id="investment_comparison",
    name="Investment Strategy Comparison",
    scenarios=[conservative_scenario, aggressive_scenario, balanced_scenario]
)

# Run all scenarios
for scenario in entity.scenarios:
    scenario.run(start=date(2026, 1, 1), months=120)

# Compare results
comparison_df = entity.compare()
print(comparison_df.tail())

# Calculate breakeven
breakeven_df = entity.breakeven_table("conservative")
print(f"Breakeven analysis:\n{breakeven_df}")

# Liquidity analysis
liquidity_df = entity.liquidity_runway(lookback_months=12, essential_share=0.6)
print(f"Liquidity runway:\n{liquidity_df.tail()}")
```

### Scenario with Income and Expenses

```python
from finbricklab import Entity, Scenario, ABrick, FBrick

# Create comprehensive scenario with income and expenses
checking = ABrick(
    id="checking",
    name="Checking Account",
    kind="a.cash",
    spec={"initial_balance": 25000.0, "interest_pa": 0.01}
)

# Income
salary = FBrick(
    id="salary",
    name="Monthly Salary",
    kind="f.income.recurring",
    links={"to": {"to_checking": "checking"}},
    spec={
        "amount_monthly": 6000.0,
        "activation_window": {"start_date": "2026-01-01", "end_date": "2036-01-01"}
    }
)

# Expenses
rent = FBrick(
    id="rent",
    name="Monthly Rent",
    kind="f.expense.recurring",
    links={"from": {"from_checking": "checking"}},
    spec={
        "amount_monthly": 2500.0,
        "activation_window": {"start_date": "2026-01-01", "end_date": "2036-01-01"}
    }
)

groceries = FBrick(
    id="groceries",
    name="Groceries",
    kind="f.expense.recurring",
    links={"from": {"from_checking": "checking"}},
    spec={
        "amount_monthly": 800.0,
        "activation_window": {"start_date": "2026-01-01", "end_date": "2036-01-01"}
    }
)

# Create scenario
budget_scenario = Scenario(
    id="budget",
    name="Monthly Budget",
    bricks=[checking, salary, rent, groceries]
)

# Run scenario
results = budget_scenario.run(start=date(2026, 1, 1), months=60)

# Analyze results
print(f"Final checking balance: ${results['totals']['cash'].iloc[-1]:,.2f}")
print(f"Total net worth: ${results['totals']['equity'].iloc[-1]:,.2f}")
```

---

## MacroBrick Usage

### Organizing Bricks with MacroBricks

MacroBricks allow you to group related bricks within a scenario for better organization and analysis:

```python
from finbricklab import Scenario, ABrick, LBrick, MacroBrick

# Individual bricks
house = ABrick(
    id="house",
    name="Family Home",
    kind="a.property",
    spec={"initial_value": 500000.0, "appreciation_pa": 0.025, "fees_pct": 0.06}
)

mortgage = LBrick(
    id="mortgage",
    name="Home Loan",
    kind="l.loan.annuity",
    links={"principal": {"from_house": "house"}},
    spec={"rate_pa": 0.035, "term_months": 360}
)

cash = ABrick(
    id="cash",
    name="Savings",
    kind="a.cash",
    spec={"initial_balance": 50000.0, "interest_pa": 0.03}
)

# Group related bricks into MacroBricks
housing_macrobrick = MacroBrick(
    id="housing",
    name="Housing Portfolio",
    members=["house", "mortgage"],
    tags=["real_estate"]
)

cash_macrobrick = MacroBrick(
    id="cash_reserves",
    name="Cash Reserves",
    members=["cash"],
    tags=["liquid"]
)

# Create scenario with MacroBricks
scenario = Scenario(
    id="organized_scenario",
    name="Organized Scenario",
    bricks=[house, mortgage, cash],
    macrobricks=[housing_macrobrick, cash_macrobrick]
)

# Run scenario
results = scenario.run(start=date(2026, 1, 1), months=60)

# Access MacroBrick aggregates
housing_totals = results["by_struct"]["housing"]
cash_totals = results["by_struct"]["cash_reserves"]

# Calculate housing net worth from asset value and debt balance
housing_net_worth = housing_totals['asset_value'][-1] - housing_totals['debt_balance'][-1]
print(f"Housing net worth: ${housing_net_worth:,.2f}")

# Cash balance is the asset value for cash
cash_balance = cash_totals['asset_value'][-1]
print(f"Cash balance: ${cash_balance:,.2f}")
```

### MacroBrick Selection and Overlaps

```python
# Run scenario with specific MacroBrick selection
results = scenario.run(
    start=date(2026, 1, 1),
    months=60,
    selection=["housing", "cash_reserves"]  # Select specific MacroBricks
)

# Check for overlaps
overlaps = results.meta["overlaps"]
if overlaps:
    print(f"Shared bricks: {list(overlaps.keys())}")

# Portfolio totals (union of all executed bricks)
portfolio_total = results.totals['total_assets']
print(f"Portfolio total: ${portfolio_total:,.2f}")

# MacroBrick aggregates (may overlap)
housing_total = results.by_struct["housing"]['total_assets']
cash_total = results.by_struct["cash_reserves"]['total_assets']
print(f"Housing total: ${housing_total:,.2f}")
print(f"Cash total: ${cash_total:,.2f}")
print(f"Sum of MacroBricks: ${housing_total + cash_total:,.2f}")
```

### Nested MacroBricks

```python
# Create nested MacroBrick structure
investment_portfolio = MacroBrick(
    id="investments",
    name="Investment Portfolio",
    members=["stocks", "bonds"]
)

total_portfolio = MacroBrick(
    id="total_portfolio",
    name="Total Portfolio",
    members=["investments", "cash_reserves"]  # Contains other MacroBrick
)

scenario = Scenario(
    id="nested_scenario",
    name="Nested Portfolio",
    bricks=[stocks, bonds, cash],
    macrobricks=[investment_portfolio, total_portfolio]
)

# The system automatically resolves nesting
results = scenario.run(start=date(2026, 1, 1), months=12, selection=["total_portfolio"])
```

---

## Advanced Patterns

### Property Investment with Refinancing

```python
from finbricklab import Scenario, ABrick, LBrick, FBrick

# Property
rental_property = ABrick(
    id="rental",
    name="Rental Property",
    kind="a.property",
    spec={
        "initial_value": 300000.0,
        "appreciation_pa": 0.03,
        "fees_pct": 0.06
    }
)

# Initial mortgage
initial_mortgage = LBrick(
    id="initial_mortgage",
    name="Initial Mortgage",
    kind="l.loan.annuity",
    links={"principal": {"from_property": "rental"}},
    spec={"rate_pa": 0.045, "term_months": 360}
)

# Refinanced mortgage (starts after 5 years)
refi_mortgage = LBrick(
    id="refi_mortgage",
    name="Refinanced Mortgage",
    kind="l.loan.annuity",
    links={"principal": {"from_property": "rental"}},
    spec={"rate_pa": 0.035, "term_months": 300}
)

# Cash for down payment and refinancing costs
cash = ABrick(
    id="cash",
    name="Investment Cash",
    kind="a.cash",
    spec={"initial_balance": 60000.0, "interest_pa": 0.02}
)

# Down payment
down_payment = FBrick(
    id="down_payment",
    name="Down Payment",
    kind="f.transfer.lumpsum",
    links={
        "to": {"to_property": "rental"},
        "from": {"from_cash": "cash"}
    },
    spec={
        "amount": -60000.0,
        "activation_window": {"start_date": "2026-01-01", "duration_m": 1}
    }
)

# Rental income
rental_income = FBrick(
    id="rental_income",
    name="Rental Income",
    kind="f.income.recurring",
    links={"to": {"to_cash": "cash"}},
    spec={
        "amount_monthly": 2000.0,
        "activation_window": {"start_date": "2026-02-01", "end_date": "2036-01-01"}
    }
)

# Refinancing costs
refi_costs = FBrick(
    id="refi_costs",
    name="Refinancing Costs",
    kind="f.expense.recurring",
    links={"from": {"from_cash": "cash"}},
    spec={
        "amount_monthly": 5000.0,  # One-time cost
        "activation_window": {"start_date": "2031-01-01", "duration_m": 1}
    }
)

# Create scenario
property_scenario = Scenario(
    id="rental_investment",
    name="Rental Property Investment",
    bricks=[rental_property, initial_mortgage, refi_mortgage, cash, down_payment, rental_income, refi_costs]
)

# Run scenario
property_scenario.run(start=date(2026, 1, 1), months=120)

# Analyze results
results = property_scenario.to_canonical_frame()
print(f"Property value: ${results['illiquid_assets'].iloc[-1]:,.2f}")
print(f"Cash balance: ${results['cash'].iloc[-1]:,.2f}")
print(f"Total liabilities: ${results['liabilities'].iloc[-1]:,.2f}")
print(f"Net worth: ${results['net_worth'].iloc[-1]:,.2f}")
```

### Multi-Asset Portfolio

```python
from finbricklab import Entity, Scenario, ABrick, FBrick

def create_portfolio_scenario(scenario_id: str, name: str, stock_allocation: float, bond_allocation: float, cash_allocation: float):
    """Create a portfolio scenario with given asset allocation."""

    # Assets
    cash = ABrick(
        id=f"{scenario_id}_cash",
        name="Cash",
        kind="a.cash",
        spec={"initial_balance": 100000.0 * cash_allocation, "interest_pa": 0.02}
    )

    stocks = ABrick(
        id=f"{scenario_id}_stocks",
        name="Stock ETF",
        kind="a.security.unitized",
        spec={
            "initial_units": (100000.0 * stock_allocation) / 100.0,
            "initial_price": 100.0,
            "drift_pa": 0.08,
            "volatility_pa": 0.20
        }
    )

    bonds = ABrick(
        id=f"{scenario_id}_bonds",
        name="Bond ETF",
        kind="a.security.unitized",
        spec={
            "initial_units": (100000.0 * bond_allocation) / 50.0,
            "initial_price": 50.0,
            "drift_pa": 0.04,
            "volatility_pa": 0.05
        }
    )

    return Scenario(
        id=scenario_id,
        name=name,
        bricks=[cash, stocks, bonds]
    )

# Create different portfolio strategies
aggressive = create_portfolio_scenario("aggressive", "Aggressive (80/20/0)", 0.8, 0.2, 0.0)
balanced = create_portfolio_scenario("balanced", "Balanced (60/30/10)", 0.6, 0.3, 0.1)
conservative = create_portfolio_scenario("conservative", "Conservative (40/40/20)", 0.4, 0.4, 0.2)

# Create entity
portfolio_entity = Entity(
    id="portfolio_comparison",
    name="Portfolio Strategy Comparison",
    scenarios=[aggressive, balanced, conservative]
)

# Run all scenarios
for scenario in portfolio_entity.scenarios:
    scenario.run(start=date(2026, 1, 1), months=120)

# Compare results
comparison_df = portfolio_entity.compare()
print("Final net worth by strategy:")
final_net_worth = comparison_df.groupby("scenario_name")["net_worth"].last()
print(final_net_worth)

# Calculate risk metrics
from finbricklab import max_drawdown
risk_analysis = comparison_df.groupby("scenario_name")["net_worth"].apply(max_drawdown)
print("\nMaximum drawdown by strategy:")
print(risk_analysis)
```

---

## Visualization Examples

### Entity Comparison Charts

```python
from finbricklab import Entity, net_worth_vs_time, asset_composition_small_multiples
from finbricklab.charts import save_chart

# Assuming we have an entity with multiple scenarios
comparison_df = entity.compare()

# Create net worth comparison chart
fig1, data1 = net_worth_vs_time(comparison_df)
fig1.show()

# Create asset composition chart
fig2, data2 = asset_composition_small_multiples(comparison_df)
fig2.show()

# Save charts
save_chart(fig1, "net_worth_comparison.html")
save_chart(fig2, "asset_composition.html", format="png")
```

### Scenario Deep Dive

```python
from finbricklab.charts import cashflow_waterfall, ltv_dsti_over_time, contribution_vs_market_growth

# Get single scenario data
scenario_data = comparison_df[comparison_df["scenario_name"] == "Buy Home"]

# Create detailed scenario charts
fig1, data1 = cashflow_waterfall(scenario_data, "Buy Home")
fig1.show()

fig2, data2 = ltv_dsti_over_time(scenario_data, "Buy Home")
fig2.show()

fig3, data3 = contribution_vs_market_growth(scenario_data, "Buy Home")
fig3.show()
```

### KPI Analysis

```python
from finbricklab import liquidity_runway, fee_drag_cum, tax_burden_cum

# Calculate KPIs for each scenario
scenarios = comparison_df["scenario_name"].unique()
kpi_results = []

for scenario_name in scenarios:
    scenario_data = comparison_df[comparison_df["scenario_name"] == scenario_name]

    # Calculate various KPIs
    runway = liquidity_runway(scenario_data).iloc[-1]
    fee_drag = fee_drag_cum(scenario_data).iloc[-1]
    tax_burden = tax_burden_cum(scenario_data).iloc[-1]

    kpi_results.append({
        "scenario": scenario_name,
        "liquidity_runway_months": runway,
        "fee_drag_pct": fee_drag * 100,
        "tax_burden_pct": tax_burden * 100
    })

kpi_df = pd.DataFrame(kpi_results)
print("KPI Summary:")
print(kpi_df)
```

---

## Custom Strategies

### Inflation-Adjusted Income

```python
from finbricklab.core.interfaces import IFlowStrategy
from finbricklab.core.registry import FlowRegistry

class InflationAdjustedIncome(IFlowStrategy):
    """Income that adjusts with inflation."""

    def route(self, context, spec, links):
        base_amount = spec["base_amount"]
        inflation_pa = spec.get("inflation_pa", 0.02)

        # Calculate inflation adjustment
        years_elapsed = context.current_month / 12
        inflation_factor = (1 + inflation_pa) ** years_elapsed
        adjusted_amount = base_amount * inflation_factor

        return {links["to"]: adjusted_amount}

# Register the strategy
FlowRegistry.register("f.income.inflation_adjusted", InflationAdjustedIncome())

# Use in scenario
salary = FBrick(
    id="salary",
    name="Inflation-Adjusted Salary",
    kind="f.income.inflation_adjusted",
    links={"to": {"to_cash": "checking"}},
    spec={
        "base_amount": 5000.0,
        "inflation_pa": 0.025
    }
)
```

### Variable Rate Mortgage

```python
from finbricklab.core.interfaces import IScheduleStrategy
from finbricklab.core.registry import ScheduleRegistry

class VariableRateMortgage(IScheduleStrategy):
    """Mortgage with variable interest rate."""

    def schedule(self, context, spec):
        principal = spec["principal"]
        initial_rate = spec["initial_rate_pa"]
        rate_adjustments = spec.get("rate_adjustments", {})

        # Get current rate (with adjustments)
        current_rate = initial_rate
        for month, adjustment in rate_adjustments.items():
            if context.current_month >= month:
                current_rate += adjustment

        # Calculate payment (simplified)
        monthly_rate = current_rate / 12
        payment = principal * monthly_rate * (1 + monthly_rate) ** spec["term_months"] / ((1 + monthly_rate) ** spec["term_months"] - 1)

        return [Event(
            time=context.current_date,
            kind="payment",
            data={"amount": -payment, "principal": -payment * 0.7, "interest": -payment * 0.3}
        )]

# Register the strategy
ScheduleRegistry.register("l.mortgage.variable", VariableRateMortgage())

# Use in scenario
variable_mortgage = LBrick(
    id="variable_mortgage",
    name="Variable Rate Mortgage",
    kind="l.mortgage.variable",
    spec={
        "principal": 400000,
        "initial_rate_pa": 0.035,
        "term_months": 360,
        "rate_adjustments": {
            24: 0.01,  # 1% increase after 2 years
            60: 0.005  # 0.5% increase after 5 years
        }
    }
)
```

---

## Real-World Scenarios

### Young Professional's Financial Plan

```python
from finbricklab import Entity, Scenario, ABrick, FBrick

# Assets
emergency_fund = ABrick(
    id="emergency_fund",
    name="Emergency Fund",
    kind="a.cash",
    spec={"initial_balance": 10000.0, "interest_pa": 0.025}
)

retirement_401k = ABrick(
    id="retirement_401k",
    name="401(k) Retirement",
    kind="a.security.unitized",
    spec={
        "initial_units": 100.0,
        "initial_price": 100.0,
        "drift_pa": 0.07,
        "volatility_pa": 0.15
    }
)

# Income
salary = FBrick(
    id="salary",
    name="Monthly Salary",
    kind="f.income.recurring",
    links={"to": {"to_emergency": "emergency_fund"}},
    spec={
        "amount_monthly": 6000.0,
        "activation_window": {"start_date": "2026-01-01", "end_date": "2046-01-01"}
    }
)

# Expenses
rent = FBrick(
    id="rent",
    name="Rent",
    kind="f.expense.recurring",
    links={"from": {"from_emergency": "emergency_fund"}},
    spec={
        "amount_monthly": 2000.0,
        "activation_window": {"start_date": "2026-01-01", "end_date": "2046-01-01"}
    }
)

living_expenses = FBrick(
    id="living_expenses",
    name="Living Expenses",
    kind="f.expense.recurring",
    links={"from": {"from_emergency": "emergency_fund"}},
    spec={
        "amount_monthly": 1500.0,
        "activation_window": {"start_date": "2026-01-01", "end_date": "2046-01-01"}
    }
)

# 401(k) contributions
retirement_contribution = FBrick(
    id="retirement_contribution",
    name="401(k) Contribution",
    kind="f.transfer.lumpsum",
    links={
        "from": {"from_emergency": "emergency_fund"},
        "to": {"to_retirement": "retirement_401k"}
    },
    spec={
        "amount": -600.0,  # $600/month
        "activation_window": {"start_date": "2026-01-01", "end_date": "2046-01-01"}
    }
)

# Create scenario
young_professional = Scenario(
    id="young_professional",
    name="Young Professional Plan",
    bricks=[emergency_fund, retirement_401k, salary, rent, living_expenses, retirement_contribution]
)

# Run scenario
young_professional.run(start=date(2026, 1, 1), months=240)

# Analyze results
results = young_professional.to_canonical_frame()
print(f"Emergency fund: ${results['cash'].iloc[-1]:,.2f}")
print(f"Retirement savings: ${results['liquid_assets'].iloc[-1]:,.2f}")
print(f"Total net worth: ${results['net_worth'].iloc[-1]:,.2f}")
```

### Family Home Purchase

```python
from finbricklab import Entity, Scenario, ABrick, LBrick, FBrick

# Create multiple home purchase scenarios
def create_home_scenario(scenario_id: str, name: str, down_payment_pct: float, rate_pa: float):
    """Create a home purchase scenario."""

    # Property
    house = ABrick(
        id=f"{scenario_id}_house",
        name="Family Home",
        kind="a.property",
        spec={
            "initial_value": 500000.0,
            "appreciation_pa": 0.025,
            "fees_pct": 0.06
        }
    )

    # Mortgage
    mortgage = LBrick(
        id=f"{scenario_id}_mortgage",
        name="Home Loan",
        kind="l.loan.annuity",
        links={"principal": {"from_house": f"{scenario_id}_house"}},
        spec={"rate_pa": rate_pa, "term_months": 360}
    )

    # Cash for down payment
    cash = ABrick(
        id=f"{scenario_id}_cash",
        name="Purchase Cash",
        kind="a.cash",
        spec={"initial_balance": 500000.0 * down_payment_pct, "interest_pa": 0.03}
    )

    # Down payment
    down_payment = FBrick(
        id=f"{scenario_id}_down_payment",
        name="Down Payment",
        kind="f.transfer.lumpsum",
        links={
            "to": {"to_house": f"{scenario_id}_house"},
            "from": {"from_cash": f"{scenario_id}_cash"}
        },
        spec={
            "amount": -500000.0 * down_payment_pct,
            "activation_window": {"start_date": "2026-01-01", "duration_m": 1}
        }
    )

    # Monthly income
    income = FBrick(
        id=f"{scenario_id}_income",
        name="Monthly Income",
        kind="f.income.recurring",
        links={"to": {"to_cash": f"{scenario_id}_cash"}},
        spec={
            "amount_monthly": 8000.0,
            "activation_window": {"start_date": "2026-01-01", "end_date": "2036-01-01"}
        }
    )

    # Living expenses
    expenses = FBrick(
        id=f"{scenario_id}_expenses",
        name="Living Expenses",
        kind="f.expense.recurring",
        links={"from": {"from_cash": f"{scenario_id}_cash"}},
        spec={
            "amount_monthly": 3000.0,
            "activation_window": {"start_date": "2026-01-01", "end_date": "2036-01-01"}
        }
    )

    return Scenario(
        id=scenario_id,
        name=name,
        bricks=[house, mortgage, cash, down_payment, income, expenses]
    )

# Create different scenarios
low_down_high_rate = create_home_scenario("low_down", "Low Down Payment (5%, 4.5%)", 0.05, 0.045)
high_down_low_rate = create_home_scenario("high_down", "High Down Payment (20%, 3.5%)", 0.20, 0.035)
balanced = create_home_scenario("balanced", "Balanced (10%, 4.0%)", 0.10, 0.040)

# Create entity
home_entity = Entity(
    id="home_purchase",
    name="Home Purchase Strategies",
    scenarios=[low_down_high_rate, high_down_low_rate, balanced]
)

# Run all scenarios
for scenario in home_entity.scenarios:
    scenario.run(start=date(2026, 1, 1), months=120)

# Compare results
comparison_df = home_entity.compare()
print("Home purchase comparison:")
final_results = comparison_df.groupby("scenario_name")["net_worth"].last()
print(final_results)

# Calculate breakeven
breakeven_df = home_entity.breakeven_table("low_down")
print(f"\nBreakeven analysis:\n{breakeven_df}")
```
