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
            "non_cash": [50200, 51300],
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


def test_owner_equity_and_mortgage_balance_forwarded():
    """Optional property columns should be forwarded when present."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-31", periods=2, freq="ME"),
            "cash": [1000.0, 1200.0],
            "liquid_assets": [500.0, 550.0],
            "property_value": [200000.0, 205000.0],
            "owner_equity": [60000.0, 65000.0],
            "mortgage_balance": [140000.0, 140500.0],
            "liabilities": [140000.0, 140500.0],
            "inflows": [0.0, 0.0],
            "outflows": [0.0, 0.0],
            "taxes": [0.0, 0.0],
            "fees": [0.0, 0.0],
        }
    ).set_index("date")

    scen = _mk_scenario(df)
    scen._last_totals = df

    cf = scen.to_canonical_frame()

    pd.testing.assert_series_equal(
        cf["owner_equity"],
        pd.Series([60000.0, 65000.0], name="owner_equity"),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        cf["mortgage_balance"],
        pd.Series([140000.0, 140500.0], name="mortgage_balance"),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        cf["property_value"],
        pd.Series([200000.0, 205000.0], name="property_value"),
        check_names=False,
    )


def test_optional_columns_default_to_zero():
    """Optional columns should default to zero when missing."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-31", periods=3, freq="ME"),
            "cash": [100.0, 110.0, 120.0],
            "liquid_assets": [50.0, 60.0, 70.0],
            "liabilities": [20.0, 25.0, 30.0],
            "inflows": [10.0, 12.0, 14.0],
            "outflows": [8.0, 9.0, 10.0],
            "taxes": [1.0, 1.0, 1.0],
            "fees": [0.5, 0.5, 0.5],
        }
    ).set_index("date")

    scen = _mk_scenario(df)
    scen._last_totals = df

    cf = scen.to_canonical_frame()
    for col in ("property_value", "owner_equity", "mortgage_balance"):
        assert col in cf.columns
        assert (cf[col] == 0.0).all()


def test_fees_and_taxes_forwarded():
    """Fees and taxes in totals should carry into canonical schema."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-31", periods=2, freq="ME"),
            "cash": [1000.0, 900.0],
            "liquid_assets": [0.0, 0.0],
            "illiquid_assets": [0.0, 0.0],
            "liabilities": [0.0, 0.0],
            "inflows": [100.0, 100.0],
            "outflows": [80.0, 80.0],
            "taxes": [5.0, 6.0],
            "fees": [3.0, 4.0],
        }
    ).set_index("date")

    scen = _mk_scenario(df)
    scen._last_totals = df

    cf = scen.to_canonical_frame()
    pd.testing.assert_series_equal(
        cf["taxes"], pd.Series([5.0, 6.0], name="taxes"), check_names=False
    )
    pd.testing.assert_series_equal(
        cf["fees"], pd.Series([3.0, 4.0], name="fees"), check_names=False
    )


def test_property_splits_non_cash_and_net_worth():
    """Non-cash assets split into liquid + property while preserving net worth."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-31", periods=3, freq="ME"),
            "cash": [100.0, 120.0, 150.0],
            "non_cash": [300.0, 320.0, 350.0],
            "property_value": [200.0, 210.0, 220.0],
            "liabilities": [80.0, 85.0, 90.0],
            "interest": [5.0, 5.5, 6.0],
            "inflows": [0.0, 0.0, 0.0],
            "outflows": [0.0, 0.0, 0.0],
            "taxes": [0.0, 0.0, 0.0],
            "fees": [0.0, 0.0, 0.0],
        }
    ).set_index("date")

    scen = _mk_scenario(df)
    scen._last_totals = df

    cf = scen.to_canonical_frame()

    expected_liquid = (
        (df["non_cash"] - df["property_value"]).clip(lower=0.0).reset_index(drop=True)
    )
    expected_illiquid = df["property_value"].reset_index(drop=True)

    pd.testing.assert_series_equal(
        cf["liquid_assets"], expected_liquid, check_names=False
    )
    pd.testing.assert_series_equal(
        cf["illiquid_assets"], expected_illiquid, check_names=False
    )

    total_assets = cf["cash"] + cf["liquid_assets"] + cf["illiquid_assets"]
    pd.testing.assert_series_equal(
        total_assets,
        (df["cash"] + df["non_cash"]).reset_index(drop=True),
        check_names=False,
    )

    expected_net_worth = total_assets - cf["liabilities"]
    pd.testing.assert_series_equal(
        cf["net_worth"], expected_net_worth, check_names=False
    )
    pd.testing.assert_series_equal(
        cf["interest"],
        df["interest"].reset_index(drop=True),
        check_names=False,
    )
