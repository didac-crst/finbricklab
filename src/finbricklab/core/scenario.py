"""
Scenario engine for orchestrating financial simulations.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from .bricks import (
    ABrick,
    FBrick,
    FinBrickABC,
    LBrick,
    TBrick,
    wire_strategies,
)
from .context import ScenarioContext
from .errors import ConfigError
from .events import Event
from .kinds import K
from .links import PrincipalLink, StartLink
from .macrobrick import MacroBrick
from .registry import Registry
from .results import BrickOutput, ScenarioResults, aggregate_totals, finalize_totals
from .specs import LMortgageSpec
from .transfer_visibility import TransferVisibility
from .utils import _apply_window_equity_neutral, active_mask, month_range
from .validation import DisjointReport


@dataclass
class ScenarioConfig:
    """Configuration options for scenario execution."""

    warn_on_overlap: bool = True
    include_struct_results: bool = True
    structs_filter: set[str] | None = None


@dataclass
class Scenario:
    """
    Scenario engine for orchestrating financial simulations.

    This class represents a complete financial scenario containing multiple
    financial bricks and optional MacroBricks. It orchestrates the simulation process by:
    1. Wiring strategies to bricks based on their kind discriminators
    2. Preparing all bricks for simulation
    3. Simulating all bricks in the correct order
    4. Routing cash flows to the designated cash account
    5. Aggregating results into summary statistics

    Attributes:
        id: Unique identifier for the scenario
        name: Human-readable name for the scenario
        bricks: List of all financial bricks in the scenario
        macrobricks: List of all MacroBricks in the scenario (optional)
        currency: Base currency for the scenario (default: 'EUR')
        config: Configuration options for scenario execution

    Note:
        The scenario supports one or more cash account bricks (kind='{K.A_CASH}')
        to receive routed cash flows from other bricks. Use links.route to control
        cash flow routing to specific accounts.
    """

    id: str
    name: str
    bricks: list[FinBrickABC]
    macrobricks: list[MacroBrick] = field(default_factory=list)
    currency: str = "EUR"
    config: ScenarioConfig = field(default_factory=ScenarioConfig)
    settlement_default_cash_id: str | None = (
        None  # Default cash account for settlement shortfalls
    )
    validate_routing: bool = True  # Validate cash flow routing balance
    _last_totals: pd.DataFrame | None = None
    _last_results: dict | None = None
    _registry: Registry | None = None

    def __post_init__(self):
        """Initialize the registry after dataclass construction."""
        if self._registry is None:
            self._registry = self._build_registry()

        # Validate MacroBrick membership (V2: A/L only, no F/T/Shell/Boundary)
        for macrobrick in self.macrobricks:
            macrobrick.validate_membership(self._registry)

    def _build_registry(self) -> Registry:
        """Build the registry from bricks and macrobricks."""
        bricks_dict = {brick.id: brick for brick in self.bricks}
        macrobricks_dict = {mb.id: mb for mb in self.macrobricks}
        return Registry(bricks_dict, macrobricks_dict)

    @classmethod
    def from_dict(cls, data: dict) -> Scenario:
        """
        Create a Scenario from a dictionary specification.

        Args:
            data: Dictionary containing scenario specification with keys:
                - id: Scenario ID
                - name: Scenario name
                - bricks: List of brick specifications
                - structs: List of MacroBrick specifications (optional)
                - currency: Base currency (optional, default: 'EUR')

        Returns:
            Configured Scenario instance
        """
        # Parse bricks
        bricks = []
        for brick_cfg in data.get("bricks", []):
            kind = brick_cfg.get("kind", "")
            if kind.startswith("a."):
                bricks.append(ABrick(**brick_cfg))
            elif kind.startswith("l."):
                bricks.append(LBrick(**brick_cfg))
            elif kind.startswith("f."):
                from .bricks import FBrick

                bricks.append(FBrick(**brick_cfg))
            else:
                raise ConfigError(f"Unknown brick kind: {kind}")

        # Parse MacroBricks
        macrobricks = []
        for struct_cfg in data.get("structs", []):
            macrobricks.append(MacroBrick(**struct_cfg))

        return cls(
            id=data.get("id", "scenario"),
            name=data.get("name", "Unnamed Scenario"),
            bricks=bricks,
            macrobricks=macrobricks,
            currency=data.get("currency", "EUR"),
        )

    def assert_disjoint(self, label: str, macrobrick_ids: list[str]) -> None:
        """
        Assert that the specified MacroBricks are disjoint (no shared bricks).

        Args:
            label: Label for the assertion (for error messages)
            macrobrick_ids: List of MacroBrick IDs to check

        Raises:
            ConfigError: If any MacroBricks share bricks
        """
        if len(macrobrick_ids) < 2:
            return  # Nothing to check

        # Build sets of member bricks for each MacroBrick
        member_sets = {}
        for mb_id in macrobrick_ids:
            if not self._registry.is_macrobrick(mb_id):
                raise ConfigError(f"MacroBrick '{mb_id}' not found in registry")
            member_sets[mb_id] = self._registry.get_struct_flat_members(mb_id)

        # Check for intersections
        for i, mb1_id in enumerate(macrobrick_ids):
            for mb2_id in macrobrick_ids[i + 1 :]:
                intersection = member_sets[mb1_id] & member_sets[mb2_id]
                if intersection:
                    raise ConfigError(
                        f"MacroBricks '{mb1_id}' and '{mb2_id}' in {label} are not disjoint. "
                        f"Shared bricks: {sorted(intersection)}"
                    )

    def check_disjoint(self, macrobrick_ids: list[str]) -> DisjointReport:
        """
        Check if the specified MacroBricks are disjoint (no shared bricks).

        Args:
            macrobrick_ids: List of MacroBrick IDs to check

        Returns:
            DisjointReport with results and details
        """
        from .validation import DisjointReport

        if len(macrobrick_ids) < 2:
            return DisjointReport(is_disjoint=True, conflicts=[])

        # Build sets of member bricks for each MacroBrick
        member_sets = {}
        for mb_id in macrobrick_ids:
            if not self._registry.is_macrobrick(mb_id):
                return DisjointReport(
                    is_disjoint=False,
                    conflicts=[f"MacroBrick '{mb_id}' not found in registry"],
                )
            member_sets[mb_id] = self._registry.get_struct_flat_members(mb_id)

        # Check for intersections
        conflicts = []
        for i, mb1_id in enumerate(macrobrick_ids):
            for mb2_id in macrobrick_ids[i + 1 :]:
                intersection = member_sets[mb1_id] & member_sets[mb2_id]
                if intersection:
                    conflicts.append(
                        {
                            "macrobrick1": mb1_id,
                            "macrobrick2": mb2_id,
                            "shared_bricks": sorted(intersection),
                        }
                    )

        return DisjointReport(is_disjoint=len(conflicts) == 0, conflicts=conflicts)

    def run(
        self,
        start: date,
        months: int,
        selection: list[str] | None = None,
        include_cash: bool = True,
    ) -> dict:
        """
        Run the complete financial scenario simulation.

        This method orchestrates the entire simulation process:
        1. Resolves the execution set from selection (bricks and/or MacroBricks)
        2. Creates the time index for the simulation period
        3. Wires strategies to bricks based on their kind discriminators
        4. Prepares all bricks for simulation
        5. Simulates all non-cash bricks and routes their cash flows
        6. Simulates the cash account with all routed flows
        7. Aggregates results into summary statistics

        Args:
            start: The starting date for the simulation
            months: Number of months to simulate
            selection: Optional list of brick IDs and/or MacroBrick IDs to execute.
                      If None, executes all bricks in the scenario.
            include_cash: Whether to include cash account in aggregated results

        Returns:
            Dictionary containing:
                - 'outputs': Dict mapping brick IDs to their individual BrickOutput results
                - 'by_struct': Dict mapping MacroBrick IDs to their aggregated BrickOutput results
                - 'totals': DataFrame with aggregated monthly totals (cash flows, assets, debt, equity)

        Raises:
            AssertionError: If there are no cash account bricks (kind='{K.A_CASH}') in selection
            ConfigError: If selection contains unknown IDs or invalid MacroBrick references

        Note:
            The simulation supports multiple cash accounts. Cash flows from other bricks
            are routed based on links.route configuration, or to the default cash account
            if no routing is specified. If MacroBricks share bricks, execution is
            deduplicated at the scenario level.
        """
        # Resolve execution set from selection
        brick_ids, overlaps = self._resolve_execution_set(selection)

        # Build dependency graph and compute deterministic execution order
        edges = self._build_dependency_graph(brick_ids)
        execution_order = self._topological_order(brick_ids, edges)

        # Initialize simulation context
        t_index, ctx = self._initialize_simulation(start, months)

        # Prepare bricks for simulation
        self._prepare_simulation(ctx)

        # Simulate selected bricks and route cash flows (in deterministic order)
        outputs, journal = self._simulate_bricks(ctx, t_index, execution_order)

        # Aggregate results into summary statistics (journal-first for V2)
        totals = self._aggregate_results(
            outputs, t_index, include_cash, journal=journal
        )

        # Build MacroBrick aggregates
        by_struct = self._build_struct_aggregates(outputs, brick_ids)

        # Store for convenience methods
        self._last_totals = totals
        self._last_results = {
            "outputs": outputs,
            "by_struct": by_struct,
            "totals": totals,
            "views": ScenarioResults(
                totals, registry=self._registry, outputs=outputs, journal=journal
            ),
            "journal": journal,
            "_scenario_bricks": self.bricks,
            "meta": {"execution_order": execution_order, "overlaps": overlaps},
        }

        return self._last_results

    def _resolve_execution_set(
        self, selection: list[str] | None
    ) -> tuple[set[str], dict[str, dict[str, any]]]:
        """
        Resolve selection to a unique set of brick IDs for execution.

        Args:
            selection: List of brick IDs and/or MacroBrick IDs, or None for all bricks

        Returns:
            Tuple of (execution_set, overlaps_report) where:
            - execution_set: Set of unique brick IDs to execute
            - overlaps_report: Dict mapping brick_id to overlap info for current selection

        Raises:
            ConfigError: If selection contains unknown IDs
        """
        if selection is None:
            # Default: execute all bricks
            return {brick.id for brick in self.bricks}, {}

        exec_set: set[str] = set()
        overlaps: dict[str, list[str]] = {}

        for sel_id in selection:
            if self._registry.is_macrobrick(sel_id):
                # Expand MacroBrick to its member bricks (using cached expansion)
                members = self._registry.get_struct_flat_members(sel_id)

                for brick_id in members:
                    exec_set.add(brick_id)
                    overlaps.setdefault(brick_id, []).append(sel_id)

            elif self._registry.is_brick(sel_id):
                # Direct brick selection
                exec_set.add(sel_id)
            else:
                raise ConfigError(f"Unknown selection id: '{sel_id}'")

        # Build structured overlap report for current selection
        overlaps_report: dict[str, dict[str, any]] = {}
        for brick_id, owners in overlaps.items():
            if len(owners) > 1:
                overlaps_report[brick_id] = {
                    "macrobricks": sorted(owners),
                    "count": len(owners),
                }

        # Warn about overlaps if configured to do so
        if self.config.warn_on_overlap and overlaps_report:
            import logging

            logger = logging.getLogger(__name__)
            for brick_id, info in overlaps_report.items():
                logger.warning(
                    "Brick '%s' is shared across MacroBricks: %s. "
                    "Execution is deduplicated at scenario level.",
                    brick_id,
                    ", ".join(info["macrobricks"]),
                )

        return exec_set, overlaps_report

    def _build_dependency_graph(self, brick_ids: set[str]) -> dict[str, set[str]]:
        """
        Build dependency graph from brick links.

        Args:
            brick_ids: Set of brick IDs to analyze

        Returns:
            Dictionary mapping brick_id to set of dependencies
        """
        edges: dict[str, set[str]] = {}

        for brick in self.bricks:
            if brick.id not in brick_ids:
                continue

            edges[brick.id] = set()

            # Check for dependency links
            if hasattr(brick, "links") and brick.links:
                for _link_type, link_data in brick.links.items():
                    if isinstance(link_data, dict):
                        # Handle PrincipalLink, StartLink, etc.
                        if "from_house" in link_data:
                            dep_id = link_data["from_house"]
                            if dep_id in brick_ids:
                                edges[brick.id].add(dep_id)
                        elif "on_end_of" in link_data:
                            dep_id = link_data["on_end_of"]
                            if dep_id in brick_ids:
                                edges[brick.id].add(dep_id)
                        elif "remaining_of" in link_data:
                            dep_id = link_data["remaining_of"]
                            if dep_id in brick_ids:
                                edges[brick.id].add(dep_id)
                    elif isinstance(link_data, str):
                        # Simple string reference
                        if link_data in brick_ids:
                            edges[brick.id].add(link_data)

        return edges

    def _topological_order(
        self, brick_ids: set[str], edges: dict[str, set[str]]
    ) -> list[str]:
        """
        Compute topological order of bricks by dependencies, fallback to stable ID sort.

        Args:
            brick_ids: Set of brick IDs to order
            edges: Dependency graph (brick_id -> set of dependencies)

        Returns:
            List of brick IDs in execution order
        """
        from collections import defaultdict, deque

        indeg = defaultdict(int)
        adj = defaultdict(set)

        # Build adjacency list and in-degree count
        for brick_id in brick_ids:
            for dep_id in edges.get(brick_id, set()):
                adj[dep_id].add(brick_id)
                indeg[brick_id] += 1

        # Start with bricks that have no dependencies
        q = deque(sorted([b for b in brick_ids if indeg[b] == 0]))
        order = []

        while q:
            u = q.popleft()
            order.append(u)
            for v in sorted(adj[u]):  # Stable sort
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)

        # Check if we processed all bricks (no cycles)
        if len(order) != len(brick_ids):
            # Cycle detected in dependencies; fallback to deterministic ID sort
            return sorted(brick_ids)

        return order

    def _build_struct_aggregates(
        self, outputs: dict[str, BrickOutput], brick_ids: set[str]
    ) -> dict[str, BrickOutput]:
        """
        Build MacroBrick aggregates from individual brick outputs.

        Args:
            outputs: Dictionary of brick outputs from simulation
            brick_ids: Set of brick IDs that were executed

        Returns:
            Dictionary mapping MacroBrick IDs to their aggregated BrickOutput
        """
        if not self.config.include_struct_results:
            return {}

        by_struct: dict[str, BrickOutput] = {}

        for struct_id, _macrobrick in self._registry.iter_macrobricks():
            # Apply structs filter if configured
            if (
                self.config.structs_filter is not None
                and struct_id not in self.config.structs_filter
            ):
                continue

            # Get the member bricks for this MacroBrick (using cached expansion)
            member_bricks = self._registry.get_struct_flat_members(struct_id)

            # Only include bricks that were actually executed
            executed_members = member_bricks & brick_ids

            if not executed_members:
                # Skip MacroBricks with no executed members
                continue

            # Create empty aggregate
            agg = self._create_empty_output(
                len(outputs[list(outputs.keys())[0]]["cash_in"])
            )

            # Sum outputs from all executed member bricks
            for brick_id in executed_members:
                if brick_id in outputs:
                    brick_output = outputs[brick_id]
                    for key in agg.keys():
                        # Map old column names to new ones for compatibility
                        brick_key = key
                        if key == "asset_value":
                            brick_key = "assets"
                        elif key == "debt_balance":
                            brick_key = "liabilities"

                        if brick_key in brick_output:
                            agg[key] += brick_output[brick_key]

            by_struct[struct_id] = agg

        return by_struct

    def _create_empty_output(self, length: int) -> BrickOutput:
        """Create an empty BrickOutput with the specified length."""
        return {
            "cash_in": np.zeros(length),
            "cash_out": np.zeros(length),
            "assets": np.zeros(length),
            "liabilities": np.zeros(length),
            "interest": np.zeros(length),
            "equity": np.zeros(length),
        }

    def _initialize_simulation(
        self, start: date, months: int
    ) -> tuple[np.ndarray, ScenarioContext]:
        """Initialize the simulation context and resolve mortgage links."""
        from .accounts import AccountRegistry
        from .journal import Journal

        t_index = month_range(start, months)

        # Create account registry and journal for V2 postings model
        account_registry = AccountRegistry()
        journal = Journal(account_registry)

        ctx = ScenarioContext(
            t_index=t_index,
            currency=self.currency,
            registry={b.id: b for b in self.bricks},
            journal=journal,
            settlement_default_cash_id=self.settlement_default_cash_id,
        )

        # Resolve mortgage links and validate settlement buckets
        self._resolve_mortgage_links()

        return t_index, ctx

    def _prepare_simulation(self, ctx: ScenarioContext) -> None:
        """Wire strategies and prepare all bricks for simulation."""
        # Wire strategies to bricks based on their kind discriminators
        wire_strategies(self.bricks)

        # Prepare all bricks for simulation (validate parameters, setup state)
        for b in self.bricks:
            b.prepare(ctx)

    def _simulate_bricks(
        self, ctx: ScenarioContext, t_index: np.ndarray, execution_order: list[str]
    ):
        """Simulate all bricks using Journal-based system."""
        from .accounts import Account, AccountScope, AccountType, BOUNDARY_NODE_ID, get_node_id

        outputs: dict[str, BrickOutput] = {}

        # Use journal and account registry from context (V2 postings model)
        if ctx.journal is None:
            raise ValueError("Journal must be provided in ScenarioContext")
        journal = ctx.journal
        account_registry = journal.account_registry

        # Track iteration count per brick and transaction type
        brick_iteration_counters = {}
        # compiler = BrickCompiler(account_registry)  # No longer needed with new journal system

        # Register all cash accounts as internal assets
        cash_ids = [
            b.id
            for b in self.bricks
            if isinstance(b, ABrick) and b.kind == K.A_CASH and b.id in execution_order
        ]

        # Track processed cash IDs to prevent duplicate opening entries
        processed_openings: set[str] = set()

        for cash_id in cash_ids:
            account_registry.register_account(
                Account(
                    cash_id,
                    f"Cash Account {cash_id}",
                    AccountScope.INTERNAL,
                    AccountType.ASSET,
                )
            )

            # Initialize cash account with opening balance
            # Guard: skip if already processed
            if cash_id in processed_openings:
                continue

            cash_brick = next(b for b in self.bricks if b.id == cash_id)
            initial_balance = cash_brick.spec.get("initial_balance", 0.0)
            if initial_balance != 0:
                import hashlib

                from .currency import create_amount

                # Create opening balance entry with canonical format
                # Positive amount = debit for assets, credit for equity
                from .journal import (
                    JournalEntry,
                    Posting,
                    stamp_entry_metadata,
                    stamp_posting_metadata,
                )

                # Get currency from postings (will be set below)
                currency = self.currency  # Default to scenario currency

                # Use node IDs for account_id (consistent with V2 model)
                cash_node_id = get_node_id(cash_id, "a")
                opening_entry = JournalEntry(
                    id=f"opening:{cash_id}:0",
                    timestamp=ctx.t_index[0],
                    postings=[
                        Posting(
                            BOUNDARY_NODE_ID,  # Use node ID for boundary side
                            create_amount(-initial_balance, currency),
                            {},
                        ),
                        Posting(
                            cash_node_id,  # Use node ID for asset side
                            create_amount(initial_balance, currency),
                            {},
                        ),
                    ],
                    metadata={},
                )

                # Generate stable origin_id from entry.id + currency
                # This ensures uniqueness per entry while staying deterministic
                origin_id = hashlib.sha256(
                    f"{opening_entry.id}:{currency}".encode()
                ).hexdigest()[:16]

                # Stamp entry metadata
                stamp_entry_metadata(
                    entry=opening_entry,
                    parent_id=f"a:{cash_id}",  # Asset brick parent
                    timestamp=ctx.t_index[0],
                    tags={"type": "opening_balance"},
                    sequence=1,
                    origin_id=origin_id,
                )

                # Set transaction_type for opening entries
                opening_entry.metadata["transaction_type"] = "opening"

                # Stamp posting metadata
                stamp_posting_metadata(
                    posting=opening_entry.postings[0],  # Equity posting
                    node_id=BOUNDARY_NODE_ID,  # Equity is boundary
                    category="equity.opening",
                    type_tag="opening_balance",
                )
                stamp_posting_metadata(
                    posting=opening_entry.postings[1],  # Asset posting
                    node_id=get_node_id(cash_id, "a"),  # Asset node ID
                    type_tag="opening_balance",
                )

                journal.post(opening_entry)
                processed_openings.add(cash_id)

        if len(cash_ids) == 0:
            raise AssertionError(
                f"At least one cash account (kind='{K.A_CASH}') is required in the selection"
            )

        # Register boundary accounts for external flows
        boundary_accounts = [
            "Income:Salary",
            "Income:Dividends",
            "Income:Interest",
            "Expenses:Groceries",
            "Expenses:BankFees",
            "Expenses:Interest",
            "P&L:Unrealized",
            "P&L:FX",
        ]

        for account_id in boundary_accounts:
            account_type = (
                AccountType.INCOME
                if account_id.startswith("Income:")
                else AccountType.EXPENSE
                if account_id.startswith("Expenses:")
                else AccountType.PNL
                if account_id.startswith("P&L:")
                else AccountType.EQUITY
            )
            account_registry.register_account(
                Account(account_id, account_id, AccountScope.BOUNDARY, account_type)
            )

        # Register cash accounts with node IDs (consistent with V2 model)
        for cash_id in cash_ids:
            cash_node_id = get_node_id(cash_id, "a")
            account_registry.register_account(
                Account(
                    cash_node_id,  # Use node ID format
                    f"Cash Account {cash_id}",
                    AccountScope.INTERNAL,
                    AccountType.ASSET,
                )
            )

        # Register liability accounts with node IDs (for loan bricks)
        liability_ids = [
            b.id
            for b in self.bricks
            if isinstance(b, LBrick) and b.id in execution_order
        ]
        for liability_id in liability_ids:
            liability_node_id = get_node_id(liability_id, "l")
            account_registry.register_account(
                Account(
                    liability_node_id,  # Use node ID format
                    f"Liability {liability_id}",
                    AccountScope.INTERNAL,
                    AccountType.LIABILITY,
                )
            )

        # Register asset accounts with node IDs (for non-cash asset bricks like ETF, property)
        asset_ids = [
            b.id
            for b in self.bricks
            if isinstance(b, ABrick)
            and b.id in execution_order
            and b.kind != K.A_CASH  # Exclude cash (already registered)
        ]
        for asset_id in asset_ids:
            asset_node_id = get_node_id(asset_id, "a")
            account_registry.register_account(
                Account(
                    asset_node_id,  # Use node ID format
                    f"Asset {asset_id}",
                    AccountScope.INTERNAL,
                    AccountType.ASSET,
                )
            )

        # Simulate all bricks and compile to journal entries

        # First pass: process all non-cash bricks and compile to journal
        for b in [ctx.registry[bid] for bid in execution_order]:
            if isinstance(b, ABrick) and b.kind == K.A_CASH:
                continue  # Skip cash accounts for now

            brick_output = self._simulate_single_brick(b, ctx, t_index)
            outputs[b.id] = brick_output

            # Journal entries are now created in _capture_monthly_transactions
            # No need to compile here as we use the new journal system

        # NEW: Capture monthly transactions for each month of simulation
        self._capture_monthly_transactions(
            journal, outputs, ctx, execution_order, brick_iteration_counters
        )

        # Second pass: process cash accounts with all journal entries available
        for b in [ctx.registry[bid] for bid in execution_order]:
            if not (isinstance(b, ABrick) and b.kind == K.A_CASH):
                continue

            # Cash bricks: use journal balances for valuation
            # Don't set initial_balance from journal - let external flows handle it

            # Calculate external flows from FBrick outputs for this cash account
            external_in = np.zeros(len(ctx.t_index))
            external_out = np.zeros(len(ctx.t_index))

            # Sum up all brick flows that route to this cash account
            for brick_id, brick_output in outputs.items():
                if brick_id == b.id:
                    continue  # Skip self

                # Check if this brick routes to our cash account
                brick = ctx.registry[brick_id]

                # Handle different brick types that generate cash flows
                if isinstance(brick, FBrick):
                    # Check for explicit routing
                    if (
                        brick.links
                        and "route" in brick.links
                        and "to" in brick.links["route"]
                    ):
                        if brick.links["route"]["to"] == b.id:
                            # This brick routes to our cash account
                            external_in += brick_output["cash_in"]
                            external_out += brick_output["cash_out"]
                    elif not (brick.links and "route" in brick.links):
                        # No explicit routing - use default routing (all flows go to first cash account)
                        # This maintains backward compatibility with the old system
                        external_in += brick_output["cash_in"]
                        external_out += brick_output["cash_out"]
                elif isinstance(brick, TBrick):
                    # Transfer bricks: route based on from/to links
                    if brick.links and "from" in brick.links and "to" in brick.links:
                        if brick.links["from"] == b.id:
                            # Money going out from this account
                            external_out += brick_output["cash_out"]
                        elif brick.links["to"] == b.id:
                            # Money coming in to this account
                            external_in += brick_output["cash_in"]
                elif isinstance(brick, ABrick) and brick.kind == K.A_PROPERTY:
                    # Property bricks generate cash flows (purchase costs, etc.)
                    # Check for explicit routing first
                    if (
                        brick.links
                        and "route" in brick.links
                        and "to" in brick.links["route"]
                    ):
                        if brick.links["route"]["to"] == b.id:
                            # This brick routes to our cash account
                            external_in += brick_output["cash_in"]
                            external_out += brick_output["cash_out"]
                    elif b.id == self.settlement_default_cash_id:
                        # Fall back to settlement account if no explicit routing
                        external_in += brick_output["cash_in"]
                        external_out += brick_output["cash_out"]
                elif isinstance(brick, LBrick):
                    # Liability bricks generate cash flows (payments, etc.)
                    # Check for explicit routing first
                    if (
                        brick.links
                        and "route" in brick.links
                        and "to" in brick.links["route"]
                    ):
                        if brick.links["route"]["to"] == b.id:
                            # This brick routes to our cash account
                            external_in += brick_output["cash_in"]
                            external_out += brick_output["cash_out"]
                    elif b.id == self.settlement_default_cash_id:
                        # Fall back to settlement account if no explicit routing
                        external_in += brick_output["cash_in"]
                        external_out += brick_output["cash_out"]
                elif isinstance(brick, ABrick) and brick.kind == K.A_CASH:
                    # Cash accounts with maturity transfers
                    # Check for explicit routing first
                    if (
                        brick.links
                        and "route" in brick.links
                        and "to" in brick.links["route"]
                    ):
                        if brick.links["route"]["to"] == b.id:
                            # This cash account routes to our cash account (maturity transfer)
                            external_in += brick_output["cash_in"]
                            external_out += brick_output["cash_out"]

            # Set external flows for backward compatibility
            b.spec["external_in"] = external_in
            b.spec["external_out"] = external_out

            outputs[b.id] = b.simulate(ctx)

        # Handle maturity transfers for cash accounts with end_date and route links
        self._handle_maturity_transfers(outputs, ctx, journal, brick_iteration_counters)

        # Validate journal invariants (V2)
        if self.validate_routing:
            errors = journal.validate_invariants(account_registry)
            if errors:
                raise AssertionError(f"Journal validation failed: {errors}")

            # V2: Validate origin_id uniqueness
            from .validation import validate_origin_id_uniqueness

            try:
                validate_origin_id_uniqueness(journal)
            except ValueError as e:
                raise AssertionError(f"Journal origin_id validation failed: {e}")

        return outputs, journal

    def _handle_maturity_transfers(
        self,
        outputs: dict[str, BrickOutput],
        ctx: ScenarioContext,
        journal,
        brick_iteration_counters: dict,
    ) -> None:
        """Handle maturity transfers for cash accounts with end_date and route links."""
        from .accounts import get_node_id
        from .currency import create_amount
        from .events import Event
        from .journal import JournalEntry, Posting

        for brick in self.bricks:
            if (
                isinstance(brick, ABrick)
                and brick.kind == K.A_CASH
                and brick.end_date is not None
                and brick.links
                and "route" in brick.links
            ):
                # Find the end month index - normalize end_date to np.datetime64[M]
                import numpy as np

                end_m = np.datetime64(brick.end_date, "M")
                end_month_idx = None
                for i, t in enumerate(ctx.t_index):
                    if t >= end_m:
                        end_month_idx = i
                        break

                if end_month_idx is not None and end_month_idx < len(ctx.t_index):
                    # Get final balance at maturity (before active mask is applied)
                    # We need to calculate the balance before the active mask zeros it out
                    # Temporarily remove the end_date to get the true balance
                    original_end_date = brick.end_date
                    brick.end_date = None

                    # Re-simulate to get the balance without active mask
                    temp_output = brick.simulate(ctx)

                    # Restore the original end_date
                    brick.end_date = original_end_date

                    # Calculate the transfer amount: balance before interest + contribution
                    # This ensures we transfer the principal + contribution, and let interest be earned on the remaining balance
                    # Use Decimal to maintain precision through currency quantization
                    from decimal import Decimal

                    idx_prev = max(0, end_month_idx - 1)
                    raw_prev = temp_output["assets"][idx_prev]
                    prev_bal_dec = (
                        Decimal(str(raw_prev))
                        if not isinstance(raw_prev, Decimal)
                        else raw_prev
                    )

                    monthly_contribution = brick.spec.get(
                        "external_in", np.zeros(len(ctx.t_index))
                    )[end_month_idx]
                    contrib_dec = (
                        Decimal(str(monthly_contribution))
                        if not isinstance(monthly_contribution, Decimal)
                        else monthly_contribution
                    )

                    # Sum as Decimal to maintain precision
                    transfer_amount_dec = prev_bal_dec + contrib_dec
                    # Convert to float for numpy array assignment (arrays use float64)
                    transfer_amount = float(transfer_amount_dec)

                    if transfer_amount > 0:
                        dest_brick_id = brick.links["route"]["to"]

                        # Get currency from brick spec (default to scenario currency)
                        currency = brick.spec.get("currency", self.currency)

                        # EOM_POST_INTEREST policy: Source transfers at end of month (external_out)
                        # Destination receives post-interest (post_interest_in)
                        # This ensures source earns interest for the month, destination doesn't double-earn

                        # Source: transfer out at end of month (earns interest first)
                        if "external_out" not in brick.spec:
                            brick.spec["external_out"] = np.zeros(len(ctx.t_index))
                        brick.spec["external_out"][end_month_idx] += transfer_amount

                        # Destination: receive post-interest (no interest on transfer this month)
                        dest_brick = None
                        for b in self.bricks:
                            if b.id == dest_brick_id:
                                dest_brick = b
                                break

                        if dest_brick:
                            if "post_interest_in" not in dest_brick.spec:
                                dest_brick.spec["post_interest_in"] = np.zeros(
                                    len(ctx.t_index)
                                )
                            dest_brick.spec["post_interest_in"][
                                end_month_idx
                            ] += transfer_amount

                        # Create maturity transfer event
                        transfer_event = Event(
                            np.datetime64(brick.end_date, "M"),
                            "maturity_transfer",
                            f"Maturity transfer: {transfer_amount:,.2f} EUR to {dest_brick_id}",
                            {
                                "amount": transfer_amount,
                                "from": brick.id,
                                "to": dest_brick_id,
                                "type": "maturity_transfer",
                                "policy": "EOM_POST_INTEREST",
                            },
                        )
                        outputs[brick.id]["events"].append(transfer_event)

                        # Create destination receive event
                        if dest_brick:
                            receive_event = Event(
                                np.datetime64(brick.end_date, "M"),
                                "maturity_transfer_in",
                                f"Received maturity transfer: {transfer_amount:,.2f} EUR from {brick.id}",
                                {
                                    "amount": transfer_amount,
                                    "from": brick.id,
                                    "to": dest_brick_id,
                                    "type": "maturity_transfer_in",
                                    "policy": "EOM_POST_INTEREST",
                                },
                            )
                            outputs[dest_brick_id]["events"].append(receive_event)

                        # Create journal entry for the transfer (EOM_POST_INTEREST policy)
                        month_timestamp = ctx.t_index[end_month_idx]

                        # Calculate iteration for the transfer
                        iteration = self._calculate_relative_iteration(
                            brick, "maturity_transfer", brick_iteration_counters
                        )

                        # Use node IDs for account_id (consistent with V2 model)
                        source_node_id = get_node_id(brick.id, "a")
                        dest_node_id = get_node_id(dest_brick_id, "a")

                        transfer_entry = JournalEntry(
                            id=f"maturity_transfer:{brick.id}:{iteration}",
                            timestamp=month_timestamp,
                            postings=[
                                Posting(
                                    source_node_id,  # Use node ID format
                                    create_amount(-transfer_amount, currency),
                                    {
                                        "type": "maturity_transfer",
                                        "month": end_month_idx,
                                        "posting_side": "credit",
                                        "from": brick.id,
                                        "to": dest_brick_id,
                                        "policy": "EOM_POST_INTEREST",
                                    },
                                ),
                                Posting(
                                    dest_node_id,  # Use node ID format
                                    create_amount(transfer_amount, currency),
                                    {
                                        "type": "maturity_transfer",
                                        "month": end_month_idx,
                                        "posting_side": "debit",
                                        "from": brick.id,
                                        "to": dest_brick_id,
                                        "policy": "EOM_POST_INTEREST",
                                    },
                                ),
                            ],
                            metadata={
                                "brick_id": brick.id,
                                "brick_type": "asset",
                                "kind": brick.kind,
                                "month": end_month_idx,
                                "iteration": iteration,
                                "transaction_type": "maturity_transfer",
                                "amount_type": "debit",
                                "from": brick.id,
                                "to": dest_brick_id,
                                "amount": transfer_amount,
                                "policy": "EOM_POST_INTEREST",
                            },
                        )
                        journal.post(transfer_entry)

                        # Re-simulate affected cash bricks to rebuild their balance time series
                        # This ensures the maturity transfer is properly integrated into the cash strategy
                        outputs[brick.id] = brick.simulate(ctx)
                        if dest_brick:
                            outputs[dest_brick_id] = dest_brick.simulate(ctx)

    def _capture_monthly_transactions(
        self,
        journal,
        outputs: dict[str, BrickOutput],
        ctx: ScenarioContext,
        execution_order: list[str],
        brick_iteration_counters: dict,
    ) -> None:
        """
        Capture monthly transactions for each month of the simulation.

        This method processes the brick outputs and creates journal entries
        for all monthly transactions (transfers, salary, loan payments, etc.)
        that occurred during the simulation.
        """

        # compiler = BrickCompiler(journal.account_registry)  # Not used in monthly capture

        # Process each month of the simulation
        for month_idx in range(len(ctx.t_index)):
            month_timestamp = ctx.t_index[month_idx]

            # Process each brick for this month
            for brick_id in execution_order:
                brick = ctx.registry[brick_id]

                # Skip cash accounts (they're handled separately)
                if isinstance(brick, ABrick) and brick.kind == K.A_CASH:
                    continue

                # Skip if brick output not available yet
                if brick_id not in outputs:
                    continue

                brick_output = outputs[brick_id]

                # Check if this brick has activity in this month
                if (
                    brick_output["cash_in"][month_idx] == 0
                    and brick_output["cash_out"][month_idx] == 0
                ):
                    continue  # No activity this month

                # Create journal entries for this month's transactions
                if isinstance(brick, TBrick):
                    # Transfer brick: create internal transfer entry
                    self._create_transfer_journal_entry(
                        journal,
                        brick,
                        brick_output,
                        month_idx,
                        month_timestamp,
                        brick_iteration_counters,
                    )
                elif isinstance(brick, FBrick):
                    # Flow brick: create external flow entry
                    self._create_flow_journal_entry(
                        journal,
                        brick,
                        brick_output,
                        month_idx,
                        month_timestamp,
                        brick_iteration_counters,
                    )
                elif isinstance(brick, LBrick):
                    # Liability brick: create loan payment entry
                    self._create_liability_journal_entry(
                        journal,
                        brick,
                        brick_output,
                        month_idx,
                        month_timestamp,
                        brick_iteration_counters,
                    )

    def _create_transfer_journal_entry(
        self,
        journal,
        brick: TBrick,
        brick_output: BrickOutput,
        month_idx: int,
        month_timestamp: np.datetime64,
        brick_iteration_counters: dict,
    ) -> None:
        """Create journal entry for transfer brick monthly transaction."""
        from .accounts import get_node_id
        from .currency import create_amount
        from .journal import JournalEntry, Posting

        cash_in = brick_output["cash_in"][month_idx]
        cash_out = brick_output["cash_out"][month_idx]

        if cash_in == 0 and cash_out == 0:
            return  # No activity this month

        # Create postings for the transfer
        postings = []

        # Get currency from brick spec (default to scenario currency)
        currency = brick.spec.get("currency", self.currency)

        # Use node IDs for account_id (consistent with V2 model)
        if cash_out > 0:
            from_node_id = get_node_id(brick.links["from"], "a")
            postings.append(
                Posting(
                    from_node_id,  # Use node ID format
                    create_amount(-cash_out, currency),
                    {
                        "type": "transfer_out",
                        "month": month_idx,
                        "posting_side": "credit",
                    },
                )
            )

        # Money comes in to destination account (debit)
        if cash_in > 0:
            to_node_id = get_node_id(brick.links["to"], "a")
            postings.append(
                Posting(
                    to_node_id,  # Use node ID format
                    create_amount(cash_in, currency),
                    {
                        "type": "transfer_in",
                        "month": month_idx,
                        "posting_side": "debit",
                    },
                )
            )

        # Create canonical record ID using sequential iteration
        iteration = self._calculate_relative_iteration(
            brick, "transfer", brick_iteration_counters
        )
        record_id = f"transfer:{brick.id}:{iteration}"

        entry = JournalEntry(
            id=record_id,
            timestamp=month_timestamp,
            postings=postings,
            metadata={
                "brick_id": brick.id,
                "brick_type": "transfer",
                "kind": brick.kind,
                "month": month_idx,
                "iteration": iteration,  # Sequential enumeration
                "transaction_type": "transfer",
                "amount_type": "credit" if cash_in > 0 else "debit",
            },
        )

        # Stamp posting metadata with node_id (V2 requirement)
        from .journal import stamp_posting_metadata

        for posting in entry.postings:
            if posting.account_id.startswith("a:"):
                stamp_posting_metadata(
                    posting, node_id=posting.account_id, type_tag="transfer"
                )

        journal.post(entry)

    def _create_flow_journal_entry(
        self,
        journal,
        brick: FBrick,
        brick_output: BrickOutput,
        month_idx: int,
        month_timestamp: np.datetime64,
        brick_iteration_counters: dict,
    ) -> None:
        """Create journal entry for flow brick monthly transaction."""
        from .accounts import get_node_id
        from .currency import create_amount
        from .journal import JournalEntry, Posting

        cash_in = brick_output["cash_in"][month_idx]
        cash_out = brick_output["cash_out"][month_idx]

        if cash_in == 0 and cash_out == 0:
            return  # No activity this month

        # Create postings for the flow
        postings = []

        # Determine the cash account to route to
        cash_account = brick.links.get("route", {}).get("to") if brick.links else None

        # Fallback to settlement_default_cash_id or first cash account
        if not cash_account:
            if self.settlement_default_cash_id:
                cash_account = self.settlement_default_cash_id
            else:
                # Fallback to first cash brick in scenario
                cash_ids = [
                    b.id
                    for b in self.bricks
                    if isinstance(b, ABrick) and b.kind == K.A_CASH
                ]
                cash_account = cash_ids[0] if cash_ids else None

        if not cash_account:
            return  # Still no cash account available

        # Use node ID for cash account (consistent with V2 model)
        cash_node_id = get_node_id(cash_account, "a")

        # Create boundary account for the flow using brick_id
        if brick.kind.startswith("f.income"):
            boundary_account = f"income:{brick.id}"
            transaction_type = "income"
        elif brick.kind.startswith("f.expense"):
            boundary_account = f"expense:{brick.id}"
            transaction_type = "expense"
        else:
            boundary_account = f"flow:{brick.id}"
            transaction_type = "flow"

        # Register boundary account if not already registered
        if not journal.account_registry.has_account(boundary_account):
            from .accounts import Account, AccountScope, AccountType

            journal.account_registry.register_account(
                Account(
                    boundary_account,
                    boundary_account,
                    AccountScope.BOUNDARY,
                    AccountType.INCOME
                    if brick.kind.startswith("f.income")
                    else AccountType.EXPENSE,
                )
            )

        # Get currency from brick spec (default to scenario currency)
        currency = brick.spec.get("currency", self.currency)

        # Money flows from boundary to cash account (income) or vice versa (expense)
        if cash_in > 0:  # Income
            # Income: credit income (boundary), debit asset cash
            postings.append(
                Posting(
                    boundary_account,
                    create_amount(-cash_in, currency),
                    {"type": "income", "month": month_idx, "posting_side": "credit"},
                )
            )
            postings.append(
                Posting(
                    cash_node_id,  # Use node ID format
                    create_amount(cash_in, currency),
                    {
                        "type": "income_allocation",
                        "month": month_idx,
                        "posting_side": "debit",
                    },
                )
            )
        elif cash_out > 0:  # Expense
            # Expense: credit asset cash, debit expense (boundary)
            postings.append(
                Posting(
                    cash_node_id,  # Use node ID format
                    create_amount(-cash_out, currency),
                    {
                        "type": "expense_payment",
                        "month": month_idx,
                        "posting_side": "credit",
                    },
                )
            )
            postings.append(
                Posting(
                    boundary_account,
                    create_amount(cash_out, currency),
                    {"type": "expense", "month": month_idx, "posting_side": "debit"},
                )
            )

        # Create canonical record ID using sequential iteration
        iteration = self._calculate_relative_iteration(
            brick, transaction_type, brick_iteration_counters
        )
        record_id = f"{transaction_type}:{brick.id}:{iteration}"

        entry = JournalEntry(
            id=record_id,
            timestamp=month_timestamp,
            postings=postings,
            metadata={
                "brick_id": brick.id,
                "brick_type": "flow",
                "kind": brick.kind,
                "month": month_idx,
                "iteration": iteration,  # Sequential enumeration
                "transaction_type": transaction_type,
                "amount_type": "credit" if transaction_type == "income" else "debit",
                "boundary_account": boundary_account,
            },
        )

        # Stamp posting metadata with node_id (V2 requirement)
        from .journal import stamp_posting_metadata
        from .accounts import BOUNDARY_NODE_ID

        for posting in entry.postings:
            if posting.account_id == boundary_account:
                # Boundary posting - use boundary account ID
                category = (
                    "income.recurring"
                    if transaction_type == "income"
                    else "expense.recurring"
                )
                stamp_posting_metadata(
                    posting,
                    node_id=BOUNDARY_NODE_ID,
                    category=category,
                    type_tag=transaction_type,
                )
            elif posting.account_id == cash_node_id:
                # Cash posting - use node ID
                stamp_posting_metadata(
                    posting, node_id=cash_node_id, type_tag=transaction_type
                )

        journal.post(entry)

    def _create_liability_journal_entry(
        self,
        journal,
        brick: LBrick,
        brick_output: BrickOutput,
        month_idx: int,
        month_timestamp: np.datetime64,
        brick_iteration_counters: dict,
    ) -> None:
        """Create journal entry for liability brick monthly transaction."""
        from .accounts import get_node_id
        from .currency import create_amount
        from .journal import JournalEntry, Posting

        cash_in = brick_output["cash_in"][month_idx]
        cash_out = brick_output["cash_out"][month_idx]

        if cash_in == 0 and cash_out == 0:
            return  # No activity this month

        # Create postings for the liability
        postings = []

        # Determine the cash account to route to
        if self.settlement_default_cash_id:
            cash_account = self.settlement_default_cash_id
        else:
            # Fallback to first cash account in scenario
            cash_ids = [
                b.id
                for b in self.bricks
                if isinstance(b, ABrick) and b.kind == K.A_CASH
            ]
            if not cash_ids:
                # No cash account available - skip journal entry
                return
            cash_account = cash_ids[0]

        # Use node ID for cash account (consistent with V2 model)
        cash_node_id = get_node_id(cash_account, "a")

        # Create boundary account for the liability using brick_id
        boundary_account = f"liability:{brick.id}"

        # Register liability account if not already registered
        if not journal.account_registry.has_account(boundary_account):
            from .accounts import Account, AccountScope, AccountType

            journal.account_registry.register_account(
                Account(
                    boundary_account,
                    boundary_account,
                    AccountScope.BOUNDARY,
                    AccountType.LIABILITY,
                )
            )

        # Get currency from brick spec (default to scenario currency)
        currency = brick.spec.get("currency", self.currency)

        # Handle disbursements first (cash_in > 0)
        if cash_in > 0:  # Disbursement
            # Disbursement: debit asset cash, credit liability (boundary)
            postings.append(
                Posting(
                    boundary_account,
                    create_amount(-cash_in, currency),
                    {
                        "type": "loan_disbursement",
                        "month": month_idx,
                        "posting_side": "credit",
                    },
                )
            )
            postings.append(
                Posting(
                    cash_node_id,  # Use node ID format
                    create_amount(cash_in, currency),
                    {
                        "type": "liability_disbursement",
                        "month": month_idx,
                        "posting_side": "debit",
                    },
                )
            )
            transaction_type = "disbursement"

            # Create disbursement journal entry
            disbursement_iteration = self._calculate_relative_iteration(
                brick, "disbursement", brick_iteration_counters
            )
            disbursement_record_id = f"disbursement:{brick.id}:{disbursement_iteration}"

            disbursement_metadata = {
                "brick_id": brick.id,
                "brick_type": "liability",
                "kind": brick.kind,
                "month": month_idx,
                "iteration": disbursement_iteration,
                "transaction_type": "disbursement",
                "amount_type": "credit",
                "boundary_account": boundary_account,
                "total_disbursement": cash_in,
            }

            disbursement_entry = JournalEntry(
                id=disbursement_record_id,
                timestamp=month_timestamp,
                postings=postings.copy(),
                metadata=disbursement_metadata,
            )

            # Stamp posting metadata with node_id (V2 requirement)
            from .journal import stamp_posting_metadata
            from .accounts import BOUNDARY_NODE_ID

            for posting in disbursement_entry.postings:
                if posting.account_id == boundary_account:
                    stamp_posting_metadata(
                        posting,
                        node_id=BOUNDARY_NODE_ID,
                        category="liability.disbursement",
                        type_tag="disbursement",
                    )
                elif posting.account_id == cash_node_id:
                    stamp_posting_metadata(
                        posting, node_id=cash_node_id, type_tag="disbursement"
                    )

            journal.post(disbursement_entry)

            # Reset postings for payment entry
            postings = []

        # Handle payments (cash_out > 0) - can be in same month as disbursement
        if cash_out > 0:  # Payment
            # Calculate interest and amortization breakdown
            interest_amount = abs(
                brick_output["interest"][month_idx]
            )  # Interest is negative, make positive
            amortization_amount = (
                cash_out - interest_amount
            )  # Total payment - interest = principal

            # Payment: credit asset cash, debit liability (boundary)
            postings.append(
                Posting(
                    cash_node_id,  # Use node ID format
                    create_amount(-cash_out, currency),
                    {
                        "type": "loan_payment",
                        "month": month_idx,
                        "posting_side": "credit",
                        "interest_amount": interest_amount,
                        "amortization_amount": amortization_amount,
                    },
                )
            )
            postings.append(
                Posting(
                    boundary_account,
                    create_amount(cash_out, currency),
                    {
                        "type": "liability_payment",
                        "month": month_idx,
                        "posting_side": "debit",
                        "interest_amount": interest_amount,
                        "amortization_amount": amortization_amount,
                    },
                )
            )
            transaction_type = "payment"

        # Create payment journal entry (if there are payments)
        if cash_out > 0:  # Payment
            # Create canonical record ID using sequential iteration
            iteration = self._calculate_relative_iteration(
                brick, transaction_type, brick_iteration_counters
            )
            record_id = f"{transaction_type}:{brick.id}:{iteration}"

            # Prepare metadata with interest and amortization breakdown for payments
            metadata = {
                "brick_id": brick.id,
                "brick_type": "liability",
                "kind": brick.kind,
                "month": month_idx,
                "iteration": iteration,  # Sequential enumeration
                "transaction_type": transaction_type,
                "amount_type": "debit",
                "boundary_account": boundary_account,
            }

            # Add interest and amortization breakdown for payments
            interest_amount = abs(brick_output["interest"][month_idx])
            amortization_amount = cash_out - interest_amount
            metadata.update(
                {
                    "interest_amount": interest_amount,
                    "amortization_amount": amortization_amount,
                    "total_payment": cash_out,
                }
            )

            entry = JournalEntry(
                id=record_id,
                timestamp=month_timestamp,
                postings=postings,
                metadata=metadata,
            )

            # Stamp posting metadata with node_id (V2 requirement)
            from .journal import stamp_posting_metadata
            from .accounts import BOUNDARY_NODE_ID

            for posting in entry.postings:
                if posting.account_id == boundary_account:
                    stamp_posting_metadata(
                        posting,
                        node_id=BOUNDARY_NODE_ID,
                        category="expense.interest"
                        if interest_amount > 0
                        else "liability.payment",
                        type_tag="payment",
                    )
                elif posting.account_id == cash_node_id:
                    stamp_posting_metadata(
                        posting, node_id=cash_node_id, type_tag="payment"
                    )

            journal.post(entry)

    def _calculate_relative_iteration(
        self, brick, transaction_type: str, brick_iteration_counters: dict
    ) -> int:
        """Calculate sequential iteration for each transaction type within each brick."""
        # Create a key for this brick and transaction type
        key = f"{brick.id}:{transaction_type}"

        # Get current count and increment
        current_count = brick_iteration_counters.get(key, 0)
        brick_iteration_counters[key] = current_count + 1

        # Return the current count (0-based) or current_count + 1 (1-based)
        return current_count  # 0-based: first transaction is iteration 0

    def _simulate_single_brick(
        self, brick: FinBrickABC, ctx: ScenarioContext, t_index: np.ndarray
    ) -> BrickOutput:
        """Simulate a single brick with delayed activation and window handling."""
        # Handle delayed brick activation
        if brick.start_date is not None:
            start_idx = self._find_start_index(brick.start_date, t_index)
            if start_idx is None:
                # Brick starts after simulation period, return empty output
                return self._create_empty_output(len(t_index))
        else:
            start_idx = 0  # Brick starts at beginning of simulation

        # Create a modified context for this brick with delayed start
        brick_ctx = self._create_delayed_context(ctx, start_idx)

        # Simulate the brick
        out = brick.simulate(brick_ctx)

        # Shift the output arrays to the correct time positions
        if start_idx > 0:
            out = self._shift_output(out, start_idx, len(t_index))

        # Apply equity-neutral activation window mask
        mask = active_mask(t_index, brick.start_date, brick.end_date, brick.duration_m)
        _apply_window_equity_neutral(out, mask)

        # Add window end event if brick has an end
        if brick.end_date is not None or brick.duration_m is not None:
            end_idx = np.where(mask)[0]
            if len(end_idx) > 0:
                last_active_idx = end_idx[-1]
                out["events"].append(
                    Event(
                        t_index[last_active_idx],
                        "window_end",
                        f"Brick '{brick.name}' window ended",
                        {"brick_id": brick.id},
                    )
                )

        return out

    def _create_empty_output(self, length: int) -> BrickOutput:
        """Create an empty BrickOutput for bricks that don't participate in simulation."""
        return BrickOutput(
            cash_in=np.zeros(length),
            cash_out=np.zeros(length),
            assets=np.zeros(length),
            liabilities=np.zeros(length),
            interest=np.zeros(length),
            events=[],
        )

    def _aggregate_results(
        self,
        outputs: dict[str, BrickOutput],
        t_index: np.ndarray,
        include_cash: bool,
        journal=None,
    ) -> pd.DataFrame:
        """Aggregate simulation results into summary statistics (journal-first for V2)."""
        # Use journal-first aggregation if journal is available (V2)
        if journal is not None and self._registry is not None:
            from .results import _aggregate_journal_monthly

            # Convert t_index to PeriodIndex
            if not isinstance(t_index, pd.PeriodIndex):
                t_index_pd = pd.PeriodIndex(
                    [pd.Period(t, freq="M") for t in t_index], freq="M"
                )
            else:
                t_index_pd = t_index

            # Aggregate from journal
            totals = _aggregate_journal_monthly(
                journal=journal,
                registry=self._registry,
                time_index=t_index_pd,
                selection=None,  # All bricks
                transfer_visibility=TransferVisibility.BOUNDARY_ONLY,
                outputs=outputs,
            )

            # Add cash column if requested
            if include_cash:
                cash_assets = None
                for b in self.bricks:
                    if isinstance(b, ABrick) and b.kind == K.A_CASH:
                        if b.id in outputs:
                            s = outputs[b.id]["assets"]
                            cash_assets = (
                                s if cash_assets is None else (cash_assets + s)
                            )
                cash_assets = (
                    cash_assets if cash_assets is not None else np.zeros(len(t_index))
                )
                totals["cash"] = cash_assets

            # Finalize totals
            return finalize_totals(totals)

        # Legacy path: aggregate from outputs (deprecated in V2)
        # Handle optional cash arrays
        cash_in_tot = sum(
            o.get("cash_in", np.zeros(len(t_index))) for o in outputs.values()
        )
        cash_out_tot = sum(
            o.get("cash_out", np.zeros(len(t_index))) for o in outputs.values()
        )
        assets_tot = sum(o["assets"] for o in outputs.values())
        liabilities_tot = sum(o["liabilities"] for o in outputs.values())
        interest_tot = sum(o["interest"] for o in outputs.values())
        net_cf = cash_in_tot - cash_out_tot
        equity = assets_tot - liabilities_tot

        # Calculate non-cash assets (total assets minus cash)
        cash_assets = None
        for b in self.bricks:
            if isinstance(b, ABrick) and b.kind == K.A_CASH:
                s = outputs[b.id]["assets"]
                cash_assets = s if cash_assets is None else (cash_assets + s)
        cash_assets = cash_assets if cash_assets is not None else np.zeros(len(t_index))
        non_cash_assets = assets_tot - cash_assets

        # Create summary DataFrame with monthly totals
        totals = pd.DataFrame(
            {
                "t": t_index,
                "cash_in": cash_in_tot,
                "cash_out": cash_out_tot,
                "net_cf": net_cf,
                "assets": assets_tot,
                "liabilities": liabilities_tot,
                "interest": interest_tot,
                "non_cash": non_cash_assets,
                "equity": equity,
            }
        ).set_index("t")

        # Add cash column if requested
        if include_cash:
            totals["cash"] = cash_assets

        # Ensure monthly PeriodIndex (period-end)
        if not isinstance(totals.index, pd.PeriodIndex):
            totals.index = totals.index.to_period("M")

        # Finalize totals with proper identities and assertions
        return finalize_totals(totals)

    def aggregate_totals(self, freq: str = "Q", **kwargs: Any) -> pd.DataFrame:
        """
        Convenience method to aggregate the last run's totals to different frequencies.

        Args:
            freq: Frequency string ('Q', 'Y', 'Q-DEC', 'Q-MAR', etc.)
            **kwargs: Additional arguments passed to aggregate_totals()

        Returns:
            Aggregated DataFrame with the specified frequency

        Raises:
            RuntimeError: If no scenario has been run yet

        Example:
            >>> scenario.run(start=date(2026, 1, 1), months=36)
            >>> quarterly = scenario.aggregate_totals("Q")
            >>> yearly = scenario.aggregate_totals("Y")
        """
        if self._last_totals is None:
            raise RuntimeError(
                "No scenario has been run yet. Call scenario.run() first."
            )
        return aggregate_totals(self._last_totals, freq=freq, **kwargs)

    def validate(self, mode: str = "raise", tol: float = 1e-6) -> None:
        """
        Validate the last run's results using the scenario's bricks.

        This is a convenience method that automatically uses the last run's results
        and the scenario's bricks, so you don't need to pass them manually.

        Args:
            mode: Validation mode - "raise" (default) or "warn"
            tol: Tolerance for floating point comparisons

        Raises:
            RuntimeError: If no scenario has been run yet
            AssertionError: If validation fails and mode="raise"

        Example:
            >>> scenario.run(start=date(2026, 1, 1), months=36)
            >>> scenario.validate()  # Raises on validation failure
            >>> scenario.validate(mode="warn")  # Warns on validation failure
        """
        if self._last_results is None:
            raise RuntimeError(
                "No scenario has been run yet. Call scenario.run() first."
            )

        # Use the stored results from the last run
        validate_run(self._last_results, self.bricks, mode=mode, tol=tol)

    def to_canonical_frame(
        self, transfer_visibility: TransferVisibility | None = None
    ) -> pd.DataFrame:
        """
        Convert scenario results to canonical schema for Entity comparison.

        Returns a DataFrame with the canonical monthly schema required by Entity:
        - date (month-end dates)
        - cash, liquid_assets, illiquid_assets, liabilities
        - inflows, outflows, taxes, fees
        - Computed: total_assets, net_worth

        Args:
            transfer_visibility: How to handle transfer visibility (default: OFF)

        Returns:
            DataFrame with canonical columns and month-end date index

        Raises:
            RuntimeError: If no scenario has been run yet
        """
        if self._last_totals is None:
            raise RuntimeError(
                "No scenario has been run yet. Call scenario.run() first."
            )

        # Start with the totals DataFrame
        df = self._last_totals.copy()

        # Ensure we have month-end dates
        if not isinstance(df.index, pd.PeriodIndex):
            # Convert to PeriodIndex if needed
            df.index = pd.to_datetime(df.index).to_period("M")

        # Convert PeriodIndex to month-end Timestamps
        df = df.to_timestamp("M")

        # Map current columns to canonical schema
        canonical_df = pd.DataFrame(index=df.index)

        # Required columns - map from current schema
        canonical_df["date"] = df.index

        # Cash and asset mapping
        canonical_df["cash"] = df.get("cash", 0.0)
        canonical_df["liquid_assets"] = df.get("non_cash", 0.0)

        # Map property_value -> illiquid_assets (Option B, strict non-negative)
        if "property_value" in df.columns:
            pv = df["property_value"]
            if (pv < 0).any():
                bad_ix = list(df.index[(pv < 0)])
                raise ValueError(
                    f"property_value contains negative entries at indices {bad_ix[:5]}..."
                )
            canonical_df["illiquid_assets"] = pv
        else:
            canonical_df["illiquid_assets"] = 0.0

        # Liabilities
        canonical_df["liabilities"] = df.get("liabilities", 0.0)

        # Cash flows
        canonical_df["inflows"] = df.get("cash_in", 0.0)
        canonical_df["outflows"] = df.get("cash_out", 0.0)

        # Fees and taxes (not currently tracked separately)
        canonical_df["taxes"] = 0.0
        canonical_df["fees"] = 0.0

        # Compute derived columns
        canonical_df["total_assets"] = (
            canonical_df["cash"]
            + canonical_df["liquid_assets"]
            + canonical_df["illiquid_assets"]
        )
        canonical_df["net_worth"] = (
            canonical_df["total_assets"] - canonical_df["liabilities"]
        )

        # Enforce dtypes
        required_numeric_cols = [
            "cash",
            "liquid_assets",
            "illiquid_assets",
            "liabilities",
            "inflows",
            "outflows",
            "taxes",
            "fees",
            "total_assets",
            "net_worth",
        ]
        for col in required_numeric_cols:
            if col in canonical_df.columns:
                canonical_df[col] = canonical_df[col].astype("float64")

        # Reset index to have date as a column
        canonical_df = canonical_df.reset_index(drop=True)

        return canonical_df

    def _resolve_mortgage_links(self) -> None:
        """
        Resolve mortgage links and validate settlement buckets.

        This method processes all mortgage bricks to:
        1. Resolve start dates from StartLink references
        2. Resolve principal amounts from PrincipalLink references
        3. Validate settlement buckets for remaining_of links
        4. Validate brick configurations
        """
        # Create brick registry for lookups
        brick_registry = {b.id: b for b in self.bricks}

        # Process each mortgage brick
        for brick in self.bricks:
            if not isinstance(brick, LBrick) or brick.kind != K.L_LOAN_ANNUITY:
                continue

            # Convert LMortgageSpec to dict for strategy compatibility
            if isinstance(brick.spec, LMortgageSpec):
                brick.spec = brick.spec.__dict__.copy()

        # Resolve start dates
        self._resolve_start_dates(brick_registry)

        # Resolve principals - handled by individual strategies now
        # self._resolve_principals(brick_registry)

        # Validate settlement buckets
        self._validate_settlement_buckets(brick_registry)

    def _resolve_start_dates(self, brick_registry: dict[str, FinBrickABC]) -> None:
        """Resolve start dates from StartLink references."""
        for brick in self.bricks:
            if not hasattr(brick, "links") or not brick.links:
                continue

            start_link_data = brick.links.get("start")
            if not start_link_data:
                continue

            start_link = StartLink(**start_link_data)

            # Calculate start date from reference
            if start_link.on_fix_end_of:
                ref_brick = brick_registry.get(start_link.on_fix_end_of)
                if not ref_brick:
                    raise ConfigError(
                        f"StartLink references unknown brick: {start_link.on_fix_end_of}"
                    )
                if (
                    not isinstance(ref_brick, LBrick)
                    or ref_brick.kind != K.L_LOAN_ANNUITY
                ):
                    raise ConfigError(
                        f"StartLink on_fix_end_of must reference a mortgage: {start_link.on_fix_end_of}"
                    )

                # Calculate fix end date
                ref_start = ref_brick.start_date
                ref_spec = ref_brick.spec
                if isinstance(ref_spec, LMortgageSpec) and ref_spec.fix_rate_months:
                    fix_end = ref_start + pd.DateOffset(
                        months=ref_spec.fix_rate_months - 1
                    )
                else:
                    # Fallback to ref_brick end
                    fix_end = ref_start + pd.DateOffset(
                        months=(getattr(ref_brick, "duration_m", 12) or 12) - 1
                    )

                calculated_start = fix_end + pd.DateOffset(months=start_link.offset_m)

            elif start_link.on_end_of:
                ref_brick = brick_registry.get(start_link.on_end_of)
                if not ref_brick:
                    raise ConfigError(
                        f"StartLink references unknown brick: {start_link.on_end_of}"
                    )

                # Calculate end date
                ref_start = ref_brick.start_date
                ref_duration = getattr(ref_brick, "duration_m", 12) or 12
                ref_end = ref_start + pd.DateOffset(months=ref_duration - 1)
                calculated_start = ref_end + pd.DateOffset(months=start_link.offset_m)
            else:
                continue

            # Validate against explicit start_date if provided
            if brick.start_date is not None:
                if brick.start_date != calculated_start:
                    raise ConfigError(
                        f"Start date conflict on {brick.id}: "
                        f"explicit={brick.start_date} vs calculated={calculated_start}"
                    )
            else:
                brick.start_date = calculated_start

    def _resolve_principals(self, brick_registry: dict[str, FinBrickABC]) -> None:
        """Resolve principal amounts from PrincipalLink references."""
        for brick in self.bricks:
            if not isinstance(brick, LBrick) or brick.kind != K.L_LOAN_ANNUITY:
                continue

            if not hasattr(brick, "links") or not brick.links:
                continue

            principal_link_data = brick.links.get("principal")
            if not principal_link_data:
                continue

            principal_link = PrincipalLink(**principal_link_data)

            # Calculate principal from reference
            if principal_link.from_house:
                house_brick = brick_registry.get(principal_link.from_house)
                if not house_brick:
                    raise ConfigError(
                        f"PrincipalLink references unknown house: {principal_link.from_house}"
                    )
                if (
                    not isinstance(house_brick, ABrick)
                    or house_brick.kind != K.A_PROPERTY
                ):
                    raise ConfigError(
                        f"PrincipalLink from_house must reference a property: {principal_link.from_house}"
                    )

                # Extract house data (require initial_value)
                house_spec = house_brick.spec
                if "initial_value" not in house_spec:
                    raise ConfigError(
                        f"Property '{principal_link.from_house}' must specify 'initial_value'"
                    )
                initial_value = float(house_spec["initial_value"])
                down_payment = float(house_spec.get("down_payment", 0))
                fees_pct = float(house_spec.get("fees_pct", 0))
                finance_fees = bool(house_spec.get("finance_fees", False))

                # Calculate principal
                principal = initial_value - down_payment
                if finance_fees:
                    principal += initial_value * fees_pct

                # Store resolved principal for later use
                brick.spec["principal"] = principal

            elif principal_link.nominal is not None:
                # Direct nominal amount
                brick.spec["principal"] = principal_link.nominal

    def _validate_settlement_buckets(
        self, brick_registry: dict[str, FinBrickABC]
    ) -> None:
        """Validate settlement buckets for remaining_of links."""
        # Group contributors by remaining_of target
        settlement_buckets = {}

        for brick in self.bricks:
            if not isinstance(brick, LBrick) or brick.kind != K.L_LOAN_ANNUITY:
                continue

            if not hasattr(brick, "links") or not brick.links:
                continue

            principal_link_data = brick.links.get("principal")
            if not principal_link_data:
                continue

            principal_link = PrincipalLink(**principal_link_data)

            if principal_link.remaining_of:
                target_id = principal_link.remaining_of
                if target_id not in settlement_buckets:
                    settlement_buckets[target_id] = []
                settlement_buckets[target_id].append((brick, principal_link))

        # Validate each settlement bucket
        for target_id, contributors in settlement_buckets.items():
            target_brick = brick_registry.get(target_id)
            if not target_brick:
                raise ConfigError(
                    f"Settlement bucket references unknown brick: {target_id}"
                )

            # For now, we'll validate the structure but defer actual amount calculation
            # until we have the remaining balance from the target brick's simulation
            sum(c[1].nominal or 0 for c in contributors if c[1].nominal is not None)
            total_share = sum(
                c[1].share or 0 for c in contributors if c[1].share is not None
            )
            fill_remaining_count = sum(1 for c in contributors if c[1].fill_remaining)

            # Basic validation
            if total_share > 1.0:
                raise ConfigError(
                    f"Settlement bucket {target_id}: total share {total_share} > 1.0"
                )

            if fill_remaining_count > 1:
                raise ConfigError(
                    f"Settlement bucket {target_id}: multiple fill_remaining=True"
                )

            # Store settlement info for later validation during simulation
            for brick, principal_link in contributors:
                if not hasattr(brick, "_settlement_info"):
                    brick._settlement_info = []
                brick._settlement_info.append(
                    {
                        "target_id": target_id,
                        "share": principal_link.share,
                        "nominal": principal_link.nominal,
                        "fill_remaining": principal_link.fill_remaining,
                    }
                )

    def _find_start_index(self, start_date: date, t_index: np.ndarray) -> int | None:
        """
        Find the index in t_index that corresponds to the start_date.

        Args:
            start_date: The date when the brick should start
            t_index: The time index array

        Returns:
            The index where the brick should start, or None if after simulation period
        """
        start_datetime64 = np.datetime64(start_date, "M")

        # Find the first index where t_index >= start_date
        for i, t in enumerate(t_index):
            if t >= start_datetime64:
                return i

        return None  # start_date is after simulation period

    def _create_delayed_context(
        self, ctx: ScenarioContext, start_idx: int
    ) -> ScenarioContext:
        """
        Create a modified context for a brick that starts at a delayed time.

        Args:
            ctx: The original simulation context
            start_idx: The index where the brick starts

        Returns:
            A new context with time index starting from start_idx
        """
        # Create a new time index starting from the brick's start time
        new_t_index = ctx.t_index[start_idx:]

        return ScenarioContext(
            t_index=new_t_index,
            currency=ctx.currency,
            registry=ctx.registry,
            journal=ctx.journal,
            settlement_default_cash_id=ctx.settlement_default_cash_id,
        )

    def _shift_output(
        self, output: BrickOutput, start_idx: int, total_length: int
    ) -> BrickOutput:
        """
        Shift a brick's output to start at the correct time index.

        Args:
            output: The brick's output
            start_idx: The index where the brick starts
            total_length: The total length of the simulation

        Returns:
            A new BrickOutput with arrays padded with zeros at the beginning
        """
        # Create arrays of the full simulation length
        full_cash_in = np.zeros(total_length)
        full_cash_out = np.zeros(total_length)
        full_assets = np.zeros(total_length)
        full_liabilities = np.zeros(total_length)
        full_interest = np.zeros(total_length)

        # Place the brick's output at the correct time positions
        brick_length = len(output["cash_in"])
        end_idx = min(start_idx + brick_length, total_length)
        actual_length = end_idx - start_idx

        full_cash_in[start_idx:end_idx] = output["cash_in"][:actual_length]
        full_cash_out[start_idx:end_idx] = output["cash_out"][:actual_length]
        full_assets[start_idx:end_idx] = output["assets"][:actual_length]
        full_liabilities[start_idx:end_idx] = output["liabilities"][:actual_length]
        full_interest[start_idx:end_idx] = output["interest"][:actual_length]

        return BrickOutput(
            cash_in=full_cash_in,
            cash_out=full_cash_out,
            assets=full_assets,
            liabilities=full_liabilities,
            interest=full_interest,
            events=output["events"],  # Events don't need shifting
        )


