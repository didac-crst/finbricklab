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
from finbricklab import Scenario, ABrick, LBrick, FBrick

# Create financial bricks
cash = ABrick(id="cash", name="Main Cash", kind="a.cash",
              spec={"initial_balance": 0.0, "interest_pa": 0.02})

house = ABrick(id="house", name="Property", kind="a.property",
               spec={"price": 420_000, "fees_pct": 0.095, "appreciation_pa": 0.02})

mortgage = LBrick(id="mortgage", name="Home Loan", kind="l.mortgage.annuity",
                  links={"principal": {"from_house": "house"}},
                  spec={"rate_pa": 0.034, "term_months": 300})

# Create and run scenario
scenario = Scenario(id="demo", name="House Purchase", 
                   bricks=[cash, house, mortgage])
results = scenario.run(start=date(2026, 1, 1), months=360)

# View results
print(results["totals"].head())
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
- `a.property`: Real estate with appreciation  
- `a.invest.etf`: ETF investment with price drift

**Liabilities:**
- `l.mortgage.annuity`: Fixed-rate mortgage with annuity payments

**Flows:**
- `f.transfer.lumpsum`: One-time lump sum transfer
- `f.income.salary`: Fixed monthly income with escalation
- `f.expense.living`: Fixed monthly expenses

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