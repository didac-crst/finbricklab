# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2025-10-25

### Fixed
- **FX transfers**: Per-currency zero-sum with correct P&L signs; FX pair base validation
- **Journal timestamps**: Normalized to month granularity for deterministic ordering across mixed types
- **Debit/credit**: Corrected posting_side labels for transfers, flows, and liabilities; removed hardcoded currency
- **Config validation**: Scheduled/recurring/lumpsum transfer validations now use ConfigError instead of assertions
- **Private equity**: Monthly compounding with integer exponent (no fractional Decimal**)
- **Flow strategies**: Added prepare() to expense_onetime and income_onetime with proper numeric coercion
- **Transfer strategies**: Fixed month precision alignment, out-of-window guards, and isinstance compatibility
- **Security valuation**: Added price0 division-by-zero guard for initial_amount conversion
- **Balloon loans**: Fix balloon month payment to include interest (not just principal)
- **Loan strategies**: Coerce credit_end_date strings to month precision; disallow balloon_after_months=0
- **Recurring transfers**: Honor brick.end_date with validation; check both attribute and spec
- **Liability routing**: Raise ConfigError instead of silently skipping when no cash account available
- **Cash validation**: Change post_interest shape validation to ConfigError (not ValueError)

### Added
- **Credit line strategy**: Added `prepare()` method with full config validation
- **Private equity strategy**: Added `prepare()` method with config validation
- **Flow strategies**: Added `prepare()` methods to expense_onetime and income_onetime strategies
- **Transfer strategies**: Added `prepare()` method to lumpsum strategy
- **Balloon loans**: Added `prepare()` method to validate balloon_after_months parameter
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
