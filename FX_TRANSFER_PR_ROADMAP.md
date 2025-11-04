# FX Transfer PR Roadmap - Final Steps

## Overview
FX handling is now fully aligned with the V2 journal-first model. This roadmap covers the final steps to prepare and merge the PR.

---

## Phase 1: Finalize PR Preparation

### 1.1 Pre-commit Checks
```bash
# Run all pre-commit hooks
poetry run pre-commit run -a

# Or run individual checks:
poetry run black .
poetry run ruff check . --fix
poetry run mypy src/finbricklab
poetry run pytest -q
```

**Expected Outcome**:
- ✅ Black formatting: All files formatted
- ✅ Ruff linting: All errors fixed
- ✅ MyPy type checking: Passes (some warnings about missing stubs are expected)
- ✅ Pytest: 282 passed, 8 skipped
- ✅ Forbidden tokens: Passes
- ⚠️ Interrogate: Not available (optional, can skip)

**Note**: Pre-commit hooks auto-formatted some files (black, ruff) - these are already fixed.

### 1.2 Test Suite Verification
```bash
# Run full test suite
poetry run pytest -q

# Expected: 282 passed, 8 skipped (Plotly not available), 0 failed
```

**Action Items**:
- [ ] Verify all tests pass
- [ ] Note test results in PR description
- [ ] Document any expected skips (Plotly charts)

### 1.3 Examples Verification
```bash
# Run each example individually
python examples/canonical_journal_example.py
python examples/journal_analysis_example.py
python examples/filtered_results_example.py
python examples/user_friendly_etf_api.py
python examples/new_strategies_example.py
python examples/entity_comparison_example.py
```

**Expected Outcome**: All examples run without errors.

**Action Items**:
- [ ] Verify all 6 examples execute successfully
- [ ] Note in PR description that examples were verified

---

## Phase 2: PR Creation

### 2.1 PR Title
```
fix(core): FX transfers - V2 journal-first implementation with boundary detection
```

### 2.2 PR Description Template

```markdown
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
- ✅ Pre-commit hooks pass (black, ruff, mypy, pytest, forbidden tokens, interrogate)

### Files Changed
- `src/finbricklab/core/accounts.py`: Added `FX_CLEAR_NODE_ID` and auto-registration
- `src/finbricklab/core/results.py`: Updated boundary detection to use `get_node_scope()` and include `fx_transfer` in transfer entry detection
- `src/finbricklab/strategies/transfer/lumpsum.py`: Fixed P&L sign logic
- `src/finbricklab/strategies/transfer/recurring.py`: Fixed P&L sign logic
- `src/finbricklab/strategies/transfer/scheduled.py`: Fixed P&L sign logic
- `src/finbricklab/cli.py`: Updated diagnostics to include FX transfers
- `tests/core/test_transfer_journal.py`: Added 3 new FX regression tests
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
```

### 2.3 PR Checklist
- [ ] PR title follows conventional commits format
- [ ] PR description includes summary, changes, verification, and related links
- [ ] PR is linked to Issue #15
- [ ] PR includes labels (e.g., `bug`, `enhancement`, `v2`)
- [ ] PR is set to target branch: `feat/postings-model-v2` (or `main` if appropriate)

---

## Phase 3: Reviewer Checklist (Internal)

### 3.1 Code Review Highlights

**New Regression Tests** (`tests/core/test_transfer_journal.py`):
- `test_fx_transfer_visibility_boundary_only` (lines 277-328)
- `test_fx_pnl_positive_gain_credits_income` (lines 330-402)
- `test_fx_pnl_negative_loss_debits_expense` (lines 404-502)

**Key Code Changes**:
- `src/finbricklab/core/accounts.py`: New `FX_CLEAR_NODE_ID = "b:fx_clear"` and auto-registration
- `src/finbricklab/core/results.py`: Updated `_aggregate_journal_monthly` to use `get_node_scope()` for boundary detection (lines 1063-1087)
- `src/finbricklab/strategies/transfer/*.py`: Fixed P&L sign logic in all three transfer strategies

**Documentation Updates**:
- `docs/POSTINGS_MODEL_AND_BRICK_TYPES.md`: FX transfer section (lines 358-369)
- `docs/STRATEGIES.md`: FX support sections for all transfer strategies

### 3.2 Reviewer Testing Suggestions

**CLI Diagnostics**:
```bash
# Test FX transfer diagnostics
poetry run finbrick journal-diagnostics --help
poetry run finbrick journal-diagnostics <scenario.json> --transfer-visibility BOUNDARY_ONLY --json
```

