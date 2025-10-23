"""
Tests for MacroBrick expansion functionality.
"""

import pytest
from finbricklab import Entity, Scenario, ABrick, MacroBrick
from finbricklab.core.kinds import K
from finbricklab.core.exceptions import ScenarioValidationError


def mk_entity():
    """Create a test entity with basic bricks and MacroBricks."""
    e = Entity(id="e", name="E")
    e.new_ABrick("cash", "Cash", K.A_CASH, {"initial_balance": 1000.0})
    e.new_ABrick("etf", "ETF", K.A_SECURITY_UNITIZED,
                 {"initial_units": 10.0, "initial_price": 100.0, "drift_pa": 0.05})
    e.new_MacroBrick("liquid", "Liquid", ["cash", "etf"])
    return e


def test_expand_nested_and_dedupe():
    """Test that nested MacroBricks expand correctly with deduplication."""
    e = mk_entity()
    e.new_MacroBrick("portfolio", "Portfolio", ["liquid", "cash"])  # 'cash' duplicated
    s = e.create_scenario(id="s", name="S", brick_ids=["portfolio"])
    ids = [b.id for b in s.bricks]
    assert ids == ["cash", "etf"]  # order-preserving dedupe


def test_unknown_id_raises():
    """Test that unknown IDs raise appropriate errors."""
    e = mk_entity()
    with pytest.raises(ScenarioValidationError) as exc:
        e.create_scenario(id="s", name="S", brick_ids=["does_not_exist"])
    assert "Unknown id" in str(exc.value)


def test_cycle_detection():
    """Test that cycles in MacroBricks are detected."""
    e = mk_entity()
    # Create MacroBricks first, then add the cycle
    e.new_MacroBrick("A", "A", ["cash"])  # Start with valid member
    e.new_MacroBrick("B", "B", ["etf"])   # Start with valid member
    
    # Now create the cycle by updating the members
    e._macrobricks["A"].members = ["B"]
    e._macrobricks["B"].members = ["A"]
    
    # The cycle detection happens during registry creation
    from finbricklab.core.errors import ConfigError
    with pytest.raises(ConfigError) as exc:
        e.create_scenario(id="s", name="S", brick_ids=["A"])
    assert "Cycle detected in MacroBrick membership" in str(exc.value)


def test_equivalence_macro_vs_explicit():
    """Test that MacroBrick expansion produces equivalent results to explicit brick lists."""
    e = mk_entity()
    s1 = e.create_scenario(id="macro", name="Macro", brick_ids=["liquid"])
    s2 = e.create_scenario(id="flat", name="Flat", brick_ids=["cash", "etf"])
    
    # Both scenarios should have the same bricks
    assert len(s1.bricks) == len(s2.bricks)
    assert set(b.id for b in s1.bricks) == set(b.id for b in s2.bricks)


def test_mixed_brick_and_macro():
    """Test that mixed brick and MacroBrick references work correctly."""
    e = mk_entity()
    e.new_ABrick("bond", "Bond", K.A_SECURITY_UNITIZED, 
                 {"initial_units": 5.0, "initial_price": 200.0, "drift_pa": 0.03})
    
    s = e.create_scenario(id="mixed", name="Mixed", brick_ids=["bond", "liquid"])
    ids = [b.id for b in s.bricks]
    assert "bond" in ids
    assert "cash" in ids
    assert "etf" in ids


def test_deep_nesting():
    """Test that deeply nested MacroBricks work correctly."""
    e = mk_entity()
    e.new_MacroBrick("level1", "Level 1", ["cash"])
    e.new_MacroBrick("level2", "Level 2", ["level1"])
    e.new_MacroBrick("level3", "Level 3", ["level2"])
    
    s = e.create_scenario(id="deep", name="Deep", brick_ids=["level3"])
    ids = [b.id for b in s.bricks]
    assert ids == ["cash"]  # Should expand to just the cash brick


def test_max_depth_protection():
    """Test that extremely deep nesting is prevented."""
    e = mk_entity()
    
    # Create a very deep chain
    current = "cash"
    for i in range(70):  # Exceeds the 64-level limit
        next_id = f"level{i}"
        e.new_MacroBrick(next_id, f"Level {i}", [current])
        current = next_id
    
    with pytest.raises(ScenarioValidationError) as exc:
        e.create_scenario(id="deep", name="Deep", brick_ids=[current])
    assert "nesting too deep" in str(exc.value)


def test_empty_brick_ids():
    """Test that empty brick_ids list is handled gracefully."""
    e = mk_entity()
    s = e.create_scenario(id="empty", name="Empty", brick_ids=[])
    assert len(s.bricks) == 0


def test_macrobrick_preservation():
    """Test that MacroBricks are preserved for rollup analysis."""
    e = mk_entity()
    s = e.create_scenario(id="preserve", name="Preserve", brick_ids=["liquid"])
    
    # Should have the liquid MacroBrick for rollup analysis
    assert len(s.macrobricks) == 1
    assert s.macrobricks[0].id == "liquid"


def test_complex_nested_structure():
    """Test a complex nested MacroBrick structure."""
    e = mk_entity()
    e.new_ABrick("bond", "Bond", K.A_SECURITY_UNITIZED, 
                 {"initial_units": 5.0, "initial_price": 200.0, "drift_pa": 0.03})
    e.new_ABrick("property", "Property", K.A_PROPERTY, 
                 {"initial_value": 500000.0, "appreciation_pa": 0.03})
    
    e.new_MacroBrick("stocks", "Stocks", ["etf"])
    e.new_MacroBrick("bonds", "Bonds", ["bond"])
    e.new_MacroBrick("securities", "Securities", ["stocks", "bonds"])
    e.new_MacroBrick("assets", "Assets", ["securities", "property", "cash"])
    
    s = e.create_scenario(id="complex", name="Complex", brick_ids=["assets"])
    ids = [b.id for b in s.bricks]
    
    # Should include all constituent bricks
    expected = {"cash", "etf", "bond", "property"}
    assert set(ids) == expected
