"""
Results and output structures for FinBrickLab.
"""

from __future__ import annotations

from typing import TypedDict

import numpy as np
import pandas as pd

from .events import Event


class BrickOutput(TypedDict):
    """
    Standard output structure for all financial brick simulations.

    This TypedDict defines the common interface that all brick strategies must return.
    It provides a consistent structure for cash flows, asset values, debt balances,
    and event tracking across all types of financial instruments.

    Attributes:
        cash_in: Monthly cash inflows (always >= 0)
        cash_out: Monthly cash outflows (always >= 0)
        asset_value: Monthly asset valuation (0 for non-assets)
        debt_balance: Monthly debt balance (0 for non-liabilities)
        events: List of time-stamped events describing key occurrences

    Note:
        All numpy arrays have the same length corresponding to the simulation period.
        Cash flows are always positive values - the direction is implicit in the field name.
        Events are time-stamped and can be used to build a simulation ledger.
    """

    cash_in: np.ndarray  # Monthly cash inflows (>=0)
    cash_out: np.ndarray  # Monthly cash outflows (>=0)
    asset_value: np.ndarray  # Monthly asset value (0 if not an asset)
    debt_balance: np.ndarray  # Monthly debt balance (0 if not a liability)
    events: list[Event]  # Time-stamped events describing key occurrences


class ScenarioResults:
    """
    Helper class for convenient access to different time aggregations of scenario results.

    Provides ergonomic methods to access quarterly and yearly views of the monthly data.
    """

    def __init__(self, totals: pd.DataFrame):
        """
        Initialize with monthly totals DataFrame (PeriodIndex).

        Args:
            totals: Monthly totals DataFrame with PeriodIndex
        """
        self._monthly_data = totals  # PeriodIndex 'M'

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

    # Calculate non_cash assets
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
