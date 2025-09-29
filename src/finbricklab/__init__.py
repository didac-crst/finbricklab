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
- **Multi-scenario Comparison**: Group scenarios into Entities for benchmarking
- **Rich Visualizations**: Interactive charts for scenario analysis

Architecture Overview:
- **FinBrickABC**: Abstract base class for all financial instruments
- **ABrick/LBrick/FBrick**: Concrete classes for Assets, Liabilities, and Flows
- **Strategy Interfaces**: Protocols for valuation, scheduling, and flow strategies
- **Registry System**: Maps kind strings to strategy implementations
- **Scenario Engine**: Orchestrates simulation and cash flow routing
- **Entity System**: Multi-scenario comparison with canonical schema
- **Chart Library**: Interactive visualizations with Plotly integration

Quick Start:
    ```python
    from datetime import date
    from finbricklab import Scenario, ABrick, LBrick, FBrick
    import finbricklab.strategies  # Registers default strategies

    # Create financial bricks
    cash = ABrick(id="cash", name="Main Cash", kind="a.cash",
                  spec={"initial_balance": 0.0, "interest_pa": 0.02})

    house = ABrick(id="house", name="Property", kind="a.property_discrete",
                   spec={"initial_value": 420_000, "fees_pct": 0.095, "appreciation_pa": 0.02})

    mortgage = LBrick(id="mortgage", name="Home Loan", kind="l.mortgage.annuity",
                      links={"principal": {"from_house": "house"}},
                      spec={"rate_pa": 0.034, "term_months": 300})

    # Create and run scenario
    scenario = Scenario(id="demo", name="House Purchase",
                       bricks=[cash, house, mortgage])
    results = scenario.run(start=date(2026, 1, 1), months=360)
    ```

Available Strategies:
    Assets:
        - 'a.cash': Cash account with interest
        - 'a.property_discrete': Real estate with appreciation
        - 'a.etf_unitized': ETF investment with unitized pricing

    Liabilities:
        - 'l.mortgage.annuity': Fixed-rate mortgage with annuity payments

    Flows:
        - 'f.transfer.lumpsum': One-time lump sum transfer
        - 'f.income.fixed': Fixed recurring income
        - 'f.expense.fixed': Fixed recurring expense

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
import finbricklab.strategies

# Import strategy interfaces
# Import kinds and strategies modules
from .core import (
    ABrick,
    BrickOutput,
    Event,
    FBrick,
    FinBrickABC,
    FlowRegistry,
    IFlowStrategy,
    IScheduleStrategy,
    IValuationStrategy,
    LBrick,
    MacroBrick,
    PrincipalLink,
    Registry,
    Scenario,
    ScenarioContext,
    ScheduleRegistry,
    StartLink,
    ValuationRegistry,
    export_ledger_csv,
    export_run_json,
    kinds,
    month_range,
    validate_run,
    wire_strategies,
)

# Import Entity system
from .core.entity import Entity

# Import validation reports
from .core.validation import DisjointReport, ValidationReport

# Import FX utilities
from .fx import FXConverter, create_fx_converter, validate_entity_currencies

# Import KPI utilities
from .kpi import (
    breakeven_month,
    dsti,
    effective_tax_rate,
    fee_drag_cum,
    interest_paid_cum,
    liquidity_runway,
    ltv,
    max_drawdown,
    savings_rate,
    tax_burden_cum,
)

# Import chart functions (optional - requires plotly)
try:
    from .charts import (
        asset_composition_small_multiples,
        cashflow_waterfall,
        category_allocation_over_time,
        category_cashflow_bars,
        contribution_vs_market_growth,
        cumulative_fees_taxes,
        event_timeline,
        holdings_cost_basis,
        liabilities_amortization,
        liquidity_runway_heatmap,
        ltv_dsti_over_time,
        net_worth_drawdown,
        net_worth_vs_time,
        owner_equity_vs_property_mortgage,
        save_chart,
    )

    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

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
    # Entity system
    "Entity",
    # FX utilities
    "FXConverter",
    "create_fx_converter",
    "validate_entity_currencies",
    # KPI utilities
    "breakeven_month",
    "dsti",
    "effective_tax_rate",
    "fee_drag_cum",
    "interest_paid_cum",
    "liquidity_runway",
    "ltv",
    "max_drawdown",
    "savings_rate",
    "tax_burden_cum",
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
    # Link classes
    "StartLink",
    "PrincipalLink",
    # MacroBrick and Registry
    "MacroBrick",
    "Registry",
    # Validation
    "ValidationReport",
    "DisjointReport",
    # Kind constants
    "kinds",
    # Version info
    "__version__",
    "__author__",
    "__description__",
]

# Add chart functions to __all__ if available
if CHARTS_AVAILABLE:
    __all__.extend(
        [
            "net_worth_vs_time",
            "asset_composition_small_multiples",
            "liabilities_amortization",
            "liquidity_runway_heatmap",
            "cumulative_fees_taxes",
            "net_worth_drawdown",
            "cashflow_waterfall",
            "owner_equity_vs_property_mortgage",
            "ltv_dsti_over_time",
            "contribution_vs_market_growth",
            "category_allocation_over_time",
            "category_cashflow_bars",
            "event_timeline",
            "holdings_cost_basis",
            "save_chart",
        ]
    )
