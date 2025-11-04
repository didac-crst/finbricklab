# V2 Architecture Implementation Questions

This document contains questions about the V2 architecture implementation that need clarification before proceeding with development.

## Answers (authoritative for V2)

Migration & Compatibility
1) a — Single cutover. Aggregations are journal‑first; no legacy flag.
2) a — Make `cash_in`/`cash_out` optional/deprecated in `BrickOutput`. Aggregators ignore them; keep `assets`/`liabilities` and signed `interest`.
3) a — Update tests to journal‑first. No parallel legacy suite.

Implementation Details
4) c — Map via `AccountRegistry` (default derives `a:/l:` from brick family + id; allow override hook).
5) c — Register `b:boundary` as a special account in `AccountRegistry` and expose a constant.
6) c — Provide helpers to stamp metadata and validate required keys at creation.
7) a + (compat) — Store `node_id` in posting.metadata; keep `account_id` for now. Aggregation uses `node_id`.
8) a — Enforce exactly 2 postings per entry (strict two‑posting invariant).
9) c — Support both `account_id` and `node_id`; aggregator uses `node_id`.
10) a — Keep `FBrick`/`TBrick`; behave as shells (no balances; only journal entries).

Strategy Changes
11) a — A/L strategies stop emitting cash arrays; emit journal entries; keep `interest` array for KPIs.
12) c — F/T strategies return `BrickOutput` with empty arrays but generate journal entries.
13) c — Strategies write directly to the `Journal` provided by the `ScenarioContext`.
14) c — Use journal entries exclusively (including opening balances); remove `external_in/out` usage.

Aggregation & Results
15) a — `ScenarioResults.monthly()` always uses journal‑first.
16) a + b — Cancel per entry when both postings are INTERNAL and both `node_id` are in selection (same entry by definition).
17) a — Cashflow includes only ASSET postings (DR=inflow, CR=outflow). LIABILITY postings inform node‑side movements only.
18) c — Attribute boundary by both `category` (fine‑grained) and `type` (coarse label).

MacroGroup Constraints
19) b — Validate membership at scenario validation time (and implicitly at expansion).
20) a — Keep existing expansion‑time DAG/cycle detection.
21) a — Reject Shells (F/T) and Boundary as members immediately (fail fast).

Validation & Guardrails
22) a — Fail fast at entry creation if invariant broken.
23) a — Validate required metadata at entry creation.
24) b + c — Enforce per‑currency zero‑sum with improved error messages.
25) a — Validate `origin_id` uniqueness at entry creation; fail on collision.

Testing & Examples
26) a — Update existing tests to journal‑first.
27) a — Update golden files to match journal‑first outputs.
28) c — Create new V2 examples; update legacy examples after core lands.

Performance & Optimization
29) c — Optimize later; start simple (no indices unless needed).
30) a — Use vectorized pandas operations in aggregation paths.

CLI & UX
31) c — Configurable; default `BOUNDARY_ONLY`.
32) c — Add a diagnostics subcommand and flags to existing commands.

Open Questions from Spec
33) c — Keep `interest` array and also create journal entries for interest cash impact.
34) b — Use journalized opening entries (equity → A/L); do not also set state openings.
35) a — Split FX into separate entries (trade legs + FX P&L) to keep per‑currency zero‑sum.
36) b — Normalize timestamps to month; include optional `value_date` metadata for day precision if relevant.

### Critical Path (must‑knows)
- Migration: single cutover; journal‑first everywhere; no legacy flag.
- Node IDs: `AccountRegistry` maps bricks → `a:/l:`; `b:boundary` registered as special.
- Entry creation: strategies write directly to the `Journal`; helpers stamp and validate metadata.
- BrickOutput: cash arrays deprecated/ignored; keep balances + `interest`.
- Two‑posting invariant: strict (exactly 2 postings per entry; per‑currency zero‑sum).

## Migration & Compatibility

1. **Migration Timeline**: The spec mentions a "single-cutover plan" with no backward compatibility. Should we:
   - a) Remove all `cash_in`/`cash_out` from `BrickOutput` immediately?
   - b) Keep them as deprecated/optional fields during transition?
   - c) Support both journal-first and legacy arrays in parallel with a feature flag?

