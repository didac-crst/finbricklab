# FinScenLab - Strategy-Driven Brick Architecture

A minimal, extensible proof-of-concept for financial scenario modeling using a strategy-driven brick architecture.

## Core Concept

FinScenLab models financial scenarios as collections of "bricks" - self-contained financial instruments that can be composed together. Each brick has a `kind` discriminator that automatically selects the appropriate strategy for simulation.

## Architecture

### Bricks
- **ABrick**: Assets (cash, property, investments)
- **LBrick**: Liabilities (mortgages, loans)  
- **FBrick**: Flows (income, expenses, transfers)

### Strategies
- **IValuationStrategy**: For assets (unitized, discrete, balance/cash)
- **IScheduleStrategy**: For liabilities (annuity, interest-only, fixed-principal)
- **IFlowStrategy**: For flows (income/expense/transfer/policy)

### Registry System
The registry maps `kind` strings to strategy implementations, allowing new behaviors to be added without modifying existing code.

## Key Benefits

1. **Extensible**: Add new behaviors by registering strategies, no class changes
2. **Modular**: Each brick is self-contained with clear interfaces
3. **Composable**: Link bricks together (e.g., mortgage auto-calculates from property)
4. **Explicit**: Cash flows are explicitly routed, no hidden assumptions

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the quickstart notebook:
   ```bash
   jupyter notebook notebooks/01_quickstart.ipynb
   ```

## Example Usage

```python
from datetime import date
from finscenlab.core import Scenario, ABrick, LBrick, FBrick
import finscenlab.strategies  # registers defaults

# Create bricks
cash = ABrick(id="cash", name="Main Cash", kind="a.cash",
              spec={"initial_balance": 0.0, "interest_pa": 0.02})

house = ABrick(id="house", name="Property", kind="a.property",
               spec={"price": 420_000, "fees_pct": 0.095, "appreciation_pa": 0.02})

mortgage = LBrick(id="mortgage", name="Home Loan", kind="l.mortgage.annuity",
                  links={"auto_principal_from": "house"},
                  spec={"rate_pa": 0.034, "term_months": 300})

# Create and run scenario
scenario = Scenario(id="demo", name="House Purchase", 
                   bricks=[cash, house, mortgage])
results = scenario.run(start=date(2026, 1, 1), months=360)
```

## Project Structure

```
finscenlab-poc/
├── README.md
├── requirements.txt
├── finscenlab/
│   ├── __init__.py
│   ├── core.py          # ABCs, engine, types, registry
│   └── strategies.py    # valuation/schedule/flow strategies
└── notebooks/
    └── 01_quickstart.ipynb
```

## Extending the System

To add a new financial instrument:

1. Create a strategy class implementing the appropriate interface
2. Register it in the registry with a new `kind` string
3. Use the new `kind` when creating bricks

Example:
```python
class ValuationCar(IValuationStrategy):
    def prepare(self, brick: ABrick, ctx: ScenarioContext) -> None:
        # Implementation here
        pass
    
    def simulate(self, brick: ABrick, ctx: ScenarioContext) -> BrickOutput:
        # Implementation here
        pass

# Register the new strategy
ValuationRegistry["a.vehicle.car"] = ValuationCar()

# Use it
car = ABrick(id="car", name="My Car", kind="a.vehicle.car",
             spec={"price": 25000, "depreciation_pa": 0.15})
```

## License

This is a proof-of-concept for educational and research purposes.
