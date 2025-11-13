"""
Results and output structures for FinBrickLab.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict

import numpy as np
import pandas as pd

from .accounts import (
    BOUNDARY_NODE_ID,
    AccountScope,
    AccountType,
    get_node_scope,
    get_node_type,
)
from .events import Event
from .journal import Journal, JournalEntry
from .registry import Registry
from .transfer_visibility import TransferVisibility


class BrickOutput(TypedDict):
    """
    Standard output structure for all financial brick simulations.

    This TypedDict defines the common interface that all brick strategies must return.
    It provides a consistent structure for cash flows, asset values, debt balances,
    interest tracking, and event tracking across all types of financial instruments.

    Attributes:
        cash_in: Monthly cash inflows (always >= 0) - DEPRECATED: use journal entries instead
        cash_out: Monthly cash outflows (always >= 0) - DEPRECATED: use journal entries instead
        assets: Monthly asset valuation (0 for non-assets)
        liabilities: Monthly debt balance (0 for non-liabilities)
        interest: Monthly interest income (+) / expense (-) (0 if not applicable)
        property_value: Monthly property valuation (for property bricks)
        owner_equity: Monthly equity in the property (property_value - linked debt)
        mortgage_balance: Monthly balance of linked property liabilities
        fees: Monthly fees associated with the brick (e.g., acquisition costs)
        taxes: Monthly taxes associated with the brick
        events: List of time-stamped events describing key occurrences

    Note:
        All numpy arrays have the same length corresponding to the simulation period.
        Cash flows (cash_in/cash_out) are deprecated in V2 - use journal entries instead.
        Aggregators will ignore cash_in/cash_out and compute cashflow from journal.
        Interest is signed: positive for income (cash accounts, securities), negative for expense (loans, credit).
        Events are time-stamped and can be used to build a simulation ledger.
    """

    cash_in: NotRequired[np.ndarray]  # Monthly cash inflows (>=0) - DEPRECATED
    cash_out: NotRequired[np.ndarray]  # Monthly cash outflows (>=0) - DEPRECATED
    assets: np.ndarray  # Monthly asset value (0 if not an asset)
    liabilities: np.ndarray  # Monthly debt balance (0 if not a liability)
    interest: np.ndarray  # Monthly interest income (+) / expense (-) (0 if not applicable)
    property_value: NotRequired[np.ndarray]  # Property-specific valuation
    owner_equity: NotRequired[np.ndarray]  # Property equity (property_value - mortgage)
    mortgage_balance: NotRequired[np.ndarray]  # Property-linked liability balance
    fees: NotRequired[np.ndarray]  # Fee flows associated with the brick
    taxes: NotRequired[np.ndarray]  # Tax flows associated with the brick
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
        default_selection: set[str] | None = None,
        default_visibility: TransferVisibility | None = None,
        include_cash: bool | None = None,
    ):
        """
        Initialize with monthly totals DataFrame (PeriodIndex).

        Args:
            totals: Monthly totals DataFrame with PeriodIndex
            registry: Optional registry for MacroBrick expansion
            outputs: Optional outputs dict for filtered views
            journal: Optional journal object for transaction analysis
            default_selection: Optional default selection set for filtered views
            default_visibility: Optional default transfer visibility for filtered views
            include_cash: Whether cash column should be included (None = default behavior)
        """
        self._monthly_data = totals  # PeriodIndex 'M'
        self._registry = registry
        self._outputs = outputs
        self._journal = journal
        self._default_selection = default_selection
        self._default_visibility = default_visibility
        self._include_cash = include_cash

    # --- Introspection helpers -------------------------------------------------
    def summary(
        self,
        selection: set[str] | None = None,
        transfer_visibility: TransferVisibility | None = None,
    ) -> dict:
        """
        Lightweight summary for API/CLI usage.

        Args:
            selection: Optional explicit selection applied to the view.
            transfer_visibility: Optional transfer visibility override.
        """
        sel = selection if selection is not None else self._default_selection
        visibility = (
            transfer_visibility
            if transfer_visibility is not None
            else (self._default_visibility or TransferVisibility.BOUNDARY_ONLY)
        )

        resolved: list[str] | None = None
        macro_ids: list[str] | None = None
        families: dict[str, int] | None = None

        if self._registry is not None:
            family_counts: dict[str, int] = {"a": 0, "l": 0, "f": 0, "t": 0}
            resolved_list: list[str] = []
            macro_ids = []
            if sel is not None:
                for item in sel:
                    try:
                        if self._registry.is_macrobrick(item):
                            macro_ids.append(item)
                            try:
                                resolved_list.extend(
                                    sorted(self._registry.get_struct_flat_members(item))
                                )
                            except Exception:
                                continue
                        elif self._registry.is_brick(item):
                            resolved_list.append(item)
                    except Exception:
                        continue

                seen: set[str] = set()
                deduped: list[str] = []
                for brick_id in resolved_list:
                    if brick_id in seen:
                        continue
                    seen.add(brick_id)
                    deduped.append(brick_id)
                resolved = deduped

            if resolved is not None:
                for brick_id in resolved:
                    try:
                        family = getattr(
                            self._registry.get_brick(brick_id), "family", None
                        )
                        if isinstance(family, str) and family in family_counts:
                            family_counts[family] += 1
                    except Exception:
                        continue

            families = family_counts

        idx = self._monthly_data.index
        date_start = None
        date_end = None
        try:
            if len(idx):
                first = idx[0]
                last = idx[-1]
                first_ts = (
                    first.to_timestamp("M") if hasattr(first, "to_timestamp") else first
                )
                last_ts = (
                    last.to_timestamp("M") if hasattr(last, "to_timestamp") else last
                )
                date_start = (
                    first_ts.isoformat()
                    if hasattr(first_ts, "isoformat")
                    else str(first_ts)
                )
                date_end = (
                    last_ts.isoformat()
                    if hasattr(last_ts, "isoformat")
                    else str(last_ts)
                )
        except Exception:
            date_start = None
            date_end = None

        def _last(series_name: str) -> float | None:
            if series_name in self._monthly_data.columns:
                try:
                    return float(self._monthly_data[series_name].iloc[-1])
                except Exception:
                    return None
            return None

        def _sum(series_name: str) -> float | None:
            if series_name in self._monthly_data.columns:
                try:
                    return float(self._monthly_data[series_name].sum())
                except Exception:
                    return None
            return None

        last_net_worth = None
        if {"total_assets", "liabilities"}.issubset(self._monthly_data.columns):
            try:
                last_net_worth = float(
                    self._monthly_data["total_assets"].iloc[-1]
                    - self._monthly_data["liabilities"].iloc[-1]
                )
            except Exception:
                last_net_worth = None
        elif {"assets", "liabilities"}.issubset(self._monthly_data.columns):
            try:
                last_net_worth = float(
                    self._monthly_data["assets"].iloc[-1]
                    - self._monthly_data["liabilities"].iloc[-1]
                )
            except Exception:
                last_net_worth = None
        elif {"cash", "non_cash", "liabilities"}.issubset(self._monthly_data.columns):
            try:
                last_net_worth = float(
                    self._monthly_data["cash"].iloc[-1]
                    + self._monthly_data["non_cash"].iloc[-1]
                    - self._monthly_data["liabilities"].iloc[-1]
                )
            except Exception:
                last_net_worth = None

        kpis = {
            "last_cash": _last("cash"),
            "last_liabilities": _last("liabilities"),
            "last_non_cash": _last("non_cash"),
            "last_property_value": _last("property_value"),
            "last_net_worth": last_net_worth,
            "total_inflows": _sum("inflows"),
            "total_outflows": _sum("outflows"),
        }

        columns = [str(col) for col in self._monthly_data.columns]
        selection_in = sorted(sel) if isinstance(sel, (set, list, tuple)) else None

        summary = {
            "type": "results_view",
            "selection_in": selection_in,
            "selection_resolved": resolved,
            "macrobricks_included": macro_ids,
            "transfer_visibility": getattr(visibility, "value", str(visibility)),
            "frame": {
                "freq": "M",
                "rows": int(len(self._monthly_data.index)),
                "date_start": date_start,
                "date_end": date_end,
                "columns": columns,
            },
            "families": families,
            "kpis": kpis,
        }

        return summary

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
        selection: set[str] | None = None,
    ) -> pd.DataFrame:
        """
        Return monthly data with journal-first aggregation (V2 postings model).

        Args:
            transfer_visibility: How to handle transfer visibility (default: BOUNDARY_ONLY)
            include_transparent: Backward compatibility flag (deprecated)
            selection: Optional set of brick/node IDs to filter (for MacroGroups)

        Returns:
            Monthly data DataFrame with journal-first aggregation
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

        # Use default selection/visibility if not explicitly provided
        if selection is None:
            selection = self._default_selection
        if transfer_visibility is None:
            transfer_visibility = (
                self._default_visibility or TransferVisibility.BOUNDARY_ONLY
            )

        # Validate and filter selection to only A/L node IDs (defensive check)
        if selection is not None:
            selection = self._validate_node_selection(selection)

        # Use journal-first aggregation if journal is available AND selection/visibility is explicitly provided
        # Empty set selection is treated as explicit (will return zeros via aggregation)
        # If no selection/visibility, use pre-aggregated data (for filtered views or legacy compatibility)
        has_explicit_selection = selection is not None  # Empty set is explicit
        has_explicit_visibility = (
            transfer_visibility != TransferVisibility.BOUNDARY_ONLY
        )
        if (
            (has_explicit_selection or has_explicit_visibility)
            and self._journal is not None
            and self._registry is not None
        ):
            # Get time index from monthly data
            time_index = self._monthly_data.index

            # Aggregate from journal
            df = _aggregate_journal_monthly(
                journal=self._journal,
                registry=self._registry,
                time_index=time_index,
                selection=selection,
                transfer_visibility=transfer_visibility,
                outputs=self._outputs,
            )

            # Apply transfer visibility if needed (already handled in aggregation)
            # Handle include_cash=False if set during filtering
            if self._include_cash is False and "cash" in df.columns:
                df = df.drop(columns=["cash"])
            return df

        # Use pre-aggregated data (for filtered views or when no explicit selection/visibility)
        # This allows filtered ScenarioResults to return their already-filtered _monthly_data
        result_df = self._monthly_data
        if (
            transfer_visibility == TransferVisibility.BOUNDARY_ONLY
            or transfer_visibility is None
        ):
            result_df = self._monthly_data
        else:
            # Apply transfer visibility filtering on legacy data
            result_df = self._apply_transfer_visibility_filter(transfer_visibility)

        # Handle include_cash=False if set during filtering
        if self._include_cash is False and "cash" in result_df.columns:
            result_df = result_df.drop(columns=["cash"])
        return result_df

    def _apply_transfer_visibility_filter(
        self, visibility: TransferVisibility
    ) -> pd.DataFrame:
        """
        Apply transfer visibility filtering to monthly data.

        Args:
            visibility: The transfer visibility setting to apply

        Returns:
            Filtered monthly data DataFrame with UI/UX guardrails
        """
        if visibility == TransferVisibility.ALL:
            # No filtering needed
            filtered_data = self._monthly_data.copy()
            filtered_data.attrs["transfer_visibility"] = "all"
            filtered_data.attrs["transfer_note"] = "All transfers visible."
            return filtered_data

        # Get the original outputs to filter at the brick level
        if not hasattr(self, "_outputs") or self._outputs is None:
            # Fallback to original data if outputs not available
            filtered_data = self._monthly_data.copy()
            filtered_data.attrs["transfer_visibility"] = "off"
            filtered_data.attrs[
                "transfer_note"
            ] = "Transfer filtering not available (outputs not accessible)."
            return filtered_data

        # Filter the outputs based on transfer visibility
        filtered_outputs = self._filter_outputs_by_transfer_visibility(visibility)

        # Re-aggregate the filtered outputs
        filtered_data = self._aggregate_filtered_outputs(filtered_outputs)

        # Add UI/UX guardrails
        self._add_transfer_metadata(filtered_data, visibility, filtered_outputs)

        return finalize_totals(filtered_data)

    def _filter_outputs_by_transfer_visibility(
        self, visibility: TransferVisibility
    ) -> dict:
        """
        Filter brick outputs based on transfer visibility settings (legacy path).

        **Note:** This method uses the legacy per-brick cash array approach and is only
        used as a fallback when journal-first aggregation is not available. For V2 scenarios,
        journal-first aggregation via `monthly(selection=..., transfer_visibility=...)` is
        authoritative and preferred.

        Args:
            visibility: The transfer visibility setting to apply

        Returns:
            Dictionary of filtered brick outputs
        """
        import warnings

        warnings.warn(
            "Using legacy transfer visibility path (per-brick cash arrays). "
            "Journal-first aggregation is authoritative. "
            "Ensure journal is available for V2 behavior.",
            DeprecationWarning,
            stacklevel=3,
        )

        filtered_outputs: dict[str, BrickOutput] = {}
        transfer_count = 0
        transfer_sum = 0.0

        if self._outputs is None:
            return filtered_outputs

        for brick_id, output in self._outputs.items():
            # Check if this is a transfer brick
            is_transfer = self._is_transfer_brick(brick_id)
            if is_transfer:
                transfer_count += 1
                # Calculate transfer sum (cash_in + cash_out) - handle optional fields
                cash_in = output.get("cash_in")
                cash_out = output.get("cash_out")
                if cash_in is not None and cash_out is not None:
                    transfer_sum += cash_in.sum() + cash_out.sum()

                # Apply visibility rules
                if visibility == TransferVisibility.OFF:
                    # Hide internal transfers - zero out the cash flows
                    filtered_output = output.copy()
                    if "cash_in" in output:
                        filtered_output["cash_in"] = np.zeros_like(output["cash_in"])
                    if "cash_out" in output:
                        filtered_output["cash_out"] = np.zeros_like(output["cash_out"])
                    filtered_outputs[brick_id] = filtered_output
                elif visibility == TransferVisibility.ONLY:
                    # Show only transfers
                    filtered_outputs[brick_id] = output
                elif visibility == TransferVisibility.BOUNDARY_ONLY:
                    # Show only boundary-crossing transfers (use scope-aware boundary detection)
                    # Check if this transfer has any boundary-touching entries in journal
                    if (
                        self._journal is not None
                        and self._journal.account_registry is not None
                    ):
                        # Check journal entries for this brick to see if any touch boundary
                        touches_boundary = False
                        # Create family prefix set for exact parent_id matching (avoid substring false positives)
                        family_parent_ids = {
                            f"a:{brick_id}",
                            f"l:{brick_id}",
                            f"fs:{brick_id}",
                            f"ts:{brick_id}",
                        }
                        for entry in self._journal.entries:
                            # Check if entry belongs to this brick (exact parent_id match)
                            parent_id = entry.metadata.get("parent_id", "")
                            if parent_id not in family_parent_ids:
                                continue
                            # Check if entry touches boundary
                            for posting in entry.postings:
                                node_id = posting.metadata.get("node_id")
                                if node_id is None or not isinstance(node_id, str):
                                    continue
                                try:
                                    scope = get_node_scope(
                                        node_id, self._journal.account_registry
                                    )
                                    if scope == AccountScope.BOUNDARY:
                                        touches_boundary = True
                                        break
                                except ValueError:
                                    # Fallback to direct comparison for known boundary nodes
                                    if node_id == BOUNDARY_NODE_ID:
                                        touches_boundary = True
                                        break
                            if touches_boundary:
                                break
                        if touches_boundary:
                            filtered_outputs[brick_id] = output
                        # If no boundary-touching entries, skip this transfer
                    else:
                        # Fallback: if no journal, include all transfers (legacy behavior)
                        filtered_outputs[brick_id] = output
                else:
                    # Show all transfers
                    filtered_outputs[brick_id] = output
            else:
                # Non-transfer brick - always include
                filtered_outputs[brick_id] = output

        # Store metadata for UI/UX
        self._transfer_metadata = {
            "transfer_count": transfer_count,
            "transfer_sum": transfer_sum,
        }

        return filtered_outputs

    def _is_transfer_brick(self, brick_id: str) -> bool:
        """
        Check if a brick is a transfer brick (TBrick).

        Args:
            brick_id: The brick ID to check

        Returns:
            True if this is a transfer brick
        """
        # Check if we have access to the registry to determine brick type
        if hasattr(self, "_registry") and self._registry:
            try:
                # Try to get the brick from the registry to check its type
                brick = self._registry.get_brick(brick_id)
                if brick and hasattr(brick, "kind"):
                    # Check if it's a transfer brick by kind using prefix check
                    is_transfer_kind = brick.kind.startswith("t.transfer.")
                    if is_transfer_kind:
                        # For transfer bricks, also check the transparent flag
                        # If transparent=True, it should be hidden by default
                        # If transparent=False, it should be visible even in OFF mode
                        return True  # It's a transfer brick, let the visibility logic handle transparency
                    return False
            except Exception:
                pass

        # Fallback: check brick ID patterns for common transfer brick names
        transfer_patterns = [
            "transfer_",
            "kredit_bezahlung",
            "eigenkapital",
            "contribution_",
            "house_contribution",
            "wohnung_hamburg_kredit_bezahlung",
            "wohnung_hamburg_eigenkapital",
        ]

        for pattern in transfer_patterns:
            if pattern in brick_id.lower():
                return True

        return False

    def _aggregate_filtered_outputs(self, filtered_outputs: dict) -> pd.DataFrame:
        """
        Re-aggregate the filtered outputs into monthly totals.

        Args:
            filtered_outputs: Dictionary of filtered brick outputs

        Returns:
            Re-aggregated monthly DataFrame
        """
        # Re-aggregate the filtered outputs using the same logic as the original aggregation
        # This is a simplified implementation that focuses on the key columns

        # Get the time index from the original data
        time_index = self._monthly_data.index

        # Initialize arrays for aggregation
        cash_in = np.zeros(len(time_index))
        cash_out = np.zeros(len(time_index))
        assets = np.zeros(len(time_index))
        liabilities = np.zeros(len(time_index))
        interest = np.zeros(len(time_index))

        # Aggregate the filtered outputs
        for output in filtered_outputs.values():
            # Handle optional cash arrays (deprecated in V2)
            cash_in += output.get("cash_in", np.zeros(len(time_index)))
            cash_out += output.get("cash_out", np.zeros(len(time_index)))
            assets += output["assets"]
            liabilities += output["liabilities"]
            interest += output["interest"]

        # Calculate net cash flow
        net_cf = cash_in - cash_out

        # Create the filtered DataFrame
        filtered_data = pd.DataFrame(
            {
                "cash_in": cash_in,
                "cash_out": cash_out,
                "net_cf": net_cf,
                "assets": assets,
                "liabilities": liabilities,
                "interest": interest,
                "equity": assets - liabilities,
            },
            index=time_index,
        )

        # Preserve original cash to keep identities consistent
        if "cash" in self._monthly_data.columns:
            filtered_data["cash"] = self._monthly_data["cash"]
        if "assets" in filtered_data.columns and "cash" in filtered_data.columns:
            filtered_data["non_cash"] = filtered_data["assets"] - filtered_data["cash"]

        return filtered_data

    def _add_transfer_metadata(
        self,
        filtered_data: pd.DataFrame,
        visibility: TransferVisibility,
        filtered_outputs: dict,
    ) -> None:
        """
        Add transfer metadata to the filtered DataFrame.

        Args:
            filtered_data: The filtered DataFrame to add metadata to
            visibility: The transfer visibility setting
            filtered_outputs: The filtered outputs used
        """
        metadata = getattr(self, "_transfer_metadata", {})
        transfer_count = metadata.get("transfer_count", 0)
        transfer_sum = metadata.get("transfer_sum", 0.0)

        if visibility == TransferVisibility.OFF:
            filtered_data.attrs["transfer_visibility"] = "off"
            filtered_data.attrs[
                "transfer_note"
            ] = f"Internal transfers hidden (n={transfer_count}, Σ={transfer_sum:,.0f}). Use monthly_transfers() to inspect."
            filtered_data.attrs["hidden_transfer_count"] = transfer_count
            filtered_data.attrs["hidden_transfer_sum"] = transfer_sum
        elif visibility == TransferVisibility.ONLY:
            filtered_data.attrs["transfer_visibility"] = "only"
            filtered_data.attrs[
                "transfer_note"
            ] = f"Showing only transfers (n={transfer_count}, Σ={transfer_sum:,.0f})."
            filtered_data.attrs["transfer_count"] = transfer_count
            filtered_data.attrs["transfer_sum"] = transfer_sum
        elif visibility == TransferVisibility.BOUNDARY_ONLY:
            filtered_data.attrs["transfer_visibility"] = "boundary_only"
            filtered_data.attrs[
                "transfer_note"
            ] = f"Showing only boundary-crossing transfers (n={transfer_count}, Σ={transfer_sum:,.0f})."
            filtered_data.attrs["boundary_transfer_count"] = transfer_count
            filtered_data.attrs["boundary_transfer_sum"] = transfer_sum

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

    def get_transfer_metadata(self) -> dict:
        """
        Get transfer visibility metadata from the last monthly() call.

        Returns:
            Dictionary containing transfer counts, sums, and notes
        """
        # This would be populated by the actual filtering logic
        # For now, return placeholder metadata
        return {
            "transfer_visibility": "off",
            "transfer_note": "Internal transfers hidden (n=0, Σ=0). Use monthly_transfers() to inspect.",
            "hidden_transfer_count": 0,
            "hidden_transfer_sum": 0.0,
        }

    def _resolve_selection(
        self, brick_ids: list[str] | None
    ) -> tuple[set[str], list[str], list[str]]:
        """
        Resolve brick IDs and MacroBricks to A/L node IDs for selection.

        This helper extracts the common logic for expanding MacroBricks and converting
        brick IDs to node IDs, used by both filter() and monthly().

        Args:
            brick_ids: List of brick IDs and/or MacroBrick IDs

        Returns:
            Tuple of (selection_set, unknown_ids, non_al_ids) where:
            - selection_set: Set of A/L node IDs for selection
            - unknown_ids: List of unknown brick IDs (warned)
            - non_al_ids: List of non-A/L brick IDs explicitly requested by the user
              (MacroBrick expansion silently drops F/T members to avoid noisy warnings)
        """
        if self._registry is None:
            return set(), [], []

        selection_set: set[str] = set()
        unknown_ids: list[str] = []
        non_al_ids: list[str] = []

        if brick_ids is not None and len(brick_ids) > 0:
            for item_id in brick_ids:
                if self._registry.is_macrobrick(item_id):
                    # Expand MacroBrick using cached expansion (get_struct_flat_members)
                    members = self._registry.get_struct_flat_members(item_id)
                    # Convert brick IDs to node IDs
                    for brick_id in members:
                        brick = self._registry.get_brick(brick_id)
                        if hasattr(brick, "family"):
                            if brick.family == "a":
                                selection_set.add(f"a:{brick_id}")
                            elif brick.family == "l":
                                selection_set.add(f"l:{brick_id}")
                            else:
                                # F/T bricks are ignored silently for MacroBrick expansion
                                continue
                elif self._registry.is_brick(item_id):
                    # Direct brick selection - convert to node ID
                    brick = self._registry.get_brick(item_id)
                    if hasattr(brick, "family"):
                        if brick.family == "a":
                            selection_set.add(f"a:{item_id}")
                        elif brick.family == "l":
                            selection_set.add(f"l:{item_id}")
                        else:
                            # F/T bricks are ignored in selection
                            non_al_ids.append(item_id)
                else:
                    # Unknown ID - skip with warning
                    unknown_ids.append(item_id)

        return selection_set, unknown_ids, non_al_ids

    def _validate_node_selection(self, selection: set[str]) -> set[str]:
        """
        Validate and filter selection to only A/L node IDs.

        This defensive helper ensures that only Asset (a:) and Liability (l:) node IDs
        are included in selection. Flow (fs:) and Transfer (ts:) node IDs are ignored,
        and boundary (b:) node IDs are removed.

        Args:
            selection: Set of node IDs to validate

        Returns:
            Filtered set containing only A/L node IDs
        """
        if not selection:
            return selection

        validated: set[str] = set()
        invalid_ids: list[str] = []

        for node_id in selection:
            if node_id.startswith("a:") or node_id.startswith("l:"):
                validated.add(node_id)
            else:
                invalid_ids.append(node_id)

        # Warn if non-A/L node IDs were provided
        if invalid_ids:
            import warnings

            warnings.warn(
                f"Non-A/L node IDs in selection ignored (only a: and l: node IDs are valid): {invalid_ids}",
                stacklevel=3,
            )

        return validated

    def filter(
        self,
        brick_ids: list[str] | None = None,
        include_cash: bool = True,
        transfer_visibility: TransferVisibility | None = None,
    ) -> ScenarioResults:
        """
        Filter results to show only selected bricks and/or MacroBricks (V2: journal-first).

        This method now uses journal-first aggregation via monthly(selection=...) for V2
        compatibility. It replaces the legacy _compute_filtered_totals() approach.

        **Selection Rules:**
        - Only Asset (A) and Liability (L) bricks produce selection node IDs
        - Flow (F) and Transfer (T) bricks are ignored in selection (they generate entries but don't filter aggregation)
        - MacroBricks are expanded recursively to their A/L member bricks
        - Unknown brick IDs are skipped with a warning

        Args:
            brick_ids: List of brick IDs and/or MacroBrick IDs to include (None = no filtering)
            include_cash: Whether to include cash column in the result (default: True)
            transfer_visibility: Optional transfer visibility setting (default: BOUNDARY_ONLY)

        Returns:
            New ScenarioResults with filtered aggregated data and preserved selection/visibility

        Raises:
            RuntimeError: If registry or journal is not available
        """
        # Validation
        if not self._registry:
            raise RuntimeError("Cannot filter: missing registry")

        # Default transfer visibility
        if transfer_visibility is None:
            transfer_visibility = TransferVisibility.BOUNDARY_ONLY

        # V2: Use journal-first aggregation if journal is available
        if self._journal is not None:
            # Build selection set of node IDs from brick_ids + MacroBrick expansion
            selection_set, unknown_ids, non_al_ids = self._resolve_selection(brick_ids)

            # Warn for unknown IDs and non-A/L bricks (consolidated warning)
            if unknown_ids or non_al_ids:
                import warnings

                warning_parts = []
                if unknown_ids:
                    warning_parts.append(f"unknown IDs: {unknown_ids}")
                if non_al_ids:
                    warning_parts.append(
                        f"non-A/L brick IDs (ignored for selection): {non_al_ids}"
                    )
                warnings.warn(
                    f"Filter selection issues, skipping: {'; '.join(warning_parts)}",
                    stacklevel=2,
                )

            # V2: Use journal-first aggregation via monthly(selection=...)
            # If selection is empty (empty brick_ids or all unknown), return zeros
            if not selection_set:
                # Return zeroed DataFrame with same index/columns as monthly data
                filtered_df = self._monthly_data.copy()
                for col in filtered_df.columns:
                    filtered_df[col] = 0.0
                # Use empty set as sentinel to preserve "empty selection = zeros" semantics
                # This ensures monthly() treats empty selection as explicit (returns zeros)
                default_selection = set()
            else:
                # Get filtered monthly data using journal-first aggregation
                filtered_df = self.monthly(
                    selection=selection_set,
                    transfer_visibility=transfer_visibility,
                )
                default_selection = selection_set

            # Handle include_cash=False
            if not include_cash and "cash" in filtered_df.columns:
                filtered_df = filtered_df.drop(columns=["cash"])

            # Return new ScenarioResults with filtered data and preserved selection/visibility
            return ScenarioResults(
                filtered_df,
                self._registry,
                self._outputs,
                self._journal,
                default_selection=default_selection,
                default_visibility=transfer_visibility,
                include_cash=include_cash,
            )

        # Fallback to legacy path if journal not available
        if not self._outputs:
            raise RuntimeError("Cannot filter: missing outputs (legacy path)")

        # Legacy: Resolve selection to brick IDs (expand MacroBricks automatically)
        selected_bricks: set[str] = set()
        if brick_ids is not None and len(brick_ids) > 0:
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

        # Legacy: If selection is empty, return zeros
        if not selected_bricks:
            filtered_df = self._monthly_data.copy()
            for col in filtered_df.columns:
                filtered_df[col] = 0.0
            # Handle include_cash=False
            if not include_cash and "cash" in filtered_df.columns:
                filtered_df = filtered_df.drop(columns=["cash"])
            return ScenarioResults(
                filtered_df, self._registry, self._outputs, self._journal
            )

        # Identify cash bricks (for cash column calculation)
        cash_bricks = set()
        for bid in selected_bricks:
            if self._registry.is_brick(bid):
                brick = self._registry.get_brick(bid)
                if hasattr(brick, "kind") and brick.kind == "a.cash":
                    cash_bricks.add(bid)

        # Legacy: Compute filtered totals
        filtered_df = _compute_filtered_totals(
            self._outputs,
            selected_bricks,
            self._monthly_data.index,
            include_cash,
            cash_bricks,
        )

        # Handle include_cash=False
        if not include_cash and "cash" in filtered_df.columns:
            filtered_df = filtered_df.drop(columns=["cash"])

        # Return new ScenarioResults with filtered data (preserve empty selection for legacy path)
        return ScenarioResults(
            filtered_df,
            self._registry,
            self._outputs,
            self._journal,
            default_selection=set() if not selected_bricks else None,
            default_visibility=None,
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
                timestamp_start_np = np.datetime64(timestamp_start, "M")
            elif isinstance(timestamp_start, datetime):
                timestamp_start_np = np.datetime64(timestamp_start, "M")
            else:
                timestamp_start_np = timestamp_start
            df = df[df["timestamp"] >= timestamp_start_np]

        if timestamp_end is not None:
            if isinstance(timestamp_end, str):
                timestamp_end_np = np.datetime64(timestamp_end, "M")
            elif isinstance(timestamp_end, datetime):
                timestamp_end_np = np.datetime64(timestamp_end, "M")
            else:
                timestamp_end_np = timestamp_end
            df = df[df["timestamp"] <= timestamp_end_np]

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
    # Handle optional cash arrays (deprecated in V2)
    cash_in_tot = sum(
        o.get("cash_in", np.zeros(len(t_index))) for o in filtered_outputs.values()
    )
    cash_out_tot = sum(
        o.get("cash_out", np.zeros(len(t_index))) for o in filtered_outputs.values()
    )
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
    flows = [
        "cash_in",
        "cash_out",
        "net_cf",
        "interest",
        "cash_delta",
        "equity_delta",
        "capitalized_cf",
        "cash_rebalancing",
        "fees",
        "taxes",
    ]
    stocks = [
        "assets",
        "liabilities",
        "equity",
        "cash",
        "non_cash",
        "property_value",
        "owner_equity",
        "mortgage_balance",
    ]

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


def _append_derived_flow_columns(df: pd.DataFrame) -> None:
    """
    Append derived cash and equity flow columns in place, preserving accounting identities.
    """

    if "cash" in df.columns and "cash_delta" not in df.columns:
        cash_delta = df["cash"].diff()
        if not cash_delta.empty:
            cash_delta.iloc[0] = df["cash"].iloc[0]
        df["cash_delta"] = cash_delta.fillna(0.0)

    if "equity" in df.columns and "equity_delta" not in df.columns:
        equity_delta = df["equity"].diff()
        if not equity_delta.empty:
            equity_delta.iloc[0] = df["equity"].iloc[0]
        df["equity_delta"] = equity_delta.fillna(0.0)

    if (
        "net_cf" in df.columns
        and "equity_delta" in df.columns
        and "capitalized_cf" not in df.columns
    ):
        df["capitalized_cf"] = df["equity_delta"] - df["net_cf"]

    if (
        "net_cf" in df.columns
        and "cash_delta" in df.columns
        and "cash_rebalancing" not in df.columns
    ):
        df["cash_rebalancing"] = df["cash_delta"] - df["net_cf"]


def _aggregate_journal_monthly(
    journal: Journal,
    registry: Registry,
    time_index: pd.PeriodIndex,
    selection: set[str] | None = None,
    transfer_visibility: TransferVisibility = TransferVisibility.BOUNDARY_ONLY,
    outputs: dict[str, BrickOutput] | None = None,
) -> pd.DataFrame:
    """
    Aggregate journal entries monthly with internal cancellation logic.

    This implements journal-first aggregation for V2 postings model:
    - Time bucket by entry timestamp (month precision)
    - For selection S (A/L set from MacroGroup or single A/L):
      - Iterate entries (two postings each)
      - Check if any posting hits `b:boundary`
      - If both postings INTERNAL and both `node_id ∈ S` → cancel for cashflow
      - Else, find ASSET posting:
        - If `node_id ∈ S`: include (DR=inflow, CR=outflow)
        - Ignore LIABILITY postings for cashflow totals
      - Attribute boundary postings by `category` for P&L

    Args:
        journal: Journal with entries
        registry: Registry for account/node lookup
        time_index: Time index for output DataFrame
        selection: Set of A/L node IDs to include (None = all)
        transfer_visibility: Transfer visibility setting
        outputs: Optional brick outputs for balance aggregation

    Returns:
        DataFrame with monthly totals (cash_in, cash_out, assets, liabilities, interest, equity)
    """
    from datetime import datetime

    import numpy as np

    # Initialize arrays
    length = len(time_index)
    cash_in = np.zeros(length)
    cash_out = np.zeros(length)
    interest_in_from_journal = np.zeros(length)
    interest_out_from_journal = np.zeros(length)
    assets = np.zeros(length)
    liabilities = np.zeros(length)
    interest = np.zeros(length)
    property_value = np.zeros(length)
    owner_equity = np.zeros(length)
    mortgage_balance = np.zeros(length)
    fees_series = np.zeros(length)
    taxes_series = np.zeros(length)

    # Get account registry from journal
    account_registry = journal.account_registry
    if account_registry is None:
        raise ValueError("Journal must have account_registry for aggregation")

    # Expand selection if needed (for MacroGroups)
    selection_set: set[str] = set()
    if selection is not None:
        # Empty selection (len=0) means return zeros - return early
        if len(selection) == 0:
            # Return all zeros DataFrame
            df = pd.DataFrame(
                {
                    "cash_in": cash_in,
                    "cash_out": cash_out,
                    "net_cf": cash_in - cash_out,
                    "assets": assets,
                    "liabilities": liabilities,
                    "interest": interest,
                    "equity": assets - liabilities,
                    "cash": np.zeros(length),
                    "non_cash": assets,
                    "property_value": np.zeros(length),
                    "owner_equity": np.zeros(length),
                    "mortgage_balance": np.zeros(length),
                    "fees": np.zeros(length),
                    "taxes": np.zeros(length),
                },
                index=time_index,
            )
            return df
        else:
            for node_id in selection:
                # Check if it's a MacroGroup
                if registry and registry.is_macrobrick(node_id):
                    # Expand MacroGroup using cached expansion (get_struct_flat_members)
                    members = registry.get_struct_flat_members(node_id)
                    # Convert brick IDs to node IDs
                    for brick_id in members:
                        brick = registry.get_brick(brick_id)
                        if hasattr(brick, "family"):
                            if brick.family == "a":
                                selection_set.add(f"a:{brick_id}")
                            elif brick.family == "l":
                                selection_set.add(f"l:{brick_id}")
                else:
                    # Direct node ID
                    selection_set.add(node_id)

    def _is_cash_node(node_id: str) -> bool:
        if not node_id or not isinstance(node_id, str):
            return False
        if not node_id.startswith("a:"):
            return False

        if registry:
            from .kinds import K

            brick_id = node_id.split(":", 1)[1]
            try:
                brick = registry.get_brick(brick_id)
            except Exception:
                brick = None
            if brick and getattr(brick, "kind", None) == K.A_CASH:
                return True
            # Registry told us it is not cash; fall through to False
            if brick is not None:
                return False

        if account_registry:
            account = account_registry.get_account(node_id)
            if account and account.account_type == AccountType.ASSET:
                name_lower = account.name.lower()
                if any(
                    keyword in name_lower
                    for keyword in ("cash", "checking", "savings", "konto")
                ):
                    return True
        return False

    selected_cash_nodes: set[str] = (
        {node_id for node_id in selection_set if _is_cash_node(node_id)}
        if selection_set
        else set()
    )

    # Group entries by month
    entries_by_month: dict[str, list[JournalEntry]] = {}
    for entry in journal.entries:
        # Normalize timestamp to month
        if isinstance(entry.timestamp, datetime):
            month_str = entry.timestamp.strftime("%Y-%m")
        else:
            # Handle numpy datetime64
            month_str = str(entry.timestamp)[:7]  # YYYY-MM

        if month_str not in entries_by_month:
            entries_by_month[month_str] = []
        entries_by_month[month_str].append(entry)

    # Process each month
    for month_idx, period in enumerate(time_index):
        month_str = period.strftime("%Y-%m")

        # Get entries for this month
        month_entries = entries_by_month.get(month_str, [])

        # Process each entry
        for entry in month_entries:
            if entry.metadata.get("transaction_type") == "opening":
                continue
            # Check if entry touches boundary
            # Use get_node_scope() to detect boundary accounts (including FX_CLEAR_NODE_ID)
            touches_boundary = False
            for posting in entry.postings:
                boundary_node_id = posting.metadata.get("node_id")
                if boundary_node_id is None or not isinstance(boundary_node_id, str):
                    continue  # Skip postings without node_id (legacy entries)
                try:
                    scope = get_node_scope(boundary_node_id, account_registry)
                    if scope == AccountScope.BOUNDARY:
                        touches_boundary = True
                        break
                except ValueError:
                    # Fallback to direct comparison for known boundary nodes
                    if boundary_node_id == BOUNDARY_NODE_ID:
                        touches_boundary = True
                        break

            # Check if this is a transfer entry
            # Include fx_transfer so it participates in transfer-visibility logic
            is_transfer_entry = entry.metadata.get("transaction_type") in {
                "transfer",
                "tbrick",
                "maturity_transfer",
                "fx_transfer",
            }

            entry_hits_selected_cash = False
            if selected_cash_nodes:
                for posting in entry.postings:
                    posting_node_id = posting.metadata.get("node_id")
                    if posting_node_id in selected_cash_nodes:
                        entry_hits_selected_cash = True
                        break

            # Check if both postings are INTERNAL (global check, regardless of selection)
            both_internal_global = not touches_boundary
            if both_internal_global:
                # Verify all postings are INTERNAL (not boundary)
                for posting in entry.postings:
                    posting_node_id = posting.metadata.get("node_id")
                    if posting_node_id is None or not isinstance(posting_node_id, str):
                        both_internal_global = False
                        break
                    try:
                        scope = get_node_scope(posting_node_id, account_registry)
                        if scope != AccountScope.INTERNAL:
                            both_internal_global = False
                            break
                    except ValueError:
                        # Fallback: if can't determine scope, assume not internal
                        both_internal_global = False
                        break

            # Check if both postings are INTERNAL and in selection (for cancellation)
            both_internal_in_selection = False
            if both_internal_global and selection_set:
                both_in_selection = True
                for posting in entry.postings:
                    posting_node_id = posting.metadata.get("node_id")
                    if posting_node_id is None or not isinstance(posting_node_id, str):
                        both_in_selection = (
                            False  # Legacy entries can't be internal transfers
                        )
                        break
                    if posting_node_id not in selection_set:
                        both_in_selection = False
                        break
                if both_in_selection:
                    both_internal_in_selection = True

            # Apply TransferVisibility filtering
            if transfer_visibility != TransferVisibility.ALL:
                if transfer_visibility == TransferVisibility.OFF:
                    # Hide internal transfers (global check, works without selection)
                    if is_transfer_entry and both_internal_global:
                        continue  # Skip internal transfers
                    if not touches_boundary:
                        continue  # Skip all internal entries
                    # Also skip if both internal and in selection (cancellation)
                    if both_internal_in_selection:
                        continue  # Skip internal transfers in selection
                elif transfer_visibility == TransferVisibility.ONLY:
                    # Show only transfer entries
                    if not is_transfer_entry:
                        continue  # Skip non-transfer entries
                elif transfer_visibility == TransferVisibility.BOUNDARY_ONLY:
                    # Show only boundary-crossing transfers (not internal transfers)
                    if not touches_boundary and not entry_hits_selected_cash:
                        continue  # Skip non-boundary entries

            # Apply cancellation: if both INTERNAL and in selection, cancel
            if both_internal_in_selection:
                # Skip this entry for cashflow (internal transfer cancels)
                continue

            cash_postings: list = []
            if selection_set:
                if selected_cash_nodes:
                    for posting in entry.postings:
                        posting_node_id = posting.metadata.get("node_id")
                        if (
                            posting_node_id is not None
                            and isinstance(posting_node_id, str)
                            and posting_node_id in selected_cash_nodes
                        ):
                            cash_postings.append(posting)
                else:
                    cash_postings = []
            else:
                # No selection_set: pick the first ASSET posting (status quo)
                for posting in entry.postings:
                    posting_node_id = posting.metadata.get("node_id")
                    if posting_node_id is None or not isinstance(posting_node_id, str):
                        continue  # Skip postings without node_id (legacy entries)
                    try:
                        node_type = get_node_type(posting_node_id, account_registry)
                        if node_type == AccountType.ASSET:
                            cash_postings = [posting]
                            break
                    except ValueError:
                        continue  # Skip if node_id is None or invalid

            # Include ASSET posting (already selection-aware if selection_set was provided)
            interest_recorded_from_cash = False
            for asset_posting in cash_postings:
                is_interest_entry = (
                    entry.metadata.get("tags", {}).get("type") == "interest"
                )
                asset_node_id = asset_posting.metadata.get("node_id")
                if asset_node_id is None or not isinstance(asset_node_id, str):
                    continue
                if selection_set and asset_node_id not in selected_cash_nodes:
                    continue
                amount = float(asset_posting.amount.value)
                if asset_posting.is_debit():
                    cash_in[month_idx] += abs(amount)
                    if is_interest_entry:
                        interest_in_from_journal[month_idx] += abs(amount)
                        interest_recorded_from_cash = True
                else:  # credit
                    cash_out[month_idx] += abs(amount)
                    if is_interest_entry:
                        interest_out_from_journal[month_idx] += abs(amount)
                        interest_recorded_from_cash = True

            # Track boundary interest postings even if no cash posting is recorded
            if (
                entry.metadata.get("tags", {}).get("type") == "interest"
                and not interest_recorded_from_cash
            ):
                for posting in entry.postings:
                    posting_node_id = posting.metadata.get("node_id")
                    if posting_node_id == BOUNDARY_NODE_ID:
                        amount = float(posting.amount.value)
                        if posting.is_debit():
                            interest_out_from_journal[month_idx] += abs(amount)
                        elif posting.is_credit():
                            interest_in_from_journal[month_idx] += abs(amount)
                        break

        # Aggregate balances from outputs if provided
        if outputs:
            for brick_id, output in outputs.items():
                # Check if this brick is in selection
                output_brick = registry.get_brick(brick_id) if registry else None
                if output_brick and hasattr(output_brick, "family"):
                    output_node_id = f"{output_brick.family}:{brick_id}"
                    if not selection_set or output_node_id in selection_set:
                        assets[month_idx] += output["assets"][month_idx]
                        liabilities[month_idx] += output["liabilities"][month_idx]
                        interest[month_idx] += output["interest"][month_idx]
                        if "property_value" in output:
                            property_value[month_idx] += output["property_value"][
                                month_idx
                            ]
                        if "owner_equity" in output:
                            owner_equity[month_idx] += output["owner_equity"][month_idx]
                        if "mortgage_balance" in output:
                            mortgage_balance[month_idx] += output["mortgage_balance"][
                                month_idx
                            ]
                        if "fees" in output:
                            fees_series[month_idx] += output["fees"][month_idx]
                        if "taxes" in output:
                            taxes_series[month_idx] += output["taxes"][month_idx]

    # Calculate derived fields
    desired_interest_in = np.clip(interest, a_min=0.0, a_max=None)
    desired_interest_out = np.clip(-interest, a_min=0.0, a_max=None)

    if not selection_set:
        cash_in += desired_interest_in - interest_in_from_journal
        cash_out += desired_interest_out - interest_out_from_journal

    net_cf = cash_in - cash_out
    equity = assets - liabilities

    # Calculate cash column (sum of cash account assets)
    cash_assets = None
    if outputs:
        from .kinds import K

        for brick_id, output in outputs.items():
            cash_brick = registry.get_brick(brick_id) if registry else None
            if (
                cash_brick
                and hasattr(cash_brick, "kind")
                and cash_brick.kind == K.A_CASH
            ):
                cash_node_id = (
                    f"{cash_brick.family}:{brick_id}"
                    if hasattr(cash_brick, "family")
                    else f"a:{brick_id}"
                )
                if not selection_set or cash_node_id in selection_set:
                    s = output["assets"]
                    cash_assets = s if cash_assets is None else (cash_assets + s)
    cash_assets = cash_assets if cash_assets is not None else np.zeros(len(time_index))

    # Calculate non_cash assets
    non_cash_assets = assets - cash_assets

    # Create DataFrame
    df = pd.DataFrame(
        {
            "cash_in": cash_in,
            "cash_out": cash_out,
            "net_cf": net_cf,
            "assets": assets,
            "liabilities": liabilities,
            "interest": interest,
            "equity": equity,
            "cash": cash_assets,
            "non_cash": non_cash_assets,
            "property_value": property_value,
            "owner_equity": owner_equity,
            "mortgage_balance": mortgage_balance,
            "fees": fees_series,
            "taxes": taxes_series,
        },
        index=time_index,
    )

    _append_derived_flow_columns(df)

    return df


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

    _append_derived_flow_columns(df)

    # Clean up numerical noise introduced by floating point arithmetic
    cleanup_eps = 1e-9
    numeric_cols = df.select_dtypes(include=["float"]).columns
    if len(numeric_cols) > 0:
        df[numeric_cols] = df[numeric_cols].mask(
            df[numeric_cols].abs() < cleanup_eps, 0.0
        )

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
