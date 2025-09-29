# Entity & Canonical Schema

This document describes the Entity system and canonical schema for financial scenario comparison and visualization in FinBrickLab.

## Overview

The Entity system provides a clean, consistent way to group and compare multiple financial scenarios. It introduces a canonical schema that ensures all scenarios emit the same data structure, enabling apples-to-apples comparisons and standardized visualizations.

## Entity Class

The `Entity` class serves as the top-level aggregator for multiple financial scenarios.

### Key Features

- **Multi-scenario comparison**: Compare multiple scenarios side-by-side
- **Benchmarking**: Define baseline scenarios for breakeven analysis
- **Consistent schema**: All scenarios emit data in the same canonical format
- **KPI calculations**: Built-in metrics like liquidity runway, breakeven analysis, and fee/tax summaries

### Basic Usage

```python
from finbricklab.core.entity import Entity
from finbricklab.core.scenario import Scenario

# Create scenarios
scenario1 = Scenario(id="conservative", name="Conservative", bricks=[...])
scenario2 = Scenario(id="aggressive", name="Aggressive", bricks=[...])

# Run scenarios
scenario1.run(start=date(2026, 1, 1), months=36)
scenario2.run(start=date(2026, 1, 1), months=36)

# Create entity
entity = Entity(
    id="my_entity",
    name="My Financial Entity",
    base_currency="EUR",
    scenarios=[scenario1, scenario2],
    benchmarks={"baseline": "conservative"}
)

# Compare scenarios
comparison_df = entity.compare(["conservative", "aggressive"])
```

## Canonical Schema

All scenarios must emit data in the canonical schema format through the `to_canonical_frame()` method.

### Required Columns

| Column | Type | Description |
|--------|------|-------------|
| `date` | datetime64 | Month-end dates (e.g., 2026-01-31) |
| `cash` | float64 | Immediately spendable cash (checking + MMF) |
| `liquid_assets` | float64 | Tradable assets (≤5 business days) |
| `illiquid_assets` | float64 | Non-tradable assets (property, private equity) |
| `liabilities` | float64 | All debt balances |
| `inflows` | float64 | Post-tax income + dividends + rents received |
| `outflows` | float64 | Consumption + rent paid + maintenance + insurance |
| `taxes` | float64 | Tax payments |
| `fees` | float64 | Fee payments |

### Derived Columns

These are computed automatically:

| Column | Type | Description | Formula |
|--------|------|-------------|---------|
| `total_assets` | float64 | Total asset value | `cash + liquid_assets + illiquid_assets` |
| `net_worth` | float64 | Net worth | `total_assets - liabilities` |

### Optional Columns

These enable richer visualizations but are not required:

| Column | Type | Description |
|--------|------|-------------|
| `interest` | float64 | Interest payments |
| `principal` | float64 | Principal payments |
| `mortgage_balance` | float64 | Outstanding mortgage balance |
| `property_value` | float64 | Property market value |
| `owner_equity` | float64 | Property owner equity |
| `contributions` | float64 | Net contributions |
| `market_growth` | float64 | Market-driven growth |
| `rent_paid` | float64 | Rent payments |
| `insurance_premiums` | float64 | Insurance payments |

## Asset Classification Rules

### Liquid Assets
- ETFs and mutual funds
- Listed bonds
- Money market funds
- Cash equivalents
- **Liquidity threshold**: ≤5 business days to convert to cash

### Illiquid Assets
- Real estate (primary residence, investment properties)
- Private equity
- Restricted retirement accounts (where withdrawal is not liquid)
- **Note**: Retirement accounts should be tagged as `restricted=True` and classified by actual withdrawability

### Cash
- Checking accounts
- Savings accounts
- Money market accounts
- **Characteristic**: Immediately spendable, no conversion time

## Key Performance Indicators (KPIs)

### Liquidity Runway
Months of essential expenses covered by current cash.

```
runway_months = cash / rolling_mean(essential_outflows, lookback_months)
essential_outflows = outflows * essential_share  # default: 0.6
```

**Thresholds**:
- <3 months: Red (critical)
- 3-6 months: Orange (caution)
- 6-12 months: Yellow (adequate)
- >12 months: Green (comfortable)

### Breakeven Analysis
First month where scenario net worth ≥ baseline net worth.

```
breakeven_month = first_month_where(net_worth(scenario) - net_worth(baseline) ≥ 0)
```

### Debt Service to Income (DSTI)
Ratio of debt payments to net income.

```
DSTI = (interest + principal) / net_income
```

### Loan-to-Value (LTV)
Ratio of mortgage balance to property value.

```
LTV = mortgage_balance / property_value
```

## Entity Methods

### `compare(scenario_ids=None)`
Returns a tidy DataFrame with canonical columns plus scenario metadata.

```python
comparison_df = entity.compare(["scenario1", "scenario2"])
# Returns DataFrame with columns: date, cash, liquid_assets, ..., scenario_id, scenario_name
```

### `breakeven_table(baseline_id)`
Calculates breakeven months for all scenarios against a baseline.

```python
breakeven_df = entity.breakeven_table("baseline_scenario")
# Returns DataFrame with columns: scenario_id, scenario_name, breakeven_month
```

### `fees_taxes_summary(horizons=[12, 60, 120, 360])`
Calculates cumulative fees and taxes at specified horizons.

```python
summary_df = entity.fees_taxes_summary(horizons=[12, 24, 60])
# Returns DataFrame with columns: scenario_id, scenario_name, horizon_months, cumulative_fees, cumulative_taxes
```