def validate_run(
    res: dict, bricks=None, mode: str = "raise", tol: float = 1e-6
) -> None:
    """
    Validate simulation results against key financial invariants.

    This function performs several consistency checks on the simulation results
    to catch potential bugs or modeling errors. It can either raise exceptions
    or issue warnings based on the mode parameter.

    Args:
        res: The results dictionary returned by Scenario.run()
        mode: Validation mode - 'raise' to raise AssertionError on failures,
              'warn' to print warnings instead
        tol: Numerical tolerance for floating-point comparisons

    Raises:
        AssertionError: If validation fails and mode='raise'

    Note:
        The validation checks include:
        - Equity identity: equity = assets - debt
        - Debt monotonicity: debt should not increase after initial draws
        - Cash flow consistency: net_cf = cash_in - cash_out
    """
    totals = res["totals"]
    outputs = res["outputs"]

    # 1) Identity checks
    fails = []

    # Equity identity: equity = assets - liabilities
    if not np.allclose(
        totals["equity"].values,
        (totals["assets"] - totals["liabilities"]).values,
        atol=tol,
    ):
        fails.append("equity != assets - liabilities")

    # Cash flow consistency: net_cf = cash_in - cash_out
    if not np.allclose(
        totals["net_cf"].values,
        (totals["cash_in"] - totals["cash_out"]).values,
        atol=tol,
    ):
        fails.append("net_cf != cash_in - cash_out")

    # Liabilities monotonicity: liabilities should not increase after initial draws
    liabilities = totals["liabilities"].values
    if len(liabilities) > 1 and not np.all(np.diff(liabilities[1:]) <= tol):
        fails.append("liabilities increased after initial draws")

    # 4) Purchase settlement validation (if applicable)
    purchase_ok = True
    purchase_messages = []

    # Check for property purchases and their settlement
    for brick_id, output in res["outputs"].items():
        # Look for property bricks that have cash_out at t=0
        if output["cash_out"][0] > 1e-6:  # Has cash outflow at t=0
            # This might be a property purchase - check if it's reasonable
            cash_out_t0 = output["cash_out"][0]

            # Find the corresponding brick to get its spec
            brick = None
            for b in res.get("_scenario_bricks", []):
                if b.id == brick_id:
                    brick = b
                    break

            if brick and hasattr(brick, "spec") and "price" in brick.spec:
                price = float(brick.spec["price"])
                fees_pct = float(brick.spec.get("fees_pct", 0.0))
                fees = price * fees_pct
                fees_fin_pct = float(
                    brick.spec.get(
                        "fees_financed_pct",
                        1.0 if brick.spec.get("finance_fees") else 0.0,
                    )
                )
                fees_cash = fees * (1.0 - fees_fin_pct)
                expected_cash_out = price + fees_cash

                if abs(cash_out_t0 - expected_cash_out) > tol:
                    purchase_ok = False
                    purchase_messages.append(
                        f"{brick_id} cash_out[t0] = €{cash_out_t0:,.2f}, expected €{expected_cash_out:,.2f}"
                    )

    if not purchase_ok:
        fails.append("purchase settlement mismatch: " + "; ".join(purchase_messages))

    # 5) Liquidity constraints (only if we have bricks)
    if bricks is not None:
        for b in bricks:
            if isinstance(b, ABrick) and b.kind == K.A_CASH:
                bal = outputs[b.id]["assets"]
                overdraft_limit = (b.spec or {}).get("overdraft_limit")
                # Only check overdraft if a limit is explicitly set (None = unlimited)
                if overdraft_limit is not None:
                    overdraft = float(overdraft_limit)
                else:
                    overdraft = float("inf")  # No limit
                minbuf = float((b.spec or {}).get("min_buffer", 0.0))

                # Overdraft breach (skip if unlimited)
                if overdraft != float("inf") and (bal < -overdraft - tol).any():
                    t_idx = int(np.where(bal < -overdraft - tol)[0][0])
                    amt = float(bal[t_idx])
                    msg = (
                        f"Liquidity breach: cash '{b.id}' = {amt:,.2f} < overdraft_limit {overdraft:,.2f}. "
                        f"Suggest: top-up ≥ {abs(amt+overdraft):,.2f} or reduce t₀ outflows / finance fees."
                    )
                    fails.append(msg)

                # Buffer breach
                if (bal < minbuf - tol).any():
                    t_idx = int(np.where(bal < minbuf - tol)[0][0])
                    amt = float(bal[t_idx])
                    msg = (
                        f"Buffer breach: cash '{b.id}' = {amt:,.2f} < min_buffer {minbuf:,.2f}. "
                        f"Suggest: top-up ≥ {minbuf-amt:,.2f} or lower min_buffer."
                    )
                    fails.append(msg)

    # 6) Balloon payment validation (only if we have bricks)
    if bricks is not None:
        for b in bricks:
            if isinstance(b, LBrick) and b.kind == K.L_LOAN_ANNUITY:
                # Check if this mortgage has a balloon policy
                balloon_policy = (b.spec or {}).get("balloon_policy", "payoff")
                if balloon_policy == "payoff":
                    # Check if balloon was properly paid off
                    debt_balance = outputs[b.id]["liabilities"]
                    cash_out = outputs[b.id]["cash_out"]

                    # Find the last active month
                    mask = active_mask(
                        res["totals"].index, b.start_date, b.end_date, b.duration_m
                    )
                    if mask.any():
                        t_stop = np.where(mask)[0][-1]
                        residual_debt = debt_balance[t_stop]

                        if residual_debt > tol:
                            fails.append(
                                f"Balloon inconsistency: mortgage '{b.id}' has residual debt €{residual_debt:,.2f} at end of window but balloon_policy='payoff'"
                            )

                        # Check if balloon cash_out includes the residual debt payment
                        # The balloon payment should be at least as large as the residual debt
                        if t_stop > 0:
                            debt_before_balloon = debt_balance[t_stop - 1]
                            balloon_cash_out = cash_out[t_stop]
                            # The balloon payment should be >= the debt before payment (includes regular payment + balloon)
                            if (
                                balloon_cash_out > tol
                                and balloon_cash_out < debt_before_balloon - tol
                            ):
                                fails.append(
                                    f"Balloon payment insufficient: mortgage '{b.id}' balloon cash_out €{balloon_cash_out:,.2f} < debt before payment €{debt_before_balloon:,.2f}"
                                )

    # 7) ETF units validation (never negative)
    for brick_id, output in outputs.items():
        # Check if this is an ETF brick
        brick = None
        for b in res.get("_scenario_bricks", []):
            if b.id == brick_id:
                brick = b
                break

        if brick and hasattr(brick, "kind") and brick.kind == K.A_SECURITY_UNITIZED:
            asset_value = output["assets"]
            # We can't directly check units, but we can check for negative asset values
            if (asset_value < -tol).any():
                t_idx = int(np.where(asset_value < -tol)[0][0])
                val = float(asset_value[t_idx])
                fails.append(
                    f"ETF units negative: '{brick_id}' has negative asset value €{val:,.2f} at month {t_idx}"
                )

    # 8) Income escalator monotonicity (when annual_step_pct >= 0)
    for brick_id, output in outputs.items():
        # Check if this is an income brick
        brick = None
        for b in res.get("_scenario_bricks", []):
            if b.id == brick_id:
                brick = b
                break

        if brick and hasattr(brick, "kind") and brick.kind == K.F_INCOME_RECURRING:
            annual_step_pct = float((brick.spec or {}).get("annual_step_pct", 0.0))
            if annual_step_pct >= 0:
                cash_in = output["cash_in"]
                # Get activation mask to only check within active periods
                mask = active_mask(
                    res["totals"].index,
                    brick.start_date,
                    brick.end_date,
                    brick.duration_m,
                )

                # Check that income is non-decreasing within active periods
                for t in range(1, len(cash_in)):
                    # Only check if both current and previous months are active
                    if mask[t] and mask[t - 1] and cash_in[t] < cash_in[t - 1] - tol:
                        fails.append(
                            f"Income escalator violation: '{brick_id}' income decreased from €{cash_in[t-1]:,.2f} to €{cash_in[t]:,.2f} at month {t}"
                        )
                        break

    # 9) Window-end equity identity validation
    if bricks is not None:
        for b in bricks:
            if isinstance(b, ABrick | LBrick):
                mask = active_mask(
                    res["totals"].index, b.start_date, b.end_date, b.duration_m
                )
                if not mask.any():
                    continue
                t_stop = int(np.where(mask)[0].max())
                if t_stop + 1 >= len(res["totals"].index):
                    continue

                ob = outputs[b.id]
                # Check if there's a stock change at t_stop (auto-dispose/payoff)
                # If stocks change at t_stop, the flows at t_stop should match the change
                d_assets = ob["asset_value"][t_stop + 1] - ob["asset_value"][t_stop]
                d_debt = ob["debt_balance"][t_stop + 1] - ob["debt_balance"][t_stop]
                flows_t = ob["cash_in"][t_stop] - ob["cash_out"][t_stop]

                # Only validate if there's a significant stock change
                if abs(d_assets - d_debt) > 0.01:
                    if abs((d_assets - d_debt) - flows_t) > 0.01:
                        fails.append(
                            f"[{b.id}] Window-end equity mismatch at {res['totals'].index[t_stop]}: "
                            f"Δstocks={d_assets - d_debt:.2f} vs flows={flows_t:.2f}. "
                            "Missing sale/payoff or misordered terminal ops?"
                        )

    # Handle failures
    if fails:
        full = "Run validation failed: " + " | ".join(fails)
        if mode == "raise":
            raise AssertionError(full)
        else:
            print(f"WARNING: {full}")


