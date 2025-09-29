"""
Entity class for grouping and comparing multiple scenarios.

This module provides the Entity class which serves as the top-level aggregator
for multiple financial scenarios, enabling benchmarking and comparison across
different financial strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .scenario import Scenario


@dataclass
class Entity:
    """
    Top-level aggregator for multiple financial scenarios.

    An Entity represents a single financial entity (person, family, portfolio)
    that can have multiple scenarios for comparison and benchmarking.

    Attributes:
        id: Unique identifier for the entity
        name: Human-readable name for the entity
        base_currency: Base currency for all scenarios (default: 'EUR')
        assumptions: Dictionary of assumptions (inflation, tax profile, fees, etc.)
        scenarios: List of scenarios belonging to this entity
        benchmarks: Dictionary mapping benchmark names to scenario IDs
    """

    id: str
    name: str
    base_currency: str = "EUR"
    assumptions: dict[str, Any] = field(default_factory=dict)
    scenarios: list[Scenario] = field(default_factory=list)
    benchmarks: dict[str, str] = field(default_factory=dict)

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

        # Return 1-indexed month number
        return int(breakeven_mask.idxmax()) + 1
