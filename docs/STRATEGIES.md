# FinBrickLab Strategy Catalog

Complete reference for all available strategies in FinBrickLab.

## Table of Contents

* [Asset Strategies](#asset-strategies)
* [Liability Strategies](#liability-strategies)
* [Flow Strategies](#flow-strategies)
* [Transfer Strategies](#transfer-strategies)

---

## Asset Strategies

### K.A_CASH

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
from finbricklab.core.kinds import K

cash = ABrick(
    id="emergency_fund",
    name="Emergency Fund",
    kind=K.A_CASH,
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

### K.A_PROPERTY

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
from finbricklab.core.kinds import K

house = ABrick(
    id="family_home",
    name="Family Home",
    kind=K.A_PROPERTY,
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

### K.A_SECURITY_UNITIZED

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
from finbricklab.core.kinds import K

etf = ABrick(
    id="stock_portfolio",
    name="Stock Portfolio",
    kind=K.A_SECURITY_UNITIZED,
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

### K.A_PRIVATE_EQUITY

**Purpose**: Private equity investment with deterministic marking.

**Specification**:
```json
{
  "initial_value": 100000.0,
  "drift_pa": 0.12,
  "valuation_frequency": "annual"
}
```

**Parameters**:
- `initial_value` (float): Initial investment value
- `drift_pa` (float): Expected annual return
- `valuation_frequency` (str): How often to mark to market ("annual", "quarterly", "monthly")

**Example**:
```python
from finbricklab.core.kinds import K

pe_fund = ABrick(
    id="pe_investment",
    name="Private Equity Fund",
    kind=K.A_PRIVATE_EQUITY,
    spec={
        "initial_value": 100000.0,
        "drift_pa": 0.12,
        "valuation_frequency": "annual"
    }
)
```

**Behavior**:
- Deterministic value growth based on drift
- Valuation updates at specified frequency
- Illiquid asset (no partial liquidation)

---

## Liability Strategies

### K.L_LOAN_ANNUITY

**Purpose**: Fixed-rate mortgage with annuity payments.

**Specification**:
```json
{
  "principal": 320000.0,
  "rate_pa": 0.034,
  "term_months": 300,
  "start_date": "2026-01-01"
}
```

**Parameters**:
- `principal` (float): Loan principal amount
- `rate_pa` (float): Annual interest rate
- `term_months` (int): Loan term in months
- `start_date` (str): Loan start date (YYYY-MM-DD)

**Example**:
```python
from finbricklab.core.kinds import K

mortgage = LBrick(
    id="home_loan",
    name="Home Loan",
    kind=K.L_LOAN_ANNUITY,
    spec={
        "principal": 320000.0,
        "rate_pa": 0.035,
        "term_months": 360,
        "start_date": "2026-01-01"
    }
)
```

**Behavior**:
- Fixed monthly payment (principal + interest)
- Interest calculated on remaining balance
- Amortization schedule follows standard annuity formula

### K.L_LOAN_BALLOON

**Purpose**: Balloon payment loan with interest-only or partial amortization periods.

**Specification**:
```json
{
  "principal": 500000.0,
  "rate_pa": 0.06,
  "term_months": 60,
  "amortization": {
    "type": "interest_only",
    "amort_months": 0
  },
  "balloon_at_maturity": "full",
  "start_date": "2026-01-01"
}
```

**Parameters**:
- `principal` (float): Loan principal amount
- `rate_pa` (float): Annual interest rate
- `term_months` (int): Loan term in months
- `amortization` (dict): Amortization configuration
  - `type` (str): "interest_only" or "linear"
  - `amort_months` (int): Months of amortization (0 for interest-only)
- `balloon_at_maturity` (str): "full" or "residual"
- `start_date` (str): Loan start date (YYYY-MM-DD)

**Example**:
```python
from finbricklab.core.kinds import K

balloon_loan = LBrick(
    id="business_loan",
    name="Business Loan",
    kind=K.L_LOAN_BALLOON,
    spec={
        "principal": 500000.0,
        "rate_pa": 0.06,
        "term_months": 60,
        "amortization": {"type": "interest_only", "amort_months": 0},
        "balloon_at_maturity": "full",
        "start_date": "2026-01-01"
    }
)
```

**Behavior**:
- Interest-only payments during specified period
- Balloon payment of remaining balance at maturity
- Optional partial amortization before balloon

### K.L_CREDIT_LINE

**Purpose**: Revolving credit line with interest accrual and minimum payments.

**Specification**:
```json
{
  "credit_limit": 10000.0,
  "rate_pa": 0.18,
  "min_payment": {
    "type": "percent",
    "percent": 0.02,
    "floor": 25.0
  },
  "billing_day": 15,
  "start_date": "2026-01-01"
}
```

**Parameters**:
- `credit_limit` (float): Maximum credit limit
- `rate_pa` (float): Annual percentage rate (APR)
- `min_payment` (dict): Minimum payment configuration
  - `type` (str): "percent", "interest_only", or "fixed_or_percent"
  - `percent` (float): Percentage of balance (for percent types)
  - `floor` (float): Minimum payment floor
- `billing_day` (int): Day of month for billing cycle
- `start_date` (str): Credit line start date (YYYY-MM-DD)

**Example**:
```python
from finbricklab.core.kinds import K

credit_card = LBrick(
    id="credit_card",
    name="Credit Card",
    kind=K.L_CREDIT_LINE,
    spec={
        "credit_limit": 10000.0,
        "rate_pa": 0.18,
        "min_payment": {"type": "percent", "percent": 0.02, "floor": 25.0},
        "billing_day": 15,
        "start_date": "2026-01-01"
    }
)
```

**Behavior**:
- Interest accrues on outstanding balance
- Minimum payments calculated based on policy
- Credit limit enforcement
- Revolving credit (can pay down and borrow again)

### K.L_CREDIT_FIXED

**Purpose**: Fixed-term credit with linear amortization.

**Specification**:
```json
{
  "principal": 15000.0,
  "rate_pa": 0.08,
  "term_months": 36,
  "start_date": "2026-01-01"
}
```

**Parameters**:
- `principal` (float): Loan principal amount
- `rate_pa` (float): Annual interest rate
- `term_months` (int): Loan term in months
- `start_date` (str): Loan start date (YYYY-MM-DD)

**Example**:
```python
from finbricklab.core.kinds import K

personal_loan = LBrick(
    id="personal_loan",
    name="Personal Loan",
    kind=K.L_CREDIT_FIXED,
    spec={
        "principal": 15000.0,
        "rate_pa": 0.08,
        "term_months": 36,
        "start_date": "2026-01-01"
    }
)
```

**Behavior**:
- Equal principal payments each month
- Interest calculated on outstanding balance
- Linear amortization schedule
- Fixed term (no revolving)

---

## Flow Strategies

### K.F_INCOME_RECURRING

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
from finbricklab.core.kinds import K

salary = FBrick(
    id="salary",
    name="Monthly Salary",
    kind=K.F_INCOME_RECURRING,
    spec={
        "amount_monthly": 6000.0,
        "activation_window": {
            "start_date": "2026-01-01",
            "end_date": "2036-01-01"
        }
    }
)
```

**Behavior**:
- Fixed monthly income payments
- No routing needed - Journal system handles automatically
- Respects activation windows

### K.F_INCOME_ONE_TIME

**Purpose**: One-time income event.

**Specification**:
```json
{
  "amount": 10000.0,
  "date": "2026-06-01",
  "tax_rate": 0.25
}
```

**Parameters**:
- `amount` (float): Income amount
- `date` (str): Income date (YYYY-MM-DD)
- `tax_rate` (float, optional): Tax rate on this income (default 0.0)

**Example**:
```python
from finbricklab.core.kinds import K

bonus = FBrick(
    id="bonus",
    name="Annual Bonus",
    kind=K.F_INCOME_ONE_TIME,
    spec={
        "amount": 10000.0,
        "date": "2026-06-01",
        "tax_rate": 0.25
    }
)
```

**Behavior**:
- Single income event on specified date
- Tax calculation included
- No routing needed - Journal system handles automatically

### K.F_EXPENSE_RECURRING

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
from finbricklab.core.kinds import K

rent = FBrick(
    id="rent",
    name="Monthly Rent",
    kind=K.F_EXPENSE_RECURRING,
    spec={
        "amount_monthly": 2500.0,
        "activation_window": {
            "start_date": "2026-01-01",
            "end_date": "2036-01-01"
        }
    }
)
```

**Behavior**:
- Fixed monthly expense payments
- No routing needed - Journal system handles automatically
- Respects activation windows

### K.F_EXPENSE_ONE_TIME

**Purpose**: One-time expense event.

**Specification**:
```json
{
  "amount": 5000.0,
  "date": "2026-03-15",
  "tax_deductible": true,
  "tax_rate": 0.25
}
```

**Parameters**:
- `amount` (float): Expense amount
- `date` (str): Expense date (YYYY-MM-DD)
- `tax_deductible` (bool, optional): Whether expense is tax deductible (default false)
- `tax_rate` (float, optional): Tax rate for deduction (default 0.0)

**Example**:
```python
from finbricklab.core.kinds import K

major_purchase = FBrick(
    id="car_purchase",
    name="Car Purchase",
    kind=K.F_EXPENSE_ONE_TIME,
    spec={
        "amount": 25000.0,
        "date": "2026-03-15",
        "tax_deductible": false,
        "tax_rate": 0.0
    }
)
```

**Behavior**:
- Single expense event on specified date
- Optional tax deduction calculation
- No routing needed - Journal system handles automatically

## Transfer Strategies

### K.T_TRANSFER_LUMP_SUM

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
from finbricklab.core.kinds import K

transfer = TBrick(
    id="emergency_transfer",
    name="Emergency Transfer",
    kind=K.T_TRANSFER_LUMP_SUM,
    spec={"amount": 5000.0, "currency": "EUR"},
    links={"from": "checking", "to": "savings"}
)
```

**Behavior**:
- Creates balanced journal entries (debit from source, credit to destination)
- Validates that both accounts are internal
- Ensures zero-sum transaction

### K.T_TRANSFER_RECURRING

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
from finbricklab.core.kinds import K

monthly_save = TBrick(
    id="monthly_save",
    name="Monthly Savings",
    kind=K.T_TRANSFER_RECURRING,
    spec={"amount": 1000.0, "currency": "EUR", "freq": "MONTHLY", "day": 1},
    links={"from": "checking", "to": "savings"}
)
```

**Behavior**:
- Creates recurring transfer events
- Respects activation windows
- Generates journal entries for each occurrence

### K.T_TRANSFER_SCHEDULED

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
from finbricklab.core.kinds import K

bonus_transfer = TBrick(
    id="bonus_transfer",
    name="Bonus Transfer",
    kind=K.T_TRANSFER_SCHEDULED,
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
