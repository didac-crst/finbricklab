# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
