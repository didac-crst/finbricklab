# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Journal-first filter refactor**: `ScenarioResults.filter()` now uses journal-first aggregation via `monthly(selection=...)` for V2 compatibility
- **Sticky filter defaults**: Filtered views persist selection, visibility, and `include_cash` settings for subsequent `monthly()` calls
- **MacroBrick cache usage**: Filter and aggregation now use `registry.get_struct_flat_members()` for cached expansion instead of recomputing
- **Empty selection sentinel**: Empty selection returns zeros across all visibility modes by design
- **Defensive selection validation**: `_validate_node_selection()` ensures only A/L node IDs are used in selection
- **O(1) journal ID checks**: Journal duplicate detection now uses `_id_index` set for O(1) lookups instead of O(n) scans
- **Scope-aware legacy visibility**: Legacy transfer visibility path now uses `get_node_scope()` for consistent boundary detection

### Fixed
- **Balloon payoff sequencing**: Loan annuity balloon payments now use distinct sequence numbers (90) to avoid ID conflicts with regular payments
- **Filter persistence**: Selection and visibility settings now correctly persist across visibility changes in filtered views
- **Include cash persistence**: `include_cash=False` now correctly persists across visibility changes in filtered views
- **Legacy filter return path**: Fixed missing return statement in legacy filter path

### Changed
- **Consolidated warnings**: Filter selection warnings now consolidated into a single message to reduce noise
- **Legacy visibility path**: Marked as fallback-only; journal-first aggregation is authoritative

### Documentation
- Updated `docs/API_REFERENCE.md` with sticky filter defaults and selection rules
- Updated `docs/EXAMPLES.md` with filter persistence examples
- Updated `docs/STRATEGIES.md` with filter semantics section
- Updated `README.md` with sticky defaults and A/L-only selection rules

## [0.2.1] - 2025-11-09

### Fixed
- **Cashflow Double Counting**: Scenario aggregation skips journal entries whose `parent_id` matches array-origin flows, preventing inflated cash totals across filtered views.
- **Recurring Transfer Sunsets**: `TransferRecurring` now respects `end_date` (attribute or spec) so funding stops after the configured month.
- **Liability Cash Routing**: All loan schedules post principal and interest to the configured cash bricks (via `links.route`), keeping routed accounts in balance.
- **Unicode Slugification**: `slugify_name()` normalizes accented characters (e.g., “São Paulo” → `sao_paulo`) to avoid empty IDs.

### Changed
- **MacroBrick Membership**: MacroBricks accept A/L/F/T bricks while de-duplicating shared members; execution still runs each shell brick once per scenario.
- **Cash Valuation**: `_normalize_timestamp()` now handles `pd.Timestamp`, `pd.Period`, and NumPy scalars; overdraft checks share a helper for monthly and initial balances.
- **Entity Scenario Catalog**: `create_scenario()` updates the legacy `scenarios` list alongside the registry so compare/breakeven flows keep working.

### Added
- **Loan Routing Utility**: New `_loan_utils.resolve_loan_cash_nodes()` centralizes validation for `links.route`, including fallbacks to the default settlement account.
- **PR Report Targets**: Makefile includes `pr-report`, `pr-report-open`, and `pr-report-clean` helpers for generating GitHub review summaries.

### Tests & Tooling
- Added regressions for routed loan schedules, multi-cash filtered views, MacroBrick shell execution, and transfer end-dates.
- Updated activation-window assertions to cent-level tolerances consistent with journal rounding.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-11-04

### Major Changes
- **V2 Postings Model**: Complete migration to journal-first architecture where Assets/Liabilities hold balances only, and all cash movements are represented as debit/credit pairs in journal entries
- **Journal-First Aggregation**: Cashflow and metrics derived exclusively from journal entries, replacing direct `cash_in`/`cash_out` arrays in `BrickOutput`
- **MacroGroup Rules**: MacroGroups now contain only A/L bricks or other MacroGroups; internal transfers cancel when both nodes are in selection (regardless of visibility mode)
- **Strategy Conversions**: All strategies (cash, ETF, loans, flows, transfers) converted to V2 pattern with journal entries