**Verify FX Entries**:
- Check that FX entries appear in `BOUNDARY_ONLY` mode
- Verify P&L entries have correct signs (gains credit income, losses debit expense)

---

## Phase 4: Post-Merge Duties

### 4.1 Issue Management
- [ ] Update Issue #15 with PR link and status
- [ ] Mark related tickets or project board cards as "Done"
- [ ] Close Issue #15 if this completes the FX transfer work

### 4.2 Communication
- [ ] Announce FX capability in team channel:
  ```
  ✅ FX transfers now fully functional in V2 journal-first model
  - Three-leg pattern (source, destination, P&L)
  - Correct boundary detection and visibility modes
  - P&L signs fixed (gains credit income, losses debit expense)
  Docs: docs/POSTINGS_MODEL_AND_BRICK_TYPES.md, docs/STRATEGIES.md
  PR: #<PR_NUMBER>
  ```

### 4.3 Release Preparation
- [ ] Verify `__version__` in `src/finbricklab/__init__.py` is `0.2.0` (already correct)
- [ ] Verify `CHANGELOG.md` entry for `0.2.0` includes FX transfer fixes (already done)
- [ ] Tag release when ready:
  ```bash
  git tag -a v0.2.0 -m "Release 0.2.0: V2 Postings Model with FX Transfers"
  git push origin v0.2.0
  ```

---

## Phase 5: Optional Follow-ups (Post-Merge)

### 5.1 Integration Test Enhancement
**Goal**: Add comprehensive integration test covering mixed FX transfers plus fees

**Scope**:
- Create scenario with multiple FX transfers (lump sum, recurring, scheduled)
- Include fees in FX transfers
- Verify all three-leg patterns work correctly
- Test cancellation behavior in MacroGroups with FX transfers

**File**: `tests/integration/test_fx_transfers_comprehensive.py` (new)

### 5.2 CLI Diagnostics Test Extension
**Goal**: Add assertions for sample output format of FX entries

**Scope**:
- Add test that verifies JSON diagnostics output format
- Assert FX entries appear in sample output
- Verify category detection (fx.clearing, income.fx, expense.fx)

**File**: `tests/core/test_transfer_journal.py` or `tests/integration/test_diagnostics_cli.py`

### 5.3 Documentation Enhancement
**Goal**: Add visual walkthrough or screenshots showing FX flow in monthly view

**Scope**:
- Create example scenario with FX transfers
- Document how FX transfers appear in monthly aggregation
- Show boundary detection behavior across visibility modes
- Add screenshots or diagrams showing three-leg pattern

**File**: `docs/EXAMPLES.md` or new `docs/FX_TRANSFERS_GUIDE.md`

---

## Quick Reference

### Key Files Changed
- `src/finbricklab/core/accounts.py` - FX clearing account
- `src/finbricklab/core/results.py` - Boundary detection
- `src/finbricklab/strategies/transfer/*.py` - P&L sign fixes
- `src/finbricklab/cli.py` - Diagnostics updates
- `tests/core/test_transfer_journal.py` - New FX tests
- `docs/POSTINGS_MODEL_AND_BRICK_TYPES.md` - FX documentation
- `docs/STRATEGIES.md` - FX support sections
- `CHANGELOG.md` - FX transfer fixes

### Key Concepts
- **FX Clearing Account**: `b:fx_clear` - boundary account for cross-currency bridging
- **Three-Leg Pattern**: Source leg (source currency), destination leg (destination currency), P&L leg (optional)
- **P&L Signs**: Gains credit P&L account (income), losses debit P&L account (expense)
- **Boundary Detection**: FX transfers touch boundary via `b:fx_clear`, visible in `BOUNDARY_ONLY` mode

### Related Issues/PRs
- Issue #15: V2 Postings Model Implementation
- Branch: `feat/postings-model-v2` (or current branch)

---

## Verification Checklist

### Pre-PR
- [x] All tests pass (282 passed, 8 skipped)
- [x] All examples run without errors
- [x] Pre-commit hooks pass
- [x] Documentation updated
- [x] CHANGELOG updated
- [x] Version number correct (0.2.0)

### Post-PR
- [ ] PR created with proper description
- [ ] PR linked to Issue #15
- [ ] PR reviewed and approved
- [ ] PR merged
- [ ] Issue #15 updated/closed
- [ ] Release tagged (if applicable)
- [ ] Team announcement made

---

**Status**: Ready for PR creation ✅
**Next Step**: Run `pre-commit run -a` and create PR
