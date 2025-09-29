"""
Scenario engine for orchestrating financial simulations.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import date
import numpy as np
import pandas as pd
import warnings
import json
import csv

from .bricks import FinBrickABC, ABrick, LBrick, wire_strategies, ValuationRegistry, ScheduleRegistry, FlowRegistry
from .context import ScenarioContext
from .results import BrickOutput, ScenarioResults, finalize_totals, aggregate_totals
from .events import Event
from .utils import month_range, active_mask, _apply_window_equity_neutral
from .links import StartLink, PrincipalLink
from .specs import LMortgageSpec
from .errors import ConfigError
from .kinds import K
from .registry import Registry
from .macrobrick import MacroBrick


@dataclass
class ScenarioConfig:
    """Configuration options for scenario execution."""
    warn_on_overlap: bool = True
    include_struct_results: bool = True
    structs_filter: Optional[set[str]] = None

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
        The scenario expects exactly one cash account brick (kind='a.cash')
        to receive all routed cash flows from other bricks.
    """
    id: str
    name: str
    bricks: List[FinBrickABC]
    macrobricks: List[MacroBrick] = field(default_factory=list)
    currency: str = "EUR"
    config: ScenarioConfig = field(default_factory=ScenarioConfig)
    settlement_default_cash_id: Optional[str] = None  # Default cash account for settlement shortfalls
    _last_totals: Optional[pd.DataFrame] = None
    _last_results: Optional[dict] = None
    _registry: Optional[Registry] = None

    def __post_init__(self):
        """Initialize the registry after dataclass construction."""
        if self._registry is None:
            self._registry = self._build_registry()

    def _build_registry(self) -> Registry:
        """Build the registry from bricks and macrobricks."""
        bricks_dict = {brick.id: brick for brick in self.bricks}
        macrobricks_dict = {mb.id: mb for mb in self.macrobricks}
        return Registry(bricks_dict, macrobricks_dict)

    @classmethod
    def from_dict(cls, data: dict) -> "Scenario":
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
            currency=data.get("currency", "EUR")
        )

    def assert_disjoint(self, label: str, macrobrick_ids: List[str]) -> None:
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
            for mb2_id in macrobrick_ids[i+1:]:
                intersection = member_sets[mb1_id] & member_sets[mb2_id]
                if intersection:
                    raise ConfigError(
                        f"MacroBricks '{mb1_id}' and '{mb2_id}' in {label} are not disjoint. "
                        f"Shared bricks: {sorted(intersection)}"
                    )

    def check_disjoint(self, macrobrick_ids: List[str]) -> "DisjointReport":
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
                    conflicts=[f"MacroBrick '{mb_id}' not found in registry"]
                )
            member_sets[mb_id] = self._registry.get_struct_flat_members(mb_id)
        
        # Check for intersections
        conflicts = []
        for i, mb1_id in enumerate(macrobrick_ids):
            for mb2_id in macrobrick_ids[i+1:]:
                intersection = member_sets[mb1_id] & member_sets[mb2_id]
                if intersection:
                    conflicts.append({
                        "macrobrick1": mb1_id,
                        "macrobrick2": mb2_id,
                        "shared_bricks": sorted(intersection)
                    })
        
        return DisjointReport(is_disjoint=len(conflicts) == 0, conflicts=conflicts)

    def run(self, start: date, months: int, selection: Optional[List[str]] = None, include_cash: bool = True) -> dict:
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
            AssertionError: If there is not exactly one cash account brick (kind='a.cash')
            ConfigError: If selection contains unknown IDs or invalid MacroBrick references
            
        Note:
            The simulation assumes exactly one cash account to receive all routed flows.
            Cash flows from all other bricks are automatically routed to this account.
            If MacroBricks share bricks, execution is deduplicated at the scenario level.
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
        outputs = self._simulate_bricks(ctx, t_index, execution_order)
        
        # Aggregate results into summary statistics
        totals = self._aggregate_results(outputs, t_index, include_cash)
        
        # Build MacroBrick aggregates
        by_struct = self._build_struct_aggregates(outputs, brick_ids)
        
        # Store for convenience methods
        self._last_totals = totals
        self._last_results = {
            "outputs": outputs, 
            "by_struct": by_struct,
            "totals": totals, 
            "views": ScenarioResults(totals), 
            "_scenario_bricks": self.bricks,
            "meta": {
                "execution_order": execution_order,
                "overlaps": overlaps
            }
        }
        
        return self._last_results

    def _resolve_execution_set(self, selection: Optional[List[str]]) -> tuple[set[str], Dict[str, Dict[str, any]]]:
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
            return set(brick.id for brick in self.bricks), {}
        
        exec_set: set[str] = set()
        overlaps: Dict[str, List[str]] = {}
        
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
        overlaps_report: Dict[str, Dict[str, any]] = {}
        for brick_id, owners in overlaps.items():
            if len(owners) > 1:
                overlaps_report[brick_id] = {
                    "macrobricks": sorted(owners),
                    "count": len(owners)
                }
        
        # Warn about overlaps if configured to do so
        if self.config.warn_on_overlap and overlaps_report:
            import logging
            logger = logging.getLogger(__name__)
            for brick_id, info in overlaps_report.items():
                logger.warning(
                    "Brick '%s' is shared across MacroBricks: %s. "
                    "Execution is deduplicated at scenario level.",
                    brick_id, ", ".join(info["macrobricks"])
                )
        
        return exec_set, overlaps_report

    def _build_dependency_graph(self, brick_ids: set[str]) -> Dict[str, set[str]]:
        """
        Build dependency graph from brick links.
        
        Args:
            brick_ids: Set of brick IDs to analyze
            
        Returns:
            Dictionary mapping brick_id to set of dependencies
        """
        edges: Dict[str, set[str]] = {}
        
        for brick in self.bricks:
            if brick.id not in brick_ids:
                continue
                
            edges[brick.id] = set()
            
            # Check for dependency links
            if hasattr(brick, 'links') and brick.links:
                for link_type, link_data in brick.links.items():
                    if isinstance(link_data, dict):
                        # Handle PrincipalLink, StartLink, etc.
                        if 'from_house' in link_data:
                            dep_id = link_data['from_house']
                            if dep_id in brick_ids:
                                edges[brick.id].add(dep_id)
                        elif 'on_end_of' in link_data:
                            dep_id = link_data['on_end_of']
                            if dep_id in brick_ids:
                                edges[brick.id].add(dep_id)
                        elif 'remaining_of' in link_data:
                            dep_id = link_data['remaining_of']
                            if dep_id in brick_ids:
                                edges[brick.id].add(dep_id)
                    elif isinstance(link_data, str):
                        # Simple string reference
                        if link_data in brick_ids:
                            edges[brick.id].add(link_data)
        
        return edges

    def _topological_order(self, brick_ids: set[str], edges: Dict[str, set[str]]) -> List[str]:
        """
        Compute topological order of bricks by dependencies, fallback to stable ID sort.
        
        Args:
            brick_ids: Set of brick IDs to order
            edges: Dependency graph (brick_id -> set of dependencies)
            
        Returns:
            List of brick IDs in execution order
        """
        from collections import deque, defaultdict
        
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

    def _build_struct_aggregates(self, outputs: Dict[str, BrickOutput], brick_ids: set[str]) -> Dict[str, BrickOutput]:
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
            
        by_struct: Dict[str, BrickOutput] = {}
        
        for struct_id, macrobrick in self._registry.iter_macrobricks():
            # Apply structs filter if configured
            if self.config.structs_filter is not None and struct_id not in self.config.structs_filter:
                continue
                
            # Get the member bricks for this MacroBrick (using cached expansion)
            member_bricks = self._registry.get_struct_flat_members(struct_id)
            
            # Only include bricks that were actually executed
            executed_members = member_bricks & brick_ids
            
            if not executed_members:
                # Skip MacroBricks with no executed members
                continue
                
            # Create empty aggregate
            agg = self._create_empty_output(len(outputs[list(outputs.keys())[0]]["cash_in"]))
            
            # Sum outputs from all executed member bricks
            for brick_id in executed_members:
                if brick_id in outputs:
                    brick_output = outputs[brick_id]
                    for key in agg.keys():
                        if key in brick_output:
                            agg[key] += brick_output[key]
            
            by_struct[struct_id] = agg
            
        return by_struct

    def _create_empty_output(self, length: int) -> BrickOutput:
        """Create an empty BrickOutput with the specified length."""
        return {
            "cash_in": np.zeros(length),
            "cash_out": np.zeros(length),
            "asset_value": np.zeros(length),
            "debt_balance": np.zeros(length),
            "equity": np.zeros(length),
        }
    
    def _initialize_simulation(self, start: date, months: int) -> tuple[np.ndarray, ScenarioContext]:
        """Initialize the simulation context and resolve mortgage links."""
        t_index = month_range(start, months)
        ctx = ScenarioContext(t_index=t_index, currency=self.currency,
                              registry={b.id: b for b in self.bricks})
        
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
    
    def _simulate_bricks(self, ctx: ScenarioContext, t_index: np.ndarray, execution_order: List[str]) -> Dict[str, BrickOutput]:
        """Simulate all bricks and route cash flows to cash account."""
        outputs: Dict[str, BrickOutput] = {}
        
        # Find the cash account brick (must be in selection)
        cash_ids = [b.id for b in self.bricks if isinstance(b, ABrick) and b.kind == "a.cash" and b.id in execution_order]
        assert len(cash_ids) == 1, "Scenario expects exactly one cash account brick (kind='a.cash') in selection"
        cash_id = cash_ids[0]
        
        # Accumulate cash flows from all non-cash bricks
        routed_in = np.zeros(len(t_index))
        routed_out = np.zeros(len(t_index))
        
        # Simulate all non-cash bricks in execution order
        for b in self.bricks:
            if b.id not in execution_order:
                continue  # Skip bricks not in selection
            if b.id == cash_id:
                continue  # Skip cash account for now
            
            # Simulate this brick
            brick_output = self._simulate_single_brick(b, ctx, t_index)
            outputs[b.id] = brick_output
            
            # Accumulate cash flows for routing
            routed_in += brick_output["cash_in"]
            routed_out += brick_output["cash_out"]
        
        # Route accumulated cash flows to the cash account
        cash_brick = ctx.registry[cash_id]
        cash_brick.spec.setdefault("external_in", np.zeros(len(t_index)))
        cash_brick.spec.setdefault("external_out", np.zeros(len(t_index)))
        cash_brick.spec["external_in"] = routed_in
        cash_brick.spec["external_out"] = routed_out
        
        # Simulate the cash account with all routed flows
        outputs[cash_id] = cash_brick.simulate(ctx)
        
        return outputs
    
    def _simulate_single_brick(self, brick: FinBrickABC, ctx: ScenarioContext, t_index: np.ndarray) -> BrickOutput:
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
                    Event(t_index[last_active_idx], "window_end", 
                          f"Brick '{brick.name}' window ended", {"brick_id": brick.id})
                )
        
        return out
    
    def _create_empty_output(self, length: int) -> BrickOutput:
        """Create an empty BrickOutput for bricks that don't participate in simulation."""
        return BrickOutput(
            cash_in=np.zeros(length),
            cash_out=np.zeros(length),
            asset_value=np.zeros(length),
            debt_balance=np.zeros(length),
            events=[]
        )
    
    def _aggregate_results(self, outputs: Dict[str, BrickOutput], t_index: np.ndarray, include_cash: bool) -> pd.DataFrame:
        """Aggregate simulation results into summary statistics."""
        # Calculate totals
        cash_in_tot = sum(o["cash_in"] for o in outputs.values())
        cash_out_tot = sum(o["cash_out"] for o in outputs.values())
        assets_tot = sum(o["asset_value"] for o in outputs.values())
        liabilities_tot = sum(o["debt_balance"] for o in outputs.values())
        net_cf = cash_in_tot - cash_out_tot
        equity = assets_tot - liabilities_tot
        
        # Calculate non-cash assets (total assets minus cash)
        cash_assets = None
        for b in self.bricks:
            if isinstance(b, ABrick) and b.kind == K.A_CASH:
                s = outputs[b.id]["asset_value"]
                cash_assets = s if cash_assets is None else (cash_assets + s)
        cash_assets = cash_assets if cash_assets is not None else np.zeros(len(t_index))
        non_cash_assets = assets_tot - cash_assets
        
        # Create summary DataFrame with monthly totals
        totals = pd.DataFrame({
            "t": t_index, 
            "cash_in": cash_in_tot, 
            "cash_out": cash_out_tot,
            "net_cf": net_cf, 
            "assets": assets_tot, 
            "liabilities": liabilities_tot,
            "non_cash": non_cash_assets,
            "equity": equity
        }).set_index("t")
        
        # Add cash column if requested
        if include_cash:
            totals["cash"] = cash_assets
        
        # Ensure monthly PeriodIndex (period-end)
        if not isinstance(totals.index, pd.PeriodIndex):
            totals.index = totals.index.to_period("M")
        
        # Finalize totals with proper identities and assertions
        return finalize_totals(totals)
    
    def aggregate_totals(self, freq: str = "Q", **kwargs) -> pd.DataFrame:
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
            raise RuntimeError("No scenario has been run yet. Call scenario.run() first.")
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
            raise RuntimeError("No scenario has been run yet. Call scenario.run() first.")
        
        # Use the stored results from the last run
        validate_run(self._last_results, self.bricks, mode=mode, tol=tol)
    
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
            if not isinstance(brick, LBrick) or brick.kind != K.L_MORT_ANN:
                continue
            
            # Convert LMortgageSpec to dict for strategy compatibility
            if isinstance(brick.spec, LMortgageSpec):
                brick.spec = brick.spec.__dict__.copy()
                
        
        # Resolve start dates
        self._resolve_start_dates(brick_registry)
        
        # Resolve principals
        self._resolve_principals(brick_registry)
        
        # Validate settlement buckets
        self._validate_settlement_buckets(brick_registry)
    
    def _resolve_start_dates(self, brick_registry: Dict[str, FinBrickABC]) -> None:
        """Resolve start dates from StartLink references."""
        for brick in self.bricks:
            if not hasattr(brick, 'links') or not brick.links:
                continue
                
            start_link_data = brick.links.get("start")
            if not start_link_data:
                continue
                
            start_link = StartLink(**start_link_data)
            
            # Calculate start date from reference
            if start_link.on_fix_end_of:
                ref_brick = brick_registry.get(start_link.on_fix_end_of)
                if not ref_brick:
                    raise ConfigError(f"StartLink references unknown brick: {start_link.on_fix_end_of}")
                if not isinstance(ref_brick, LBrick) or ref_brick.kind != K.L_MORT_ANN:
                    raise ConfigError(f"StartLink on_fix_end_of must reference a mortgage: {start_link.on_fix_end_of}")
                
                # Calculate fix end date
                ref_start = ref_brick.start_date
                ref_spec = ref_brick.spec
                if isinstance(ref_spec, LMortgageSpec) and ref_spec.fix_rate_months:
                    fix_end = ref_start + pd.DateOffset(months=ref_spec.fix_rate_months - 1)
                else:
                    # Fallback to brick end
                    fix_end = ref_start + pd.DateOffset(months=(getattr(brick, 'duration_m', 12) or 12) - 1)
                
                calculated_start = fix_end + pd.DateOffset(months=start_link.offset_m)
                
            elif start_link.on_end_of:
                ref_brick = brick_registry.get(start_link.on_end_of)
                if not ref_brick:
                    raise ConfigError(f"StartLink references unknown brick: {start_link.on_end_of}")
                
                # Calculate end date
                ref_start = ref_brick.start_date
                ref_duration = getattr(ref_brick, 'duration_m', 12) or 12
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
    
    def _resolve_principals(self, brick_registry: Dict[str, FinBrickABC]) -> None:
        """Resolve principal amounts from PrincipalLink references."""
        for brick in self.bricks:
            if not isinstance(brick, LBrick) or brick.kind != K.L_MORT_ANN:
                continue
                
            if not hasattr(brick, 'links') or not brick.links:
                continue
                
            principal_link_data = brick.links.get("principal")
            if not principal_link_data:
                continue
                
            principal_link = PrincipalLink(**principal_link_data)
            
            # Calculate principal from reference
            if principal_link.from_house:
                house_brick = brick_registry.get(principal_link.from_house)
                if not house_brick:
                    raise ConfigError(f"PrincipalLink references unknown house: {principal_link.from_house}")
                if not isinstance(house_brick, ABrick) or house_brick.kind != K.A_PROPERTY_DISCRETE:
                    raise ConfigError(f"PrincipalLink from_house must reference a property: {principal_link.from_house}")
                
                # Extract house data (require initial_value)
                house_spec = house_brick.spec
                if "initial_value" not in house_spec:
                    raise ConfigError(f"Property '{principal_link.from_house}' must specify 'initial_value'")
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
    
    def _validate_settlement_buckets(self, brick_registry: Dict[str, FinBrickABC]) -> None:
        """Validate settlement buckets for remaining_of links."""
        # Group contributors by remaining_of target
        settlement_buckets = {}
        
        for brick in self.bricks:
            if not isinstance(brick, LBrick) or brick.kind != K.L_MORT_ANN:
                continue
                
            if not hasattr(brick, 'links') or not brick.links:
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
                raise ConfigError(f"Settlement bucket references unknown brick: {target_id}")
            
            # For now, we'll validate the structure but defer actual amount calculation
            # until we have the remaining balance from the target brick's simulation
            total_nominal = sum(
                c[1].nominal or 0 for c in contributors if c[1].nominal is not None
            )
            total_share = sum(
                c[1].share or 0 for c in contributors if c[1].share is not None
            )
            fill_remaining_count = sum(
                1 for c in contributors if c[1].fill_remaining
            )
            
            # Basic validation
            if total_share > 1.0:
                raise ConfigError(f"Settlement bucket {target_id}: total share {total_share} > 1.0")
            
            if fill_remaining_count > 1:
                raise ConfigError(f"Settlement bucket {target_id}: multiple fill_remaining=True")
            
            # Store settlement info for later validation during simulation
            for brick, principal_link in contributors:
                if not hasattr(brick, '_settlement_info'):
                    brick._settlement_info = []
                brick._settlement_info.append({
                    'target_id': target_id,
                    'share': principal_link.share,
                    'nominal': principal_link.nominal,
                    'fill_remaining': principal_link.fill_remaining
                })
    
    def _find_start_index(self, start_date: date, t_index: np.ndarray) -> Optional[int]:
        """
        Find the index in t_index that corresponds to the start_date.
        
        Args:
            start_date: The date when the brick should start
            t_index: The time index array
            
        Returns:
            The index where the brick should start, or None if after simulation period
        """
        start_datetime64 = np.datetime64(start_date, 'M')
        
        # Find the first index where t_index >= start_date
        for i, t in enumerate(t_index):
            if t >= start_datetime64:
                return i
        
        return None  # start_date is after simulation period
    
    def _create_delayed_context(self, ctx: ScenarioContext, start_idx: int) -> ScenarioContext:
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
            registry=ctx.registry
        )
    
    def _shift_output(self, output: BrickOutput, start_idx: int, total_length: int) -> BrickOutput:
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
        full_asset_value = np.zeros(total_length)
        full_debt_balance = np.zeros(total_length)
        
        # Place the brick's output at the correct time positions
        brick_length = len(output["cash_in"])
        end_idx = min(start_idx + brick_length, total_length)
        actual_length = end_idx - start_idx
        
        full_cash_in[start_idx:end_idx] = output["cash_in"][:actual_length]
        full_cash_out[start_idx:end_idx] = output["cash_out"][:actual_length]
        full_asset_value[start_idx:end_idx] = output["asset_value"][:actual_length]
        full_debt_balance[start_idx:end_idx] = output["debt_balance"][:actual_length]
        
        return BrickOutput(
            cash_in=full_cash_in,
            cash_out=full_cash_out,
            asset_value=full_asset_value,
            debt_balance=full_debt_balance,
            events=output["events"]  # Events don't need shifting
        )


