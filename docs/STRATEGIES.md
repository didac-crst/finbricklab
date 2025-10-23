# FinBrickLab Strategy Catalog

Complete reference for all available strategies in FinBrickLab.

## Table of Contents

* [Asset Strategies](#asset-strategies)
* [Liability Strategies](#liability-strategies)
* [Flow Strategies](#flow-strategies)
* [Transfer Strategies](#transfer-strategies)
* [Strategy Registration](#strategy-registration)
* [Custom Strategies](#custom-strategies)

---

## Asset Strategies

### a.cash

**Purpose**: Cash account with interest accrual.

**Specification**:
```json
{
  "initial_balance": 0.0,
  "interest_pa": 0.02
}
```

**Parameters**:
- `initial_balance` (float): Starting cash balance
- `interest_pa` (float): Annual interest rate (e.g., 0.02 for 2%)

**Example**:
```python
cash = ABrick(
    id="emergency_fund",
    name="Emergency Fund",
    kind="a.cash",
    spec={
        "initial_balance": 10000.0,
        "interest_pa": 0.025
    }
)
```

**Behavior**:
- Earns interest monthly (compounded)
- No fees or restrictions
- Immediate liquidity

### a.property_discrete

**Purpose**: Real estate investment with appreciation and transaction costs.

**Specification**:
```json
{
  "initial_value": 420000.0,
  "appreciation_pa": 0.03,
  "fees_pct": 0.095,
  "sell_on_window_end": false
}
```

**Parameters**:
- `initial_value` (float): Property purchase price
- `appreciation_pa` (float): Annual appreciation rate
- `fees_pct` (float): Transaction fees as percentage (e.g., 0.095 for 9.5%)
- `sell_on_window_end` (bool): Whether to sell at end of activation window

**Example**:
```python
house = ABrick(
    id="family_home",
    name="Family Home",
    kind="a.property_discrete",
    spec={
        "initial_value": 500000.0,
        "appreciation_pa": 0.025,
        "fees_pct": 0.06,
        "sell_on_window_end": True
    }
)
```

**Behavior**:
- Appreciates monthly (compounded)
- Transaction fees applied on sale
- Illiquid asset (cannot be partially sold)

### a.etf_unitized

**Purpose**: ETF investment with unitized pricing, drift, and volatility.

**Specification**:
```json
{
  "initial_units": 100.0,
  "initial_price": 50.0,
  "drift_pa": 0.07,
  "volatility_pa": 0.15,
  "liquidation_threshold": 0.0,
  "sell_on_window_end": false
}
```

**Parameters**:
- `initial_units` (float): Starting number of units
- `initial_price` (float): Starting price per unit
- `drift_pa` (float): Expected annual return
- `volatility_pa` (float): Annual volatility (0 = deterministic)
- `liquidation_threshold` (float): Auto-liquidate if value drops below this
- `sell_on_window_end` (bool): Whether to sell at end of activation window

**Example**:
```python
etf = ABrick(
    id="stock_portfolio",
    name="Stock Portfolio",
    kind="a.etf_unitized",
    spec={
        "initial_units": 1000.0,
        "initial_price": 100.0,
        "drift_pa": 0.08,
        "volatility_pa": 0.20,
        "liquidation_threshold": 50000.0,
        "sell_on_window_end": False
    }
)
```

**Behavior**:
- Price follows geometric Brownian motion
- Can be partially liquidated
- Liquidation threshold triggers automatic sale

---

## Liability Strategies

### l.mortgage.annuity

**Purpose**: Fixed-rate mortgage with annuity payments.

**Specification**:
```json
{
  "rate_pa": 0.034,
  "term_months": 300,
  "fees_financed_pct": 0.0
}
```

**Parameters**:
- `rate_pa` (float): Annual interest rate
- `term_months` (int): Loan term in months
- `fees_financed_pct` (float): Percentage of fees financed (default 0.0)

**Example**:
```python
mortgage = LBrick(
    id="home_loan",
    name="Home Loan",
    kind="l.mortgage.annuity",
    links={"principal": {"from_house": "family_home"}},
    spec={
        "rate_pa": 0.035,
        "term_months": 360,
        "fees_financed_pct": 0.0
    }
)
```

**Behavior**:
- Fixed monthly payment (principal + interest)
- Principal amount determined by linked property
- Interest calculated on remaining balance

**Links**:
- `principal`: Links to property asset to determine loan amount

---

## Flow Strategies

### f.transfer.lumpsum

**Purpose**: One-time lump sum transfer between accounts.

**Specification**:
```json
{
  "amount": 50000.0,
  "activation_window": {
    "start_date": "2026-06-01",
    "duration_m": 1
  }
}
```

**Parameters**:
- `amount` (float): Transfer amount (negative for outflows)
- `activation_window`: When the transfer occurs
  - `start_date` (date): Start of activation window
  - `duration_m` (int): Duration in months
  - `end_date` (date, optional): Alternative to duration_m

**Example**:
```python
down_payment = FBrick(
    id="down_payment",
    name="Down Payment",
    kind="f.transfer.lumpsum",
    links={
        "to": {"to_house": "family_home"},
        "from": {"from_cash": "savings_account"}
    },
    spec={
        "amount": -50000.0,
        "activation_window": {
            "start_date": "2026-06-01",
            "duration_m": 1
        }
    }
)
```

**Links**:
- `to`: Destination brick (positive amount flows here)
- `from`: Source brick (negative amount flows from here)

### f.income.fixed

**Purpose**: Fixed recurring income.

**Specification**:
```json
{
  "amount_monthly": 5000.0,
  "activation_window": {
    "start_date": "2026-01-01",
    "end_date": "2036-01-01"
  }
}
```

**Parameters**:
- `amount_monthly` (float): Monthly income amount
- `activation_window`: When income is received
  - `start_date` (date): First payment date
  - `end_date` (date): Last payment date
  - `duration_m` (int, optional): Alternative to end_date

**Example**:
```python
salary = FBrick(
    id="salary",
    name="Monthly Salary",
    kind="f.income.fixed",
    links={"to": {"to_cash": "checking_account"}},
    spec={
        "amount_monthly": 6000.0,
        "activation_window": {
            "start_date": "2026-01-01",
            "end_date": "2036-01-01"
        }
    }
)
```

**Links**:
- `to`: Destination brick (typically cash account)

### f.expense.fixed

**Purpose**: Fixed recurring expense.

**Specification**:
```json
{
  "amount_monthly": 2000.0,
  "activation_window": {
    "start_date": "2026-01-01",
    "end_date": "2036-01-01"
  }
}
```

**Parameters**:
- `amount_monthly` (float): Monthly expense amount (positive value)
- `activation_window`: When expense is paid
  - `start_date` (date): First payment date
  - `end_date` (date): Last payment date
  - `duration_m` (int, optional): Alternative to end_date

**Example**:
```python
rent = FBrick(
    id="rent",
    name="Monthly Rent",
    kind="f.expense.fixed",
    links={"from": {"from_cash": "checking_account"}},
    spec={
        "amount_monthly": 2500.0,
        "activation_window": {
            "start_date": "2026-01-01",
            "end_date": "2036-01-01"
        }
    }
)
```

**Links**:
- `from`: Source brick (typically cash account)

---

## Transfer Strategies

### t.transfer.lumpsum

**Purpose**: One-time internal transfer between accounts.

**Specification**:
```json
{
  "amount": 5000.0,
  "currency": "EUR"
}
```

**Parameters**:
- `amount` (float): Transfer amount (must be positive)
- `currency` (str): Currency code (e.g., "EUR", "USD")

**Links**:
- `from` (str): Source account ID
- `to` (str): Destination account ID

**Example**:
```python
transfer = TBrick(
    id="emergency_transfer",
    name="Emergency Transfer",
    kind="t.transfer.lumpsum",
    spec={"amount": 5000.0, "currency": "EUR"},
    links={"from": "checking", "to": "savings"}
)
```

**Behavior**:
- Creates balanced journal entries (debit from source, credit to destination)
- Validates that both accounts are internal
- Ensures zero-sum transaction

### t.transfer.recurring

**Purpose**: Recurring internal transfer between accounts.

**Specification**:
```json
{
  "amount": 1000.0,
  "currency": "EUR",
  "freq": "MONTHLY",
  "day": 1
}
```

**Parameters**:
- `amount` (float): Transfer amount per period
- `currency` (str): Currency code
- `freq` (str): Frequency ("MONTHLY", "QUARTERLY", "YEARLY")
- `day` (int): Day of month for monthly transfers (1-28)

**Links**:
- `from` (str): Source account ID
- `to` (str): Destination account ID

**Example**:
```python
monthly_save = TBrick(
    id="monthly_save",
    name="Monthly Savings",
    kind="t.transfer.recurring",
    spec={"amount": 1000.0, "currency": "EUR", "freq": "MONTHLY", "day": 1},
    links={"from": "checking", "to": "savings"}
)
```

**Behavior**:
- Creates recurring transfer events
- Respects activation windows
- Generates journal entries for each occurrence

### t.transfer.scheduled

**Purpose**: Scheduled internal transfers on specific dates.

**Specification**:
```json
{
  "schedule": [
    {
      "date": "2026-06-01",
      "amount": 2000.0,
      "currency": "EUR"
    },
    {
      "date": "2026-12-01", 
      "amount": 5000.0,
      "currency": "EUR"
    }
  ]
}
```

**Parameters**:
- `schedule` (list): List of transfer events
  - `date` (str): Transfer date (YYYY-MM-DD)
  - `amount` (float): Transfer amount
  - `currency` (str): Currency code

**Links**:
- `from` (str): Source account ID
- `to` (str): Destination account ID

**Example**:
```python
bonus_transfer = TBrick(
    id="bonus_transfer",
    name="Bonus Transfer",
    kind="t.transfer.scheduled",
    spec={
        "schedule": [
            {"date": "2026-06-01", "amount": 2000.0, "currency": "EUR"},
            {"date": "2026-12-01", "amount": 5000.0, "currency": "EUR"}
        ]
    },
    links={"from": "checking", "to": "savings"}
)
```

**Behavior**:
- Creates transfers on specified dates
- Handles multiple currencies
- Validates date format and amounts

---

## Strategy Registration

### Automatic Registration

Most strategies are registered automatically when you import the strategies module:

```python
import finbricklab.strategies  # Registers all default strategies
```

### Manual Registration

For custom strategies, register them explicitly:

```python
from finbricklab.core.registry import ValuationRegistry

class MyCustomStrategy:
    def value(self, context, spec):
        return spec["custom_value"]

# Register the strategy
ValuationRegistry.register("a.custom", MyCustomStrategy())
```

---

## Custom Strategies

### Creating a Custom Asset Strategy

```python
from finbricklab.core.interfaces import IValuationStrategy
from finbricklab.core.context import ScenarioContext

class BondStrategy(IValuationStrategy):
    """Custom bond strategy with coupon payments."""

    def value(self, context: ScenarioContext, spec: dict) -> float:
        """Calculate bond value including accrued interest."""
        face_value = spec["face_value"]
        coupon_rate = spec["coupon_rate"]
        current_price = spec.get("current_price", face_value)

        # Calculate accrued interest
        months_held = context.current_month - spec["purchase_month"]
        accrued_interest = face_value * coupon_rate * (months_held / 12)

        return current_price + accrued_interest

# Register the strategy
from finbricklab.core.registry import ValuationRegistry
ValuationRegistry.register("a.bond", BondStrategy())
```

### Creating a Custom Flow Strategy

```python
from finbricklab.core.interfaces import IFlowStrategy

class VariableIncomeStrategy(IFlowStrategy):
    """Income that varies with inflation."""

    def route(self, context: ScenarioContext, spec: dict, links: dict) -> dict:
        """Calculate inflation-adjusted income."""
        base_amount = spec["base_amount"]
        inflation_rate = spec.get("inflation_pa", 0.02)

        # Adjust for inflation
        months_elapsed = context.current_month
        inflation_factor = (1 + inflation_rate) ** (months_elapsed / 12)
        adjusted_amount = base_amount * inflation_factor

        return {links["to"]: adjusted_amount}

# Register the strategy
from finbricklab.core.registry import FlowRegistry
FlowRegistry.register("f.income.variable", VariableIncomeStrategy())
```

---

## Strategy Best Practices

### Naming Conventions

- **Assets**: `a.{category}` (e.g., `a.cash`, `a.property`, `a.bond`)
- **Liabilities**: `l.{type}.{subtype}` (e.g., `l.mortgage.annuity`, `l.loan.fixed`)
- **Flows**: `f.{type}.{subtype}` (e.g., `f.income.fixed`, `f.expense.variable`)

### Parameter Design

1. **Use Descriptive Names**: `initial_balance` not `init_bal`
2. **Include Units**: `rate_pa` for per-annum rates
3. **Provide Defaults**: Use sensible defaults where possible
4. **Validate Inputs**: Check parameter ranges and types

### Performance Considerations

1. **Efficient Calculations**: Avoid expensive operations in tight loops
2. **Cache Results**: Store computed values when appropriate
3. **Minimize Dependencies**: Reduce coupling between strategies
4. **Test Thoroughly**: Include edge cases and boundary conditions

### Testing Strategies

```python
def test_bond_strategy():
    """Test custom bond strategy."""
    strategy = BondStrategy()
    context = ScenarioContext(current_month=6, ...)
    spec = {
        "face_value": 10000,
        "coupon_rate": 0.05,
        "purchase_month": 0
    }

    value = strategy.value(context, spec)
    expected = 10000 + (10000 * 0.05 * 0.5)  # 6 months of interest

    assert abs(value - expected) < 0.01
```

---

## Common Patterns

### Activation Windows

All strategies support activation windows to control when they're active:

```python
activation_window = {
    "start_date": "2026-01-01",    # Start date
    "end_date": "2030-01-01",      # End date (inclusive)
    # OR
    "duration_m": 48               # Duration in months
}
```

### Linking Bricks

Use links to create dependencies between bricks:

```python
links = {
    "principal": {"from_property": "house"},     # Link to property value
    "to": {"to_account": "savings"},            # Link to destination
    "from": {"from_account": "checking"}        # Link to source
}
```

### Error Handling

Strategies should handle edge cases gracefully:

```python
def value(self, context: ScenarioContext, spec: dict) -> float:
    """Calculate value with error handling."""
    try:
        # Main calculation
        return self._calculate_value(context, spec)
    except KeyError as e:
        raise ConfigError(f"Missing required parameter: {e}")
    except ValueError as e:
        raise ConfigError(f"Invalid parameter value: {e}")
```
