# Postings Model & Brick Types (v2)

This specification simplifies how we think about balances and cash movements. Assets/Liabilities hold balances only. Every cash movement is a pair of postings (one Debit, one Credit). “Shell” bricks generate those postings; MacroGroups aggregate Assets/Liabilities cleanly.

TL;DR
- Assets/Liabilities = balances only. No direct inflow/outflow arrays.
- Every cash movement = 2 postings (DR/CR) inside one entry (CDPair).
- FlowShellBrick (income/expense) and TransferShellBrick (internal transfer) generate postings; they carry no balances.
- BoundaryInterface = a single hidden node for the “outside world” side of income/expense.
- MacroGroups = containers of A/L (and/or other MacroGroups). Internal transfers cancel when both sides are inside the selection.

## Motivation

Today, ABricks/LBricks both compute balances and often also emit in/outflows directly. In macro views, this can mix responsibilities and lead to double counting or noisy intra‑transfers. The proposed split:

- A/L bricks: only state (assets, liabilities, optionally derived equity), no direct in/outflows.
- D/C transactions: all cash movements, always created in debit/credit pairs, and always attributable to envelopes (TBricks, FBricks, schedules inside LBricks, etc.).
- Macrobricks: only contain A/L bricks; flows shown are those attributable to selected A/L members, with intra‑selection D/C pairs cancelled.

This follows well‑understood accounting principles and aligns with the existing double‑entry `Journal` scaffolding present in the codebase.

## Feasibility (high)

The core engine already includes:
- Double‑entry `Journal` with `JournalEntry` and `Posting` (pairing by currency, zero‑sum invariant).
- `AccountScope` and `AccountType` to distinguish INTERNAL vs BOUNDARY (income/expense/equity) accounts.
- `TransferVisibility` and registry plumbing for transfer‑like bricks (TBricks) and flows (FBricks).

Therefore, this proposal can be implemented incrementally by shifting flows into journal entries and keeping A/L bricks balance‑only, while preserving compatibility during a transition phase.

## Glossary (plain language)

 - Debit (DR) / Credit (CR): the two sides of a double‑entry. Their effect depends on the type of account the posting hits. “Increase/decrease” here means the account’s own running total for the period, not cash by itself.
  - Assets: DR increases the asset total; CR decreases it.
  - Liabilities: DR decreases the liability total; CR increases it.
  - Equity: DR decreases equity; CR increases equity.
  - Income (Revenue): CR increases the income total; DR reduces it.
  - Expense: DR increases the expense total; CR reduces it.
  - Where these live in this model:
    - Asset/Liability postings hit internal nodes (`a:/l:`).
    - Income/Expense postings hit the `b:boundary` node with tags that name the category (e.g., `income.salary`, `expense.rent`). They are not assets or liabilities.
  - Cash movement is always the other posting in the pair (typically an Asset posting like `a:cash`).

  Examples:
  - Salary received:
    - DR asset:cash 5,000 (cash up), CR income.salary 5,000 (income up)
  - Rent paid:
    - DR expense.rent 1,500 (expense up), CR asset:cash 1,500 (cash down)
  - Loan principal payment:
    - DR liability:mortgage 1,000 (liability down), CR asset:cash 1,000 (cash down)
  - Interest expense:
    - DR expense.interest 300 (expense up), CR asset:cash 300 (cash down)
  - Expense refund:
    - DR asset:cash 200 (cash up), CR expense.rent 200 (expense down)

  Mnemonic
  - DEAD CLIC: Debits increase Expenses, Assets, (and Dividends); Credits increase Liabilities, Income, and Capital (Equity).

  Contra postings (reductions within the same category)
  - DR on Income: reduces an income category (e.g., salary clawback, sales return, correction). It is not an Expense; it’s negative Income.
  - CR on Expense: reduces an expense category (e.g., refund, rebate, reversal). It is not Income; it’s negative Expense.
  - In analysis, show these as negatives within their category, not reclassified to the opposite side.