def validate_run(res: dict, bricks=None, mode: str = "raise", tol: float = 1e-6) -> None:
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
    if not np.allclose(totals["equity"].values, (totals["assets"] - totals["liabilities"]).values, atol=tol):
        fails.append("equity != assets - liabilities")
    
    # Cash flow consistency: net_cf = cash_in - cash_out
    if not np.allclose(totals["net_cf"].values, (totals["cash_in"] - totals["cash_out"]).values, atol=tol):
        fails.append("net_cf != cash_in - cash_out")
    
    # Liabilities monotonicity: liabilities should not increase after initial draws
    liabilities = totals["liabilities"].values
    if len(liabilities) > 1 and not np.all(np.diff(liabilities[1:]) <= tol):
        fails.append("liabilities increased after t0")
    
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
            
            if brick and hasattr(brick, 'spec') and "price" in brick.spec:
                price = float(brick.spec["price"])
                fees_pct = float(brick.spec.get("fees_pct", 0.0))
                fees = price * fees_pct
                fees_fin_pct = float(brick.spec.get("fees_financed_pct", 1.0 if brick.spec.get("finance_fees") else 0.0))
                fees_cash = fees * (1.0 - fees_fin_pct)
                expected_cash_out = price + fees_cash
                
                if abs(cash_out_t0 - expected_cash_out) > tol:
                    purchase_ok = False
                    purchase_messages.append(f"{brick_id} cash_out[t0] = €{cash_out_t0:,.2f}, expected €{expected_cash_out:,.2f}")
    
    if not purchase_ok:
        fails.append("purchase settlement mismatch: " + "; ".join(purchase_messages))
    
    # 5) Liquidity constraints (only if we have bricks)
    if bricks is not None:
        for b in bricks:
            if isinstance(b, ABrick) and b.kind == K.A_CASH:
                bal = outputs[b.id]["asset_value"]
                overdraft = float((b.spec or {}).get("overdraft_limit", 0.0))
                minbuf = float((b.spec or {}).get("min_buffer", 0.0))
                
                # Overdraft breach
                if (bal < -overdraft - tol).any():
                    t_idx = int(np.where(bal < -overdraft - tol)[0][0])
                    amt = float(bal[t_idx])
                    msg = (f"Liquidity breach: cash '{b.id}' = {amt:,.2f} < overdraft_limit {overdraft:,.2f}. "
                           f"Suggest: top-up ≥ {abs(amt+overdraft):,.2f} or reduce t₀ outflows / finance fees.")
                    fails.append(msg)
                
                # Buffer breach
                if (bal < minbuf - tol).any():
                    t_idx = int(np.where(bal < minbuf - tol)[0][0])
                    amt = float(bal[t_idx])
                    msg = (f"Buffer breach: cash '{b.id}' = {amt:,.2f} < min_buffer {minbuf:,.2f}. "
                           f"Suggest: top-up ≥ {minbuf-amt:,.2f} or lower min_buffer.")
                    fails.append(msg)
    
    # 6) Balloon payment validation (only if we have bricks)
    if bricks is not None:
        for b in bricks:
            if isinstance(b, LBrick) and b.kind == K.L_MORT_ANN:
                # Check if this mortgage has a balloon policy
                balloon_policy = (b.spec or {}).get("balloon_policy", "payoff")
                if balloon_policy == "payoff":
                    # Check if balloon was properly paid off
                    debt_balance = outputs[b.id]["debt_balance"]
                    cash_out = outputs[b.id]["cash_out"]
                    
                    # Find the last active month
                    mask = active_mask(res["totals"].index, b.start_date, b.end_date, b.duration_m)
                    if mask.any():
                        t_stop = np.where(mask)[0][-1]
                        residual_debt = debt_balance[t_stop]
                        
                        if residual_debt > tol:
                            fails.append(f"Balloon inconsistency: mortgage '{b.id}' has residual debt €{residual_debt:,.2f} at end of window but balloon_policy='payoff'")
                        
                        # Check if balloon cash_out includes the residual debt payment
                        # The balloon payment should be at least as large as the residual debt
                        if t_stop > 0:
                            debt_before_balloon = debt_balance[t_stop - 1]
                            balloon_cash_out = cash_out[t_stop]
                            # The balloon payment should be >= the debt before payment (includes regular payment + balloon)
                            if balloon_cash_out > tol and balloon_cash_out < debt_before_balloon - tol:
                                fails.append(f"Balloon payment insufficient: mortgage '{b.id}' balloon cash_out €{balloon_cash_out:,.2f} < debt before payment €{debt_before_balloon:,.2f}")
    
    # 7) ETF units validation (never negative)
    for brick_id, output in outputs.items():
        # Check if this is an ETF brick
        brick = None
        for b in res.get("_scenario_bricks", []):
            if b.id == brick_id:
                brick = b
                break
        
            if brick and hasattr(brick, 'kind') and brick.kind == K.A_ETF_UNITIZED:
                asset_value = output["asset_value"]
                # We can't directly check units, but we can check for negative asset values
                if (asset_value < -tol).any():
                    t_idx = int(np.where(asset_value < -tol)[0][0])
                    val = float(asset_value[t_idx])
                    fails.append(f"ETF units negative: '{brick_id}' has negative asset value €{val:,.2f} at month {t_idx}")
    
    # 8) Income escalator monotonicity (when annual_step_pct >= 0)
    for brick_id, output in outputs.items():
        # Check if this is an income brick
        brick = None
        for b in res.get("_scenario_bricks", []):
            if b.id == brick_id:
                brick = b
                break
        
            if brick and hasattr(brick, 'kind') and brick.kind == K.F_INCOME_FIXED:
                annual_step_pct = float((brick.spec or {}).get("annual_step_pct", 0.0))
                if annual_step_pct >= 0:
                    cash_in = output["cash_in"]
                    # Get activation mask to only check within active periods
                    mask = active_mask(res["totals"].index, brick.start_date, brick.end_date, brick.duration_m)
                
                # Check that income is non-decreasing within active periods
                for t in range(1, len(cash_in)):
                    # Only check if both current and previous months are active
                    if mask[t] and mask[t-1] and cash_in[t] < cash_in[t-1] - tol:
                        fails.append(f"Income escalator violation: '{brick_id}' income decreased from €{cash_in[t-1]:,.2f} to €{cash_in[t]:,.2f} at month {t}")
                        break
    
    # 9) Window-end equity identity validation
    if bricks is not None:
        for b in bricks:
            if isinstance(b, (ABrick, LBrick)):
                mask = active_mask(res["totals"].index, b.start_date, b.end_date, b.duration_m)
                if not mask.any():
                    continue
                t_stop = int(np.where(mask)[0].max())
                if t_stop + 1 >= len(res["totals"].index):
                    continue
                
                ob = outputs[b.id]
                # Check if there's a stock change at t_stop (auto-dispose/payoff)
                # If stocks change at t_stop, the flows at t_stop should match the change
                d_assets = ob["asset_value"][t_stop+1] - ob["asset_value"][t_stop]
                d_debt = ob["debt_balance"][t_stop+1] - ob["debt_balance"][t_stop]
                flows_t = ob["cash_in"][t_stop] - ob["cash_out"][t_stop]
                
                # Only validate if there's a significant stock change
                if abs(d_assets - d_debt) > 0.01:
                    if abs((d_assets - d_debt) - flows_t) > 0.01:
                        raise ValueError(
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


def export_run_json(path: str, scenario: Scenario, res: dict, include_specs: bool = False, precision: int = 2) -> None:
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
        for key in ["cash_in", "cash_out", "asset_value", "debt_balance"]:
            if key in output:
                # Convert to list and round to specified precision
                if hasattr(output[key], "tolist"):
                    values = output[key].tolist()
                elif isinstance(output[key], (list, tuple)):
                    values = list(output[key])
                else:
                    values = [output[key]]
                
                if precision >= 0:
                    values = [round(v, precision) if isinstance(v, (int, float)) else v for v in values]
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
                "meta": event.meta or {}
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
            values = [round(v, precision) if isinstance(v, (int, float)) else v for v in values]
        totals[col] = values
    
    # Run validation and capture results
    validation_results = {}
    try:
        # Capture validation output
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        
        validate_run(res, mode="warn", tol=1e-6)
        
        sys.stdout = old_stdout
        validation_output = buffer.getvalue()
        
        # Parse validation results
        validation_results = {
            "equity_identity": "equity != assets - liabilities" not in validation_output,
            "liabilities_monotone": "liabilities increased after initial draws" not in validation_output,
            "cash_flow_consistent": "net_cf != cash_in - cash_out" not in validation_output,
            "purchase_settlement_ok": "purchase settlement mismatch" not in validation_output,
            "messages": [line.strip() for line in validation_output.split('\n') if line.strip() and "WARNING:" in line]
        }
    except Exception as e:
        validation_results = {
            "error": str(e),
            "equity_identity": False,
            "liabilities_monotone": False,
            "cash_flow_consistent": False,
            "purchase_settlement_ok": False,
            "messages": [f"Validation error: {str(e)}"]
        }
    
    # Build the comprehensive JSON structure
    payload = {
        "metadata": {
            "scenario": {
                "id": scenario.id,
                "name": scenario.name
            },
            "simulation_period": {
                "start": t_index[0],
                "end": t_index[-1],
                "months": len(t_index)
            },
            "bricks": [
                {
                    "id": brick.id,
                    "name": brick.name,
                    "family": brick.family,
                    "kind": brick.kind,
                    "start_date": str(brick.start_date) if brick.start_date else None
                }
                for brick in scenario.bricks
            ]
        },
        "t_index": t_index,
        "series": series,
        "events": events,
        "totals": totals,
        "invariants": validation_results
    }
    
    # Optionally include brick specifications
    if include_specs:
        payload["brick_specs"] = {
            brick.id: {
                "spec": brick.spec,
                "links": brick.links
            }
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
            elif hasattr(obj, 'tolist'):
                return obj.tolist()
            return super(NumpyEncoder, self).default(obj)
    
    # Write to file
    with open(path, 'w') as f:
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
                    rows.append({
                        "t": t_index[i].strftime("%Y-%m"),
                        "brick_id": brick_id,
                        "flow": flow_type,
                        "amount": float(val),
                        "note": ""
                    })
    
    # Extract events
    for brick_id, output in res["outputs"].items():
        for event in output.get("events", []):
            amount = 0.0
            if event.meta and "amount" in event.meta:
                amount = float(event.meta["amount"])
            elif event.meta and "price" in event.meta:
                amount = float(event.meta["price"])
            
            rows.append({
                "t": str(event.t.astype("datetime64[M]")),
                "brick_id": brick_id,
                "flow": "event",
                "amount": amount,
                "note": f"{event.kind}: {event.message}"
            })
    
    # Sort by time, then by brick_id
    rows.sort(key=lambda x: (x["t"], x["brick_id"]))
    
    # Write CSV
    if rows:
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["t", "brick_id", "flow", "amount", "note"])
            writer.writeheader()
            writer.writerows(rows)
