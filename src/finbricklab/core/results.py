"""
Results and output structures for FinBrickLab.
"""

from __future__ import annotations

from typing import TypedDict

import numpy as np
import pandas as pd

from .events import Event
from .registry import Registry


class BrickOutput(TypedDict):
    """
    Standard output structure for all financial brick simulations.

    This TypedDict defines the common interface that all brick strategies must return.
    It provides a consistent structure for cash flows, asset values, debt balances,
    and event tracking across all types of financial instruments.

    Attributes:
        cash_in: Monthly cash inflows (always >= 0)
        cash_out: Monthly cash outflows (always >= 0)
        assets: Monthly asset valuation (0 for non-assets)
        liabilities: Monthly debt balance (0 for non-liabilities)
        events: List of time-stamped events describing key occurrences

    Note:
        All numpy arrays have the same length corresponding to the simulation period.
        Cash flows are always positive values - the direction is implicit in the field name.
        Events are time-stamped and can be used to build a simulation ledger.
    """

    cash_in: np.ndarray  # Monthly cash inflows (>=0)
    cash_out: np.ndarray  # Monthly cash outflows (>=0)
    assets: np.ndarray  # Monthly asset value (0 if not an asset)
    liabilities: np.ndarray  # Monthly debt balance (0 if not a liability)
    events: list[Event]  # Time-stamped events describing key occurrences


class ScenarioResults:
    """
    Helper class for convenient access to different time aggregations of scenario results.

    Provides ergonomic methods to access quarterly and yearly views of the monthly data.
    """

    def __init__(
        self,
        totals: pd.DataFrame,
        registry: Registry | None = None,
        outputs: dict[str, BrickOutput] | None = None,
    ):
        """
        Initialize with monthly totals DataFrame (PeriodIndex).

        Args:
            totals: Monthly totals DataFrame with PeriodIndex
            registry: Optional registry for MacroBrick expansion
            outputs: Optional outputs dict for filtered views
        """
        self._monthly_data = totals  # PeriodIndex 'M'
        self._registry = registry
        self._outputs = outputs

    def to_freq(self, freq: str = "Q") -> pd.DataFrame:
        """
        Aggregate to specified frequency.

        Args:
            freq: Frequency string ('Q', 'Y', 'Q-DEC', etc.)

        Returns:
            Aggregated DataFrame with PeriodIndex
        """
        return aggregate_totals(self._monthly_data, freq=freq, return_period_index=True)

    def monthly(self) -> pd.DataFrame:
        """Return monthly data (no aggregation needed)."""
        return self._monthly_data

    def quarterly(self) -> pd.DataFrame:
        """Return quarterly aggregated data."""
        return self.to_freq("Q")

    def yearly(self) -> pd.DataFrame:
        """Return yearly aggregated data."""
        return self.to_freq("Y")

    def filter(
        self,
        brick_ids: list[str] | None = None,
        include_cash: bool = True,
    ) -> ScenarioResults:
        """
        Filter results to show only selected bricks and/or MacroBricks.

        Args:
            brick_ids: List of brick IDs and/or MacroBrick IDs to include (None = no filtering)
            include_cash: Whether to include cash in the aggregation

        Returns:
            New ScenarioResults with filtered aggregated data

        Raises:
            RuntimeError: If registry or outputs are not available
        """
        # Validation
        if not self._registry or not self._outputs:
            raise RuntimeError("Cannot filter: missing registry or outputs")

        # Resolve selection to brick IDs (expand MacroBricks automatically)
        selected_bricks = set()
        if brick_ids:
            for item_id in brick_ids:
                if self._registry.is_macrobrick(item_id):
                    # Expand MacroBrick to its constituent bricks
                    members = self._registry.get_struct_flat_members(item_id)
                    selected_bricks.update(members)
                elif self._registry.is_brick(item_id):
                    # Direct brick selection
                    selected_bricks.add(item_id)
                else:
                    # Unknown ID - skip with warning
                    import warnings
                    warnings.warn(f"Unknown ID '{item_id}' in filter selection, skipping")

        # Identify cash bricks (for cash column calculation)
        cash_bricks = set()
        for bid in selected_bricks:
            if self._registry.is_brick(bid):
                brick = self._registry.get_brick(bid)
                if hasattr(brick, "kind") and brick.kind == "a.cash":
                    cash_bricks.add(bid)

        # Compute filtered totals
        filtered_df = _compute_filtered_totals(
            self._outputs,
            selected_bricks,
            self._monthly_data.index,
            include_cash,
            cash_bricks,
        )

        # Return new ScenarioResults with filtered data
        return ScenarioResults(filtered_df, self._registry, self._outputs)


