"""
Smoke tests to verify basic imports and functionality.
"""

import pytest
from datetime import date

def test_import_finbricklab():
    """Test that we can import the main package."""
    import finbricklab
    assert hasattr(finbricklab, '__version__')
    assert finbricklab.__version__ == "0.1.0"

def test_import_finscenlab_compatibility():
    """Test that the compatibility shim works."""
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        import finscenlab
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "deprecated" in str(w[0].message)

def test_import_core_components():
    """Test that core components can be imported."""
    from finbricklab import (
        Scenario, ABrick, LBrick, FBrick,
        ScenarioContext, BrickOutput, Event,
        wire_strategies, validate_run
    )
    assert Scenario is not None
    assert ABrick is not None
    assert LBrick is not None
    assert FBrick is not None

def test_import_strategies():
    """Test that strategies can be imported."""
    from finbricklab import strategies
    assert strategies is not None

def test_basic_scenario_creation():
    """Test that we can create a basic scenario."""
    from finbricklab import Scenario, ABrick
    
    cash = ABrick(
        id="cash",
        name="Main Cash",
        kind="a.cash",
        spec={"initial_balance": 1000.0, "interest_pa": 0.02}
    )
    
    scenario = Scenario(
        id="test",
        name="Test Scenario",
        bricks=[cash]
    )
    
    assert scenario.id == "test"
    assert len(scenario.bricks) == 1
    assert scenario.bricks[0].id == "cash"
