# FinBrickLab API Reference

Complete reference for all classes, functions, and modules in FinBrickLab.

## Table of Contents

* [Core Classes](#core-classes)
* [Entity System](#entity-system)
* [KPI Utilities](#kpi-utilities)
* [FX Utilities](#fx-utilities)
* [Chart Functions](#chart-functions)
* [Strategy Interfaces](#strategy-interfaces)
* [Utility Functions](#utility-functions)

---

## Core Classes

### Scenario

```python
class Scenario:
    """Financial scenario orchestrator with Journal-based bookkeeping."""

    def __init__(self, id: str, name: str, bricks: List[FinBrickABC]):
        """Initialize scenario with bricks."""

    def run(self, start: date, months: int) -> ScenarioResults:
        """Run scenario simulation with Journal compilation."""

    def to_canonical_frame(self) -> pd.DataFrame:
        """Convert to canonical schema for Entity comparison."""
```

**Key Methods:**
- `run(start, months)` - Execute simulation with Journal compilation
- `to_canonical_frame()` - Export to Entity-compatible format
- `validate()` - Check configuration validity

### Journal System

```python
class Journal:
    """Double-entry bookkeeping system for financial transactions."""

    def __init__(self, account_registry: AccountRegistry):
        """Initialize journal with account registry."""

    def post(self, entry: JournalEntry) -> None:
        """Post a journal entry to the ledger."""

    def balance(self, account_id: str, currency: str) -> Decimal:
        """Get account balance for specific currency."""

    def trial_balance(self) -> Dict[str, Dict[str, Decimal]]:
        """Get trial balance for all accounts."""

    def validate_invariants(self, registry: AccountRegistry) -> List[str]:
        """Validate journal invariants and return any errors."""
```

### ScenarioResults

```python
class ScenarioResults:
    """Results container with time aggregation and journal analysis capabilities."""

    def __init__(self, totals: pd.DataFrame, registry: Registry = None, outputs: Dict = None, journal: Journal = None):
        """Initialize with monthly totals and optional journal."""

    def monthly(self, transfer_visibility: TransferVisibility = TransferVisibility.BOUNDARY_ONLY, selection: set[str] | None = None) -> pd.DataFrame:
        """Get monthly aggregated results (journal-first).

        Args:
            transfer_visibility: OFF | ONLY | BOUNDARY_ONLY | ALL
            selection: Optional set of A/L node IDs (e.g., {"a:cash", "l:mortgage"}) and/or MacroBrick IDs
        Returns:
            Monthly DataFrame with journal-first cashflow aggregation.
        """

    def quarterly(self) -> pd.DataFrame:
        """Get quarterly aggregated results."""

    def yearly(self) -> pd.DataFrame:
        """Get yearly aggregated results."""

def journal(self) -> pd.DataFrame:
    """Get complete journal of all transactions."""
    # Returns DataFrame with canonical columns: record_id (clean format), brick_id, brick_type, account_id, posting_side, timestamp, amount, currency, metadata, entry_metadata

    def transactions(self, account_id: str) -> pd.DataFrame:
        """Get all transactions for a specific account."""

    def filter(self, brick_ids: List[str]) -> ScenarioResults:
        """Filter results to specific bricks or MacroBricks (legacy, non-journal-first behavior).

        Notes:
            This method uses legacy aggregation logic and may not reflect journal-first semantics.
            For V2 journal-first aggregation, use `monthly(selection=...)` instead.
        """
```

**Key Features (V2):**
- **Time Aggregation**: Monthly, quarterly, yearly views
- **Journal Analysis**: Complete transaction-level detail with canonical structure
- **Account Filtering**: Get transactions for specific accounts
- **Selection-based Aggregation**: Focus on specific A/L nodes or MacroBricks via `monthly(selection=...)`
- **Double-Entry Validation**: Ensure proper accounting
- **Canonical Structure**: Self-documenting record IDs and primary columns for easy analysis

### Account System

```python
class Account:
    """Financial account with scope and type classification."""

    def __init__(self, id: str, name: str, scope: AccountScope, account_type: AccountType):
        """Initialize account with scope and type."""

class AccountRegistry:
    """Registry for managing account definitions and validation."""

    def register_account(self, account: Account) -> None:
        """Register an account in the registry."""

    def validate_transfer_accounts(self, from_id: str, to_id: str) -> None:
        """Validate that transfer accounts are internal."""
```

### Transfer Bricks

```python
class TBrick(FinBrickABC):
    """Transfer brick for internal account transfers."""

    def __init__(self, id: str, name: str, kind: str, spec: Dict, links: Dict):
        """Initialize transfer brick with from/to account links."""
```

**Transfer Kinds:**
- `K.T_TRANSFER_LUMP_SUM` - One-time transfer
- `K.T_TRANSFER_RECURRING` - Recurring transfer
- `K.T_TRANSFER_SCHEDULED` - Scheduled transfers

### FinBrickABC

```python
class FinBrickABC:
    """Abstract base class for all financial instruments."""

    def __init__(self, id: str, name: str, kind: str, spec: Dict):
        """Initialize brick with strategy kind and configuration."""
```

**Concrete Classes:**
- `ABrick` - Assets (cash, property, ETFs)
- `LBrick` - Liabilities (mortgages, loans)
- `FBrick` - Flows (income, expenses, transfers)

### MacroBrick

```python
class MacroBrick:
    """Composite structure for grouping bricks within scenarios."""

    def __init__(self, id: str, name: str, members: List[str], tags: List[str] = None):
        """Initialize with member brick/MacroBrick IDs."""

    def expand_member_bricks(self, registry: Registry) -> List[str]:
        """Resolve to flat list of brick IDs (transitive, ensures DAG)."""
```

**Key Features:**
- Groups heterogeneous bricks into logical structures
- Supports hierarchical nesting (MacroBricks can contain other MacroBricks)
- View-only aggregations (doesn't participate in simulation)
- DAG enforcement (no cycles allowed)
- Overlap detection and handling

**Usage Note**: MacroBricks are used within individual scenarios for organization. The Entity system works at the scenario level and doesn't directly use MacroBricks.

---

## Entity System

### Entity

```python
class Entity:
    """Top-level aggregator for multiple scenarios."""

    def __init__(self, id: str, name: str, base_currency: str = "EUR"):
        """Initialize entity with scenarios."""

    def compare(self, scenario_ids: List[str] = None) -> pd.DataFrame:
        """Compare scenarios and return canonical DataFrame."""

    def breakeven_table(self, baseline_id: str) -> pd.DataFrame:
        """Calculate breakeven months vs baseline."""

    def fees_taxes_summary(self, horizons: List[int] = None) -> pd.DataFrame:
        """Summary of cumulative fees and taxes."""

    def liquidity_runway(self, lookback_months: int = 6, essential_share: float = 0.6) -> pd.DataFrame:
        """Calculate liquidity runway in months."""
```

**Key Features:**
- Multi-scenario comparison
- KPI calculations
- Canonical schema enforcement
- Currency normalization

---

## KPI Utilities

All KPI functions operate on canonical DataFrames:

### Liquidity & Risk

```python
def liquidity_runway(df: pd.DataFrame, lookback_months: int = 6, essential_share: float = 0.6) -> pd.Series:
    """Calculate liquidity runway in months."""

def max_drawdown(series_or_df: pd.Series | pd.DataFrame) -> pd.Series:
    """Calculate maximum drawdown from peak."""
```

### Cost Analysis

```python
def fee_drag_cum(df: pd.DataFrame, fees_col: str = "fees", inflows_col: str = "inflows") -> pd.Series:
    """Calculate cumulative fee drag as percentage of inflows."""

def tax_burden_cum(df: pd.DataFrame, taxes_col: str = "taxes", inflows_col: str = "inflows") -> pd.Series:
    """Calculate cumulative tax burden as percentage of inflows."""

def interest_paid_cum(df: pd.DataFrame, interest_col: str = "interest") -> pd.Series:
    """Calculate cumulative interest paid."""
```

### Financial Ratios

```python
def dsti(df: pd.DataFrame, interest_col: str = "interest", principal_col: str = "principal", net_income_col: str = "net_income") -> pd.Series:
    """Calculate Debt Service to Income ratio."""

def ltv(df: pd.DataFrame, mortgage_balance_col: str = "mortgage_balance", property_value_col: str = "property_value") -> pd.Series:
    """Calculate Loan to Value ratio."""

def savings_rate(df: pd.DataFrame, inflows_col: str = "inflows", outflows_col: str = "outflows") -> pd.Series:
    """Calculate savings rate."""
```

### Comparison

```python
def breakeven_month(scenario_df: pd.DataFrame, baseline_df: pd.DataFrame, net_worth_col: str = "net_worth") -> Optional[int]:
    """Calculate breakeven month for scenario vs baseline."""
```

---

## FX Utilities

### FXConverter

```python
class FXConverter:
    """Foreign exchange converter for multi-currency scenarios."""

    def __init__(self, base_currency: str, rates: Dict[Tuple[str, str], float] = None):
        """Initialize with base currency and exchange rates."""

    def convert_frame(self, df: pd.DataFrame, from_currency: str, to_currency: str) -> pd.DataFrame:
        """Convert DataFrame values between currencies."""

    def get_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Get exchange rate between currencies."""

    def add_rate(self, from_currency: str, to_currency: str, rate: float) -> None:
        """Add an exchange rate."""
```

### Helper Functions

```python
def create_fx_converter(base_currency: str = "EUR", rates: Dict[Tuple[str, str], float] = None) -> FXConverter:
    """Create FX converter with common rates."""

def validate_entity_currencies(entity: Entity, scenarios: List[Scenario]) -> Dict[str, str]:
    """Validate that all scenarios can be compared within an Entity."""
```

---

## Chart Functions

All chart functions return `(plotly_figure, tidy_dataframe_used)` tuples.

### Entity-Level Charts

```python
def net_worth_vs_time(tidy: pd.DataFrame) -> tuple[go.Figure, pd.DataFrame]:
    """Plot net worth over time for all scenarios."""

def asset_composition_small_multiples(tidy: pd.DataFrame) -> tuple[go.Figure, pd.DataFrame]:
    """Asset composition small multiples per scenario."""

def liabilities_amortization(tidy: pd.DataFrame) -> tuple[go.Figure, pd.DataFrame]:
    """Plot liabilities amortization over time."""

def liquidity_runway_heatmap(tidy: pd.DataFrame, lookback_months: int = 6) -> tuple[go.Figure, pd.DataFrame]:
    """Liquidity runway heatmap with threshold bands."""

def cumulative_fees_taxes(tidy: pd.DataFrame, horizons: List[int] = None) -> tuple[go.Figure, pd.DataFrame]:
    """Cumulative fees and taxes at chosen horizons."""

def net_worth_drawdown(tidy: pd.DataFrame) -> tuple[go.Figure, pd.DataFrame]:
    """Net worth drawdown curves per scenario."""
```

### Scenario-Level Charts

```python
def cashflow_waterfall(tidy: pd.DataFrame, scenario_name: str = None) -> tuple[go.Figure, pd.DataFrame]:
    """Annual cashflow waterfall chart."""

def owner_equity_vs_property_mortgage(tidy: pd.DataFrame, scenario_name: str = None) -> tuple[go.Figure, pd.DataFrame]:
    """Owner equity vs property value vs mortgage."""

def ltv_dsti_over_time(tidy: pd.DataFrame, scenario_name: str = None) -> tuple[go.Figure, pd.DataFrame]:
    """LTV & DSTI over time with linked axes."""

def contribution_vs_market_growth(tidy: pd.DataFrame, scenario_name: str = None) -> tuple[go.Figure, pd.DataFrame]:
    """Contribution vs market growth decomposition."""
```

### MacroBrick-Level Charts

```python
def category_allocation_over_time(tidy: pd.DataFrame, scenario_name: str = None) -> tuple[go.Figure, pd.DataFrame]:
    """Category allocation over time as stacked area chart."""

def category_cashflow_bars(tidy: pd.DataFrame, scenario_name: str = None) -> tuple[go.Figure, pd.DataFrame]:
    """Category cashflow bars per year."""
```

### FinBrick-Level Charts

```python
def event_timeline(tidy: pd.DataFrame, scenario_name: str = None) -> tuple[go.Figure, pd.DataFrame]:
    """Event timeline for FinBricks."""

def holdings_cost_basis(tidy: pd.DataFrame, scenario_name: str = None) -> tuple[go.Figure, pd.DataFrame]:
    """Holdings and cost basis over time."""
```

### Utility

```python
def save_chart(fig: go.Figure, filename: str, format: str = "html") -> None:
    """Save chart to file (html, png, pdf, svg)."""
```

---

## Strategy Interfaces

### IValuationStrategy

```python
class IValuationStrategy(Protocol):
    """Strategy for asset valuation."""

    def value(self, context: ScenarioContext, spec: Dict) -> float:
        """Calculate current value."""
```

### IScheduleStrategy

```python
class IScheduleStrategy(Protocol):
    """Strategy for cash flow scheduling."""

    def schedule(self, context: ScenarioContext, spec: Dict) -> List[Event]:
        """Generate scheduled events."""
```

### IFlowStrategy

```python
class IFlowStrategy(Protocol):
    """Strategy for cash flow routing."""

    def route(self, context: ScenarioContext, spec: Dict, links: Dict) -> Dict[str, float]:
        """Route cash flows between bricks."""
```

---

## Utility Functions

### Data Export

```python
def export_run_json(results: ScenarioResults, filename: str) -> None:
    """Export scenario results to JSON."""

def export_ledger_csv(results: ScenarioResults, filename: str) -> None:
    """Export detailed ledger to CSV."""
```

### Validation

```python
def validate_run(results: ScenarioResults) -> ValidationReport:
    """Validate scenario results for consistency."""

def wire_strategies() -> None:
    """Register all default strategies."""
```

### Time Utilities

```python
def month_range(start: date, months: int) -> pd.DatetimeIndex:
    """Generate month-end date range."""
```

---

## Strategy Catalog

### Available Asset Strategies

- `K.A_CASH` - Cash account with interest
- `K.A_PROPERTY` - Real estate with appreciation
- `K.A_SECURITY_UNITIZED` - ETF investment with unitized pricing
- `K.A_PRIVATE_EQUITY` - Private equity investment

### Available Liability Strategies

- `K.L_LOAN_ANNUITY` - Fixed-rate mortgage with annuity payments
- `K.L_LOAN_BALLOON` - Balloon payment loan
- `K.L_CREDIT_LINE` - Revolving credit line
- `K.L_CREDIT_FIXED` - Fixed-term credit

### Available Flow Strategies

- `K.F_INCOME_RECURRING` - Fixed recurring income
- `K.F_INCOME_ONE_TIME` - One-time income
- `K.F_EXPENSE_RECURRING` - Fixed recurring expense
- `K.F_EXPENSE_ONE_TIME` - One-time expense

### Available Transfer Strategies

- `K.T_TRANSFER_LUMP_SUM` - One-time lump sum transfer
- `K.T_TRANSFER_RECURRING` - Recurring transfer
- `K.T_TRANSFER_SCHEDULED` - Scheduled transfers

---

## Error Handling

### Common Exceptions

```python
class ConfigError(Exception):
    """Configuration or setup error."""

class ValidationError(Exception):
    """Data validation error."""

class RuntimeError(Exception):
    """Simulation runtime error."""
```

### Error Patterns

- **Missing Strategy**: `ConfigError: Unknown valuation strategy: a.unknown`
- **Invalid Links**: `ConfigError: Unknown brick ID in link: 'missing_brick'`
- **Currency Mismatch**: `ValueError: Multiple currencies found in Entity`
- **Missing Data**: `RuntimeError: No scenario has been run yet`

---

## Best Practices

### Scenario Design

1. **Start Simple**: Begin with basic bricks (cash, income, expenses)
2. **Validate Early**: Use `scenario.validate()` before running
3. **Test Incrementally**: Add complexity gradually
4. **Use Meaningful IDs**: Choose descriptive brick and scenario IDs

### Entity Comparison

1. **Consistent Schemas**: Ensure all scenarios use canonical schema
2. **Same Currency**: Use same base currency or provide FX converter
3. **Apples-to-Apples**: Compare similar time horizons and assumptions
4. **Validate Results**: Check for unexpected values or trends

### Performance

1. **Batch Operations**: Use Entity methods for multiple scenarios
2. **Canonical Schema**: Use `to_canonical_frame()` for consistency
3. **Chart Caching**: Save charts to avoid regeneration
4. **Memory Management**: Clear large DataFrames when done

### Extensibility

1. **Strategy Pattern**: Add new behaviors via strategy registration
2. **Interface Compliance**: Implement required strategy interfaces
3. **Testing**: Add tests for new strategies and behaviors
4. **Documentation**: Update API reference for new features