- Posting: one row hitting one account/node with a direction (DR/CR) and an amount.
- CDPair (entry): exactly two postings that belong together (one DR, one CR). They net to zero per currency.
- Operation: a higher‑level event (e.g., a monthly loan payment) that may create multiple CDPairs (principal, interest, fee).
- Nodes (brick‑like types):
  - AssetNode (ABrick): can create postings and be posted to.
  - LiabilityNode (LBrick): can create postings and be posted to.
  - FlowShellBrick: creates postings for boundary↔internal flows (income/expense). Not posted to.
  - TransferShellBrick: creates postings for internal↔internal transfers. Not posted to.
  - BoundaryInterface: singleton node representing the “outside world” side. Hidden; posted to but does not create postings.
- MacroGroup (MacroBrick): container of A/L nodes and/or other MacroGroups (DAG; no cycles). Shells/Boundary cannot be members.

Why this helps: single source of truth for flows (postings), clear separation of concerns, robust cancellation in MacroGroups, and easy inspection by node or by operation.

## Canonical Posting Schema

Posting (row)
- direction: `DR` | `CR`
- amount: Decimal (absolute)
- currency: str
- node_id: which node/account this line hits (A/L or Boundary)
- entry_id: ID of the CDPair (groups the two postings)
- parent_id: creator node (A/L/FlowShell/TransferShell)
- timestamp: normalized to month
- tags: `{type: principal|interest|fee|income|expense|contribution|...}`
- metadata: optional dict

CDPair (entry)
- entry_id: e.g., `cp:<operation_id>:<seq>`
- operation_id: `op:<parent_id>:<YYYY-MM>[:hash]`
- parent_id: same as postings.parent_id
- timestamp
- tags/metadata: shared context

Node IDs
- Asset: `a:<slug>` (e.g., `a:cash`, `a:etf`)
- Liability: `l:<slug>` (e.g., `l:mortgage`)
- FlowShell: `fs:<slug>` (e.g., `fs:salary`)
- TransferShell: `ts:<slug>` (e.g., `ts:contrib_etf`)
- BoundaryInterface: `b:boundary` (singleton)
- MacroGroup: `mg:<slug>`

Notes
- Counterparty is implicit: it’s the other posting in the same entry_id.
- “Target” is just the posting’s node_id on the DR line; you can always reconstruct both sides from the pair.

The following practices reduce foot‑guns and make failures obvious:

- Deterministic origins
  - Always compute `origin_id` via `generate_transaction_id(brick_id, timestamp, spec, links, sequence)` where `timestamp` is normalized to month and `sequence` disambiguates multiple entries per month.
  - Include `envelope_brick_id` and `type` tags (`principal`, `interest`, `fee`, `contribution`, `dividend`, etc.).

- Per‑currency zero‑sum
  - Keep `JournalEntry` zero‑sum by currency (already enforced). For cross‑currency events, split into two entries: trade legs and FX P&L, or use explicit FX accounts so each entry balances per currency.

- Account scope/type validation
  - Use `AccountRegistry.validate_transfer_accounts(from, to)` for TBricks (both must be INTERNAL).
  - Use `AccountRegistry.validate_flow_accounts(boundary, [internal...])` for FBricks.
  - Validate that LBrick schedules post to the correct INTERNAL/BOUNDARY accounts depending on leg (principal vs interest/fees).

- MacroGroup membership (a.k.a. MacroBrick)
  - Members may be A/L bricks and/or other MacroGroups (nested). The structure must be a DAG (no cycles). Shells (FlowShell/TransferShell) and Boundary are not valid members.
  - Intra‑selection cancellation is applied only when: all internal postings of an entry map to selected A/L members (after expansion/dedup) and there are no boundary postings.

- Journal‑first aggregation (feature flag)
  - Add a flag (e.g., `journal_mode = 'derived' | 'journal_first'`) in aggregators. Default to `derived` initially; switch default after migration.
  - On mismatch between derived and journal totals beyond tolerance, emit warnings and attach reconciliation metadata.

- Opening balance policy
  - Choose exactly one: state‑only openings (A/L arrays initialize balances) OR journalized opening entries (equity → asset/liability). Do not do both.

