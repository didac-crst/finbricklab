"""
Entity class for grouping and comparing multiple scenarios.

This module provides the Entity class which serves as the top-level aggregator
for multiple financial scenarios, enabling benchmarking and comparison across
different financial strategies.
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from .bricks import ABrick, FBrick, FinBrickABC, LBrick, TBrick
from .clone import clone_brick
from .exceptions import ScenarioValidationError
from .links import RouteLink
from .macrobrick import MacroBrick
from .registry import Registry
from .scenario import Scenario


@dataclass
class Entity:
    """
    Top-level aggregator for multiple financial scenarios.

    An Entity represents a single financial entity (person, family, portfolio)
    that can have multiple scenarios for comparison and benchmarking.

    The Entity serves as both a catalog of financial instruments (bricks and MacroBricks)
    and a builder for creating scenarios from these instruments.

    Attributes:
        id: Unique identifier for the entity
        name: Human-readable name for the entity
        base_currency: Base currency for all scenarios (default: 'EUR')
        assumptions: Dictionary of assumptions (inflation, tax profile, fees, etc.)
        scenarios: List of scenarios belonging to this entity
        benchmarks: Dictionary mapping benchmark names to scenario IDs

        # Catalog fields (internal)
        _bricks: Dictionary mapping brick IDs to brick objects
        _macrobricks: Dictionary mapping MacroBrick IDs to MacroBrick objects
        _scenarios: Dictionary mapping scenario IDs to scenario objects
    """

    id: str
    name: str
    base_currency: str = "EUR"
    assumptions: dict[str, Any] = field(default_factory=dict)
    scenarios: list[Scenario] = field(default_factory=list)
    benchmarks: dict[str, str] = field(default_factory=dict)

    # NEW: catalog + scenarios owned by Entity
    _bricks: dict[str, FinBrickABC] = field(default_factory=dict, repr=False)
    _macrobricks: dict[str, MacroBrick] = field(default_factory=dict, repr=False)
    _scenarios: dict[str, Scenario] = field(default_factory=dict, repr=False)

    def compare(self, scenario_ids: list[str] | None = None) -> pd.DataFrame:
        """
        Compare multiple scenarios and return a tidy DataFrame with canonical columns.

        Args:
            scenario_ids: List of scenario IDs to include. If None, includes all scenarios.

        Returns:
            DataFrame with canonical columns plus scenario_id and scenario_name.
            Includes computed total_assets and net_worth columns.

        Raises:
            ValueError: If scenario_ids contains unknown scenario IDs
        """
        if scenario_ids is None:
            scenario_ids = [s.id for s in self.scenarios]

        # Validate scenario IDs
        available_ids = {s.id for s in self.scenarios}
        invalid_ids = set(scenario_ids) - available_ids
        if invalid_ids:
            raise ValueError(f"Unknown scenario IDs: {sorted(invalid_ids)}")

        # Validate currencies (placeholder - assumes all scenarios use entity's base currency)
        try:
            from ..fx import validate_entity_currencies

            scenarios_to_validate = [s for s in self.scenarios if s.id in scenario_ids]
            validate_entity_currencies(self, scenarios_to_validate)
        except ImportError:
            # FX module not available - assume all scenarios are compatible
            pass

        dfs = []
        for scenario in self.scenarios:
            if scenario.id in scenario_ids:
                # Get canonical frame from scenario
                df = scenario.to_canonical_frame()

                # Add scenario metadata
                df = df.copy()
                df["scenario_id"] = scenario.id
                df["scenario_name"] = scenario.name

                dfs.append(df)

        if not dfs:
            # Return empty DataFrame with correct structure
            empty_df = pd.DataFrame(
                columns=[
                    "date",
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
                    "scenario_id",
                    "scenario_name",
                ]
            )
            return empty_df

        # Concatenate all scenario data
        result = pd.concat(dfs, axis=0, ignore_index=True)

        # Ensure required columns exist (fill with zeros if missing)
        required_columns = [
            "cash",
            "liquid_assets",
            "illiquid_assets",
            "liabilities",
            "inflows",
            "outflows",
            "taxes",
            "fees",
        ]
        for col in required_columns:
            if col not in result.columns:
                result[col] = 0.0

        # Compute derived columns
        result["total_assets"] = (
            result["cash"] + result["liquid_assets"] + result["illiquid_assets"]
        )
        result["net_worth"] = result["total_assets"] - result["liabilities"]

        return result

    def breakeven_table(self, baseline_id: str) -> pd.DataFrame:
        """
        Calculate breakeven months for all scenarios against a baseline.

        Args:
            baseline_id: ID of the baseline scenario

        Returns:
            DataFrame with columns: scenario_id, scenario_name, breakeven_month
            breakeven_month is None if scenario never breaks even with baseline

        Raises:
            ValueError: If baseline_id is not found
        """
        baseline = self._get_scenario(baseline_id)
        baseline_df = baseline.to_canonical_frame()

        results = []
        for scenario in self.scenarios:
            if scenario.id == baseline_id:
                continue  # Skip baseline itself

            scenario_df = scenario.to_canonical_frame()

            # Find first month where scenario net worth >= baseline net worth
            breakeven_month = self._find_breakeven_month(scenario_df, baseline_df)

            results.append(
                {
                    "scenario_id": scenario.id,
                    "scenario_name": scenario.name,
                    "breakeven_month": breakeven_month,
                }
            )

        return pd.DataFrame(results)

    def fees_taxes_summary(
        self,
        horizons: list[int] | None = None,
        scenario_ids: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Calculate cumulative fees and taxes at specified horizons.

        Args:
            horizons: List of month horizons to evaluate (default: [12, 60, 120, 360])
            scenario_ids: List of scenario IDs to include. If None, includes all scenarios.

        Returns:
            DataFrame with columns: scenario_id, scenario_name, horizon_months,
            cumulative_fees, cumulative_taxes
        """
        if horizons is None:
            horizons = [12, 60, 120, 360]
        if scenario_ids is None:
            scenario_ids = [s.id for s in self.scenarios]

        results = []
        for scenario in self.scenarios:
            if scenario.id not in scenario_ids:
                continue

            df = scenario.to_canonical_frame()

            for horizon in horizons:
                if horizon > len(df):
                    continue  # Skip if horizon exceeds scenario length

                # Calculate cumulative fees and taxes up to horizon
                horizon_data = df.iloc[:horizon]
                cumulative_fees = horizon_data["fees"].sum()
                cumulative_taxes = horizon_data["taxes"].sum()

                results.append(
                    {
                        "scenario_id": scenario.id,
                        "scenario_name": scenario.name,
                        "horizon_months": horizon,
                        "cumulative_fees": cumulative_fees,
                        "cumulative_taxes": cumulative_taxes,
                    }
                )

        return pd.DataFrame(results)

    def liquidity_runway(
        self,
        lookback_months: int = 6,
        essential_share: float = 0.6,
        scenario_ids: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Calculate liquidity runway (months of buffer) for each scenario.

        Args:
            lookback_months: Number of months to look back for calculating average outflows
            essential_share: Fraction of outflows considered essential (default: 0.6)
            scenario_ids: List of scenario IDs to include. If None, includes all scenarios.

        Returns:
            DataFrame with columns: scenario_id, scenario_name, date, cash,
            essential_outflows, liquidity_runway_months
        """
        if scenario_ids is None:
            scenario_ids = [s.id for s in self.scenarios]

        results = []
        for scenario in self.scenarios:
            if scenario.id not in scenario_ids:
                continue

            df = scenario.to_canonical_frame().copy()

            # Calculate essential outflows
            df["essential_outflows"] = df["outflows"] * essential_share

            # Calculate rolling average of essential outflows
            df["avg_essential_outflows"] = (
                df["essential_outflows"]
                .rolling(window=lookback_months, min_periods=1)
                .mean()
            )

            # Calculate liquidity runway (avoid division by zero)
            df["liquidity_runway_months"] = np.where(
                df["avg_essential_outflows"] > 0,
                df["cash"] / df["avg_essential_outflows"],
                np.inf,  # Infinite runway if no essential outflows
            )

            # Add scenario metadata
            df["scenario_id"] = scenario.id
            df["scenario_name"] = scenario.name

            # Select relevant columns
            result_cols = [
                "scenario_id",
                "scenario_name",
                "date",
                "cash",
                "essential_outflows",
                "liquidity_runway_months",
            ]
            results.append(df[result_cols])

        if not results:
            return pd.DataFrame(
                columns=[
                    "scenario_id",
                    "scenario_name",
                    "date",
                    "cash",
                    "essential_outflows",
                    "liquidity_runway_months",
                ]
            )

        return pd.concat(results, axis=0, ignore_index=True)

    def _get_scenario(self, scenario_id: str) -> Scenario:
        """Get scenario by ID."""
        for scenario in self.scenarios:
            if scenario.id == scenario_id:
                return scenario
        raise ValueError(f"Scenario not found: {scenario_id}")

    def _find_breakeven_month(
        self, scenario_df: pd.DataFrame, baseline_df: pd.DataFrame
    ) -> int | None:
        """
        Find the first month where scenario net worth >= baseline net worth.

        Returns:
            Month number (1-indexed) or None if no breakeven
        """
        # Ensure both DataFrames have the same length
        min_length = min(len(scenario_df), len(baseline_df))
        scenario_net_worth = scenario_df["net_worth"].iloc[:min_length]
        baseline_net_worth = baseline_df["net_worth"].iloc[:min_length]

        # Find first month where scenario advantage >= 0
        advantage = scenario_net_worth - baseline_net_worth
        breakeven_mask = advantage >= 0

        if not breakeven_mask.any():
            return None

        # Return 1-indexed month number (use position, not label)
        pos = int(np.argmax(breakeven_mask.to_numpy()))
        return pos + 1

    # ---------- Builder API ----------

    def new_ABrick(
        self,
        id: str,
        name: str,
        kind: str,
        spec: dict,
        links: dict | RouteLink | None = None,
        **kwargs,
    ) -> ABrick:
        """
        Create and register a new asset brick.

        Args:
            id: Unique identifier for the brick
            name: Human-readable name for the brick
            kind: Brick kind (e.g., 'a.cash', 'a.security.unitized')
            spec: Brick specification dictionary
            links: Brick links (dict or RouteLink object)
            **kwargs: Additional brick attributes

        Returns:
            The created ABrick object

        Raises:
            ValueError: If ID already exists in catalog
        """
        self._assert_unique_id(id)
        _links = self._normalize_links(links)
        brick = ABrick(
            id=id, name=name, kind=kind, spec=spec, links=_links or {}, **kwargs
        )
        self._bricks[id] = brick
        return brick

    def new_LBrick(
        self,
        id: str,
        name: str,
        kind: str,
        spec: dict,
        links: dict | RouteLink | None = None,
        **kwargs,
    ) -> LBrick:
        """
        Create and register a new liability brick.

        Args:
            id: Unique identifier for the brick
            name: Human-readable name for the brick
            kind: Brick kind (e.g., 'l.loan.annuity')
            spec: Brick specification dictionary
            links: Brick links (dict or RouteLink object)
            **kwargs: Additional brick attributes

        Returns:
            The created LBrick object

        Raises:
            ValueError: If ID already exists in catalog
        """
        self._assert_unique_id(id)
        _links = self._normalize_links(links)
        brick = LBrick(
            id=id, name=name, kind=kind, spec=spec, links=_links or {}, **kwargs
        )
        self._bricks[id] = brick
        return brick

    def new_FBrick(
        self,
        id: str,
        name: str,
        kind: str,
        spec: dict,
        links: dict | RouteLink | None = None,
        **kwargs,
    ) -> FBrick:
        """
        Create and register a new flow brick.

        Args:
            id: Unique identifier for the brick
            name: Human-readable name for the brick
            kind: Brick kind (e.g., 'f.income.recurring', 'f.expense.recurring')
            spec: Brick specification dictionary
            links: Brick links (dict or RouteLink object)
            **kwargs: Additional brick attributes

        Returns:
            The created FBrick object

        Raises:
            ValueError: If ID already exists in catalog
        """
        self._assert_unique_id(id)
        _links = self._normalize_links(links)
        brick = FBrick(
            id=id, name=name, kind=kind, spec=spec, links=_links or {}, **kwargs
        )
        self._bricks[id] = brick
        return brick

    def new_TBrick(
        self,
        id: str,
        name: str,
        kind: str,
        spec: dict[str, Any] | None = None,
        links: dict[str, Any] | None = None,
        start_date: date | None = None,
    ) -> TBrick:
        """
        Create and register a new TBrick (Transfer Brick).

        Args:
            id: Unique identifier for the brick
            name: Human-readable name for the brick
            kind: Transfer strategy kind (e.g., 't.transfer.lumpsum')
            spec: Strategy-specific parameters
            links: Links to other bricks (must include 'from' and 'to' accounts)
            start_date: Optional start date for the transfer

        Returns:
            The created TBrick object

        Raises:
            ValueError: If ID already exists or required links are missing
        """
        self._assert_unique_id(id)

        # Validate required links for transfers
        if not links:
            raise ValueError(
                "Transfer bricks require 'links' with 'from' and 'to' accounts"
            )
        if "from" not in links:
            raise ValueError("Transfer bricks must specify 'from' account")
        if "to" not in links:
            raise ValueError("Transfer bricks must specify 'to' account")

        brick = TBrick(
            id=id,
            name=name,
            kind=kind,
            spec=spec or {},
            links=links,
            start_date=start_date,
        )
        self._bricks[id] = brick
        return brick

    def new_MacroBrick(
        self, id: str, name: str, member_ids: list[str], tags: list[str] | None = None
    ) -> MacroBrick:
        """
        Create and register a new MacroBrick.

        Args:
            id: Unique identifier for the MacroBrick
            name: Human-readable name for the MacroBrick
            member_ids: List of brick/MacroBrick IDs to include
            tags: Optional list of tags for categorization

        Returns:
            The created MacroBrick object

        Raises:
            ValueError: If ID already exists or member IDs not found
        """
        self._assert_unique_id(id)
        # Validate membership against current catalog
        for member_id in member_ids:
            if member_id not in self._bricks and member_id not in self._macrobricks:
                raise ValueError(f"Member ID '{member_id}' not found")

        macrobrick = MacroBrick(id=id, name=name, members=member_ids, tags=tags or [])
        self._macrobricks[id] = macrobrick
        return macrobrick

    def create_scenario(
        self,
        id: str,
        name: str,
        brick_ids: list[str],
        currency: str | None = None,
        settlement_default_cash_id: str | None = None,
        validate: bool = True,
        **config_kwargs,
    ) -> Scenario:
        """
        Create a scenario using unified brick references.

        This method creates a new scenario by selecting bricks and/or MacroBricks
        from the entity's catalog. MacroBricks are automatically expanded to their
        constituent bricks with cycle detection and order preservation.

        Args:
            id: Unique identifier for the scenario
            name: Human-readable name for the scenario
            brick_ids: List of brick IDs and/or MacroBrick IDs to include
            currency: Currency for the scenario (defaults to entity's base_currency)
            settlement_default_cash_id: Default cash account ID for routing
            validate: Whether to validate the scenario structure
            **config_kwargs: Additional scenario configuration

        Returns:
            The created Scenario object

        Raises:
            ValueError: If scenario ID already exists
            ScenarioValidationError: If validation fails or cycles detected

        Note:
            Ensure strategies are registered (e.g., import finbricklab.strategies)
            before calling this method.
        """
        if id in self._scenarios:
            raise ValueError(f"Scenario ID '{id}' already exists")

        # Build a full registry of all catalog items for validation/expansion
        reg_full = Registry(self._bricks, self._macrobricks)

        def expand(ids: list[str]) -> tuple[list[str], set[str]]:
            """Expand MacroBricks recursively with cycle detection and deduplication."""
            out: list[str] = []
            seen = set()
            all_macrobricks = set()

            def push(brick_id: str):
                if brick_id not in seen:
                    out.append(brick_id)
                    seen.add(brick_id)

            def dfs(item_id: str, stack: set[str], path: list[str]):
                if reg_full.is_macrobrick(item_id):
                    all_macrobricks.add(item_id)
                    if item_id in stack:
                        cycle_path = " → ".join(path + [item_id])
                        raise ScenarioValidationError(
                            id, f"Cycle in MacroBricks: {cycle_path}", problem_ids=[item_id]
                        )
                    stack.add(item_id)
                    path.append(item_id)
                    
                    # Cap recursion depth
                    if len(path) > 64:
                        raise ScenarioValidationError(
                            id, f"MacroBrick nesting too deep: {len(path)} levels", problem_ids=[item_id]
                        )
                    
                    # Get the MacroBrick and traverse its members directly
                    macro = reg_full.get_macrobrick(item_id)
                    for member_id in macro.members:
                        dfs(member_id, stack, path)
                    
                    stack.remove(item_id)
                    path.pop()
                elif reg_full.is_brick(item_id):
                    push(item_id)
                else:
                    raise ScenarioValidationError(
                        id, f"Unknown id '{item_id}'", problem_ids=[item_id]
                    )

            for item_id in ids or []:
                dfs(item_id, set(), [])
            return out, all_macrobricks

        included_ids, all_macrobricks = expand(brick_ids)

        # Build a **scenario-local** registry of only the included bricks + all macrobricks (for rollups)
        scen_bricks = [clone_brick(self._bricks[bid]) for bid in included_ids]
        
        # Include all referenced MacroBricks for rollup analysis
        scen_mbs = [deepcopy(self._macrobricks[mid]) for mid in sorted(all_macrobricks)]

        scenario = Scenario(
            id=id,
            name=name,
            bricks=scen_bricks,
            macrobricks=scen_mbs,
            currency=currency or self.base_currency,
            settlement_default_cash_id=settlement_default_cash_id,
            **config_kwargs,
        )

        if validate:
            report = scenario._build_registry().validate()
            if not getattr(report, "is_valid", lambda: True)():
                # Collect top offending ids if the report exposes them; else fallback to selection
                problem_ids = (
                    getattr(report, "problem_ids", None) or sorted(included_ids)[:10]
                )
                raise ScenarioValidationError(
                    id, "Validation failed", report=report, problem_ids=problem_ids
                )

        self._scenarios[id] = scenario
        return scenario

    # ---------- Catalog helpers ----------

    def get_brick(self, id: str) -> FinBrickABC | None:
        """Get brick by ID."""
        return self._bricks.get(id)

    def get_macrobrick(self, id: str) -> MacroBrick | None:
        """Get MacroBrick by ID."""
        return self._macrobricks.get(id)

    def get_scenario(self, id: str) -> Scenario | None:
        """Get scenario by ID."""
        return self._scenarios.get(id)

    def list_bricks(self) -> list[str]:
        """List all brick IDs."""
        return sorted(self._bricks.keys())

    def list_macrobricks(self) -> list[str]:
        """List all MacroBrick IDs."""
        return sorted(self._macrobricks.keys())

    def list_scenarios(self) -> list[str]:
        """List all scenario IDs."""
        return sorted(self._scenarios.keys())

    # ---------- Internals ----------

    def _assert_unique_id(self, id_: str) -> None:
        """Assert that an ID is unique across the catalog."""
        if id_ in self._bricks or id_ in self._macrobricks:
            raise ValueError(f"ID '{id_}' already exists in catalog")

    def run_scenario(
        self,
        scenario_id: str,
        *,
        start: date,
        months: int,
        selection: list[str] | None = None,
        include_cash: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Run a scenario by ID via the Entity catalog.

        Parameters
        ----------
        scenario_id : str
            The ID of the scenario previously created in this Entity.
        start : date
            Simulation start date.
        months : int
            Number of months to simulate.
        selection : list[str] | None
            Optional subset selection of brick and/or MacroBrick IDs. If None,
            the scenario's full selection is used.
        include_cash : bool
            Whether to include cash bricks in the simulation.
        **kwargs : Any
            Forwarded to Scenario.run(...). Keep stable signature upstream.

        Returns
        -------
        dict[str, Any]
            Whatever Scenario.run(...) returns (results dict / RunResult).

        Raises
        ------
        ValueError
            If the scenario ID is not found in this Entity.
        ScenarioValidationError
            If Scenario-level validation fails (propagated).
        """
        scen = self.get_scenario(scenario_id)
        if scen is None:
            available = ", ".join(self.list_scenarios()[:10])
            more = "..." if len(self.list_scenarios()) > 10 else ""
            raise ValueError(
                f"Scenario '{scenario_id}' not found in Entity '{self.id}'. "
                f"Available: [{available}{more}]"
            )

        return scen.run(
            start=start,
            months=months,
            selection=selection,
            include_cash=include_cash,
            **kwargs,
        )

    def run_many(
        self,
        scenario_ids: Iterable[str],
        *,
        start: date,
        months: int,
        selection: list[str] | None = None,
        include_cash: bool = True,
        **kwargs: Any,
    ) -> dict[str, dict[str, Any]]:
        """
        Run multiple scenarios and return a mapping {scenario_id: results}.

        Raises on first missing scenario_id; consider try/except in caller if you want partial results.

        Parameters
        ----------
        scenario_ids : Iterable[str]
            The IDs of scenarios to run.
        start : date
            Simulation start date.
        months : int
            Number of months to simulate.
        selection : list[str] | None
            Optional subset selection of brick and/or MacroBrick IDs. If None,
            the scenario's full selection is used.
        include_cash : bool
            Whether to include cash bricks in the simulation.
        **kwargs : Any
            Forwarded to Scenario.run(...).

        Returns
        -------
        dict[str, dict[str, Any]]
            Mapping of scenario_id to results dict.

        Raises
        ------
        ValueError
            If any scenario ID is not found in this Entity.
        ScenarioValidationError
            If Scenario-level validation fails (propagated).
        """
        out: dict[str, dict[str, Any]] = {}
        for sid in scenario_ids:
            out[sid] = self.run_scenario(
                sid,
                start=start,
                months=months,
                selection=selection,
                include_cash=include_cash,
                **kwargs,
            )
        return out

    @staticmethod
    def _normalize_links(links: dict | RouteLink | None) -> dict[str, Any] | None:
        """
        Normalize links to dict format for uniform storage.

        Args:
            links: Links in various formats (dict, RouteLink, or None)

        Returns:
            Normalized links dict or None

        Raises:
            TypeError: If links type is unsupported
        """
        if links is None:
            return None
        if isinstance(links, RouteLink):
            return {"route": {"to": links.to, "from": getattr(links, "from_", None)}}
        if isinstance(links, dict):
            return deepcopy(links)  # defensive
        raise TypeError(f"Unsupported links type: {type(links).__name__}")
