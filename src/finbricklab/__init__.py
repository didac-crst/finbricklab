"""
FinBrickLab - Strategy-Driven Brick Architecture for Financial Scenarios

FinBrickLab is a modular, extensible framework for modeling complex financial scenarios
using a strategy-driven brick architecture. It allows you to compose financial instruments
as self-contained "bricks" that can be easily combined to create sophisticated financial models.

Key Features:
- **Strategy Pattern**: Behaviors are determined by 'kind' discriminators, not inheritance
- **Modular Design**: Each brick is self-contained with clear interfaces
- **Composable**: Link bricks together for complex interdependencies
- **Extensible**: Add new behaviors by registering strategies, no code changes required
- **Explicit**: Cash flows are explicitly routed, no hidden assumptions

Architecture Overview:
- **FinBrickABC**: Abstract base class for all financial instruments
- **ABrick/LBrick/FBrick**: Concrete classes for Assets, Liabilities, and Flows
- **Strategy Interfaces**: Protocols for valuation, scheduling, and flow strategies
- **Registry System**: Maps kind strings to strategy implementations
- **Scenario Engine**: Orchestrates simulation and cash flow routing

Quick Start:
    ```python
    from datetime import date
    from finscenlab.core import Scenario, ABrick, LBrick, FBrick
    import finscenlab.strategies  # Registers default strategies
    
    # Create financial bricks
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

Available Strategies:
    Assets:
        - 'a.cash': Cash account with interest
        - 'a.property': Real estate with appreciation  
        - 'a.invest.etf': ETF investment with price drift
        
    Liabilities:
        - 'l.mortgage.annuity': Fixed-rate mortgage with annuity payments
        
    Flows:
        - 'f.transfer.lumpsum': One-time lump sum transfer
        - 'f.income.salary': Fixed monthly income
        - 'f.expense.living': Fixed monthly expenses

Extending the System:
    To add new financial instruments, simply:
    1. Create a strategy class implementing the appropriate interface
    2. Register it in the appropriate registry with a new kind string
    3. Use the new kind when creating bricks
    
    No changes to existing code required!

License:
    This is a proof-of-concept for educational and research purposes.
"""

# Version information
__version__ = "0.1.0"
__author__ = "FinBrickLab Team"
__description__ = "Strategy-Driven Brick Architecture for Financial Scenarios"

# Import core components for easy access
from .core import (
    FinBrickABC,
    ABrick,
    LBrick, 
    FBrick,
    Scenario,
    ScenarioContext,
    BrickOutput,
    Event,
    month_range,
    wire_strategies,
    validate_run,
    export_run_json,
    export_ledger_csv,
    ValuationRegistry,
    ScheduleRegistry,
    FlowRegistry
)

# Import strategy interfaces
from .core import (
    IValuationStrategy,
    IScheduleStrategy,
    IFlowStrategy
)

# Import kinds and strategies modules
from .core import kinds
import finbricklab.strategies

# Define what gets imported with "from finbricklab import *"
__all__ = [
    # Core classes
    "FinBrickABC",
    "ABrick", 
    "LBrick",
    "FBrick",
    "Scenario",
    "ScenarioContext",
    "BrickOutput",
    "Event",
    
    # Utility functions
    "month_range",
    "wire_strategies",
    "validate_run",
    "export_run_json",
    "export_ledger_csv",
    
    # Strategy interfaces
    "IValuationStrategy",
    "IScheduleStrategy", 
    "IFlowStrategy",
    
    # Registries
    "ValuationRegistry",
    "ScheduleRegistry",
    "FlowRegistry",
    
    # Kind constants
    "kinds",
    
    # Version info
    "__version__",
    "__author__",
    "__description__"
]
