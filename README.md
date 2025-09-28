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

# Create financial bricks
cash = ABrick(
    id="cash", 
    name="Main Cash", 
    kind="a.cash",
    spec={"initial_balance": 50000.0, "interest_pa": 0.02}
)

house = ABrick(
    id="house", 
    name="Primary Residence", 
    kind="a.property_discrete",
    spec={
        "initial_value": 400000.0,
        "appreciation_pa": 0.03,
        "sell_on_window_end": False
    }
)

mortgage = LBrick(
    id="mortgage", 
    name="Home Loan", 
    kind="l.mortgage.annuity",
    links={"principal": {"from_house": "house"}},
    spec={
        "rate_pa": 0.034, 
        "term_months": 300,
        "loan_to_value": 0.8
    }
)

# Create and run scenario
scenario = Scenario(
    id="demo", 
    name="House Purchase Demo", 
    bricks=[cash, house, mortgage]
)
results = scenario.run(start=date(2026, 1, 1), months=12)

# View results
print("Scenario completed successfully!")
print(f"Final cash balance: ${results['totals']['cash_balance'][-1]:,.2f}")
print(f"Final house value: ${results['totals']['asset_value'][-1]:,.2f}")
print(f"Final mortgage balance: ${results['totals']['debt_balance'][-1]:,.2f}")
```

### Using the CLI

You can also use the command-line interface:

```bash
# Generate an example scenario
finbrick example > my_scenario.json

# Validate the scenario
finbrick validate -i my_scenario.json

# Run the scenario
finbrick run -i my_scenario.json -o results.json --months 12

# View results
cat results.json
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

MIT License - see LICENSE file for details.