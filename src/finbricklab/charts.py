"""
Chart functions for visualizing financial scenarios and entities.

This module provides chart functions for different levels of financial analysis:
- Entity level: Multi-scenario comparisons and benchmarking
- Scenario level: Deep-dive analysis of individual scenarios
- MacroBrick level: Category-based analysis
- FinBrick level: Individual instrument analysis

All chart functions return (figure, tidy_dataframe_used) for consistency.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Plotly imports with graceful fallback
try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def _check_plotly() -> None:
    """Check if Plotly is available and raise helpful error if not."""
    if not PLOTLY_AVAILABLE:
        raise ImportError(
            "Plotly is required for chart functions. Install with:\n"
            "pip install plotly kaleido\n"
            "or\n"
            "poetry install --extras viz"
        )


# =============================================================================
# Entity-level charts (multi-scenario comparisons)
# =============================================================================


def net_worth_vs_time(tidy: pd.DataFrame) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot net worth over time for multiple scenarios.

    Args:
        tidy: DataFrame from Entity.compare() with scenario_id, scenario_name columns

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    fig = px.line(
        tidy,
        x="date",
        y="net_worth",
        color="scenario_name",
        title="Net Worth Over Time",
        labels={"net_worth": "Net Worth", "date": "Date"},
    )

    fig.update_layout(hovermode="x unified", legend_title="Scenario")

    return fig, tidy


def asset_composition_small_multiples(
    tidy: pd.DataFrame,
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot asset composition (cash/liquid/illiquid) as small multiples per scenario.

    Args:
        tidy: DataFrame from Entity.compare() with asset columns

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    # Melt data for stacked area chart
    asset_cols = ["cash", "liquid_assets", "illiquid_assets"]
    melted = tidy.melt(
        id_vars=["date", "scenario_id", "scenario_name"],
        value_vars=asset_cols,
        var_name="asset_type",
        value_name="value",
    )

    # Create small multiples
    fig = px.area(
        melted,
        x="date",
        y="value",
        color="asset_type",
        facet_row="scenario_name",
        title="Asset Composition Over Time",
        labels={"value": "Asset Value", "date": "Date", "asset_type": "Asset Type"},
    )

    fig.update_layout(
        legend_title="Asset Type",
        height=300
        * len(tidy["scenario_name"].nunique()),  # Adjust height for multiple scenarios
    )

    # Reverse legend order for better stacking
    fig.update_layout(legend_traceorder="reversed")

    return fig, melted


def liabilities_amortization(tidy: pd.DataFrame) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot liabilities amortization over time.

    Args:
        tidy: DataFrame from Entity.compare() with liabilities column

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    fig = px.area(
        tidy,
        x="date",
        y="liabilities",
        color="scenario_name",
        title="Liabilities Amortization Over Time",
        labels={"liabilities": "Liabilities", "date": "Date"},
    )

    fig.update_layout(hovermode="x unified", legend_title="Scenario")

    return fig, tidy


def liquidity_runway_heatmap(
    tidy: pd.DataFrame, runway_data: pd.DataFrame
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot liquidity runway as a heatmap with threshold bands.

    Args:
        tidy: DataFrame from Entity.compare()
        runway_data: DataFrame from Entity.liquidity_runway()

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    # Create heatmap data
    heatmap_data = runway_data.pivot_table(
        index="scenario_name",
        columns="date",
        values="liquidity_runway_months",
        aggfunc="last",
    )

    fig = go.Figure(
        data=go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            colorscale=[
                [0.0, "red"],  # < 3 months
                [0.33, "orange"],  # 3-6 months
                [0.67, "yellow"],  # 6-12 months
                [1.0, "green"],  # > 12 months
            ],
            zmin=0,
            zmax=12,
            colorbar={"title": "Months of Runway"},
        )
    )

    fig.update_layout(
        title="Liquidity Runway Heatmap",
        xaxis_title="Date",
        yaxis_title="Scenario",
        height=400,
    )

    # Add threshold annotations (no overlapping lines)
    fig.add_annotation(
        x=0.02,
        y=0.98,
        xref="paper",
        yref="paper",
        text="< 3 months: Red<br/>3-6 months: Orange<br/>6-12 months: Yellow<br/>> 12 months: Green",
        showarrow=False,
        bgcolor="white",
        bordercolor="black",
        borderwidth=1,
    )

    return fig, runway_data


def cumulative_fees_taxes(
    tidy: pd.DataFrame, summary_data: pd.DataFrame
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot cumulative fees and taxes at different horizons.

    Args:
        tidy: DataFrame from Entity.compare()
        summary_data: DataFrame from Entity.fees_taxes_summary()

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    # Create grouped bar chart
    fig = go.Figure()

    # Add fees bars
    fig.add_trace(
        go.Bar(
            name="Cumulative Fees",
            x=summary_data["scenario_name"],
            y=summary_data["cumulative_fees"],
            marker_color="red",
            opacity=0.7,
        )
    )

    # Add taxes bars
    fig.add_trace(
        go.Bar(
            name="Cumulative Taxes",
            x=summary_data["scenario_name"],
            y=summary_data["cumulative_taxes"],
            marker_color="blue",
            opacity=0.7,
        )
    )

    fig.update_layout(
        title="Cumulative Fees & Taxes by Scenario",
        xaxis_title="Scenario",
        yaxis_title="Cumulative Amount",
        barmode="group",
        legend_title="Type",
    )

    return fig, summary_data


def net_worth_drawdown(tidy: pd.DataFrame) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot net worth drawdown (peak-to-trough) for each scenario.

    Args:
        tidy: DataFrame from Entity.compare() with net_worth column

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    # Calculate drawdown for each scenario
    drawdown_data = []

    for scenario_name in tidy["scenario_name"].unique():
        scenario_data = tidy[tidy["scenario_name"] == scenario_name].copy()
        scenario_data = scenario_data.sort_values("date")

        # Calculate running maximum and drawdown
        scenario_data["peak"] = scenario_data["net_worth"].cummax()
        # Guard against division by zero
        scenario_data["drawdown"] = np.where(
            scenario_data["peak"] > 0,
            (scenario_data["net_worth"] - scenario_data["peak"])
            / scenario_data["peak"]
            * 100,
            0.0,
        )

        drawdown_data.append(scenario_data)

    drawdown_df = pd.concat(drawdown_data, ignore_index=True)

    fig = px.line(
        drawdown_df,
        x="date",
        y="drawdown",
        color="scenario_name",
        title="Net Worth Drawdown (%)",
        labels={"drawdown": "Drawdown (%)", "date": "Date"},
    )

    fig.update_layout(
        hovermode="x unified", legend_title="Scenario", yaxis_title="Drawdown (%)"
    )

    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

    return fig, drawdown_df


# =============================================================================
# Scenario-level charts (deep-dive analysis)
# =============================================================================


def cashflow_waterfall(
    tidy: pd.DataFrame, scenario_name: str | None = None
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot annual cashflow waterfall for a single scenario.

    Args:
        tidy: DataFrame from Entity.compare()
        scenario_name: Name of scenario to analyze. If None, uses first scenario.

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    if scenario_name is None:
        scenario_name = tidy["scenario_name"].iloc[0]

    scenario_data = tidy[tidy["scenario_name"] == scenario_name].copy()
    scenario_data = scenario_data.sort_values("date")

    # Aggregate to annual data
    scenario_data["year"] = pd.to_datetime(scenario_data["date"]).dt.year
    annual_data = (
        scenario_data.groupby("year")
        .agg({"inflows": "sum", "outflows": "sum", "taxes": "sum", "fees": "sum"})
        .reset_index()
    )

    # Create waterfall components
    waterfall_data = []
    running_total = 0

    for _, row in annual_data.iterrows():
        year = row["year"]
        inflows = row["inflows"]
        taxes = row["taxes"]
        fees = row["fees"]
        outflows = row["outflows"]

        # Add inflow
        waterfall_data.append(
            {
                "year": year,
                "category": "Inflows",
                "amount": inflows,
                "running_total": running_total + inflows,
            }
        )
        running_total += inflows

        # Subtract taxes
        waterfall_data.append(
            {
                "year": year,
                "category": "Taxes",
                "amount": -taxes,
                "running_total": running_total - taxes,
            }
        )
        running_total -= taxes

        # Subtract fees
        waterfall_data.append(
            {
                "year": year,
                "category": "Fees",
                "amount": -fees,
                "running_total": running_total - fees,
            }
        )
        running_total -= fees

        # Subtract outflows
        waterfall_data.append(
            {
                "year": year,
                "category": "Outflows",
                "amount": -outflows,
                "running_total": running_total - outflows,
            }
        )
        running_total -= outflows

    waterfall_df = pd.DataFrame(waterfall_data)

    fig = go.Figure()

    colors = {"Inflows": "green", "Taxes": "red", "Fees": "orange", "Outflows": "blue"}

    for category in waterfall_df["category"].unique():
        category_data = waterfall_df[waterfall_df["category"] == category]
        fig.add_trace(
            go.Bar(
                name=category,
                x=category_data["year"],
                y=category_data["amount"],
                marker_color=colors.get(category, "gray"),
            )
        )

    fig.update_layout(
        title=f"Cashflow Waterfall - {scenario_name}",
        xaxis_title="Year",
        yaxis_title="Amount",
        barmode="relative",
    )

    return fig, waterfall_df


def owner_equity_vs_property_mortgage(
    tidy: pd.DataFrame, scenario_name: str | None = None
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot owner equity vs property value vs mortgage balance.

    Args:
        tidy: DataFrame from Entity.compare()
        scenario_name: Name of scenario to analyze. If None, uses first scenario.

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    if scenario_name is None:
        scenario_name = tidy["scenario_name"].iloc[0]

    scenario_data = tidy[tidy["scenario_name"] == scenario_name].copy()
    scenario_data = scenario_data.sort_values("date")

    # This chart requires additional columns that may not be in canonical schema
    # For now, create a placeholder implementation
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            name="Total Assets",
            x=scenario_data["date"],
            y=scenario_data["total_assets"],
            mode="lines",
            line={"color": "blue"},
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Liabilities",
            x=scenario_data["date"],
            y=scenario_data["liabilities"],
            mode="lines",
            line={"color": "red"},
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Net Worth",
            x=scenario_data["date"],
            y=scenario_data["net_worth"],
            mode="lines",
            line={"color": "green"},
        )
    )

    fig.update_layout(
        title=f"Assets vs Liabilities - {scenario_name}",
        xaxis_title="Date",
        yaxis_title="Amount",
        hovermode="x unified",
    )

    return fig, scenario_data


def ltv_dsti_over_time(
    tidy: pd.DataFrame, scenario_name: str | None = None
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot LTV and DSTI over time (requires additional data not in canonical schema).

    Args:
        tidy: DataFrame from Entity.compare()
        scenario_name: Name of scenario to analyze. If None, uses first scenario.

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    if scenario_name is None:
        scenario_name = tidy["scenario_name"].iloc[0]

    scenario_data = tidy[tidy["scenario_name"] == scenario_name].copy()
    scenario_data = scenario_data.sort_values("date")

    # Create subplots
    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=["LTV (Loan-to-Value)", "DSTI (Debt Service to Income)"],
        vertical_spacing=0.1,
    )

    # Placeholder implementation - would need actual LTV/DSTI data
    fig.add_trace(
        go.Scatter(
            name="LTV",
            x=scenario_data["date"],
            y=scenario_data["liabilities"]
            / scenario_data["total_assets"].clip(lower=1)
            * 100,
            mode="lines",
            line={"color": "red"},
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            name="DSTI",
            x=scenario_data["date"],
            y=scenario_data["outflows"] / scenario_data["inflows"].clip(lower=1) * 100,
            mode="lines",
            line={"color": "blue"},
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        title=f"LTV & DSTI Over Time - {scenario_name}", height=600, showlegend=False
    )

    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="LTV (%)", row=1, col=1)
    fig.update_yaxes(title_text="DSTI (%)", row=2, col=1)

    return fig, scenario_data


def contribution_vs_market_growth(
    tidy: pd.DataFrame, scenario_name: str | None = None
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot contribution vs market growth decomposition.

    Args:
        tidy: DataFrame from Entity.compare()
        scenario_name: Name of scenario to analyze. If None, uses first scenario.

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    if scenario_name is None:
        scenario_name = tidy["scenario_name"].iloc[0]

    scenario_data = tidy[tidy["scenario_name"] == scenario_name].copy()
    scenario_data = scenario_data.sort_values("date")

    # Calculate net cash flow (contributions)
    scenario_data["net_contribution"] = (
        scenario_data["inflows"] - scenario_data["outflows"]
    )
    scenario_data["net_worth_change"] = scenario_data["net_worth"].diff()
    scenario_data["market_growth"] = (
        scenario_data["net_worth_change"] - scenario_data["net_contribution"]
    )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            name="Net Contributions",
            x=scenario_data["date"],
            y=scenario_data["net_contribution"],
            mode="lines",
            line={"color": "blue"},
            stackgroup="one",
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Market Growth",
            x=scenario_data["date"],
            y=scenario_data["market_growth"],
            mode="lines",
            line={"color": "green"},
            stackgroup="one",
        )
    )

    fig.update_layout(
        title=f"Contribution vs Market Growth - {scenario_name}",
        xaxis_title="Date",
        yaxis_title="Net Worth Change",
        hovermode="x unified",
    )

    return fig, scenario_data


# =============================================================================
# MacroBrick-level charts
# =============================================================================


def category_allocation_over_time(
    tidy: pd.DataFrame, scenario_name: str | None = None
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot category allocation over time as stacked area chart.

    This chart shows how assets are allocated across different categories
    (housing, investing, income, insurance, other) over time.

    Args:
        tidy: DataFrame from Entity.compare()
        scenario_name: Name of scenario to analyze. If None, uses first scenario.

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    if scenario_name is None:
        scenario_name = tidy["scenario_name"].iloc[0]

    scenario_data = tidy[tidy["scenario_name"] == scenario_name].copy()
    scenario_data = scenario_data.sort_values("date")

    # Create category allocation data
    # For now, we'll use the canonical schema fields as proxies for categories
    allocation_df = pd.DataFrame(
        {
            "date": scenario_data["date"],
            "Cash": scenario_data["cash"],
            "Liquid Assets": scenario_data["liquid_assets"],
            "Illiquid Assets": scenario_data["illiquid_assets"],
            "Liabilities": -scenario_data["liabilities"],  # Negative for stacked area
        }
    )

    # Melt for stacked area chart
    melted = allocation_df.melt(
        id_vars=["date"], var_name="category", value_name="value"
    )

    fig = px.area(
        melted,
        x="date",
        y="value",
        color="category",
        title=f"Category Allocation Over Time - {scenario_name}",
        labels={"value": "Amount", "date": "Date", "category": "Category"},
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Amount",
        hovermode="x unified",
    )

    return fig, melted


def category_cashflow_bars(
    tidy: pd.DataFrame, scenario_name: str | None = None
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot category cashflow bars per year.

    Shows inflow/outflow per year per category to quickly spot cost centers.

    Args:
        tidy: DataFrame from Entity.compare()
        scenario_name: Name of scenario to analyze. If None, uses first scenario.

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    if scenario_name is None:
        scenario_name = tidy["scenario_name"].iloc[0]

    scenario_data = tidy[tidy["scenario_name"] == scenario_name].copy()
    scenario_data = scenario_data.sort_values("date")

    # Create yearly aggregation
    scenario_data["year"] = scenario_data["date"].dt.year
    yearly_data = (
        scenario_data.groupby("year")
        .agg(
            {
                "inflows": "sum",
                "outflows": "sum",
                "taxes": "sum",
                "fees": "sum",
            }
        )
        .reset_index()
    )

    # Melt for grouped bar chart
    cashflow_df = yearly_data.melt(
        id_vars=["year"],
        value_vars=["inflows", "outflows", "taxes", "fees"],
        var_name="category",
        value_name="amount",
    )

    # Color mapping
    colors = {
        "inflows": "green",
        "outflows": "red",
        "taxes": "orange",
        "fees": "purple",
    }

    fig = go.Figure()

    for category in cashflow_df["category"].unique():
        category_data = cashflow_df[cashflow_df["category"] == category]
        fig.add_trace(
            go.Bar(
                name=category.title(),
                x=category_data["year"],
                y=category_data["amount"],
                marker_color=colors.get(category, "gray"),
            )
        )

    fig.update_layout(
        title=f"Category Cashflows Per Year - {scenario_name}",
        xaxis_title="Year",
        yaxis_title="Amount",
        barmode="group",
    )

    return fig, cashflow_df


# =============================================================================
# FinBrick-level charts
# =============================================================================


def event_timeline(
    tidy: pd.DataFrame, scenario_name: str | None = None
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot event timeline for FinBricks.

    Shows buys, sells, prepayments, resets, and other events over time.
    This is a placeholder implementation since events are not yet in the canonical schema.

    Args:
        tidy: DataFrame from Entity.compare()
        scenario_name: Name of scenario to analyze. If None, uses first scenario.

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    if scenario_name is None:
        scenario_name = tidy["scenario_name"].iloc[0]

    scenario_data = tidy[tidy["scenario_name"] == scenario_name].copy()
    scenario_data = scenario_data.sort_values("date")

    # Create mock event data for demonstration
    # In a real implementation, this would come from the scenario's event history
    events_data = []

    # Add some mock events based on cashflow patterns
    for i, row in scenario_data.iterrows():
        if i > 0:  # Skip first row
            prev_row = scenario_data.iloc[i - 1]

            # Detect significant cashflow changes as "events"
            if abs(row["inflows"] - prev_row["inflows"]) > 100:
                events_data.append(
                    {
                        "date": row["date"],
                        "event_type": "Income Change",
                        "amount": row["inflows"] - prev_row["inflows"],
                        "description": f"Inflow changed by {row['inflows'] - prev_row['inflows']:.0f}",
                    }
                )

            if abs(row["outflows"] - prev_row["outflows"]) > 100:
                events_data.append(
                    {
                        "date": row["date"],
                        "event_type": "Expense Change",
                        "amount": row["outflows"] - prev_row["outflows"],
                        "description": f"Outflow changed by {row['outflows'] - prev_row['outflows']:.0f}",
                    }
                )

    if not events_data:
        # Create a placeholder event if no events detected
        events_data = [
            {
                "date": scenario_data["date"].iloc[0],
                "event_type": "Scenario Start",
                "amount": 0,
                "description": "Scenario initialization",
            }
        ]

    events_df = pd.DataFrame(events_data)

    # Create timeline chart
    fig = go.Figure()

    # Color mapping for event types
    event_colors = {
        "Income Change": "green",
        "Expense Change": "red",
        "Scenario Start": "blue",
        "Property Purchase": "orange",
        "Investment": "purple",
        "Loan": "brown",
    }

    for event_type in events_df["event_type"].unique():
        type_data = events_df[events_df["event_type"] == event_type]
        fig.add_trace(
            go.Scatter(
                x=type_data["date"],
                y=[event_type] * len(type_data),
                mode="markers",
                marker={
                    "size": 10,
                    "color": event_colors.get(event_type, "gray"),
                },
                name=event_type,
                text=type_data["description"],
                hovertemplate="<b>%{text}</b><br>"
                + "Date: %{x}<br>"
                + "Event: %{y}<br>"
                + "<extra></extra>",
            )
        )

    fig.update_layout(
        title=f"Event Timeline - {scenario_name}",
        xaxis_title="Date",
        yaxis_title="Event Type",
        hovermode="closest",
    )

    return fig, events_df


def holdings_cost_basis(
    tidy: pd.DataFrame, scenario_name: str | None = None
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Plot holdings and cost basis over time.

    Shows units, average price, and unrealized P/L for assets.

    Args:
        tidy: DataFrame from Entity.compare()
        scenario_name: Name of scenario to analyze. If None, uses first scenario.

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    if scenario_name is None:
        scenario_name = tidy["scenario_name"].iloc[0]

    scenario_data = tidy[tidy["scenario_name"] == scenario_name].copy()
    scenario_data = scenario_data.sort_values("date")

    # Create mock holdings data based on liquid assets
    # In a real implementation, this would come from individual brick outputs
    holdings_df = pd.DataFrame(
        {
            "date": scenario_data["date"],
            "asset_type": "Liquid Assets",  # Placeholder
            "units": scenario_data["liquid_assets"] / 100,  # Mock units
            "avg_price": 100.0,  # Mock average price
            "market_value": scenario_data["liquid_assets"],
            "cost_basis": scenario_data["liquid_assets"]
            * 0.95,  # Mock cost basis (5% gain)
            "unrealized_pl": scenario_data["liquid_assets"] * 0.05,  # Mock 5% gain
        }
    )

    # Create subplot with secondary y-axis
    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=["Holdings Value", "Unrealized P&L"],
        vertical_spacing=0.1,
    )

    # Holdings value - add Cost Basis first (fill="tozeroy")
    fig.add_trace(
        go.Scatter(
            x=holdings_df["date"],
            y=holdings_df["cost_basis"],
            name="Cost Basis",
            line={"color": "red"},
            fill="tozeroy",
        ),
        row=1,
        col=1,
    )

    # Then Market Value (fill="tonexty" to Cost Basis)
    fig.add_trace(
        go.Scatter(
            x=holdings_df["date"],
            y=holdings_df["market_value"],
            name="Market Value",
            line={"color": "blue"},
            fill="tonexty",
        ),
        row=1,
        col=1,
    )

    # Unrealized P&L
    fig.add_trace(
        go.Scatter(
            x=holdings_df["date"],
            y=holdings_df["unrealized_pl"],
            name="Unrealized P&L",
            line={"color": "green"},
            fill="tonexty",
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        title=f"Holdings & Cost Basis - {scenario_name}",
        height=600,
        showlegend=True,
    )

    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Value", row=1, col=1)
    fig.update_yaxes(title_text="P&L", row=2, col=1)

    return fig, holdings_df


# =============================================================================
# Utility functions
# =============================================================================


def save_chart(fig: go.Figure, filename: str, format: str = "html") -> None:
    """
    Save chart to file.

    Args:
        fig: Plotly figure
        filename: Output filename
        format: Output format ('html', 'png', 'pdf', 'svg')
    """
    _check_plotly()

    if format == "html":
        fig.write_html(filename)
    elif format == "png":
        fig.write_image(filename, format="png")
    elif format == "pdf":
        fig.write_image(filename, format="pdf")
    elif format == "svg":
        fig.write_image(filename, format="svg")
    else:
        raise ValueError(f"Unsupported format: {format}")