### Added
- **Diagnostics CLI**: New `journal-diagnostics` command with `--selection`, `--transfer-visibility`, `--month`, and `--sample N` options
  - JSON output for CI-friendly assertions
  - Comprehensive counts (total entries, boundary entries by category, transfer entries, internal-only entries, cancelled entries)
  - Sample entry details with `entry_id`, `timestamp`, `transaction_type`, `node_ids`, `categories`, `amounts`
- **Transfer Visibility Modes**: `TransferVisibility` enum (OFF, ONLY, BOUNDARY_ONLY, ALL) for controlling how transfers are displayed in aggregated views
- **Selection-Aware Aggregation**: `_aggregate_journal_monthly` prioritizes ASSET postings whose `node_id` is in selection set
- **Opening Entry Normalization**: Opening entries now use canonical node IDs (`BOUNDARY_NODE_ID` and `get_node_id(cash_id, "a")`) for consistency
- **Transaction Type Metadata**: All journal entries now include `transaction_type` metadata (opening, disbursement, payment, income, expense, transfer, fx_transfer, maturity_transfer)
- **Origin ID Uniqueness**: Deterministic `origin_id` generation with sequence-based uniqueness (e.g., `t*100 + sequence` or `month_idx*100 + sequence`)
- **FX Transfer Support**: Full V2-compliant FX transfer implementation with three-leg pattern (source leg, destination leg, optional P&L leg)
  - FX clearing account (`b:fx_clear`) as boundary account for cross-currency bridging
  - P&L handling with correct income/expense classification
  - Support in all transfer strategies (lump sum, recurring, scheduled)
- **Test Structure Standardization**: Reorganized test suite into `tests/core/`, `tests/strategies/` (with flow/schedule/valuation subdirectories), and `tests/integration/` with consistent naming conventions

### Changed
- **Deprecated**: `BrickOutput.cash_in` and `BrickOutput.cash_out` arrays are now `NotRequired` and deprecated; strategies return zero arrays
- **Journal Entries**: All strategies now create journal entries directly via `ScenarioContext.journal` instead of returning cash arrays
- **Account IDs**: Normalized to use node ID format (`a:<id>`, `l:<id>`, `b:boundary`) instead of legacy `asset:<id>` format
- **Opening Balances**: Use deterministic `origin_id` based on `sha256(f"{opening_entry.id}:{currency}")[:16]` with `transaction_type="opening"`
- **Maturity Transfers**: Account IDs now use `get_node_id()` for source and destination accounts
- **Legacy Journal Entry Creation**: Updated `_create_transfer_journal_entry`, `_create_flow_journal_entry`, and `_create_liability_journal_entry` to use node IDs and stamp posting metadata

### Fixed
- **Duplicate Entry IDs**: Added guards in cash and loan strategies to skip posting if entry ID already exists (prevents errors during re-simulation)
- **Orphan Account Errors**: Fixed non-cash asset account registration (ETF, property) to prevent "Orphan account" validation errors
- **None Node ID Handling**: Added graceful handling of `None` node_id in aggregation for legacy entries
- **Cash and Non-Cash Columns**: Added `cash` and `non_cash` columns to journal aggregation for `monthly()` DataFrame consistency
- **Single-Node Selection**: Fixed aggregation to prioritize ASSET postings whose `node_id` is in selection set when provided
- **FX Transfers**: Fixed FX transfer visibility in `BOUNDARY_ONLY` mode (FX entries now recognized as boundary-touching via `b:fx_clear`)
- **FX P&L Signs**: Fixed inverted debit/credit logic for FX P&L entries (gains now credit P&L account as income, losses debit it as expense)
- **FX Diagnostics**: Updated CLI diagnostics to properly categorize FX transfers and include `fx_transfer` in transfer entry detection

### Documentation
- Added comprehensive diagnostics section to README with examples, output description, visibility modes, and cancellation policy
- Added test structure and pytest marker policy to CONTRIBUTING.md
- Updated README repository layout to reflect new test directory structure
- Added "At a Glance" section in AGENTS.md (if applicable) with V2 status, specs, and cancellation policy
- Added FX transfer documentation to `POSTINGS_MODEL_AND_BRICK_TYPES.md` and `STRATEGIES.md`:
  - Three-leg FX transfer pattern explanation (source leg, destination leg, P&L leg)
  - FX clearing account (`b:fx_clear`) role and behavior
  - P&L handling (gains as income, losses as expense)
  - FX transfer visibility in `BOUNDARY_ONLY` mode

