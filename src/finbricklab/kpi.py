"""
KPI calculation utilities for financial scenario analysis.

This module provides standalone functions for computing key performance indicators
from canonical DataFrame data. All functions operate on DataFrames with the
canonical schema and return pandas Series or DataFrames.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def liquidity_runway(
    df: pd.DataFrame,
    lookback_months: int = 6,
    essential_share: float = 0.6,
    cash_col: str = "cash",
    outflows_col: str = "outflows",
) -> pd.Series:
    """
    Calculate liquidity runway in months.

    Liquidity runway = cash / rolling_average(essential_outflows, lookback_months)

    Args:
        df: DataFrame with canonical schema
        lookback_months: Number of months to look back for essential outflows
        essential_share: Share of outflows considered essential (default 0.6)
        cash_col: Column name for cash balance
        outflows_col: Column name for outflows

    Returns:
        Series with liquidity runway in months per row
    """
    cash = df[cash_col]
    outflows = df[outflows_col]

    # Calculate essential outflows
    essential_outflows = outflows * essential_share

    # Calculate rolling average of essential outflows
    rolling_avg_outflows = essential_outflows.rolling(
        window=lookback_months, min_periods=1
    ).mean()

    # Calculate runway (avoid division by zero)
    runway = np.where(
        rolling_avg_outflows > 0,
        cash / rolling_avg_outflows,
        np.inf,  # Infinite runway if no essential outflows
    )

    return pd.Series(runway, index=df.index, name="liquidity_runway_months")


def max_drawdown(series_or_df: pd.Series | pd.DataFrame) -> pd.Series:
    """
    Calculate maximum drawdown from peak.

    For a Series, returns the maximum drawdown.
    For a DataFrame, returns maximum drawdown per column.

    Args:
        series_or_df: Series or DataFrame with values to analyze

    Returns:
        Series with maximum drawdown values
    """
    if isinstance(series_or_df, pd.Series):
        # Calculate running maximum (peak)
        running_max = series_or_df.expanding().max()

        # Calculate drawdown from peak
        drawdown = (series_or_df - running_max) / running_max

        # Return maximum drawdown
        return pd.Series(
            [drawdown.min()], index=[series_or_df.name or "value"], name="max_drawdown"
        )
    else:
        # DataFrame case - calculate per column
        results = {}
        for col in series_or_df.columns:
            if pd.api.types.is_numeric_dtype(series_or_df[col]):
                running_max = series_or_df[col].expanding().max()
                drawdown = (series_or_df[col] - running_max) / running_max
                results[col] = drawdown.min()
            else:
                results[col] = np.nan

        return pd.Series(results, name="max_drawdown")


def fee_drag_cum(
    df: pd.DataFrame,
    fees_col: str = "fees",
    inflows_col: str = "inflows",
) -> pd.Series:
    """
    Calculate cumulative fee drag as percentage of cumulative inflows.

    Args:
        df: DataFrame with canonical schema
        fees_col: Column name for fees
        inflows_col: Column name for inflows

    Returns:
        Series with cumulative fee drag percentage
    """
    cum_fees = df[fees_col].cumsum()
    cum_inflows = df[inflows_col].cumsum()

    # Avoid division by zero
    fee_drag = np.where(
        cum_inflows > 0,
        cum_fees / cum_inflows,
        0.0,
    )

    return pd.Series(fee_drag, index=df.index, name="fee_drag_cum_pct")


def tax_burden_cum(
    df: pd.DataFrame,
    taxes_col: str = "taxes",
    inflows_col: str = "inflows",
) -> pd.Series:
    """
    Calculate cumulative tax burden as percentage of cumulative inflows.

    Args:
        df: DataFrame with canonical schema
        taxes_col: Column name for taxes
        inflows_col: Column name for inflows

    Returns:
        Series with cumulative tax burden percentage
    """
    cum_taxes = df[taxes_col].cumsum()
    cum_inflows = df[inflows_col].cumsum()

    # Avoid division by zero
    tax_burden = np.where(
        cum_inflows > 0,
        cum_taxes / cum_inflows,
        0.0,
    )

    return pd.Series(tax_burden, index=df.index, name="tax_burden_cum_pct")


def effective_tax_rate(
    df: pd.DataFrame,
    taxes_col: str = "taxes",
    inflows_col: str = "inflows",
) -> pd.Series:
    """
    Calculate effective tax rate (cumulative taxes / cumulative inflows).

    This is an alias for tax_burden_cum for clarity.

    Args:
        df: DataFrame with canonical schema
        taxes_col: Column name for taxes
        inflows_col: Column name for inflows

    Returns:
        Series with effective tax rate
    """
    return tax_burden_cum(df, taxes_col, inflows_col)


def interest_paid_cum(
    df: pd.DataFrame,
    interest_col: str = "interest",
) -> pd.Series:
    """
    Calculate cumulative interest paid.

    Args:
        df: DataFrame with canonical schema
        interest_col: Column name for interest (optional field)

    Returns:
        Series with cumulative interest paid
    """
    if interest_col not in df.columns:
        # Return zeros if interest column doesn't exist
        return pd.Series(0.0, index=df.index, name="interest_paid_cum")

    return df[interest_col].cumsum().rename("interest_paid_cum")


def dsti(
    df: pd.DataFrame,
    interest_col: str = "interest",
    principal_col: str = "principal",
    net_income_col: str = "net_income",
) -> pd.Series:
    """
    Calculate Debt Service to Income ratio.

    DSTI = (interest + principal) / net_income

    Args:
        df: DataFrame with canonical schema
        interest_col: Column name for interest payments
        principal_col: Column name for principal payments
        net_income_col: Column name for net income

    Returns:
        Series with DSTI ratio (NaN where data unavailable)
    """
    # Check if required columns exist
    required_cols = [interest_col, principal_col, net_income_col]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        # Return NaN if any required columns are missing
        return pd.Series(np.nan, index=df.index, name="dsti")

    # Calculate DSTI
    debt_service = df[interest_col] + df[principal_col]
    net_income = df[net_income_col]

    # Avoid division by zero
    dsti = np.where(
        net_income > 0,
        debt_service / net_income,
        np.nan,
    )

    return pd.Series(dsti, index=df.index, name="dsti")


def ltv(
    df: pd.DataFrame,
    mortgage_balance_col: str = "mortgage_balance",
    property_value_col: str = "property_value",
    liabilities_col: str = "liabilities",
    total_assets_col: str = "total_assets",
) -> pd.Series:
    """
    Calculate Loan to Value ratio.

    If property-specific columns exist: LTV = mortgage_balance / property_value
    Otherwise: LTV = liabilities / total_assets (proxy)

    Args:
        df: DataFrame with canonical schema
        mortgage_balance_col: Column name for mortgage balance
        property_value_col: Column name for property value
        liabilities_col: Column name for total liabilities
        total_assets_col: Column name for total assets

    Returns:
        Series with LTV ratio (NaN where data unavailable)
    """
    # Try property-specific LTV first
    if mortgage_balance_col in df.columns and property_value_col in df.columns:
        mortgage_balance = df[mortgage_balance_col]
        property_value = df[property_value_col]

        # Avoid division by zero
        ltv = np.where(
            property_value > 0,
            mortgage_balance / property_value,
            np.nan,
        )

        return pd.Series(ltv, index=df.index, name="ltv")

    # Fallback to general LTV proxy
    elif liabilities_col in df.columns and total_assets_col in df.columns:
        liabilities = df[liabilities_col]
        total_assets = df[total_assets_col]

        # Avoid division by zero
        ltv = np.where(
            total_assets > 0,
            liabilities / total_assets,
            np.nan,
        )

        return pd.Series(ltv, index=df.index, name="ltv_proxy")

    else:
        # Return NaN if no suitable columns exist
        return pd.Series(np.nan, index=df.index, name="ltv")


def breakeven_month(
    scenario_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    net_worth_col: str = "net_worth",
    date_col: str = "date",
) -> int | None:
    """
    Calculate breakeven month for a scenario vs baseline.

    Args:
        scenario_df: DataFrame for the scenario to analyze
        baseline_df: DataFrame for the baseline scenario
        net_worth_col: Column name for net worth
        date_col: Column name for date

    Returns:
        Month number (1-based) where scenario first matches or exceeds baseline,
        or None if no breakeven occurs
    """
    # Align by date using inner join to handle mismatched calendars
    merged = pd.merge(
        scenario_df[[date_col, net_worth_col]],
        baseline_df[[date_col, net_worth_col]],
        on=date_col,
        how="inner",
        suffixes=("_scenario", "_baseline"),
    )

    if merged.empty:
        return None

    # Calculate advantage (scenario - baseline)
    advantage = (
        merged[f"{net_worth_col}_scenario"] - merged[f"{net_worth_col}_baseline"]
    )

    # Find first month where advantage >= 0
    breakeven_mask = advantage >= 0

    if not breakeven_mask.any():
        return None

    # Return 1-based month number
    first_breakeven_idx = np.where(breakeven_mask)[0][0]
    return first_breakeven_idx + 1


def savings_rate(
    df: pd.DataFrame,
    inflows_col: str = "inflows",
    outflows_col: str = "outflows",
) -> pd.Series:
    """
    Calculate savings rate.

    Savings rate = (net_income - consumption) / net_income
    For canonical schema: (inflows - outflows) / inflows

    Args:
        df: DataFrame with canonical schema
        inflows_col: Column name for inflows
        outflows_col: Column name for outflows

    Returns:
        Series with savings rate (NaN where inflows <= 0)
    """
    inflows = df[inflows_col]
    outflows = df[outflows_col]

    # Calculate net income (inflows - outflows)
    net_income = inflows - outflows

    # Calculate savings rate
    savings_rate = np.where(
        inflows > 0,
        net_income / inflows,
        np.nan,
    )

    return pd.Series(savings_rate, index=df.index, name="savings_rate")