- Precision & rounding
  - Use `Decimal` for monetary amounts in postings; round to currency minor units at posting boundaries; avoid accumulating binary float error.

- Idempotency & determinism
  - Strategy `simulate` must be deterministic given the same inputs; repeated runs produce identical journal (IDs and postings ordering).
  - Raise if two distinct entries collide on `origin_id`. Recommend prefixing with envelope brick id or include sequence.

- Time normalization
  - Normalize all posting timestamps to month precision for consistency with monthly engine. If day precision is needed later, keep a `value_date` in metadata.

- Transfer visibility defaults
  - Prefer `TransferVisibility.BOUNDARY_ONLY` in end‑user views. Surface `ALL`/`ONLY` in CLI/UX for diagnostics.

- Performance hygiene
  - Index journal entries by month and by account for fast selection/cancellation.
  - Avoid per‑entry Python loops in hot aggregation paths; prefer vectorized/groupby over pre‑bucketed arrays.

## Core Rules (must hold)

- Two‑posting invariant: each entry_id has exactly 2 postings: {DR, CR}.
- Zero‑sum by currency: per entry_id and per currency: sum(DR.amount) == sum(CR.amount).
- Parent consistency: both postings share the same parent_id and timestamp.
- Account scope/type:
  - TransferShell: both postings hit INTERNAL nodes (Assets/Liabilities), no Boundary.
  - FlowShell: exactly one posting hits BoundaryInterface; the other hits an INTERNAL node.
  - A/L schedules: principal is INTERNAL↔INTERNAL; interest/fees are BOUNDARY↔INTERNAL.
- BoundaryInterface: may be node_id on postings; must never be a parent_id; hidden and non‑selectable.
- MacroGroup membership: members are A/L and/or other MacroGroups; DAG only; Shells/Boundary are invalid members.

## Guardrails & Best Practices

Run these checks during scenario build/run; fail or warn as indicated:

- Entry zero‑sum (fail): each `JournalEntry` sums to zero per currency.
- Posting scope (fail): TBrick postings are INTERNAL↔INTERNAL only; FBrick postings include exactly one BOUNDARY side.
- Envelope pairing (fail): each envelope event creates at least one DR and one CR posting.
- Origin metadata (fail): `origin_id` and `envelope_brick_id` present.
- Duplicate origin (fail): no duplicate `(origin_id, currency)` within the same run.
- Macro membership (warn→fail): Macrobricks contain only A/L bricks.
- Orphan accounts (warn): each posting account exists in `AccountRegistry`.
- Opening policy (warn): detect and warn if both state openings and opening journal entries are used for the same brick.
- Aggregation reconciliation (warn): journal‑first vs derived totals differ beyond tolerance.

## Cancellation & Views

- MacroGroup cancellation (expanded and deduped A/L set):
  - For a CDPair, if both postings’ node_id are INTERNAL and both are inside the selection → cancel (net 0 in flows).
  - If any posting hits BoundaryInterface → never cancel.

- Single node inspection (A/L):
  - Balances: taken from the A/L strategy (assets/liabilities, and signed interest if provided).
  - Node‑side movements: include postings where `node_id == this A/L id` (e.g., principal DR to `l:mortgage`). This shows how the balance changes by type.
  - Attributed cashflow: from entries where `parent_id == this A/L id`, include only the cash (asset) leg of the pair when computing cash_in/cash_out. Do not sum both postings; pick the cash leg and sign it by DR/CR on the asset posting (DR = inflow, CR = outflow).
  - Boundary attribution: from the same parent entries, show the boundary posting as P&L attribution (e.g., interest expense), separate from cashflow.
  - This avoids cancellation while keeping provenance: principal appears as node‑side movement; interest appears as boundary P&L; cash effects come from the cash leg only.

  Shells (FlowShell/TransferShell):
  - Show postings they created (`parent_id = shell id`). No balances.

MacroGroup (MacroBrick) inspection
- Purpose: show balances and flows for a container of A/L nodes (and nested MacroGroups) without double‑counting internal churn.
- Expand members:
  - Recursively expand to a flat, deduped set S of A/L node_ids. Validate DAG (no cycles).
