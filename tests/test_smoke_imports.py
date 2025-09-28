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

def test_legacy_api_failures():
    """Test that legacy APIs properly fail with clear error messages."""
    from finbricklab import ABrick, LBrick
    from finbricklab.core.kinds import K
    
    # Test that old auto_principal_from fails
    with pytest.raises(AssertionError, match="Missing principal"):
        LBrick(
            id="mortgage",
            name="Test Mortgage",
            kind=K.L_MORT_ANN,
            links={"auto_principal_from": "house"},  # legacy format
            spec={"rate_pa": 0.03, "term_months": 300}
        )
    
    # Test that old property price fails
    with pytest.raises(AssertionError, match="Missing required parameter"):
        ABrick(
            id="house",
            name="Test House",
            kind=K.A_PROPERTY_DISCRETE,
            spec={"price": 100000, "fees_pct": 0.095, "appreciation_pa": 0.02}  # legacy price
        )

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
