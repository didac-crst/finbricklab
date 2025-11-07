## Summary
Fixes FX transfer handling in the V2 journal-first model. Implements three-leg FX pattern with correct P&L signs, boundary detection, and visibility modes.

Closes #15 (V2 Postings Model Implementation)

## Changes

### Core Implementation
- **FX Transfer Strategy**: Three-leg pattern (source leg, destination leg, optional P&L leg)
  - Source leg: DR `b:fx_clear` / CR source asset (source currency)
  - Destination leg: DR destination asset / CR `b:fx_clear` (destination currency)
  - P&L leg: DR/CR between `b:fx_clear` and P&L account (gains credit income, losses debit expense)
- **FX Clearing Account**: Added `b:fx_clear` as boundary account in `core/accounts.py`
- **Boundary Detection**: Updated `_aggregate_journal_monthly` to recognize `b:fx_clear` as boundary account
- **Transfer Visibility**: Included `fx_transfer` in transfer entry detection for proper visibility filtering

### Fixes
- **FX Visibility**: Fixed FX entries being hidden in `BOUNDARY_ONLY` mode (now correctly recognized as boundary-touching)
- **P&L Signs**: Fixed inverted debit/credit logic for FX P&L entries (gains now credit P&L account as income, losses debit it as expense)
- **CLI Diagnostics**: Updated diagnostics to properly categorize FX transfers and include `fx_transfer` in transfer entry detection

### Tests
- Added 3 new regression tests in `tests/core/test_transfer_journal.py`:
  - `test_fx_transfer_visibility_boundary_only`: Verifies FX transfers are visible in `BOUNDARY_ONLY` mode
  - `test_fx_pnl_positive_gain_credits_income`: Verifies positive P&L (gain) credits the P&L account (income)
  - `test_fx_pnl_negative_loss_debits_expense`: Verifies negative P&L (loss) debits the P&L account (expense)

### Documentation
- **POSTINGS_MODEL_AND_BRICK_TYPES.md**: Added FX clearing account (`b:fx_clear`) to node IDs, updated diagram, expanded per-currency zero-sum section with three-leg pattern, added FX transfer example
- **STRATEGIES.md**: Added FX support sections to all three transfer strategies (`K.T_TRANSFER_LUMP_SUM`, `K.T_TRANSFER_RECURRING`, `K.T_TRANSFER_SCHEDULED`) with parameter examples and behavior notes
- **CHANGELOG.md**: Added FX transfer fixes and documentation updates

### CLI Diagnostics
- Updated `journal-diagnostics` command to:
  - Include `fx_transfer` in transfer entry detection
  - Categorize FX clearing account (`b:fx_clear`) and P&L accounts as boundary accounts
  - Detect FX transfer categories (fx.clearing, income.fx, expense.fx)

## Verification

### Test Results
- ✅ 282 tests passed, 8 skipped (Plotly charts), 0 failed
- ✅ All 6 examples run without errors
- ✅ Pre-commit hooks pass (black, ruff, mypy, pytest, forbidden tokens)

### Files Changed
- `src/finbricklab/core/accounts.py`: Added `FX_CLEAR_NODE_ID` and auto-registration
- `src/finbricklab/core/results.py`: Updated boundary detection to use `get_node_scope()` and include `fx_transfer` in transfer entry detection
- `src/finbricklab/strategies/transfer/lumpsum.py`: Fixed P&L sign logic
- `src/finbricklab/strategies/transfer/recurring.py`: Fixed P&L sign logic
- `src/finbricklab/strategies/transfer/scheduled.py`: Fixed P&L sign logic
- `src/finbricklab/cli.py`: Updated diagnostics to include FX transfers
- `tests/core/test_transfer_journal.py`: Added 3 new FX regression tests
- `tests/core/test_journal_v2_invariants.py`: Fixed import
- `docs/POSTINGS_MODEL_AND_BRICK_TYPES.md`: Added FX documentation
- `docs/STRATEGIES.md`: Added FX support sections
- `CHANGELOG.md`: Added FX transfer fixes

## Related
- Issue #15: V2 Postings Model Implementation
- Specs: `docs/POSTINGS_MODEL_AND_BRICK_TYPES.md`, `docs/TECHNICAL_SPEC_POSTINGS_MODEL.md`

## Breaking Changes
None - FX transfers were previously broken (NotImplementedError), now fully functional.

## Migration Notes
Existing FX transfer configurations will now work correctly. No migration required for users.