def _compute_filtered_totals(
    outputs: dict[str, BrickOutput],
    brick_ids: set[str],
    t_index: pd.PeriodIndex,
    include_cash: bool,
    cash_brick_ids: set[str],
) -> pd.DataFrame:
    """
    Compute aggregated totals for a filtered set of bricks.

    This mirrors the logic in Scenario._aggregate_results() but operates
    on a subset of bricks.

    Args:
        outputs: All brick outputs from simulation
        brick_ids: Set of brick IDs to include in aggregation
        t_index: Time index for the DataFrame
        include_cash: Whether to include cash in aggregation
        cash_brick_ids: Set of brick IDs that are cash accounts

    Returns:
        DataFrame with same structure as scenario totals
    """
    # Filter outputs to only selected bricks
    filtered_outputs = {bid: outputs[bid] for bid in brick_ids if bid in outputs}

    if not filtered_outputs:
        # Return empty DataFrame with correct structure
        empty_df = pd.DataFrame(
            {
                "cash_in": np.zeros(len(t_index)),
                "cash_out": np.zeros(len(t_index)),
                "net_cf": np.zeros(len(t_index)),
                "assets": np.zeros(len(t_index)),
                "liabilities": np.zeros(len(t_index)),
                "non_cash": np.zeros(len(t_index)),
                "equity": np.zeros(len(t_index)),
            },
            index=t_index,
        )
        if include_cash:
            empty_df["cash"] = np.zeros(len(t_index))
        return empty_df

    # Calculate totals for selected bricks only
    cash_in_tot = sum(o["cash_in"] for o in filtered_outputs.values())
    cash_out_tot = sum(o["cash_out"] for o in filtered_outputs.values())
    assets_tot = sum(o["assets"] for o in filtered_outputs.values())
    liabilities_tot = sum(o["liabilities"] for o in filtered_outputs.values())
    net_cf = cash_in_tot - cash_out_tot
    equity = assets_tot - liabilities_tot

    # Calculate non-cash assets (total assets minus cash from selected cash bricks)
    cash_assets = None
    for bid in cash_brick_ids:
        if bid in filtered_outputs:
            s = filtered_outputs[bid]["assets"]
            cash_assets = s if cash_assets is None else (cash_assets + s)
    cash_assets = cash_assets if cash_assets is not None else np.zeros(len(t_index))
    non_cash_assets = assets_tot - cash_assets

    # Create summary DataFrame with monthly totals
    totals = pd.DataFrame(
        {
            "cash_in": cash_in_tot,
            "cash_out": cash_out_tot,
            "net_cf": net_cf,
            "assets": assets_tot,
            "liabilities": liabilities_tot,
            "non_cash": non_cash_assets,
            "equity": equity,
        },
        index=t_index,
    )

    # Add cash column if requested
    if include_cash:
        totals["cash"] = cash_assets

    # Finalize totals with proper identities and assertions
    return finalize_totals(totals)


def aggregate_totals(
    df: pd.DataFrame, freq: str = "Q", return_period_index: bool = True
) -> pd.DataFrame:
    """
    Aggregate scenario totals by frequency with proper financial semantics.

    Stocks (assets, liabilities, equity, cash, non_cash) are aggregated using 'last'
    (period-end values). Flows (cash_in, cash_out, net_cf) are aggregated using 'sum'
    (total over the period).

    Args:
        df: Monthly totals DataFrame
        freq: Frequency string ('M', 'Q', 'Y', 'Q-DEC', 'Q-MAR', etc.)
        return_period_index: If True, return PeriodIndex; if False, return Timestamp index

    Returns:
        Aggregated DataFrame

    Example:
        >>> monthly = scenario.run(start=date(2026, 1, 1), months=36)["totals"]
        >>> quarterly = aggregate_totals(monthly, "Q")
        >>> yearly = aggregate_totals(monthly, "Y")
    """
    if not isinstance(df.index, pd.PeriodIndex):
        df = df.copy()
        df.index = df.index.to_period("M")

    # Handle monthly frequency (no aggregation needed)
    if freq.upper() in ["M", "MONTHLY"]:
        return df

    # Define aggregation rules based on financial semantics
    flows = ["cash_in", "cash_out", "net_cf"]
    stocks = ["assets", "liabilities", "equity", "cash", "non_cash"]

    # Only aggregate columns that exist
    flows = [c for c in flows if c in df.columns]
    stocks = [c for c in stocks if c in df.columns]

    agg = {**{c: "sum" for c in flows}, **{c: "last" for c in stocks}}
    out = df.groupby(df.index.asfreq(freq)).agg(agg)

    if return_period_index:
        return out
    return out.to_timestamp(how="end")  # Convert to period-end timestamps


def finalize_totals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Finalize totals DataFrame with proper column names, non_cash calculation, and identity assertions.

    Args:
        df: Raw totals DataFrame

    Returns:
        Finalized DataFrame with proper financial identities

    Raises:
        AssertionError: If financial identities are violated
    """
    df = df.copy()

    # Rename debt to liabilities if present
    if "debt" in df.columns:
        df = df.rename(columns={"debt": "liabilities"})

    # Calculate non_cash assets (only if both columns exist)
    if "assets" in df.columns and "cash" in df.columns:
        df["non_cash"] = df["assets"] - df["cash"]

    # Assert financial identities with small tolerance for floating point errors
    eps = 1e-6
    if (
        "equity" in df.columns
        and "assets" in df.columns
        and "liabilities" in df.columns
    ):
        equity_identity = (
            (df["equity"] - (df["assets"] - df["liabilities"])).abs().max()
        )
        assert (
            equity_identity < eps
        ), f"Equity identity violated: max error = {equity_identity}"

    if "assets" in df.columns and "cash" in df.columns and "non_cash" in df.columns:
        assets_identity = (df["assets"] - (df["cash"] + df["non_cash"])).abs().max()
        assert (
            assets_identity < eps
        ), f"Assets identity violated: max error = {assets_identity}"

    return df


# JSON encoder for numpy types
class NumpyEncoder:
    """Custom JSON encoder that handles numpy types."""

    @staticmethod
    def encode(obj):
        """Convert numpy types to native Python types for JSON serialization."""
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.datetime64):
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