- Balances:
  - Sum assets/liabilities (and optional signed interest) across nodes in S on the time index.
- Cashflow (journal‑first): for each CDPair (entry_id):
  - Read the two postings (DR, CR) with their node_id.
  - If both postings are INTERNAL and both node_id ∈ S → cancel (ignore for cash_in/out).
  - Else, include only the posting whose node_id ∈ S and whose node type is ASSET:
    - DR on ASSET → inflow; CR on ASSET → outflow.
    - Ignore LIABILITY postings for cashflow totals; treat them as node‑side movements.
  - If any posting hits Boundary (`b:boundary`): never cancel; include the cash (ASSET) posting if its node_id ∈ S, and attribute boundary by tag (income/expense) in P&L.
- Node‑side movements:
  - Separately, aggregate postings where node_id ∈ S and node is LIABILITY by tags (principal, fee, etc.) to explain balance changes.
- Transfer visibility:
  - Apply `TransferVisibility` after selection (OFF/ONLY/BOUNDARY_ONLY/ALL). BOUNDARY_ONLY is recommended default for end‑user views.
- Cross‑currency:
  - Enforce zero‑sum per currency at entry level. Aggregate by currency or convert via FX before aggregation if configured.

Examples
- MacroGroup S = {a:cash, a:etf}
  - DR a:etf 1,500; CR a:cash 1,500 → both INTERNAL and in S → cancel (no cashflow).
  - DR a:cash 5,000; CR b:boundary (income.salary) 5,000 → include inflow +5,000; never cancel.
- MacroGroup S = {l:mortgage}
  - DR l:mortgage 1,000; CR a:cash 1,000 → cash leg not in S → no cashflow; record principal under node‑side movements.
  - DR b:boundary (expense.interest) 300; CR a:cash 300 → boundary present; no cashflow unless a:cash ∈ S; attribute interest in P&L.

## Test Matrix

Add/extend tests to cover:

- Single mortgage (LBrick): principal/interest split; principal internal transfer cancels inside macro selection; interest shows as boundary flow.
- Salary (FBrick): boundary‑crossing inflow appears; switching `TransferVisibility` modes changes only transfer visibility.
- Internal transfer (TBrick): cancels in macro when both sides included; appears when only one side selected.
- Multi‑leg month: multiple entries per month from one envelope; `sequence` ensures distinct `origin_id`s.
- Cross‑currency: split entries and FX P&L; zero‑sum enforced per currency; aggregation works per currency.
- Macro cycles: Macro expansion still DAG; dedup keeps cancellation reliable.
- Opening balances: journalized vs state‑only policy does not double count.
- Determinism: re‑running scenario produces identical journal ids/postings.

## Examples

Transfer cash → ETF (internal)
- Parent: `ts:contrib_etf`
- Entry: `cp:op:ts:contrib_etf:2026-01:1`
  - DR posting: amount=1000, node_id=`a:etf`
  - CR posting: amount=1000, node_id=`a:cash`
- In a MacroGroup containing both `a:cash` and `a:etf`, this cancels in flows.

Loan principal (internal)
- Parent: `l:mortgage`
- Entry: `cp:op:l:mortgage:2026-01:1`, tags.type=principal
  - DR: 1000 → `l:mortgage`
  - CR: 1000 → `a:cash`

Loan interest (boundary)
- Parent: `l:mortgage`
- Entry: `cp:op:l:mortgage:2026-01:2`, tags.type=interest
  - DR: 300 → `b:boundary` (expense.interest)
  - CR: 300 → `a:cash`

Salary income (boundary)
- Parent: `fs:salary`
- Entry: `cp:op:fs:salary:2026-01:1`, tags.type=income
  - DR: 5000 → `a:cash`
  - CR: 5000 → `b:boundary` (income.salary)

## Instrumentation & Logging

- Attach aggregation metadata: number of transfer entries, sum of transfer amounts, number of cancelled internal entries, reconciliation deltas.
- Emit concise warnings with remediation hints (e.g., “Macro contains F/T; use A/L only”).
- Provide a CLI subcommand to dump journal diagnostics per selection and per month.

