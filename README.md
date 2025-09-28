# FinBrickLab

Strategy-Driven Brick Architecture for Financial Scenarios

FinBrickLab is a modular, extensible framework for modeling complex financial scenarios using a strategy-driven brick architecture. It allows you to compose financial instruments as self-contained "bricks" that can be easily combined to create sophisticated financial models.

## Install

```bash
pip install finbricklab
```

## Quickstart

```python
from datetime import date
from finbricklab import Scenario, ABrick, LBrick

# 1) Bricks
cash = ABrick(
    id="cash",
    name="Main Cash",
    kind="a.cash",
    spec={"initial_balance": 50_000.0, "interest_pa": 0.02}
)

house = ABrick(
    id="house",
    name="Primary Residence",
    kind="a.property_discrete",
    spec={
        "initial_value": 400_000.0,
        "fees_pct": 0.05,
        "appreciation_pa": 0.03,
        "sell_on_window_end": False
    }
)

mortgage = LBrick(
    id="mortgage",
    name="Fixed Mortgage",
    kind="l.mortgage.annuity",
    spec={
        # Either provide principal directly...
        "principal": 320_000.0,
        # ...or link to the house (if your engine supports links)
        # "links": {"principal": {"type": "from_house", "house_id": "house", "ltv": 0.8}},

        "rate_pa": 0.035,
        "term_months": 360,
        "start_date": "2026-01-01",
        # Optional: prepayments, fees, etc.
    }
)

# 2) Scenario
scenario = Scenario(
    id="demo",
    name="House Purchase Demo",
    bricks=[cash, house, mortgage]
)

# 3) Run
results = scenario.run(start=date(2026, 1, 1), months=12)

# 4) Inspect
totals = results["totals"]
print("Scenario completed.")
print(f"Final cash balance: {totals['cash'].iloc[-1]:,.2f}")
print(f"Final asset value:  {totals['assets'].iloc[-1]:,.2f}")
print(f"Final debt balance: {totals['liabilities'].iloc[-1]:,.2f}")
```

### Using the CLI

```bash
# Print a sample scenario
finbrick example > demo.json

# Run it for one year starting Jan 2026
finbrick run -i demo.json -o results.json --start 2026-01-01 --months 12

# Validate a scenario (errors by default; use --warn to downgrade)
finbrick validate -i demo.json
```

## Concepts

### Bricks

Financial instruments are modeled as "bricks" with three types:

- **Assets** (`ABrick`): Cash accounts, real estate, investments
- **Liabilities** (`LBrick`): Mortgages, loans, credit cards  
- **Flows** (`FBrick`): Income, expenses, transfers

### Strategies

Brick behavior is determined by their `kind` discriminator and associated strategy:

- **Valuation Strategies**: Handle asset valuation and cash flow generation
- **Schedule Strategies**: Handle liability payment schedules and balance tracking
- **Flow Strategies**: Handle cash flow events like income, expenses, transfers

### Available Strategies

**Assets:**
- `a.cash`: Cash account with interest
- `a.property_discrete`: Real estate with appreciation  
- `a.etf_unitized`: ETF investment with unitized pricing

**Liabilities:**
- `l.mortgage.annuity`: Fixed-rate mortgage with annuity payments

**Flows:**
- `f.transfer.lumpsum`: One-time lump sum transfer
- `f.income.fixed`: Fixed monthly income with escalation
- `f.expense.fixed`: Fixed monthly expenses

## Roadmap

- [ ] Plugin system for custom strategies
- [ ] CLI tools for scenario analysis
- [ ] Interactive documentation and examples
- [ ] Performance optimizations for large scenarios

## Development

```bash
# Clone and setup
git clone https://github.com/your-org/finbricklab
cd finbricklab
poetry install

# Run tests
pytest

# Lint and format
ruff check .
black .

# Build package
poetry build
```

## License

Apache-2.0 License - see LICENSE file for details.