### `liquidity_runway(lookback_months=6, essential_share=0.6)`
Calculates liquidity runway for each scenario.

```python
runway_df = entity.liquidity_runway(lookback_months=3, essential_share=0.5)
# Returns DataFrame with columns: scenario_id, scenario_name, date, cash, essential_outflows, liquidity_runway_months
```

## Chart Functions

Chart functions are available in `finbricklab.charts` and require Plotly installation:

```bash
pip install plotly kaleido
# or
poetry install --extras viz
```

### Entity-Level Charts

#### `net_worth_vs_time(tidy_df)`
Plot net worth over time for multiple scenarios.

```python
from finbricklab.charts import net_worth_vs_time

fig, data = net_worth_vs_time(comparison_df)
fig.show()
```

#### `asset_composition_small_multiples(tidy_df)`
Plot asset composition (cash/liquid/illiquid) as small multiples per scenario.

```python
from finbricklab.charts import asset_composition_small_multiples

fig, data = asset_composition_small_multiples(comparison_df)
fig.show()
```

#### `liquidity_runway_heatmap(tidy_df, runway_df)`
Plot liquidity runway as a heatmap with threshold bands.

```python
from finbricklab.charts import liquidity_runway_heatmap

runway_df = entity.liquidity_runway()
fig, data = liquidity_runway_heatmap(comparison_df, runway_df)
fig.show()
```

#### `cumulative_fees_taxes(tidy_df, summary_df)`
Plot cumulative fees and taxes at different horizons.

```python
from finbricklab.charts import cumulative_fees_taxes

summary_df = entity.fees_taxes_summary()
fig, data = cumulative_fees_taxes(comparison_df, summary_df)
fig.show()
```

#### `net_worth_drawdown(tidy_df)`
Plot net worth drawdown (peak-to-trough) for each scenario.

```python
from finbricklab.charts import net_worth_drawdown

fig, data = net_worth_drawdown(comparison_df)
fig.show()
```

### Scenario-Level Charts

#### `cashflow_waterfall(tidy_df, scenario_name=None)`
Plot annual cashflow waterfall for a single scenario.

```python
from finbricklab.charts import cashflow_waterfall

fig, data = cashflow_waterfall(comparison_df, scenario_name="Conservative")
fig.show()
```

#### `contribution_vs_market_growth(tidy_df, scenario_name=None)`
Plot contribution vs market growth decomposition.

```python
from finbricklab.charts import contribution_vs_market_growth

fig, data = contribution_vs_market_growth(comparison_df, scenario_name="Aggressive")
fig.show()
```

## Migration from Legacy Systems

### Scenario Integration
Existing scenarios automatically support the canonical schema through the `to_canonical_frame()` method:

```python
# Existing scenario
scenario = Scenario(id="my_scenario", name="My Scenario", bricks=[...])
result = scenario.run(start=date(2026, 1, 1), months=36)

# Get canonical frame
canonical_df = scenario.to_canonical_frame()
```

### Currency Normalization
All data should be normalized to the Entity's base currency before emitting the canonical schema. Currency conversion should happen upstream in the scenario execution.

### Backwards Compatibility
The Entity system is fully backwards compatible. Existing scenarios continue to work unchanged, and the canonical schema is an additional output format.

## Best Practices

### Data Quality
- Ensure all scenarios emit the same time periods for fair comparison
- Validate that financial identities hold (e.g., `total_assets = cash + liquid_assets + illiquid_assets`)
- Use consistent currency normalization across all scenarios

### Performance
- The `compare()` method is optimized for fast concatenation and comparison
- Chart functions are designed to work with tidy DataFrames for efficient plotting
- Large scenarios should consider data sampling for visualization

### Error Handling
- Entity methods provide clear error messages for invalid scenario IDs
- Chart functions gracefully handle missing Plotly installation
- All methods handle empty scenarios appropriately

## Examples

### Complete Entity Workflow

```python
from finbricklab.core.entity import Entity
from finbricklab.core.scenario import Scenario
from finbricklab.core.bricks import ABrick
from finbricklab.core.kinds import K
from finbricklab.charts import net_worth_vs_time, asset_composition_small_multiples
from datetime import date

# Create scenarios
cash1 = ABrick(id="cash1", name="Cash 1", kind=K.A_CASH, spec={"initial_balance": 1000.0})
cash2 = ABrick(id="cash2", name="Cash 2", kind=K.A_CASH, spec={"initial_balance": 2000.0})

scenario1 = Scenario(id="conservative", name="Conservative", bricks=[cash1])
scenario2 = Scenario(id="aggressive", name="Aggressive", bricks=[cash2])

# Run scenarios
scenario1.run(start=date(2026, 1, 1), months=12)
scenario2.run(start=date(2026, 1, 1), months=12)

# Create entity
entity = Entity(
    id="my_entity",
    name="My Financial Entity",
    scenarios=[scenario1, scenario2]
)

# Compare scenarios
comparison_df = entity.compare()

# Create visualizations
fig1, _ = net_worth_vs_time(comparison_df)
fig2, _ = asset_composition_small_multiples(comparison_df)

# Analyze breakeven
breakeven_df = entity.breakeven_table("conservative")
print(breakeven_df)

# Check liquidity
runway_df = entity.liquidity_runway()
print(runway_df.head())
```

This Entity system provides a robust foundation for financial scenario analysis, comparison, and visualization while maintaining clean, consistent data structures throughout the FinBrickLab ecosystem.