## Migration Safety Nets

- Dual‑path compare: compute cash_in/out via both legacy per‑brick arrays and journal; log diffs; assert within tolerance in CI for core scenarios.
- Feature flag: gate journal‑first in CLI and library; allow fallback to legacy path for users until parity validated.
- Deprecation warnings: when A/L strategies emit `cash_in`/`cash_out`, issue warnings with link to this doc.

## Scope

- In scope: data model, aggregation rules, inspection rules, macrobrick membership constraints, migration path.
- Out of scope: immediate refactor of all strategies (phased), UI changes beyond documented views, storage/backends.

## Concepts

- ABrick: Asset balance producer (no direct in/outflows).
- LBrick: Liability balance/schedule producer (no direct in/outflows). Interest may be tracked as part of P&L but not as raw cashflow fields; cash impact is reflected via D/C entries.
- FBrick: Envelope for boundary‑crossing flows (income/expense). Produces D/C journal entries (income/expense ↔ internal account).
- TBrick: Envelope for internal transfers (internal ↔ internal). Produces D/C journal entries (no boundary accounts). Transparent by default in summaries.
- DBrick/CBrick: Transparent paired transaction “bricks.” These are not user‑facing standalone bricks; they are modeled as debit/credit postings within `JournalEntry` with clear provenance. They always occur in pairs for the same origin.
- MacroBrick: Composite selection of A/L bricks only, used for analysis/rollups.

## Data Model

- Journal entry is the canonical source of flows. Every cash movement is a `JournalEntry` with two or more `Posting`s:
  - Debit postings (DR) and Credit postings (CR). By convention: assets increase on DR, liabilities decrease on DR, expense is DR, income is CR.
  - `metadata.origin_id`: unique origin (see below) for pairing/cancellation.
  - `metadata.envelope_brick_id`: the envelope (e.g., `mortgage`, `salary_income`, `transfer_cash_to_etf`).
  - `metadata.tags`: optional tags like `{"type": "interest"}`, `{\"type\": \"principal\"}`, `{\"type\": \"fee\"}`.
- Origin ID: Use the existing deterministic generator to ensure stable IDs per month/transaction: `core.journal.generate_transaction_id(...)`.
- BrickOutput (canonical target):
  - A/L bricks emit: `assets`, `liabilities`, and optionally signed `interest` (P&L attribution). They do not emit `cash_in`/`cash_out` directly.
  - F/T bricks do not emit balances; they produce only journal entries.
  - For backward compatibility, scenario aggregation can derive `cash_in`/`cash_out` from the journal when needed.

## Invariants

- Pairing: Every D/C transaction has at least one DR and one CR posting; zero‑sum by currency enforced by `JournalEntry`.
- Transparency: D/C “bricks” (postings) are not user‑creatable; they are produced by strategies/envelopes.
- Provenance: All journal entries include `origin_id` and `envelope_brick_id`.
- Macro membership: Macrobricks accept only A/L brick IDs.

## Creation Rules (who emits D/C entries)

- LBrick schedules (e.g., loan annuity):
  - Principal amortization: DR Liability (reduce), CR Cash (pay from asset).
  - Interest: DR Expense (boundary), CR Cash (or accrue then settle, depending on spec).
  - Fees: DR Expense (boundary), CR Cash or add to principal per spec.
- FBrick (income/expense):
  - Income: CR Income (boundary), DR Cash (internal).
  - Expense: DR Expense (boundary), CR Cash (internal).
- TBrick (internal transfer):
  - Transfer: DR Destination internal account, CR Source internal account (no boundary accounts).

## Views & Aggregation

- Brick inspection (single A/L brick):
  - Show balances from the brick.
  - Include flows from journal entries that touch accounts linked to this brick. Show categorized contributions: principal, interest, fees, transfers.
  - Do not include postings to other internal bricks except as context; the net effect on this brick is what matters.