def export_run_json(
    path: str,
    scenario: Scenario,
    res: dict,
    include_specs: bool = False,
    precision: int = 2,
) -> None:
    """
    Export simulation results to a comprehensive JSON format.

    This function creates a structured JSON export that includes:
    - Scenario metadata and brick definitions
    - Time series data for all bricks
    - Time-stamped events with metadata
    - Aggregated totals
    - Validation results and invariants

    Args:
        path: Output file path for the JSON file
        scenario: The scenario that was run
        res: Results dictionary from Scenario.run()
        include_specs: Whether to include brick specifications in the export
        precision: Number of decimal places for numeric values
    """
    # Convert time index to string format
    t_index = res["totals"].index.strftime("%Y-%m").tolist()

    # Extract series data for all bricks
    series = {}
    for brick_id, output in res["outputs"].items():
        series[brick_id] = {}
        for key in [
            "cash_in",
            "cash_out",
            "assets",
            "liabilities",
            "asset_value",
            "debt_balance",
        ]:
            if key in output:
                # Convert to list and round to specified precision
                if hasattr(output[key], "tolist"):
                    values = output[key].tolist()
                elif isinstance(output[key], list | tuple):
                    values = list(output[key])
                else:
                    values = [output[key]]

                if precision >= 0:
                    values = [
                        round(v, precision) if isinstance(v, int | float) else v
                        for v in values
                    ]
                series[brick_id][key] = values

    # Extract and format events
    events = []
    for brick_id, output in res["outputs"].items():
        for event in output.get("events", []):
            event_data = {
                "t": str(event.t.astype("datetime64[M]")),
                "brick_id": brick_id,
                "kind": event.kind,
                "message": event.message,
                "meta": event.meta or {},
            }
            # Add amount if available in meta
            if event.meta and "amount" in event.meta:
                event_data["amount"] = round(event.meta["amount"], precision)
            events.append(event_data)

    # Sort events by time
    events.sort(key=lambda x: x["t"])

    # Extract totals with precision
    totals = {}
    for col in res["totals"].columns:
        if hasattr(res["totals"][col], "tolist"):
            values = res["totals"][col].tolist()
        else:
            values = list(res["totals"][col])

        if precision >= 0:
            values = [
                round(v, precision) if isinstance(v, int | float) else v for v in values
            ]
        totals[col] = values

    # Run validation and capture results
    validation_results = {}
    try:
        # Capture validation output
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            validate_run(res, mode="warn", tol=1e-6)

        validation_output = buffer.getvalue()

        # Parse validation results
        validation_results = {
            "equity_identity": "equity != assets - liabilities"
            not in validation_output,
            "liabilities_monotone": "liabilities increased after initial draws"
            not in validation_output,
            "cash_flow_consistent": "net_cf != cash_in - cash_out"
            not in validation_output,
            "purchase_settlement_ok": "purchase settlement mismatch"
            not in validation_output,
            "messages": [
                line.strip()
                for line in validation_output.split("\n")
                if line.strip() and "WARNING:" in line
            ],
        }
    except Exception as e:
        validation_results = {
            "error": str(e),
            "equity_identity": False,
            "liabilities_monotone": False,
            "cash_flow_consistent": False,
            "purchase_settlement_ok": False,
            "messages": [f"Validation error: {str(e)}"],
        }

    # Build the comprehensive JSON structure
    payload = {
        "metadata": {
            "scenario": {"id": scenario.id, "name": scenario.name},
            "simulation_period": {
                "start": t_index[0],
                "end": t_index[-1],
                "months": len(t_index),
            },
            "bricks": [
                {
                    "id": brick.id,
                    "name": brick.name,
                    "family": brick.family,
                    "kind": brick.kind,
                    "start_date": str(brick.start_date) if brick.start_date else None,
                }
                for brick in scenario.bricks
            ],
        },
        "t_index": t_index,
        "series": series,
        "events": events,
        "totals": totals,
        "invariants": validation_results,
    }

    # Optionally include brick specifications
    if include_specs:
        payload["brick_specs"] = {
            brick.id: {"spec": brick.spec, "links": brick.links}
            for brick in scenario.bricks
        }

    # Custom JSON encoder to handle numpy types
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif hasattr(obj, "tolist"):
                return obj.tolist()
            return super().default(obj)

    # Write to file
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)


