"""Tests for canonical schema mapping functionality."""


import pandas as pd
import pytest
from finbricklab.core.scenario import Scenario


def _mk_scenario(df):
    """Create minimal scenario stub for testing."""
    return Scenario(id="test_scenario", name="test_scenario", bricks=[], currency="EUR")


def test_maps_property_value_to_illiquid_assets():
    """Test that property_value is correctly mapped to illiquid_assets."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-31", periods=2, freq="ME"),
            "cash": [1000, 1000],
            "non_cash": [200, 300],
            "property_value": [50000, 51000],
            "liabilities": [0, 0],
            "inflows": [0, 0],
            "outflows": [0, 0],
            "taxes": [0, 0],
            "fees": [0, 0],
        }
    )
    df.set_index("date", inplace=True)

    scen = _mk_scenario(df)
    # Mock the _last_totals to simulate a completed scenario
    scen._last_totals = df

    cf = scen.to_canonical_frame()
    assert (cf["illiquid_assets"] == pd.Series([50000, 51000], index=cf.index)).all()
    assert (cf["liquid_assets"] == pd.Series([200, 300], index=cf.index)).all()


def test_no_property_value_sets_illiquid_zero():
    """Test that illiquid_assets defaults to 0 when property_value is missing."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-31", periods=2, freq="ME"),
            "cash": [1000, 1000],
            "non_cash": [200, 300],
            "liabilities": [0, 0],
            "inflows": [0, 0],
            "outflows": [0, 0],
            "taxes": [0, 0],
            "fees": [0, 0],
        }
    )
    df.set_index("date", inplace=True)

    scen = _mk_scenario(df)
    scen._last_totals = df

    cf = scen.to_canonical_frame()
    assert (cf["illiquid_assets"] == 0.0).all()


def test_negative_property_value_raises():
    """Test that negative property_value raises ValueError."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-31", periods=1, freq="ME"),
            "cash": [1000],
            "property_value": [-1.0],
            "liabilities": [0.0],
            "inflows": [0.0],
            "outflows": [0.0],
            "taxes": [0.0],
            "fees": [0.0],
        }
    )
    df.set_index("date", inplace=True)

    scen = _mk_scenario(df)
    scen._last_totals = df

    with pytest.raises(ValueError, match="property_value contains negative entries"):
        scen.to_canonical_frame()


def test_canonical_dtypes_enforced():
    """Test that canonical frame enforces correct dtypes."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-31", periods=1, freq="ME"),
            "cash": [1000],
            "non_cash": [200],
            "property_value": [50000],
            "liabilities": [0],
            "inflows": [0],
            "outflows": [0],
            "taxes": [0],
            "fees": [0],
        }
    )
    df.set_index("date", inplace=True)

    scen = _mk_scenario(df)
    scen._last_totals = df

    cf = scen.to_canonical_frame()

    # Check that numeric columns are float64
    numeric_cols = [
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
    ]
    for col in numeric_cols:
        if col in cf.columns:
            assert (
                cf[col].dtype == "float64"
            ), f"Column {col} should be float64, got {cf[col].dtype}"
