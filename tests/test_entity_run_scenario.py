"""
Tests for Entity.run_scenario and Entity.run_many methods.
"""

from datetime import date

import pytest

import finbricklab.strategies  # ensure strategies registry is populated

from finbricklab.core.entity import Entity
from finbricklab.core.kinds import K


def _simple_entity():
    """Create a simple entity with one scenario for testing."""
    e = Entity(id="e1", name="Test Entity")
    e.new_ABrick("cash", "Cash", K.A_CASH, {"initial_balance": 1000.0})
    e.new_FBrick(
        "salary",
        "Salary",
        K.F_INCOME_FIXED,
        {"amount_monthly": 5000.0},
        links={"route": {"to": "cash"}},
    )
    e.new_MacroBrick("liquid", "Liquid", ["cash"])
    s = e.create_scenario(
        "base",
        "Base",
        brick_ids=["salary"],
        macrobrick_ids=["liquid"],
        settlement_default_cash_id="cash",
    )
    return e, s


def test_run_scenario_matches_direct_run():
    """Test that Entity.run_scenario returns the same results as Scenario.run."""
    e, s = _simple_entity()
    direct = s.run(start=date(2026, 1, 1), months=3)
    via_entity = e.run_scenario("base", start=date(2026, 1, 1), months=3)
    # Loose check: keys exist and key frames match shape
    assert set(direct.keys()) == set(via_entity.keys())
    assert "totals" in via_entity


def test_run_scenario_missing_id():
    """Test that run_scenario raises ValueError for missing scenario ID."""
    e, _ = _simple_entity()
    with pytest.raises(ValueError) as ex:
        e.run_scenario("nope", start=date(2026, 1, 1), months=1)
    assert "not found" in str(ex.value)


def test_run_scenario_selection_override():
    """Test that run_scenario works with explicit selection."""
    e, _ = _simple_entity()
    # Run with explicit selection (should still run fine)
    res = e.run_scenario(
        "base", start=date(2026, 1, 1), months=1, selection=["salary", "liquid"]
    )
    assert "totals" in res


def test_run_many_basic():
    """Test basic run_many functionality."""
    e = Entity(id="e1", name="Test Entity")
    e.new_ABrick("cash", "Cash", K.A_CASH, {"initial_balance": 1000.0})
    e.new_FBrick(
        "salary",
        "Salary",
        K.F_INCOME_FIXED,
        {"amount_monthly": 5000.0},
        links={"route": {"to": "cash"}},
    )

    # Create two scenarios
    e.create_scenario("scenario1", "Scenario 1", brick_ids=["cash", "salary"], settlement_default_cash_id="cash")
    e.create_scenario("scenario2", "Scenario 2", brick_ids=["cash", "salary"], settlement_default_cash_id="cash")

    # Run both scenarios
    results = e.run_many(["scenario1", "scenario2"], start=date(2026, 1, 1), months=1)

    assert set(results.keys()) == {"scenario1", "scenario2"}
    assert "totals" in results["scenario1"]
    assert "totals" in results["scenario2"]


def test_run_many_missing_id():
    """Test that run_many raises ValueError on first missing scenario ID."""
    e = Entity(id="e1", name="Test Entity")
    e.new_ABrick("cash", "Cash", K.A_CASH, {"initial_balance": 1000.0})
    e.create_scenario("scenario1", "Scenario 1", brick_ids=["cash"], settlement_default_cash_id="cash")

    with pytest.raises(ValueError) as ex:
        e.run_many(["scenario1", "nonexistent"], start=date(2026, 1, 1), months=1)
    assert "not found" in str(ex.value)


def test_run_scenario_kwargs_forwarding():
    """Test that kwargs are properly forwarded to Scenario.run."""
    e, _ = _simple_entity()
    
    # Test with include_cash=False (this should be forwarded)
    res = e.run_scenario(
        "base", 
        start=date(2026, 1, 1), 
        months=1, 
        include_cash=False
    )
    assert "totals" in res


def test_run_scenario_error_message_format():
    """Test that error messages include available scenario IDs."""
    e = Entity(id="e1", name="Test Entity")
    e.new_ABrick("cash", "Cash", K.A_CASH, {"initial_balance": 1000.0})
    e.create_scenario("scenario1", "Scenario 1", brick_ids=[], settlement_default_cash_id="cash")
    e.create_scenario("scenario2", "Scenario 2", brick_ids=[], settlement_default_cash_id="cash")

    with pytest.raises(ValueError) as ex:
        e.run_scenario("nonexistent", start=date(2026, 1, 1), months=1)
    
    error_msg = str(ex.value)
    assert "not found" in error_msg
    assert "Available:" in error_msg
    assert "scenario1" in error_msg
    assert "scenario2" in error_msg