- Macrobrick inspection (multiple A/L bricks):
  - Members: only A/L bricks. Expand recursively and dedupe.
  - Balances: sum of member A/L balances.
  - Flows: include boundary‑crossing flows that touch any member account.
  - Internal cancellation rule: when both sides of a transaction are within the selected set, net them out (do not surface as inflow/outflow). Implementation uses `origin_id` and/or both accounts being internal and within selection.

- Transfer visibility (UI guardrails):
  - Keep existing `TransferVisibility` enum and extend application:
    - OFF: hide internal transfers entirely (set their net to zero in views).
    - ONLY: show transfers only (debug/finance‑ops mode).
    - BOUNDARY_ONLY: hide internal, show boundary‑crossing (income/expense) flows.
    - ALL: show everything (developer mode).

## Algorithms (sketch)

- Intra‑selection cancellation for macro views:
  1. Expand MacroBrick to member A/L set `S`.
  2. For each journal entry, partition postings by whether their accounts map to bricks in `S`.
  3. If all internal postings in the entry map to accounts within `S` and there is no boundary posting, cancel the entry (net 0 contribution to inflow/outflow).
  4. If there are boundary postings (income/expense/equity), include those contributions attributable to `S`.
  5. Aggregate remaining flows by month into `cash_in`/`cash_out` for display.

- Single brick flows:
  - Filter journal entries to those where at least one posting touches an account linked to the brick; show the per‑type breakdowns using posting metadata.

## API & Spec Changes

- MacroBrick:
  - Constraint: `members` may reference only A/L bricks or other MacroBricks.
  - Validation warning/error when F/T are referenced.

- Scenario.run(...):
  - Continue to return monthly totals, but compute `cash_in`/`cash_out` from the journal in “journal‑first” mode.
  - Return `journal` in results with `origin_id`, `envelope_brick_id`, and typed posting metadata for downstream analytics.

- Strategies:
  - A/L valuation/schedule strategies: stop emitting direct `cash_in`/`cash_out` over time; instead, publish journal entries. Keep `assets`, `liabilities`, `interest` arrays.
  - F/T strategies: publish journal entries only.

- Validation:
  - Journal zero‑sum enforced (already present).
  - For any envelope event (F/T or scheduled L), assert at least one DR and one CR.
  - Optional: assert that paired postings reference valid internal/boundary accounts consistent with the envelope type.

## Single‑Cutover Plan (immediate)

Given this is still a prototype with no users, adopt a clean cutover without parallel versions:

1) Journal‑first by default
   - Compute inflow/outflow exclusively from the Journal; remove per‑brick cash arrays for A/L strategies.
   - Keep A/L outputs to `assets`, `liabilities`, and signed `interest` only.

2) Enforce Macro A/L‑only
   - Update validation to fail fast if Macrobricks contain F/T bricks.

3) Strategy refactor
   - L strategies: stop emitting `cash_in`/`cash_out`; post principal/interest/fees to Journal with origin metadata.
   - F strategies: post boundary‑crossing entries only; no balances.
   - T strategies: post internal transfers; default transparent.

4) Cancellation semantics
   - Implement intra‑selection cancellation by origin_id and account scope in macro views.

5) Guardrails baked‑in
   - Enforce account scope/type validation, zero‑sum by currency, origin metadata presence, and duplicate origin detection as hard errors.

6) Test hardening
   - Add the test matrix in this doc; CI blocks on failures (no legacy path fallback).

## Worked Examples

- Mortgage payment (monthly, LBrick):
  - Journal entries per month (simplified):
    - Principal: DR `liability:mortgage` 1,000; CR `asset:cash` 1,000; `origin_id=...`, `envelope_brick_id="mortgage"`, `type=principal`.
    - Interest: DR `expense:interest` 300; CR `asset:cash` 300; `type=interest`.
  - Inspect LBrick `mortgage`: show liability balance over time, principal paid, interest expense tagged to this envelope. Cash postings are not double counted elsewhere when both sides are inside a macro selection.

- Salary income (FBrick):
  - Journal: CR `income:salary` 5,000; DR `asset:cash` 5,000; `origin_id=...`, `envelope_brick_id="salary"`.
  - Macrobrick `assets`: shows inflow from salary; no internal cancellation applied because one side is boundary.

