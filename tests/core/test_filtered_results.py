"""
Tests for filtered results functionality in ScenarioResults.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest
from finbricklab.core.entity import Entity
from finbricklab.core.kinds import K
from finbricklab.core.results import ScenarioResults, _compute_filtered_totals


def _create_test_scenario():
    """Create a test scenario with multiple bricks and a MacroBrick."""
    e = Entity(id="test_entity", name="Test Entity")

    # Create bricks
    e.new_ABrick("cash", "Cash Account", K.A_CASH, {"initial_balance": 10000.0})
    e.new_ABrick(
        "etf",
        "ETF Investment",
        K.A_SECURITY_UNITIZED,
        {"initial_units": 100.0, "price_series": [100.0, 101.0, 102.0, 103.0, 104.0]},
    )
    e.new_LBrick(
        "mortgage",
        "Mortgage",
        K.L_LOAN_ANNUITY,
        {"rate_pa": 0.034, "term_months": 300, "principal": 300000.0},
    )
    e.new_FBrick(
        "salary",
        "Salary",
        K.F_INCOME_RECURRING,
        {"amount_monthly": 5000.0},
        links={"route": {"to": "cash"}},
    )
    e.new_FBrick(
        "rent",
        "Rent",
        K.F_EXPENSE_RECURRING,
        {"amount_monthly": 1500.0},
        links={"route": {"from": "cash"}},
    )

    # Create MacroBrick
    e.new_MacroBrick("investments", "Investment Portfolio", ["etf"])
    e.new_MacroBrick("housing", "Housing", ["mortgage"])

    # Create scenario
    scenario = e.create_scenario(
        "test_scenario",
        "Test Scenario",
        brick_ids=["cash", "etf", "mortgage", "salary", "rent"],
        macrobrick_ids=["investments", "housing"],
        settlement_default_cash_id="cash",
    )

    return e, scenario


def test_filter_with_brick_ids_only():
    """Test filtering with brick_ids only."""
    e, scenario = _create_test_scenario()

    # Run scenario
    results = scenario.run(start=date(2026, 1, 1), months=4)

    # Filter to only cash and salary
    filtered_view = results["views"].filter(brick_ids=["cash", "salary"])

    # Check that we get a new ScenarioResults object
    assert isinstance(filtered_view, ScenarioResults)
    assert filtered_view is not results["views"]  # Different object

    # Check monthly data
    monthly = filtered_view.monthly()
    assert isinstance(monthly, pd.DataFrame)
    assert len(monthly) == 4  # 4 months

    # Check that we have the expected columns
    expected_cols = [
        "cash_in",
        "cash_out",
        "net_cf",
        "assets",
        "liabilities",
        "non_cash",
        "equity",
        "cash",
    ]
    for col in expected_cols:
        assert col in monthly.columns

    # Check quarterly aggregation works
    quarterly = filtered_view.quarterly()
    assert isinstance(quarterly, pd.DataFrame)
    assert len(quarterly) == 2  # 2 quarters for 4 months

    # Check yearly aggregation works
    yearly = filtered_view.yearly()
    assert isinstance(yearly, pd.DataFrame)
    assert len(yearly) == 1  # 1 year for 4 months


def test_filter_with_macrobrick_ids_only():
    """Test filtering with macrobrick_ids only."""
    e, scenario = _create_test_scenario()

    # Run scenario
    results = scenario.run(start=date(2026, 1, 1), months=4)

    # Filter to only investments MacroBrick (which contains etf)
    filtered_view = results["views"].filter(macrobrick_ids=["investments"])

    # Check that we get a new ScenarioResults object
    assert isinstance(filtered_view, ScenarioResults)

    # Check monthly data
    monthly = filtered_view.monthly()
    assert isinstance(monthly, pd.DataFrame)
    assert len(monthly) == 4

    # The investments MacroBrick should only include the ETF
    # So we should see asset_value from ETF but no cash flows
    assert "assets" in monthly.columns
    assert "cash_in" in monthly.columns
    assert "cash_out" in monthly.columns


def test_filter_with_both_brick_and_macrobrick_ids():
    """Test filtering with both brick_ids and macrobrick_ids."""
    e, scenario = _create_test_scenario()

    # Run scenario
    results = scenario.run(start=date(2026, 1, 1), months=4)

    # Filter to cash brick and investments MacroBrick
    filtered_view = results["views"].filter(
        brick_ids=["cash"], macrobrick_ids=["investments"]
    )

    # Check that we get a new ScenarioResults object
    assert isinstance(filtered_view, ScenarioResults)

    # Check monthly data
    monthly = filtered_view.monthly()
    assert isinstance(monthly, pd.DataFrame)
    assert len(monthly) == 4

    # Should include both cash and ETF (from investments MacroBrick)
    expected_cols = [
        "cash_in",
        "cash_out",
        "net_cf",
        "assets",
        "liabilities",
        "non_cash",
        "equity",
        "cash",
    ]
    for col in expected_cols:
        assert col in monthly.columns


def test_filter_empty_selection():
    """Test filtering with no selection returns empty results."""
    e, scenario = _create_test_scenario()

    # Run scenario
    results = scenario.run(start=date(2026, 1, 1), months=4)

    # Filter with no selection
    filtered_view = results["views"].filter(brick_ids=[], macrobrick_ids=[])

    # Check that we get a new ScenarioResults object
    assert isinstance(filtered_view, ScenarioResults)

    # Check monthly data should be all zeros
    monthly = filtered_view.monthly()
    assert isinstance(monthly, pd.DataFrame)
    assert len(monthly) == 4

    # All values should be zero
    for col in [
        "cash_in",
        "cash_out",
        "net_cf",
        "assets",
        "liabilities",
        "non_cash",
        "equity",
        "cash",
    ]:
        if col in monthly.columns:
            assert (monthly[col] == 0).all()


def test_filter_validation_errors():
    """Test that filter raises appropriate errors when registry/outputs missing."""
    # Create ScenarioResults without registry and outputs
    empty_df = pd.DataFrame(
        {
            "cash_in": [0, 0, 0, 0],
            "cash_out": [0, 0, 0, 0],
            "net_cf": [0, 0, 0, 0],
            "assets": [0, 0, 0, 0],
            "liabilities": [0, 0, 0, 0],
            "non_cash": [0, 0, 0, 0],
            "equity": [0, 0, 0, 0],
            "cash": [0, 0, 0, 0],
        },
        index=pd.PeriodIndex(["2026-01", "2026-02", "2026-03", "2026-04"], freq="M"),
    )

    views = ScenarioResults(empty_df)  # No registry or outputs

    # Should raise RuntimeError when trying to filter
    with pytest.raises(
        RuntimeError, match="Cannot filter: missing registry or outputs"
    ):
        views.filter(brick_ids=["cash"])


def test_filtered_totals_match_manual_calculation():
    """Test that filtered totals match manual summation of selected bricks."""
    e, scenario = _create_test_scenario()

    # Run scenario
    results = scenario.run(start=date(2026, 1, 1), months=4)

    # Get individual brick outputs
    cash_output = results["outputs"]["cash"]
    salary_output = results["outputs"]["salary"]

    # Filter to cash and salary
    filtered_view = results["views"].filter(brick_ids=["cash", "salary"])
    filtered_monthly = filtered_view.monthly()

    # Manually calculate expected totals
    expected_cash_in = cash_output["cash_in"] + salary_output["cash_in"]
    expected_cash_out = cash_output["cash_out"] + salary_output["cash_out"]
    expected_assets = cash_output["asset_value"] + salary_output["asset_value"]
    expected_liabilities = cash_output["debt_balance"] + salary_output["debt_balance"]

    # Check that filtered results match manual calculation
    np.testing.assert_array_almost_equal(filtered_monthly["cash_in"], expected_cash_in)
    np.testing.assert_array_almost_equal(
        filtered_monthly["cash_out"], expected_cash_out
    )
    np.testing.assert_array_almost_equal(filtered_monthly["assets"], expected_assets)
    np.testing.assert_array_almost_equal(
        filtered_monthly["liabilities"], expected_liabilities
    )


def test_filter_with_include_cash_false():
    """Test filtering with include_cash=False."""
    e, scenario = _create_test_scenario()

    # Run scenario
    results = scenario.run(start=date(2026, 1, 1), months=4)

    # Filter to cash brick but exclude cash column
    filtered_view = results["views"].filter(brick_ids=["cash"], include_cash=False)

    # Check monthly data
    monthly = filtered_view.monthly()
    assert isinstance(monthly, pd.DataFrame)

    # Should not have cash column
    assert "cash" not in monthly.columns

    # But should have other columns
    expected_cols = [
        "cash_in",
        "cash_out",
        "net_cf",
        "assets",
        "liabilities",
        "non_cash",
        "equity",
    ]
    for col in expected_cols:
        assert col in monthly.columns


def test_filter_preserves_time_aggregation_methods():
    """Test that filtered views support all time aggregation methods."""
    e, scenario = _create_test_scenario()

    # Run scenario
    results = scenario.run(start=date(2026, 1, 1), months=12)

    # Filter to a subset
    filtered_view = results["views"].filter(brick_ids=["cash", "salary"])

    # Test all aggregation methods
    monthly = filtered_view.monthly()
    quarterly = filtered_view.quarterly()
    yearly = filtered_view.yearly()
    custom_freq = filtered_view.to_freq("Q")

    # Check that all return DataFrames
    assert isinstance(monthly, pd.DataFrame)
    assert isinstance(quarterly, pd.DataFrame)
    assert isinstance(yearly, pd.DataFrame)
    assert isinstance(custom_freq, pd.DataFrame)

    # Check that quarterly and custom_freq are the same
    pd.testing.assert_frame_equal(quarterly, custom_freq)

    # Check that yearly has fewer rows than quarterly
    assert len(yearly) <= len(quarterly)
    assert len(quarterly) <= len(monthly)


def test_compute_filtered_totals_helper():
    """Test the _compute_filtered_totals helper function directly."""
    # Create mock data
    t_index = pd.PeriodIndex(["2026-01", "2026-02", "2026-03"], freq="M")

    outputs = {
        "brick1": {
            "cash_in": np.array([100, 200, 300]),
            "cash_out": np.array([50, 100, 150]),
            "asset_value": np.array([1000, 1100, 1200]),
            "debt_balance": np.array([0, 0, 0]),
            "events": [],
        },
        "brick2": {
            "cash_in": np.array([0, 0, 0]),
            "cash_out": np.array([25, 50, 75]),
            "asset_value": np.array([0, 0, 0]),
            "debt_balance": np.array([500, 450, 400]),
            "events": [],
        },
    }

    # Test with both bricks
    result = _compute_filtered_totals(
        outputs, {"brick1", "brick2"}, t_index, True, set()
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 3
    assert "cash_in" in result.columns
    assert "cash_out" in result.columns
    assert "assets" in result.columns
    assert "liabilities" in result.columns

    # Check that values are summed correctly
    expected_cash_in = np.array([100, 200, 300])  # Only brick1 has cash_in
    expected_cash_out = np.array([75, 150, 225])  # brick1 + brick2
    expected_assets = np.array([1000, 1100, 1200])  # Only brick1 has assets
    expected_liabilities = np.array([500, 450, 400])  # Only brick2 has debt

    np.testing.assert_array_almost_equal(result["cash_in"], expected_cash_in)
    np.testing.assert_array_almost_equal(result["cash_out"], expected_cash_out)
    np.testing.assert_array_almost_equal(result["assets"], expected_assets)
    np.testing.assert_array_almost_equal(result["liabilities"], expected_liabilities)


def test_compute_filtered_totals_empty_selection():
    """Test _compute_filtered_totals with empty selection."""
    t_index = pd.PeriodIndex(["2026-01", "2026-02"], freq="M")

    outputs = {
        "brick1": {
            "cash_in": np.array([100, 200]),
            "cash_out": np.array([50, 100]),
            "asset_value": np.array([1000, 1100]),
            "debt_balance": np.array([0, 0]),
            "events": [],
        }
    }

    # Test with empty selection
    result = _compute_filtered_totals(
        outputs, set(), t_index, True, set()  # Empty selection
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2

    # All values should be zero
    for col in [
        "cash_in",
        "cash_out",
        "net_cf",
        "assets",
        "liabilities",
        "non_cash",
        "equity",
        "cash",
    ]:
        if col in result.columns:
            assert (result[col] == 0).all()


def test_filter_with_nonexistent_brick_ids():
    """Test filtering with brick IDs that don't exist in outputs."""
    e, scenario = _create_test_scenario()

    # Run scenario
    results = scenario.run(start=date(2026, 1, 1), months=4)

    # Filter with non-existent brick ID
    filtered_view = results["views"].filter(brick_ids=["nonexistent_brick"])

    # Should return empty results (all zeros)
    monthly = filtered_view.monthly()
    assert isinstance(monthly, pd.DataFrame)
    assert len(monthly) == 4

    # All values should be zero
    for col in [
        "cash_in",
        "cash_out",
        "net_cf",
        "assets",
        "liabilities",
        "non_cash",
        "equity",
        "cash",
    ]:
        if col in monthly.columns:
            assert (monthly[col] == 0).all()