2. **Strategy Interface Changes**: The `BrickOutput` TypedDict currently requires `cash_in` and `cash_out` arrays. Should we:
   - a) Make these fields optional (nullable/zero arrays)?
   - b) Create a new `BrickOutputV2` type?
   - c) Update the TypedDict to remove these fields entirely?

3. **Existing Tests**: Many tests likely depend on `cash_in`/`cash_out` arrays. Should we:
   - a) Update all tests to use journal-first aggregation?
   - b) Keep legacy tests in a separate suite temporarily?
   - c) Delete legacy tests immediately?

## Implementation Details

4. **Node ID Mapping**: How should we map brick IDs to node IDs consistently?
   - a) Derive from brick ID (e.g., `a:cash` from brick `cash` with kind `a.cash`)?
   - b) Require explicit node_id in brick spec?
   - c) Use a mapping function in AccountRegistry?

5. **BoundaryInterface Singleton**: The spec mentions `b:boundary` as a singleton. Should we:
   - a) Create a special BoundaryInterface class/constant?
   - b) Use a string literal `"b:boundary"` everywhere?
   - c) Register it in AccountRegistry as a special account?

6. **Journal Entry Metadata**: The spec requires `operation_id`, `parent_id`, `sequence`, `origin_id`, and `tags` in entry metadata. Should we:
   - a) Validate all required keys at entry creation time?
   - b) Provide helper functions to stamp metadata automatically?
   - c) Both validate and provide helpers?

7. **Posting Metadata**: Postings need `node_id` and optionally `category` (for boundary). Should we:
   - a) Store `node_id` in `posting.metadata` as specified?
   - b) Also keep `account_id` field for backward compatibility?
   - c) Replace `account_id` with `node_id` entirely?

8. **Two-Posting Invariant**: The spec says each entry must have exactly 2 postings. Should we:
   - a) Enforce this strictly (fail if != 2)?
   - b) Allow multiple postings but validate they net to zero?
   - c) Start with 2-postings only, allow multiple later?

9. **Account Registry Integration**: Currently, `Posting` uses `account_id`. How should we integrate:
   - a) Map `node_id` -> `account_id` via AccountRegistry?
   - b) Use `node_id` directly and update Posting class?
   - c) Support both during transition?

10. **Shell Bricks (FlowShell/TransferShell)**: Currently FBrick and TBrick classes exist. Should we:
    - a) Keep classes but change behavior (no balances, only journal entries)?
    - b) Create new FlowShellBrick/TransferShellBrick classes?
    - c) Add a flag/kind to distinguish shell vs regular?

## Strategy Changes

11. **A/L Strategy Refactoring**: A/L strategies currently emit `cash_in`/`cash_out`. When migrating:
    - a) Remove these arrays entirely, only emit journal entries?
    - b) Keep arrays but populate from journal entries (for compatibility)?
    - c) Make arrays optional and populate from journal if present?

12. **F/T Strategy Refactoring**: FlowShell and TransferShell strategies should:
    - a) Return zero arrays for `cash_in`/`cash_out` and only create journal entries?
    - b) Not return BrickOutput at all (create new interface)?
    - c) Return BrickOutput but with empty arrays and journal entries?

13. **Journal Entry Creation**: Where should strategies create journal entries?
    - a) In strategy.simulate() and pass to context?
    - b) Return entries in BrickOutput.metadata?
    - c) Context provides a journal that strategies write to directly?

14. **Cash Account Strategy**: The cash account strategy currently uses `external_in`/`external_out` from spec. Should we:
    - a) Remove these and compute balance purely from journal entries?
    - b) Keep them for initial balance setup?
    - c) Use journal entries exclusively?

## Aggregation & Results

15. **Journal-First Aggregation**: Should `ScenarioResults.monthly()`:
    - a) Always use journal-first (no legacy path)?
    - b) Support both with a flag (default journal-first)?
    - c) Only use journal-first if journal is present?

16. **Internal Cancellation**: For MacroGroup cancellation, should we:
    - a) Cancel when both postings are INTERNAL and both node_ids in selection?
    - b) Also check that both postings belong to same entry?
    - c) Use `origin_id` to group related entries for cancellation?

17. **Asset vs Liability Postings**: For cashflow, should we:
    - a) Only include ASSET postings (DR = inflow, CR = outflow)?
    - b) Include LIABILITY postings but with opposite sign?
    - c) Track both separately?