### Migration Notes
- **Legacy Tests**: Many legacy tests still check `cash_in`/`cash_out` arrays; these need migration to journal-first assertions using `results["views"].monthly()` or diagnostics JSON
- **Test Migration**: Tests are being migrated incrementally (18+ tests migrated so far); remaining tests will be updated in subsequent releases
- **Breaking Change**: Per-brick `cash_in`/`cash_out` arrays are deprecated; use `ScenarioResults.monthly(transfer_visibility=...)` for cashflow views

## [0.1.2] - 2025-01-XX

### Fixed
- **FX transfers**: Per-currency zero-sum with correct P&L signs; FX pair base validation
- **Journal timestamps**: Normalized to month granularity for deterministic ordering across mixed types
- **Debit/credit**: Corrected posting_side labels for transfers, flows, and liabilities; removed hardcoded currency
- **Config validation**: Scheduled/recurring transfer validations now use ConfigError instead of assertions
- **Private equity**: Monthly compounding with integer exponent (no fractional Decimal**)

### Added
- **Credit line strategy**: Added `prepare()` method with full config validation
- **Private equity strategy**: Added `prepare()` method with config validation
- **Overdraft policy**: Configurable `overdraft_policy` = ignore|warn|raise (default: ignore); `overdraft_limit=None` (unlimited default)
- **BOUNDARY_ONLY mode**: Filters transfers that touch boundary accounts

### Changed
- **Cash valuation**: Apply active mask before interest calculations (don't compute then zero out)
- **Credit line**: Pre-start balance = 0; apply `initial_draw` only at `ms==0`; month-delta billing from `ms>=1`
- **Private equity**: Monthly drift calculation using float math for fractional exponent, then integer Decimal** month_idx

### Documentation
- Documented `credit_line.initial_draw` defaults to 0 (set explicitly to avoid surprises)
- Documented `billing_day` reserved for future calendar-accurate cycles
- Documented `overdraft_limit=None` (unlimited default) and `overdraft_policy='ignore'` default
- Added note that strict overdraft enforcement is opt-in via `overdraft_policy='raise'`

## [0.1.1] - 2025-10-25

### Fixed
- **Currency quantization**: Fixed `RoundingPolicy.HALF_UP` enum and `quantize` quantum calculation
- **Journal integrity**: Normalized timestamps to month precision with order-independent balance calculation
- **FX transfers**: Ensured per-currency zero-sum with proper P&L balancing legs
- **Opening balances**: Corrected `posting_side` labels (asset=debit, equity=credit)
- **Maturity transfers**: Fixed precision issues by using Decimal throughout with currency quantization
- **Maturity transfers**: Fixed `posting_side` labels for correct journal entry balance
- **Schedule strategies**:
  - `credit_line`: Billing starts from `ms >= 1` (month after start)
  - `credit_fixed`: Zero debt before disbursement month; principal only from start month
  - Both: Interest accrues on prior closing balance with month-delta alignment
- **Transfer strategies**:
  - `scheduled`: Exact month-precision alignment with out-of-window guard
  - `recurring`: Month-precision normalization and timeline alignment
  - Both: All events (transfer, fees, FX) use canonical `event_t` timestamp
- **Routing**: Added fallbacks for flow and liability bricks to `settlement_default_cash_id` or first cash account
- **Maturity currency routing**: Uses brick's currency spec instead of hardcoded "EUR"

### Added
- Transfer visibility feature with `TransferVisibility` enum (OFF, ONLY, ALL, BOUNDARY_ONLY)
- `transparent` flag on TBricks for granular transfer visibility control
- Meta-assertion tests for journal zero-sum and accounting identities
- Property-based tests for FX transfers and accounting identities (requires Hypothesis)
- Comprehensive smoke scenario test covering all major features

### Changed
- `credit_line.initial_draw` now defaults to 0 (was 10% of credit_limit)
- `FlowIncomeOneTime` uses `brick.start_date` instead of redundant `spec["date"]`
- TBrick supports `end_date` and `duration_m` parameters

### Documentation
- Added docstring note that `credit_line.initial_draw` defaults to 0
- Added FX P&L sign convention explanation for future maintainers

## [0.1.0] - Initial Release

Initial release of FinBrickLab.
