"""
Unit tests for chart helpers covering enhanced behaviour.
"""

from __future__ import annotations

import importlib.util

import numpy as np
import pandas as pd
import pytest

plotly_available = importlib.util.find_spec("plotly") is not None


def _skip_if_no_plotly():
    return pytest.mark.skipif(
        not plotly_available, reason="Plotly is required for chart tests"
    )


@_skip_if_no_plotly()
def test_cumulative_fees_taxes_labels_and_filtering():
    from finbricklab.charts import cumulative_fees_taxes

    summary = pd.DataFrame(
        {
            "scenario_id": ["a1"],
            "scenario_name": ["Baseline"],
            "horizon_months": [12],
            "cumulative_fees": [120.0],
            "cumulative_taxes": [80.0],
        }
    )

    fig, filtered = cumulative_fees_taxes(pd.DataFrame(), summary)

    assert len(fig.data) == 2
    assert any("(12m)" in str(x) for x in fig.data[0].x)
    assert filtered["scenario_horizon"].iloc[0].endswith("(12m)")

    zero_summary = summary.assign(cumulative_fees=0.0, cumulative_taxes=0.0)
    empty_fig, empty_filtered = cumulative_fees_taxes(pd.DataFrame(), zero_summary)

    assert len(empty_fig.data) == 0
    assert empty_filtered.empty
    assert empty_fig.layout.annotations[0]["text"].startswith("No fees or taxes")


@_skip_if_no_plotly()
def test_category_allocation_over_time_liability_band():
    from finbricklab.charts import category_allocation_over_time

    tidy = pd.DataFrame(
        {
            "scenario_name": ["Scenario A"] * 3,
            "date": pd.date_range("2024-01-31", periods=3, freq="ME"),
            "cash": [100.0, 110.0, 120.0],
            "liquid_assets": [50.0, 60.0, 55.0],
            "illiquid_assets": [200.0, 205.0, 210.0],
            "liabilities": [80.0, 82.0, 79.0],
        }
    )

    fig, allocation = category_allocation_over_time(tidy)

    assert set(allocation["group"]) == {"asset", "liability"}
    liabilities = allocation[allocation["category"] == "Liabilities"]["value"]
    assert (liabilities <= 0).all()

    shapes = getattr(fig.layout, "shapes", [])
    assert any(getattr(shape, "y0", None) == 0 for shape in shapes)


@_skip_if_no_plotly()
def test_contribution_vs_market_growth_decomposition():
    from finbricklab.charts import contribution_vs_market_growth

    tidy = pd.DataFrame(
        {
            "scenario_name": ["Scenario A"] * 4,
            "date": pd.date_range("2024-01-31", periods=4, freq="ME"),
            "inflows": [100.0, 100.0, 100.0, 100.0],
            "outflows": [60.0, 60.0, 70.0, 65.0],
            "net_worth": [1000.0, 1035.0, 1060.0, 1080.0],
            "liabilities": [500.0, 495.0, 490.0, 480.0],
        }
    )

    fig, scenario_data = contribution_vs_market_growth(tidy)

    assert {"net_contribution", "market_growth", "principal_repayment"}.issubset(
        scenario_data.columns
    )
    assert np.isclose(scenario_data["principal_repayment"].iloc[0], 0.0)
    assert len(fig.data) == 3


@_skip_if_no_plotly()
def test_category_cashflow_bars_handles_zero_series():
    from finbricklab.charts import category_cashflow_bars

    tidy = pd.DataFrame(
        {
            "scenario_name": ["Scenario A", "Scenario A"],
            "date": pd.date_range("2024-01-31", periods=2, freq="ME"),
            "inflows": [0.0, 0.0],
            "outflows": [0.0, 0.0],
            "taxes": [0.0, 0.0],
            "fees": [0.0, 0.0],
        }
    )

    fig, melted = category_cashflow_bars(tidy)

    assert melted.empty or np.isclose(melted["amount"], 0.0).all()
    assert len(fig.data) == 0
    annotations = getattr(fig.layout, "annotations", [])
    assert annotations and "No cashflow activity" in annotations[0]["text"]
