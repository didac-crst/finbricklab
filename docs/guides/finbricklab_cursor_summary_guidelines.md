# FinBrickLab Summary Helpers (Cursor Guide)

This guide gives Cursor (and other AI assistants) the guardrails needed to extend the new `summary()` helpers safely.

## Goals

- Keep summaries cheap to compute and strictly JSON-serializable (scalars, lists, dicts).
- Preserve stable payload shapes for API, CLI, and UI consumers.
- Avoid any behavioural changes or side effects in the simulation engine.

## Current Summary APIs

- `FinBrickABC.summary(include_spec: bool = False) -> dict`
  - Core: `type`, `id`, `name`, `family`, `kind`, `currency`
  - Window: `start`, `end`, `duration_m`
  - Links: `route_to` when present
  - Strategy hint: `strategy_bound`
  - Optional: `spec_summary` (small whitelist of spec fields)

- `MacroBrick.summary(registry=None, *, flatten=False, include_members=False) -> dict`
  - Core: `type`, `id`, `name`, `tags`, `n_direct`, `is_empty`
  - Optional: `direct_members`, `contains_macros`, `flat_members`, `n_flat`

- `Scenario.summary(*, include_members=False, include_validation=False, include_last_run=True) -> dict`
  - Core: `type`, `id`, `name`, `currency`, `n_bricks`, `n_macrobricks`, `families`, `has_cash`, `default_cash_id`
  - Optional: `brick_ids`, `macrobrick_ids`
  - Optional validation block (never raises; records `validation_error` if needed)
  - Optional last-run block: `has_run`, `months`, `date_start`, `date_end`, `execution_order_len`, `overlaps`

- `ScenarioResults.summary(selection=None, transfer_visibility=None) -> dict`
  - Selection: `selection_in`, `selection_resolved`, `macrobricks_included`
  - Frame: `freq`, `rows`, `date_start`, `date_end`, `columns`
  - Transfer visibility: enum value as string
  - Families (when resolvable) and quick KPIs: `last_cash`, `last_liabilities`, `last_non_cash`, `last_property_value`, `last_net_worth`, `total_inflows`, `total_outflows`

## Design Rules

1. **JSON only** – cast pandas/numpy objects to primitives, convert dates to ISO strings.
2. **Cheap by default** – gate heavy work behind explicit flags (`include_*`, `flatten`).
3. **Never raise** – wrap risky lookups in `try/except`; surface issues as strings.
4. **Additive changes** – append new optional keys without renaming/removing existing ones.
5. **Read-only** – summaries must not mutate state, run simulations, or perform I/O.

## Adding Fields Checklist

- Confirm the data is already available and fast to access.
- Convert custom classes to primitives/strings before returning.
- Wrap registry/journal lookups defensively.
- Guard loops over large collections with feature flags.
- Update docstrings/tests if the payload shape grows.

## Sample Payloads

- Brick:
  ```json
  {"type":"brick","id":"cash","name":"Cash","family":"a","kind":"a.cash","currency":"EUR","strategy_bound":true}
  ```

- MacroBrick:
  ```json
  {"type":"macrobrick","id":"portfolio","name":"Portfolio","n_direct":3,"contains_macros":1}
  ```

- Scenario:
  ```json
  {"type":"scenario","id":"baseline","name":"Baseline","n_bricks":12,"families":{"a":6,"l":2,"f":3,"t":1},"has_cash":true}
  ```

- Results view:
  ```json
  {"type":"results_view","selection_in":["portfolio"],"frame":{"freq":"M","rows":120,"date_start":"2024-01-31","date_end":"2034-12-31","columns":["cash","net_worth"]}}
  ```

## Quick Checks

- Fast regression: `python -m pytest tests/strategies/valuation/test_security_unitized.py`
- Broader coverage (optional): `python -m pytest tests/integration/test_cash_account_regressions.py`
- Spot-check summary outputs in `examples/` notebooks when adding new keys.

## Performance Notes

- Registries can contain 100+ bricks – avoid expanding everything unless flags request it.
- Results DataFrames can be wide – check column existence before aggregating.
- Validation runs are cached, but still guard them behind `include_validation`.