18. **Boundary Attribution**: How should we attribute boundary postings to P&L?
    - a) By `category` tag (e.g., `income.salary`, `expense.interest`)?
    - b) By `type` tag (e.g., `income`, `expense`)?
    - c) Both category and type?

## MacroGroup Constraints

19. **MacroGroup Membership Validation**: Should we:
    - a) Validate at MacroBrick creation time?
    - b) Validate at scenario validation time?
    - c) Validate at expansion time (lazy)?

20. **DAG Validation**: Cycle detection already exists in `expand_member_bricks()`. Should we:
    - a) Keep existing implementation?
    - b) Add explicit validation at creation time?
    - c) Both?

21. **Shell/Boundary Exclusion**: When validating MacroGroup members, should we:
    - a) Reject F/T bricks immediately?
    - b) Allow but warn, then fail at expansion?
    - c) Silently skip F/T bricks during expansion?

## Validation & Guardrails

22. **Two-Posting Validation**: Should validation:
    - a) Fail fast on entry creation?
    - b) Collect all errors and report at end?
    - c) Warn on first, fail on second?

23. **Metadata Validation**: Should we validate required metadata:
    - a) At entry creation time?
    - b) At journal posting time?
    - c) At aggregation time (lazy)?

24. **Zero-Sum Validation**: The journal already validates zero-sum. Should we:
    - a) Keep existing validation?
    - b) Add per-currency validation as specified?
    - c) Enhance with better error messages?

25. **Origin ID Uniqueness**: Should we:
    - a) Validate uniqueness at entry creation?
    - b) Check at journal posting time?
    - c) Warn on duplicates, fail on collision?

## Testing & Examples

26. **Test Migration Strategy**: Should we:
    - a) Update existing tests to use journal entries?
    - b) Create new test suite for V2?
    - c) Keep both until V2 is stable?

27. **Golden Tests**: Do we have golden test data that needs updating?
    - a) Yes, update golden files to match journal-first output?
    - b) No, create new golden files?
    - c) Keep both old and new?

28. **Example Updates**: Should we update examples in `examples/` directory:
    - a) Immediately to show V2 usage?
    - b) After core implementation is done?
    - c) Create new examples for V2?

## Performance & Optimization

29. **Journal Indexing**: The spec mentions indexing by month and account. Should we:
    - a) Add indexes to Journal class?
    - b) Use pandas DataFrames for fast lookups?
    - c) Optimize later if performance becomes an issue?

30. **Vectorized Operations**: Should we:
    - a) Use vectorized pandas operations for aggregation?
    - b) Keep Python loops for clarity?
    - c) Profile first, optimize hot paths?

## CLI & UX

31. **Transfer Visibility Default**: Should CLI default to:
    - a) `BOUNDARY_ONLY` as recommended?
    - b) `ALL` for backward compatibility?
    - c) Make it configurable with `BOUNDARY_ONLY` as default?

32. **Diagnostics Output**: Should we:
    - a) Add a new CLI subcommand for journal diagnostics?
    - b) Add flags to existing commands?
    - c) Both?

## Open Questions from Spec

33. **Interest Attribution**: The spec says "retain signed `interest` in `BrickOutput` for KPIs while using journal for cash impact." Should we:
    - a) Keep `interest` array in BrickOutput?
    - b) Also create journal entries for interest?
    - c) Both?

34. **Opening Balance Policy**: The spec says "choose exactly one: state-only openings OR journalized opening entries." Which should we:
    - a) Use state-only (A/L arrays initialize balances)?
    - b) Use journalized (equity → asset/liability entries)?
    - c) Make it configurable?

35. **FX Handling**: For cross-currency events, should we:
    - a) Split into separate entries (trade + FX P&L)?
    - b) Use explicit FX accounts?
    - c) Implement basic support first, enhance later?

36. **Time Normalization**: The spec says normalize to month precision. Should we:
    - a) Always normalize to month (existing behavior)?
    - b) Keep `value_date` in metadata for day precision?
    - c) Support both month and day precision?

## Critical Path Questions (Must Answer Before Starting)

These questions are critical for implementation to begin:

- **Question 1**: Migration approach (Question 1 above)
- **Question 2**: Node ID mapping strategy (Question 4 above)
- **Question 3**: Journal entry creation location (Question 13 above)
- **Question 4**: BrickOutput interface changes (Question 2 above)
- **Question 5**: Two-posting invariant strictness (Question 8 above)
