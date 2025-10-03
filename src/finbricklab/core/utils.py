"""
Utility functions for FinBrickLab.
"""

from __future__ import annotations

import warnings
from datetime import date

import numpy as np
import pandas as pd
from pandas import Index


def month_range(start: date, months: int) -> np.ndarray:
    """
    Generate a range of monthly dates starting from a given date.

    This utility function creates a numpy array of datetime64 objects representing
    consecutive months, which is used throughout the system for time-based simulations.

    **Use Cases:**
    - Creating time indices for scenario simulations
    - Generating monthly date ranges for financial calculations
    - Building time-based arrays for pandas DataFrames
    - Setting up periodic evaluation schedules

    **Args:**
        start: The starting date for the range
        months: Number of months to generate

    **Returns:**
        A numpy array of datetime64 objects representing monthly intervals

    **Example:**
        ```python
        from datetime import date
        from finbricklab.core.utils import month_range

        # Create a 12-month range starting January 2026
        dates = month_range(date(2026, 1, 1), 12)
        print(dates)
        # Output: ['2026-01' '2026-02' '2026-03' ... '2026-12']

        # Use with pandas DataFrame
        df = pd.DataFrame(index=dates)
        ```
    """
    s = np.datetime64(start, "M")
    return s + np.arange(months).astype("timedelta64[M]")


def active_mask(
    t_index: Index | np.ndarray,
    start_date: date | None,
    end_date: date | None,
    duration_m: int | None,
) -> np.ndarray:
    """
    Create a boolean mask indicating when a brick is active during simulation.

    This function determines the active periods for a financial brick based on its
    start date, end date, or duration. It's used throughout the system to handle
    bricks that activate at different times during a scenario.

    **Use Cases:**
    - Implementing brick activation windows (e.g., house purchase in 2028)
    - Handling temporary income sources (e.g., 2-year contract job)
    - Modeling life events with specific start/end dates
    - Creating time-based filtering for financial calculations

    **Args:**
        t_index: Time index array (np.datetime64[M] or pd.PeriodIndex)
        start_date: When the brick becomes active (None = scenario start)
        end_date: When the brick becomes inactive (None = scenario end)
        duration_m: Duration in months (alternative to end_date)

    **Returns:**
        Boolean array where True indicates the brick is active

    **Example:**
        ```python
        from datetime import date
        from finbricklab.core.utils import active_mask, month_range

        # Create a 24-month time index
        t_index = month_range(date(2026, 1, 1), 24)

        # Brick active from month 6 to month 18 (12 months duration)
        mask = active_mask(t_index, start_date=None, end_date=None, duration_m=12)

        # Brick active from specific start date
        mask = active_mask(t_index, start_date=date(2026, 6, 1), end_date=None, duration_m=None)

        # Use mask to filter data
        active_data = data[mask]
        ```

    **Note:**
        - duration_m includes the start month (duration_m=12 means 12 months including start_date)
        - end_date takes precedence over duration_m if both are provided
        - Inactive periods are masked with False (will be zeroed in outputs)
        - Handles both DatetimeIndex and PeriodIndex
    """
    # Handle PeriodIndex by converting to datetime64 for comparison
    if isinstance(t_index, pd.PeriodIndex):
        t_index_dt = t_index.to_timestamp()
    else:
        t_index_dt = t_index

    # Ensure t_index_dt is monthly precision
    if t_index_dt.dtype != "datetime64[M]":
        if isinstance(t_index_dt, pd.DatetimeIndex):
            t_index_dt = t_index_dt.to_numpy().astype("datetime64[M]")
        else:
            t_index_dt = t_index_dt.astype("datetime64[M]")

    # Normalize start date
    if start_date is not None:
        start_m = np.datetime64(start_date, "M")
    else:
        start_m = t_index_dt[0]

    # Determine end date with inclusive logic
    if end_date is not None:
        end_m = np.datetime64(end_date, "M")  # inclusive
        # Warn if both end_date and duration_m are provided
        if duration_m is not None:
            warnings.warn(
                f"Both end_date and duration_m provided; using end_date {end_date}",
                stacklevel=2,
            )
    elif duration_m is not None:
        if duration_m < 1:
            raise ValueError("duration_m must be >= 1")
        # duration_m counts the start month; duration_m=1 => same month
        span = int(duration_m)
        end_m = start_m + np.timedelta64(span - 1, "M")
    else:
        end_m = t_index_dt[-1]

    return (t_index_dt >= start_m) & (t_index_dt <= end_m)


def _apply_window_equity_neutral(out, mask):
    """
    Apply activation window mask in an equity-neutral way.

    Only flows (cash_in, cash_out) are masked to zero outside the window.
    Stock series (asset_value, debt_balance) are NOT zeroed - they carry forward
    the last active value unless explicitly set by terminal disposal/payoff events.

    Args:
        out: BrickOutput dictionary with cash_in, cash_out, asset_value, debt_balance
        mask: Boolean array indicating when the brick is active

    Note:
        This preserves the accounting identity: equity only changes via explicit flows.
        Terminal disposal/payoff events must book the appropriate cash legs at t_stop.
    """
    import numpy as np

    # Mask flows to zero outside the window
    out["cash_in"] = np.where(mask, out["cash_in"], 0.0)
    out["cash_out"] = np.where(mask, out["cash_out"], 0.0)

    # Do NOT touch stocks here; terminal actions set them explicitly at t_stop


def resolve_prepayments_to_month_idx(
    t_index: np.ndarray, prepayments: list, mortgage_start_date: date
) -> dict:
    """
    Resolve prepayment directives to month indices.

    Args:
        t_index: Time index array (np.datetime64[M])
        prepayments: List of prepayment directives
        mortgage_start_date: Start date of the mortgage for relative calculations

    Returns:
        Dictionary mapping month index to prepayment amount

    Note:
        Supports both absolute dates ("t": "YYYY-MM") and periodic schedules
        ({"every": "year", "month": 12, "amount": 5000})
    """
    prepay_map = {}

    for prepay in prepayments:
        if "t" in prepay:
            # Absolute date specification
            prepay_date = np.datetime64(prepay["t"], "M")
            month_idx = np.where(t_index == prepay_date)[0]
            if len(month_idx) > 0:
                idx = month_idx[0]
                if "amount" in prepay:
                    prepay_map[idx] = float(prepay["amount"])
                elif "pct_balance" in prepay:
                    prepay_map[idx] = (
                        "pct",
                        float(prepay["pct_balance"]),
                        float(prepay.get("cap", float("inf"))),
                    )
        elif "every" in prepay:
            # Periodic specification
            if prepay["every"] == "year":
                start_year = prepay.get("start_year", mortgage_start_date.year)
                end_year = prepay.get("end_year", start_year + 10)
                month = prepay["month"]

                for year in range(start_year, end_year + 1):
                    prepay_date = np.datetime64(f"{year}-{month:02d}", "M")
                    month_idx = np.where(t_index == prepay_date)[0]
                    if len(month_idx) > 0:
                        idx = month_idx[0]
                        if "amount" in prepay:
                            prepay_map[idx] = float(prepay["amount"])
                        elif "pct_balance" in prepay:
                            prepay_map[idx] = (
                                "pct",
                                float(prepay["pct_balance"]),
                                float(prepay.get("cap", float("inf"))),
                            )

    return prepay_map
