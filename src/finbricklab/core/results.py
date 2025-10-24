"""
Results and output structures for FinBrickLab.
"""

from __future__ import annotations

from typing import TypedDict

import numpy as np
import pandas as pd

from .events import Event
from .registry import Registry
from .transfer_visibility import TransferVisibility


class BrickOutput(TypedDict):
    """
    Standard output structure for all financial brick simulations.

    This TypedDict defines the common interface that all brick strategies must return.
    It provides a consistent structure for cash flows, asset values, debt balances,
    interest tracking, and event tracking across all types of financial instruments.

    Attributes:
        cash_in: Monthly cash inflows (always >= 0)
        cash_out: Monthly cash outflows (always >= 0)
        assets: Monthly asset valuation (0 for non-assets)
        liabilities: Monthly debt balance (0 for non-liabilities)
        interest: Monthly interest income (+) / expense (-) (0 if not applicable)
        events: List of time-stamped events describing key occurrences

    Note:
        All numpy arrays have the same length corresponding to the simulation period.
        Cash flows are always positive values - the direction is implicit in the field name.
        Interest is signed: positive for income (cash accounts, securities), negative for expense (loans, credit).
        Events are time-stamped and can be used to build a simulation ledger.
    """

    cash_in: np.ndarray  # Monthly cash inflows (>=0)
    cash_out: np.ndarray  # Monthly cash outflows (>=0)
    assets: np.ndarray  # Monthly asset value (0 if not an asset)
    liabilities: np.ndarray  # Monthly debt balance (0 if not a liability)
    interest: np.ndarray  # Monthly interest income (+) / expense (-) (0 if not applicable)
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
        journal=None,
    ):
        """
        Initialize with monthly totals DataFrame (PeriodIndex).

        Args:
            totals: Monthly totals DataFrame with PeriodIndex
            registry: Optional registry for MacroBrick expansion
            outputs: Optional outputs dict for filtered views
            journal: Optional journal object for transaction analysis
        """
        self._monthly_data = totals  # PeriodIndex 'M'
        self._registry = registry
        self._outputs = outputs
        self._journal = journal

    def to_freq(self, freq: str = "Q") -> pd.DataFrame:
        """
        Aggregate to specified frequency.

        Args:
            freq: Frequency string ('Q', 'Y', 'Q-DEC', etc.)

        Returns:
            Aggregated DataFrame with PeriodIndex
        """
        return aggregate_totals(self._monthly_data, freq=freq, return_period_index=True)

    def monthly(
        self,
        transfer_visibility: TransferVisibility | None = None,
        include_transparent: bool | None = None,
    ) -> pd.DataFrame:
        """
        Return monthly data with optional transfer visibility filtering.

        Args:
            transfer_visibility: How to handle transfer visibility (default: OFF)
            include_transparent: Backward compatibility flag (deprecated)

        Returns:
            Monthly data DataFrame with optional transfer filtering applied
        """
        # Handle backward compatibility
        if include_transparent is not None:
            import warnings

            warnings.warn(
                "include_transparent parameter is deprecated. Use transfer_visibility instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            # Map old parameter to new enum
            if include_transparent:
                transfer_visibility = TransferVisibility.ALL
            else:
                transfer_visibility = TransferVisibility.OFF

        # Default to OFF if not specified
        if transfer_visibility is None:
            transfer_visibility = TransferVisibility.OFF

        # If no filtering needed, return data as-is
        if transfer_visibility == TransferVisibility.ALL:
            return self._monthly_data

        # Apply transfer visibility filtering
        return self._apply_transfer_visibility_filter(transfer_visibility)

    def _apply_transfer_visibility_filter(
        self, visibility: TransferVisibility
    ) -> pd.DataFrame:
        """
        Apply transfer visibility filtering to monthly data.

        Args:
            visibility: The transfer visibility setting to apply

        Returns:
            Filtered monthly data DataFrame
        """
        # For now, return the data as-is since we need to implement journal-based filtering
        # This is a placeholder that will be implemented when we have access to the journal
        if visibility == TransferVisibility.OFF:
            # TODO: Implement journal-based filtering to hide internal transfers
            # For now, return data as-is
            return self._monthly_data
        elif visibility == TransferVisibility.ONLY:
            # TODO: Implement filtering to show only transfers
            # For now, return data as-is
            return self._monthly_data
        elif visibility == TransferVisibility.BOUNDARY_ONLY:
            # TODO: Implement filtering to show only boundary-crossing transfers
            # For now, return data as-is
            return self._monthly_data
        else:
            return self._monthly_data

    def quarterly(self) -> pd.DataFrame:
        """Return quarterly aggregated data."""
        return self.to_freq("Q")

    def yearly(self) -> pd.DataFrame:
        """Return yearly aggregated data."""
        return self.to_freq("Y")

    def monthly_detailed(self) -> pd.DataFrame:
        """Return monthly data with all transfers visible (alias for monthly(transfer_visibility=ALL))."""
        return self.monthly(transfer_visibility=TransferVisibility.ALL)

    def monthly_transfers(self) -> pd.DataFrame:
        """Return monthly data showing only transfers (alias for monthly(transfer_visibility=ONLY))."""
        return self.monthly(transfer_visibility=TransferVisibility.ONLY)

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
        selected_bricks: set[str] = set()
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

                    warnings.warn(
                        f"Unknown ID '{item_id}' in filter selection, skipping",
                        stacklevel=2,
                    )

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
        return ScenarioResults(
            filtered_df, self._registry, self._outputs, self._journal
        )

    def journal(
        self,
        # Category filters (exact matches)
        brick_id: str | list[str] | None = None,
        brick_type: str | list[str] | None = None,
        transaction_type: str | list[str] | None = None,
        account_id: str | list[str] | None = None,
        posting_side: str | list[str] | None = None,
        # Range filters
        iteration_min: int | None = None,
        iteration_max: int | None = None,
        timestamp_start: str | None = None,
        timestamp_end: str | None = None,
        amount_min: float | None = None,
        amount_max: float | None = None,
        # Advanced filters
        metadata_filter: dict | None = None,
        account_type: str | None = None,
        # Output options
        sort_by: str = "timestamp",
        ascending: bool = True,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Convert journal entries to a DataFrame for analysis with comprehensive filtering.

        Args:
            brick_id: Filter by brick IDs (supports MacroBricks - automatically expands)
            brick_type: Filter by brick types (flow, transfer, liability, asset)
            transaction_type: Filter by transaction types (income, expense, transfer, payment, disbursement, opening)
            account_id: Filter by account IDs (asset:checking, income:salary, etc.)
            posting_side: Filter by posting side (credit, debit)

            iteration_min: Minimum iteration number
            iteration_max: Maximum iteration number
            timestamp_start: Start date for filtering (string or datetime)
            timestamp_end: End date for filtering (string or datetime)
            amount_min: Minimum transaction amount
            amount_max: Maximum transaction amount

            metadata_filter: Filter by metadata keys/values (e.g., {'interest_amount': {'>': 100}})
            account_type: Filter by account type (asset, income, expense, liability, equity)

            sort_by: Column to sort by (default: 'timestamp')
            ascending: Sort order (default: True)
            limit: Maximum number of results to return

        Returns:
            DataFrame with canonical journal structure:
            - record_id: Clean, self-documenting unique ID (e.g., "income:salary:0", "opening:checking:0")
            - brick_id: Primary column for filtering by brick
            - brick_type: Type of financial instrument (flow, transfer, liability, asset)
            - transaction_type: Transaction type (income, expense, transfer, payment, disbursement, opening)
            - iteration: Iteration number (0, 1, 2, etc.) for recurring transactions
            - account_id: Where money flows (standardized format: Asset:brick_id, Income:brick_id, etc.)
            - posting_side: Credit or debit side of the transaction
            - timestamp: Transaction timestamp
            - amount: Transaction amount
            - currency: Transaction currency
            - metadata: Combined rich transaction information (entry + posting metadata)

        Raises:
            ValueError: If journal object is not available
        """
        if self._journal is None:
            raise ValueError(
                "Journal object not available. Journal is only available for scenarios with journal-based routing."
            )

        import pandas as pd

        # Convert journal entries to DataFrame with canonical structure
        entries_data = []
        for entry in self._journal.entries:
            for posting in entry.postings:
                entries_data.append(
                    {
                        "record_id": entry.id,  # Canonical record ID
                        "brick_id": entry.metadata.get("brick_id"),  # Primary column
                        "brick_type": entry.metadata.get(
                            "brick_type"
                        ),  # Primary column
                        "transaction_type": entry.metadata.get(
                            "transaction_type"
                        ),  # Transaction type (income, expense, transfer, etc.)
                        "iteration": entry.metadata.get(
                            "iteration"
                        ),  # Iteration number (0, 1, 2, etc.)
                        "account_id": posting.account_id,  # Where money flows (standardized format)
                        "posting_side": posting.metadata.get(
                            "posting_side"
                        ),  # credit/debit
                        "timestamp": entry.timestamp,
                        "amount": float(posting.amount.value),
                        "currency": posting.amount.currency.code,
                        "metadata": {**entry.metadata, **posting.metadata},
                    }
                )

        df = pd.DataFrame(entries_data)
        if df.empty:
            return df

        # Keep timestamps as np.datetime64 for consistency with the rest of the codebase
        # No conversion needed - timestamps are already in the correct format

        # Apply filters
        df = self._apply_journal_filters(
            df,
            brick_id,
            brick_type,
            transaction_type,
            account_id,
            posting_side,
            iteration_min,
            iteration_max,
            timestamp_start,
            timestamp_end,
            amount_min,
            amount_max,
            metadata_filter,
            account_type,
        )

        # Sort and limit results
        if not df.empty:
            df = df.sort_values(sort_by, ascending=ascending).reset_index(drop=True)
            if limit is not None:
                df = df.head(limit)

        return df

    def _expand_brick_ids(self, brick_ids: list[str]) -> list[str]:
        """Expand brick IDs, automatically handling MacroBricks."""
        if self._registry is None:
            return brick_ids

        expanded = []
        for brick_id in brick_ids:
            try:
                # Try to get as a regular brick first
                self._registry.get_brick(brick_id)
                expanded.append(brick_id)  # Regular brick
            except Exception:
                try:
                    # Try to get as a MacroBrick
                    macrobrick = self._registry.get_macrobrick(brick_id)
                    # Recursively expand MacroBrick members
                    expanded.extend(self._expand_brick_ids(macrobrick.members))
                except Exception:
                    # Not found in registry, treat as direct brick ID
                    expanded.append(brick_id)
        return list(set(expanded))  # Remove duplicates

    def _apply_journal_filters(
        self,
        df: pd.DataFrame,
        brick_id: str | list[str] | None,
        brick_type: str | list[str] | None,
        transaction_type: str | list[str] | None,
        account_id: str | list[str] | None,
        posting_side: str | list[str] | None,
        iteration_min: int | None,
        iteration_max: int | None,
        timestamp_start: str | None,
        timestamp_end: str | None,
        amount_min: float | None,
        amount_max: float | None,
        metadata_filter: dict | None,
        account_type: str | None,
    ) -> pd.DataFrame:
        """Apply all journal filters to the DataFrame."""
        from datetime import datetime

        import numpy as np

        # Handle brick_id filtering (with MacroBrick expansion)
        if brick_id is not None:
            if isinstance(brick_id, str):
                brick_id = [brick_id]

            # Expand MacroBricks to constituent bricks
            expanded_brick_ids = self._expand_brick_ids(brick_id)
            df = df[df["brick_id"].isin(expanded_brick_ids)]

        # Handle other category filters
        if brick_type is not None:
            if isinstance(brick_type, str):
                brick_type = [brick_type]
            df = df[df["brick_type"].isin(brick_type)]

        if transaction_type is not None:
            if isinstance(transaction_type, str):
                transaction_type = [transaction_type]
            df = df[df["transaction_type"].isin(transaction_type)]

        if account_id is not None:
            if isinstance(account_id, str):
                account_id = [account_id]
            df = df[df["account_id"].isin(account_id)]

        if posting_side is not None:
            if isinstance(posting_side, str):
                posting_side = [posting_side]
            df = df[df["posting_side"].isin(posting_side)]

        # Handle range filters
        if iteration_min is not None:
            df = df[df["iteration"] >= iteration_min]

        if iteration_max is not None:
            df = df[df["iteration"] <= iteration_max]

        if timestamp_start is not None:
            if isinstance(timestamp_start, str):
                timestamp_start = np.datetime64(timestamp_start, "M")
            elif isinstance(timestamp_start, datetime):
                timestamp_start = np.datetime64(timestamp_start, "M")
            df = df[df["timestamp"] >= timestamp_start]

        if timestamp_end is not None:
            if isinstance(timestamp_end, str):
                timestamp_end = np.datetime64(timestamp_end, "M")
            elif isinstance(timestamp_end, datetime):
                timestamp_end = np.datetime64(timestamp_end, "M")
            df = df[df["timestamp"] <= timestamp_end]

        if amount_min is not None:
            df = df[df["amount"] >= amount_min]

        if amount_max is not None:
            df = df[df["amount"] <= amount_max]

        # Handle account_type filter
        if account_type is not None:
            df = df[df["account_id"].str.startswith(f"{account_type}:")]

        # Handle metadata filter
        if metadata_filter is not None:
            for key, value in metadata_filter.items():
                if isinstance(value, dict):
                    # Handle comparison operators
                    for op, val in value.items():

                        def _filter_func(x, k=key, v=val, op_type=op):
                            if op_type == ">":
                                return x.get(k, 0) > v
                            elif op_type == "<":
                                return x.get(k, 0) < v
                            elif op_type == ">=":
                                return x.get(k, 0) >= v
                            elif op_type == "<=":
                                return x.get(k, 0) <= v
                            elif op_type == "==":
                                return x.get(k, 0) == v
                            elif op_type == "!=":
                                return x.get(k, 0) != v
                            return False

                        df = df[df["metadata"].apply(_filter_func)]
                else:
                    # Exact match
                    def _exact_filter_func(x, k=key, v=value):
                        return x.get(k) == v

                    df = df[df["metadata"].apply(_exact_filter_func)]

        return df

    def transactions(self, account_id: str) -> pd.DataFrame:
        """
        Get all transactions for a specific account.

        Args:
            account_id: Account ID to filter by

        Returns:
            DataFrame with transactions for the specified account

        Raises:
            ValueError: If journal object is not available
        """
        if self._journal is None:
            raise ValueError(
                "Journal object not available. Journal is only available for scenarios with journal-based routing."
            )

        # Get all entries affecting this account
        account_entries = self._journal.get_entries_by_account(account_id)

        # Convert to DataFrame
        entries_data = []
        for entry in account_entries:
            for posting in entry.postings:
                if posting.account_id == account_id:
                    entries_data.append(
                        {
                            "entry_id": entry.id,
                            "timestamp": entry.timestamp,
                            "account_id": posting.account_id,
                            "amount": float(posting.amount.value),
                            "currency": posting.amount.currency.code,
                            "metadata": posting.metadata,
                            "entry_metadata": entry.metadata,
                        }
                    )

        import pandas as pd

        df = pd.DataFrame(entries_data)
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")

        return df


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
                "interest": np.zeros(len(t_index)),
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
    interest_tot = sum(o["interest"] for o in filtered_outputs.values())
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
            "interest": interest_tot,
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
    flows = ["cash_in", "cash_out", "net_cf", "interest"]
    stocks = ["assets", "liabilities", "equity", "cash", "non_cash"]

    # Only aggregate columns that exist
    flows = [c for c in flows if c in df.columns]
    stocks = [c for c in stocks if c in df.columns]

    # Create aggregation dictionary preserving original column order
    agg = {}
    for col in df.columns:
        if col in flows:
            agg[col] = "sum"
        elif col in stocks:
            agg[col] = "last"
        else:
            # For any other columns, use 'last' as default
            agg[col] = "last"

    out = df.groupby(df.index.asfreq(freq)).agg(agg)

    # Ensure column order matches original DataFrame
    out = out.reindex(columns=df.columns)

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
