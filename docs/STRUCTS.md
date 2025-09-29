# MacroBrick Aggregation Semantics

This document explains how MacroBricks work and how aggregation is performed in FinBrickLab.

## Overview

MacroBricks are composite structures that group heterogeneous financial bricks (Assets, Liabilities, Flows) into named, hierarchical structures. They provide composite views and aggregations for analysis and presentation without duplicating state or altering the core simulation logic.

## Key Concepts

### MacroBrick Structure
- **ID**: Unique identifier for the MacroBrick
- **Name**: Human-readable name
- **Members**: List of brick IDs and/or other MacroBrick IDs
- **Tags**: Optional tags for UI/grouping

### Execution Model
- MacroBricks are **view-only** - they don't participate directly in simulation
- Only individual bricks are simulated
- MacroBrick results are computed post-run by aggregating member brick outputs

## Aggregation Rules

### 1. Execution Set Resolution
When you select MacroBricks for execution:
1. Each MacroBrick is expanded to its flat list of member bricks
2. The union of all selected bricks (direct + expanded) forms the execution set
3. Each brick is simulated exactly once, regardless of how many MacroBricks contain it

### 2. Portfolio Totals
Portfolio totals represent the **union** of executed bricks:
- Each brick contributes its output exactly once
- No double-counting, even if bricks appear in multiple MacroBricks
- This is the "true" portfolio value

### 3. MacroBrick Aggregates
Each MacroBrick shows the sum of its **executed** member bricks:
- If a MacroBrick contains 3 bricks but only 2 are executed, only those 2 contribute
- Shared bricks contribute to multiple MacroBrick views
- This can lead to apparent "overstatement" when summing MacroBrick totals

## Mathematical Invariants

### Union ≤ Sum (Overlap Present)
When MacroBricks share bricks:
```
Portfolio Total ≤ Sum of MacroBrick Totals
```

### Disjoint Equality (No Overlap)
When MacroBricks are disjoint:
```
Portfolio Total = Sum of MacroBrick Totals
```

## Example

Consider this scenario:
```json
{
  "bricks": [
    {"id": "cash", "kind": "a.cash", "spec": {"initial_balance": 10000}},
    {"id": "house", "kind": "a.property_discrete", "spec": {"initial_value": 400000}},
    {"id": "mortgage", "kind": "l.mortgage.annuity", "spec": {"rate_pa": 0.034}}
  ],
  "structs": [
    {"id": "primary", "members": ["house", "mortgage"]},
    {"id": "property", "members": ["house", "cash"]}
  ]
}
```

### Execution with Selection: ["primary", "property"]

**Execution Set**: `{cash, house, mortgage}` (union, no duplicates)

**Portfolio Totals**: Sum of cash + house + mortgage outputs

**MacroBrick Aggregates**:
- `primary`: house + mortgage outputs
- `property`: house + cash outputs

**Overlap**: `house` appears in both MacroBricks

**Invariant Check**:
- Portfolio Total = cash + house + mortgage
- Sum of MacroBrick Totals = (house + mortgage) + (house + cash) = 2×house + mortgage + cash
- Portfolio Total ≤ Sum of MacroBrick Totals ✓

## Best Practices

### 1. Use Portfolio Totals for True Values
For accurate portfolio metrics, always use the portfolio totals, not the sum of MacroBrick totals.

### 2. Check for Overlaps
Use the `results.meta["overlaps"]` to identify shared bricks:
```python
overlaps = results["meta"]["overlaps"]
if overlaps:
    print(f"Shared bricks: {list(overlaps.keys())}")
```

### 3. Assert Disjointness When Needed
If you expect MacroBricks to be disjoint:
```python
scenario.assert_disjoint("portfolio_views", ["primary", "secondary"])
```

### 4. Use Structured Selection
Be explicit about what you're selecting:
```bash
# Select specific MacroBricks
finbricklab run --select primary property

# Select individual bricks
finbricklab run --select house mortgage cash

# Mix both
finbricklab run --select primary cash
```

## Execution Order

Bricks are executed in deterministic order:
1. **Topological sort** by dependency links (e.g., mortgage depends on house)
2. **Fallback to stable ID sort** if no dependencies or cycles detected

The execution order is recorded in `results.meta["execution_order"]` for reproducibility.

## Performance Considerations

### Caching
- MacroBrick member expansions are cached for O(1) access
- Cache is precomputed during scenario validation
- No repeated DFS traversal during execution

### Results Filtering
Control which MacroBrick aggregates are computed:
```python
scenario.config.include_struct_results = False  # Skip all struct aggregates
scenario.config.structs_filter = {"primary"}    # Only compute primary aggregate
```

## Validation

The system validates:
- All MacroBrick members exist (bricks or other MacroBricks)
- No cycles in MacroBrick membership graph
- No ID conflicts between bricks and MacroBricks
- Reserved prefix usage (warns if IDs start with `b:` or `mb:`)

Use the CLI to validate scenarios:
```bash
finbricklab validate -i scenario.json
finbricklab validate -i scenario.json --format json  # For CI/CD
```

## CLI Integration

### Execution Summary
The CLI shows execution details:
```
Executing 3 bricks (deduped) from 2 MacroBricks [primary,property]; overlaps: house
```

### List MacroBricks
Inspect MacroBrick structure:
```bash
finbricklab list-macrobricks -i scenario.json
finbricklab list-macrobricks -i scenario.json --json  # Machine-readable
```

### Validation Reports
Get structured validation results:
```bash
finbricklab validate -i scenario.json --format json
```

## Troubleshooting

### Common Issues

1. **"Cycle detected"**: MacroBricks form a circular dependency
   - Solution: Restructure to remove cycles

2. **"Unknown member id"**: MacroBrick references non-existent brick/MacroBrick
   - Solution: Check member IDs in MacroBrick definitions

3. **"ID conflicts"**: Same ID used for both brick and MacroBrick
   - Solution: Use unique IDs across all entities

4. **Overstated totals**: Summing MacroBrick totals instead of portfolio total
   - Solution: Use `results["totals"]` for accurate portfolio values

### Debugging Tips

1. Use `--list-macrobricks` to inspect structure
2. Check `results.meta["overlaps"]` for shared bricks
3. Verify execution order in `results.meta["execution_order"]`
4. Use validation reports to catch configuration issues early