- Internal contribution (TBrick) from `cash` to `etf`:
  - Journal: DR `asset:etf` 1,500; CR `asset:cash` 1,500; `origin_id=...`, `envelope_brick_id="contrib_etf"`.
  - Macrobrick `assets` containing both `cash` and `etf`: contribution nets to zero in flows; balances move accordingly.

## Pros & Cons

- Pros:
  - Clear separation of state (A/L) and flows (journal).
  - Macro views become clean; intra‑selection churn cancels out.
  - Strong auditability via origin IDs and envelopes; aligns with accounting.
- Cons:
  - Requires phased refactor of strategies and aggregation.
  - Potential performance considerations if generating many journal entries (can be mitigated with vectorized or batched creation).

## Open Questions

- Interest attribution: retain signed `interest` in `BrickOutput` for KPIs while using journal for cash impact? Recommended: yes.
- Account mapping: standardize mapping from bricks to account IDs; enforce via `AccountRegistry`.
- UI/CLI defaults: should transfer visibility default to `BOUNDARY_ONLY` for most views? Likely yes.

## Implementation Notes

- Reuse `generate_transaction_id` for `origin_id` across all strategies (ensure consistent normalization to month granularity).
- Store `envelope_brick_id` to support inspection and traceability.
- Start by implementing journal‑first aggregation in `ScenarioResults.monthly(...)`. No legacy path required.

## DR/CR Cheat Sheet (quick reference)

- Asset (cash, ETF): DR increases, CR decreases
- Liability (loan): DR decreases, CR increases
- Equity: DR decreases, CR increases
- Income (salary/dividend): DR decreases, CR increases
- Expense (interest/rent): DR increases, CR decreases

## Terminology: DR/CR and Directionality

- DR (Debit) and CR (Credit) are the two sides of a double‑entry posting.
  - Debits increase assets and expenses; decrease liabilities and equity.
  - Credits decrease assets and expenses; increase liabilities and equity.
- CDPair: the atomic transaction unit consisting of exactly one DebitPosting (DR) and one CreditPosting (CR), zero‑sum by currency.
- Parent: the node (Asset/Liability/FlowShell/TransferShell) that created the CDPair.
- Target: the node referenced by the DR side (where value lands).
- Counterparty: the node referenced by the CR side.

Examples with IDs and roles:
- Transfer cash → ETF (internal ↔ internal)
  - Parent: `ts:contrib_etf`
  - DR: `a:etf` +1,000 → Target: `a:etf`
  - CR: `a:cash` −1,000 → Counterparty: `a:cash`
  - Cancellation: internal‑only; in a MacroGroup containing both `a:cash` and `a:etf`, this CDPair nets to 0 in flows.

- Loan principal (internal ↔ internal)
  - Parent: `l:mortgage`
  - DR: `l:mortgage` +1,000 (reduces liability) → Target: `l:mortgage`
  - CR: `a:cash` −1,000 → Counterparty: `a:cash`
  - Cancellation: internal‑only; cancels if both `l:mortgage` and `a:cash` are in the MacroGroup selection.

- Loan interest (boundary ↔ internal)
  - Parent: `l:mortgage`
  - DR: `b:boundary` (expense.interest) +300 → Target: `b:boundary`
  - CR: `a:cash` −300 → Counterparty: `a:cash`
  - Cancellation: never cancels (touches boundary).

- Salary income (boundary ↔ internal)
  - Parent: `fs:salary`
  - DR: `a:cash` +5,000 → Target: `a:cash`
  - CR: `b:boundary` (income.salary) −5,000 → Counterparty: `b:boundary`
  - Cancellation: never cancels (touches boundary).

MacroGroup membership
- MacroGroups may contain A/L nodes and/or other MacroGroups; DAG only (no cycles). Shells and Boundary cannot be members.
- Cancellation logic evaluates the expanded, deduplicated set of A/L members when deciding whether a CDPair is internal‑only and fully inside selection.