def export_ledger_csv(path: str, res: dict) -> None:
    """
    Export simulation results to a flat ledger CSV format.

    This creates a simple CSV with one row per cash flow or event,
    making it easy to eyeball the financial transactions.

    Args:
        path: Output file path for the CSV file
        res: Results dictionary from Scenario.run()
    """
    t_index = res["totals"].index
    rows = []

    # Extract cash flows
    for brick_id, output in res["outputs"].items():
        for flow_type in ["cash_in", "cash_out"]:
            arr = output[flow_type]
            for i, val in enumerate(arr):
                if abs(val) > 1e-9:  # Only include non-zero flows
                    rows.append(
                        {
                            "t": t_index[i].strftime("%Y-%m"),
                            "brick_id": brick_id,
                            "flow": flow_type,
                            "amount": float(val),
                            "note": "",
                        }
                    )

    # Extract events
    for brick_id, output in res["outputs"].items():
        for event in output.get("events", []):
            amount = 0.0
            if event.meta and "amount" in event.meta:
                amount = float(event.meta["amount"])
            elif event.meta and "price" in event.meta:
                amount = float(event.meta["price"])

            rows.append(
                {
                    "t": str(event.t.astype("datetime64[M]")),
                    "brick_id": brick_id,
                    "flow": "event",
                    "amount": amount,
                    "note": f"{event.kind}: {event.message}",
                }
            )

    # Sort by time, then by brick_id
    rows.sort(key=lambda x: (x["t"], x["brick_id"]))

    # Write CSV
    if rows:
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["t", "brick_id", "flow", "amount", "note"]
            )
            writer.writeheader()
            writer.writerows(rows)
