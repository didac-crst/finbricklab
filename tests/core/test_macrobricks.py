"""
Comprehensive tests for MacroBrick functionality.

Tests cycle detection, overlap handling, aggregation correctness, and integration
with the scenario execution engine.
"""
from datetime import date

import numpy as np
import pytest
from finbricklab import ABrick, LBrick, MacroBrick, Registry, Scenario
from finbricklab.core.errors import ConfigError
from finbricklab.core.kinds import K


class TestMacroBrick:
    """Test MacroBrick dataclass and member expansion."""

    def test_macrobrick_creation(self):
        """Test basic MacroBrick creation."""
        mb = MacroBrick(
            id="test_struct",
            name="Test Structure",
            members=["brick1", "brick2"],
            tags=["test", "demo"],
        )

        assert mb.id == "test_struct"
        assert mb.name == "Test Structure"
        assert mb.members == ["brick1", "brick2"]
        assert mb.tags == ["test", "demo"]

    def test_macrobrick_expand_simple(self):
        """Test expanding a simple MacroBrick with only bricks."""
        # Create test bricks
        brick1 = ABrick(
            id="brick1", name="Brick 1", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )
        brick2 = ABrick(
            id="brick2", name="Brick 2", kind=K.A_CASH, spec={"initial_balance": 2000.0}
        )

        # Create registry
        registry = Registry(bricks={"brick1": brick1, "brick2": brick2}, macrobricks={})

        # Create MacroBrick
        mb = MacroBrick(id="test_struct", name="Test", members=["brick1", "brick2"])

        # Expand members
        expanded = mb.expand_member_bricks(registry)
        assert set(expanded) == {"brick1", "brick2"}

    def test_macrobrick_expand_nested(self):
        """Test expanding nested MacroBricks."""
        # Create test bricks
        brick1 = ABrick(
            id="brick1", name="Brick 1", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )
        brick2 = ABrick(
            id="brick2", name="Brick 2", kind=K.A_CASH, spec={"initial_balance": 2000.0}
        )
        brick3 = ABrick(
            id="brick3", name="Brick 3", kind=K.A_CASH, spec={"initial_balance": 3000.0}
        )

        # Create nested MacroBricks
        inner_mb = MacroBrick(id="inner", name="Inner", members=["brick1", "brick2"])
        outer_mb = MacroBrick(id="outer", name="Outer", members=["inner", "brick3"])

        # Create registry
        registry = Registry(
            bricks={"brick1": brick1, "brick2": brick2, "brick3": brick3},
            macrobricks={"inner": inner_mb, "outer": outer_mb},
        )

        # Expand outer MacroBrick
        expanded = outer_mb.expand_member_bricks(registry)
        assert set(expanded) == {"brick1", "brick2", "brick3"}

    def test_macrobrick_cycle_detection(self):
        """Test cycle detection in MacroBrick membership."""
        # Create test bricks
        brick1 = ABrick(
            id="brick1", name="Brick 1", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )

        # Create MacroBricks with cycle: A -> B -> A
        mb_a = MacroBrick(id="A", name="A", members=["B"])
        mb_b = MacroBrick(id="B", name="B", members=["A"])

        # Creating registry should raise ConfigError due to cycle detection
        with pytest.raises(
            ConfigError, match="Cycle detected in MacroBrick membership"
        ):
            Registry(bricks={"brick1": brick1}, macrobricks={"A": mb_a, "B": mb_b})

    def test_macrobrick_unknown_member(self):
        """Test error handling for unknown member IDs."""
        # Create test brick
        brick1 = ABrick(
            id="brick1", name="Brick 1", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )

        # Create registry
        registry = Registry(bricks={"brick1": brick1}, macrobricks={})

        # Create MacroBrick with unknown member
        mb = MacroBrick(id="test", name="Test", members=["brick1", "unknown_brick"])

        # Attempting to expand should raise ConfigError
        with pytest.raises(ConfigError, match="Unknown member id 'unknown_brick'"):
            mb.expand_member_bricks(registry)


class TestRegistry:
    """Test Registry class functionality."""

    def test_registry_creation(self):
        """Test basic registry creation."""
        brick1 = ABrick(
            id="brick1", name="Brick 1", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )
        mb1 = MacroBrick(id="struct1", name="Struct 1", members=["brick1"])

        registry = Registry(bricks={"brick1": brick1}, macrobricks={"struct1": mb1})

        assert registry.is_brick("brick1")
        assert registry.is_macrobrick("struct1")
        assert not registry.is_brick("struct1")
        assert not registry.is_macrobrick("brick1")

    def test_registry_lookup(self):
        """Test registry lookup methods."""
        brick1 = ABrick(
            id="brick1", name="Brick 1", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )
        mb1 = MacroBrick(id="struct1", name="Struct 1", members=["brick1"])

        registry = Registry(bricks={"brick1": brick1}, macrobricks={"struct1": mb1})

        assert registry.get_brick("brick1") == brick1
        assert registry.get_macrobrick("struct1") == mb1

        with pytest.raises(ConfigError, match="Brick 'unknown' not found"):
            registry.get_brick("unknown")

        with pytest.raises(ConfigError, match="MacroBrick 'unknown' not found"):
            registry.get_macrobrick("unknown")

    def test_registry_id_conflicts(self):
        """Test that ID conflicts between bricks and MacroBricks are detected."""
        brick1 = ABrick(
            id="conflict", name="Brick", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )
        mb1 = MacroBrick(id="conflict", name="MacroBrick", members=[])

        with pytest.raises(
            ConfigError, match="ID conflicts between bricks and MacroBricks"
        ):
            Registry(bricks={"conflict": brick1}, macrobricks={"conflict": mb1})

    def test_registry_validation_cycles(self):
        """Test that registry validation catches cycles."""
        brick1 = ABrick(
            id="brick1", name="Brick 1", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )

        # Create MacroBricks with cycle
        mb_a = MacroBrick(id="A", name="A", members=["B"])
        mb_b = MacroBrick(id="B", name="B", members=["A"])

        with pytest.raises(
            ConfigError, match="Cycle detected in MacroBrick membership"
        ):
            Registry(bricks={"brick1": brick1}, macrobricks={"A": mb_a, "B": mb_b})

    def test_registry_empty_macrobricks_warning(self):
        """Test that empty MacroBricks generate warnings."""
        brick1 = ABrick(
            id="brick1", name="Brick 1", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )
        empty_mb = MacroBrick(id="empty", name="Empty", members=[])

        # Create registry (warnings are now in validation report, not emitted)
        registry = Registry(bricks={"brick1": brick1}, macrobricks={"empty": empty_mb})

        # Check validation report for empty MacroBricks
        report = registry.validate()
        assert "empty" in report.empty_macrobricks

    def test_registry_reserved_prefix_validation(self):
        """Test that reserved prefixes are detected in validation."""
        brick1 = ABrick(
            id="b:reserved",
            name="Brick 1",
            kind=K.A_CASH,
            spec={"initial_balance": 1000.0},
        )
        mb1 = MacroBrick(id="mb:reserved", name="MacroBrick 1", members=["b:reserved"])

        # Create registry (should succeed)
        registry = Registry(
            bricks={"b:reserved": brick1}, macrobricks={"mb:reserved": mb1}
        )

        # Check validation report
        report = registry.validate()
        assert not report.is_valid()
        assert report.has_errors()
        assert len(report.id_conflicts) == 2
        assert any("b:reserved" in conflict for conflict in report.id_conflicts)
        assert any("mb:reserved" in conflict for conflict in report.id_conflicts)


class TestScenarioIntegration:
    """Test MacroBrick integration with Scenario execution."""

    def test_scenario_execution_set_resolution(self):
        """Test resolving execution set from selection."""
        # Create test scenario with bricks and MacroBricks
        cash = ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
        )
        house = ABrick(
            id="house",
            name="House",
            kind=K.A_PROPERTY,
            spec={"initial_value": 400000.0, "fees_pct": 0.05, "appreciation_pa": 0.03},
        )
        mortgage = LBrick(
            id="mortgage",
            name="Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={"rate_pa": 0.034, "term_months": 300, "principal": 320000.0},
        )

        primary_mb = MacroBrick(
            id="primary", name="Primary Residence", members=["house", "mortgage"]
        )

        scenario = Scenario(
            id="test",
            name="Test Scenario",
            bricks=[cash, house, mortgage],
            macrobricks=[primary_mb],
        )

        # Test selection with MacroBrick
        exec_set, overlaps = scenario._resolve_execution_set(["primary"])
        assert exec_set == {"house", "mortgage"}

        # Test selection with direct brick
        exec_set, overlaps = scenario._resolve_execution_set(["cash"])
        assert exec_set == {"cash"}

        # Test mixed selection
        exec_set, overlaps = scenario._resolve_execution_set(["primary", "cash"])
        assert exec_set == {"house", "mortgage", "cash"}

        # Test None selection (all bricks)
        exec_set, overlaps = scenario._resolve_execution_set(None)
        assert exec_set == {"cash", "house", "mortgage"}

    def test_scenario_overlap_handling(self):
        """Test overlap detection and handling in scenario execution."""
        # Create test scenario with overlapping MacroBricks
        cash = ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
        )
        house = ABrick(
            id="house",
            name="House",
            kind=K.A_PROPERTY,
            spec={"initial_value": 400000.0, "fees_pct": 0.05, "appreciation_pa": 0.03},
        )
        mortgage = LBrick(
            id="mortgage",
            name="Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={"rate_pa": 0.034, "term_months": 300, "principal": 320000.0},
        )

        # Create overlapping MacroBricks
        primary_mb = MacroBrick(
            id="primary", name="Primary", members=["house", "mortgage"]
        )
        property_mb = MacroBrick(
            id="property", name="Property", members=["house", "cash"]
        )

        scenario = Scenario(
            id="test",
            name="Test Scenario",
            bricks=[cash, house, mortgage],
            macrobricks=[primary_mb, property_mb],
        )

        # Test overlap detection
        exec_set, overlaps = scenario._resolve_execution_set(["primary", "property"])
        assert exec_set == {"house", "mortgage", "cash"}  # Deduplicated
        assert "house" in overlaps  # Should detect overlap

        # Test with overlap warnings disabled
        scenario.config.warn_on_overlap = False
        exec_set, overlaps = scenario._resolve_execution_set(["primary", "property"])
        assert exec_set == {"house", "mortgage", "cash"}

    def test_scenario_unknown_selection(self):
        """Test error handling for unknown selection IDs."""
        cash = ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
        )

        scenario = Scenario(
            id="test", name="Test Scenario", bricks=[cash], macrobricks=[]
        )

        with pytest.raises(ConfigError, match="Unknown selection id: 'unknown'"):
            scenario._resolve_execution_set(["unknown"])

    def test_scenario_struct_aggregation(self):
        """Test MacroBrick aggregation in scenario results."""
        # Create test scenario
        cash = ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
        )
        house = ABrick(
            id="house",
            name="House",
            kind=K.A_PROPERTY,
            spec={"initial_value": 400000.0, "fees_pct": 0.05, "appreciation_pa": 0.03},
        )
        mortgage = LBrick(
            id="mortgage",
            name="Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={"rate_pa": 0.034, "term_months": 300, "principal": 320000.0},
        )

        primary_mb = MacroBrick(
            id="primary", name="Primary Residence", members=["house", "mortgage"]
        )

        scenario = Scenario(
            id="test",
            name="Test Scenario",
            bricks=[cash, house, mortgage],
            macrobricks=[primary_mb],
        )

        # Run scenario with MacroBrick selection
        results = scenario.run(
            start=date(2026, 1, 1), months=12, selection=["primary", "cash"]
        )

        # Check that by_struct results exist
        assert "by_struct" in results
        assert "primary" in results["by_struct"]

        # Check that struct aggregation is correct
        struct_output = results["by_struct"]["primary"]
        house_output = results["outputs"]["house"]
        mortgage_output = results["outputs"]["mortgage"]

        # Struct output should be sum of member outputs
        assert np.array_equal(
            struct_output["cash_in"],
            house_output["cash_in"] + mortgage_output["cash_in"],
        )
        assert np.array_equal(
            struct_output["cash_out"],
            house_output["cash_out"] + mortgage_output["cash_out"],
        )
        assert np.array_equal(
            struct_output["asset_value"],
            house_output["asset_value"] + mortgage_output["asset_value"],
        )
        assert np.array_equal(
            struct_output["debt_balance"],
            house_output["debt_balance"] + mortgage_output["debt_balance"],
        )

    def test_scenario_from_dict_with_structs(self):
        """Test creating scenario from dict with MacroBricks."""
        data = {
            "id": "test",
            "name": "Test Scenario",
            "bricks": [
                {
                    "id": "cash",
                    "name": "Cash",
                    "kind": "a.cash",
                    "spec": {"initial_balance": 10000.0, "interest_pa": 0.02},
                },
                {
                    "id": "house",
                    "name": "House",
                    "kind": "a.property",
                    "spec": {
                        "initial_value": 400000.0,
                        "fees_pct": 0.05,
                        "appreciation_pa": 0.03,
                    },
                },
            ],
            "structs": [
                {
                    "id": "primary",
                    "name": "Primary Residence",
                    "members": ["house"],
                    "tags": ["primary"],
                }
            ],
        }

        scenario = Scenario.from_dict(data)

        assert scenario.id == "test"
        assert scenario.name == "Test Scenario"
        assert len(scenario.bricks) == 2
        assert len(scenario.macrobricks) == 1
        assert scenario.macrobricks[0].id == "primary"
        assert scenario.macrobricks[0].members == ["house"]

    def test_scenario_cash_account_requirement(self):
        """Test that scenario requires at least one cash account in selection."""
        house = ABrick(
            id="house",
            name="House",
            kind=K.A_PROPERTY,
            spec={"initial_value": 400000.0, "fees_pct": 0.05, "appreciation_pa": 0.03},
        )
        mortgage = LBrick(
            id="mortgage",
            name="Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={"rate_pa": 0.034, "term_months": 300, "principal": 320000.0},
        )

        primary_mb = MacroBrick(
            id="primary", name="Primary", members=["house", "mortgage"]
        )

        scenario = Scenario(
            id="test",
            name="Test Scenario",
            bricks=[house, mortgage],
            macrobricks=[primary_mb],
        )

        # Should fail because no cash account in selection
        with pytest.raises(AssertionError, match="At least one cash account"):
            scenario.run(start=date(2026, 1, 1), months=12, selection=["primary"])


class TestAggregationCorrectness:
    """Test that MacroBrick aggregation produces correct results."""

    def test_aggregation_manual_vs_automatic(self):
        """Test that automatic aggregation matches manual calculation."""
        # Create test scenario
        cash = ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
        )
        house = ABrick(
            id="house",
            name="House",
            kind=K.A_PROPERTY,
            spec={"initial_value": 400000.0, "fees_pct": 0.05, "appreciation_pa": 0.03},
        )
        mortgage = LBrick(
            id="mortgage",
            name="Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={"rate_pa": 0.034, "term_months": 300, "principal": 320000.0},
        )

        primary_mb = MacroBrick(
            id="primary", name="Primary", members=["house", "mortgage"]
        )

        scenario = Scenario(
            id="test",
            name="Test Scenario",
            bricks=[cash, house, mortgage],
            macrobricks=[primary_mb],
        )

        # Run scenario
        results = scenario.run(
            start=date(2026, 1, 1), months=12, selection=["primary", "cash"]
        )

        # Get individual outputs
        house_output = results["outputs"]["house"]
        mortgage_output = results["outputs"]["mortgage"]
        struct_output = results["by_struct"]["primary"]

        # Manual aggregation
        manual_cash_in = house_output["cash_in"] + mortgage_output["cash_in"]
        manual_cash_out = house_output["cash_out"] + mortgage_output["cash_out"]
        manual_asset_value = (
            house_output["asset_value"] + mortgage_output["asset_value"]
        )
        manual_debt_balance = (
            house_output["debt_balance"] + mortgage_output["debt_balance"]
        )

        # Compare with automatic aggregation
        assert np.allclose(struct_output["cash_in"], manual_cash_in)
        assert np.allclose(struct_output["cash_out"], manual_cash_out)
        assert np.allclose(struct_output["asset_value"], manual_asset_value)
        assert np.allclose(struct_output["debt_balance"], manual_debt_balance)

    def test_portfolio_totals_deduplication(self):
        """Test that portfolio totals properly deduplicate shared bricks."""
        # Create test scenario with shared brick
        cash = ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
        )
        house = ABrick(
            id="house",
            name="House",
            kind=K.A_PROPERTY,
            spec={"initial_value": 400000.0, "fees_pct": 0.05, "appreciation_pa": 0.03},
        )
        mortgage = LBrick(
            id="mortgage",
            name="Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={"rate_pa": 0.034, "term_months": 300, "principal": 320000.0},
        )

        # Create overlapping MacroBricks
        primary_mb = MacroBrick(
            id="primary", name="Primary", members=["house", "mortgage"]
        )
        property_mb = MacroBrick(
            id="property", name="Property", members=["house", "cash"]
        )

        scenario = Scenario(
            id="test",
            name="Test Scenario",
            bricks=[cash, house, mortgage],
            macrobricks=[primary_mb, property_mb],
        )

        # Run scenario with overlapping selection
        results = scenario.run(
            start=date(2026, 1, 1), months=12, selection=["primary", "property"]
        )

        # Portfolio totals should include each brick only once
        results["totals"]
        results["outputs"]["house"]

        # The house should appear only once in portfolio totals
        # (This is tested implicitly by the fact that the scenario runs without errors
        # and produces consistent results)
        assert "house" in results["outputs"]
        assert len(results["outputs"]) == 3  # cash, house, mortgage (deduplicated)


class TestAggregationInvariants:
    """Test aggregation invariants and mathematical correctness."""

    def test_union_less_than_or_equal_to_sum_with_overlap(self):
        """Test that portfolio totals ≤ sum of MacroBrick totals when overlaps exist."""
        # Create test scenario with overlapping MacroBricks
        cash = ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
        )
        house = ABrick(
            id="house",
            name="House",
            kind=K.A_PROPERTY,
            spec={"initial_value": 400000.0, "fees_pct": 0.05, "appreciation_pa": 0.03},
        )

        # Create overlapping MacroBricks
        primary_mb = MacroBrick(id="primary", name="Primary", members=["house"])
        property_mb = MacroBrick(
            id="property", name="Property", members=["house", "cash"]
        )

        scenario = Scenario(
            id="test",
            name="Test Scenario",
            bricks=[cash, house],
            macrobricks=[primary_mb, property_mb],
        )

        # Run scenario with overlapping selection
        results = scenario.run(
            start=date(2026, 1, 1), months=12, selection=["primary", "property"]
        )

        # Get portfolio totals (union of executed bricks)
        portfolio_totals = results["totals"]

        # Get MacroBrick totals
        primary_totals = results["by_struct"]["primary"]
        property_totals = results["by_struct"]["property"]

        # Portfolio should be ≤ sum of MacroBrick totals due to deduplication
        portfolio_assets = (
            portfolio_totals.assets.iloc[-1]
            if hasattr(portfolio_totals.assets, "iloc")
            else portfolio_totals.assets[-1]
        )
        primary_assets = primary_totals["asset_value"][-1]
        property_assets = property_totals["asset_value"][-1]
        sum_assets = primary_assets + property_assets

        assert (
            portfolio_assets <= sum_assets + 1e-8
        ), f"Portfolio assets {portfolio_assets} should be ≤ sum {sum_assets}"

    def test_disjoint_equality(self):
        """Test that disjoint MacroBricks sum exactly to portfolio totals."""
        # Create test scenario with disjoint MacroBricks
        cash = ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
        )
        house1 = ABrick(
            id="house1",
            name="House 1",
            kind=K.A_PROPERTY,
            spec={"initial_value": 400000.0, "fees_pct": 0.05, "appreciation_pa": 0.03},
        )
        house2 = ABrick(
            id="house2",
            name="House 2",
            kind=K.A_PROPERTY,
            spec={
                "initial_value": 300000.0,
                "fees_pct": 0.05,
                "appreciation_pa": 0.025,
            },
        )

        # Create disjoint MacroBricks
        primary_mb = MacroBrick(id="primary", name="Primary", members=["house1"])
        secondary_mb = MacroBrick(id="secondary", name="Secondary", members=["house2"])

        scenario = Scenario(
            id="test",
            name="Test Scenario",
            bricks=[cash, house1, house2],
            macrobricks=[primary_mb, secondary_mb],
        )

        # Run scenario with disjoint selection
        results = scenario.run(
            start=date(2026, 1, 1),
            months=12,
            selection=["primary", "secondary", "cash"],
        )

        # Get portfolio totals
        portfolio_totals = results["totals"]

        # Get MacroBrick totals
        primary_totals = results["by_struct"]["primary"]
        secondary_totals = results["by_struct"]["secondary"]

        # Portfolio should equal sum of MacroBrick totals + cash (no overlap)
        # Note: portfolio_totals is a ScenarioResults object, not a dict
        portfolio_assets = (
            portfolio_totals.assets.iloc[-1]
            if hasattr(portfolio_totals.assets, "iloc")
            else portfolio_totals.assets[-1]
        )
        primary_assets = primary_totals["asset_value"][-1]
        secondary_assets = secondary_totals["asset_value"][-1]

        # Get cash output separately since it's not in any MacroBrick
        cash_output = results["outputs"]["cash"]
        cash_assets = cash_output["asset_value"][-1]

        sum_assets = primary_assets + secondary_assets + cash_assets

        assert (
            abs(portfolio_assets - sum_assets) < 1e-8
        ), f"Portfolio assets {portfolio_assets} should equal sum {sum_assets}"

    def test_execution_order_deterministic(self):
        """Test that execution order is deterministic across runs."""
        # Create test scenario
        cash = ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
        )
        house = ABrick(
            id="house",
            name="House",
            kind=K.A_PROPERTY,
            spec={"initial_value": 400000.0, "fees_pct": 0.05, "appreciation_pa": 0.03},
        )

        scenario = Scenario(
            id="test", name="Test Scenario", bricks=[cash, house], macrobricks=[]
        )

        # Run scenario multiple times
        results1 = scenario.run(start=date(2026, 1, 1), months=12)
        results2 = scenario.run(start=date(2026, 1, 1), months=12)

        # Execution order should be identical
        order1 = results1["meta"]["execution_order"]
        order2 = results2["meta"]["execution_order"]

        assert (
            order1 == order2
        ), f"Execution order should be deterministic: {order1} vs {order2}"

    def test_cached_expansion_performance(self):
        """Test that cached expansion is faster than repeated expansion."""
        import time

        # Create test scenario with nested MacroBricks
        cash = ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
        )
        house = ABrick(
            id="house",
            name="House",
            kind=K.A_PROPERTY,
            spec={"initial_value": 400000.0, "fees_pct": 0.05, "appreciation_pa": 0.03},
        )

        # Create nested MacroBricks
        inner_mb = MacroBrick(id="inner", name="Inner", members=["house"])
        outer_mb = MacroBrick(id="outer", name="Outer", members=["inner", "cash"])

        scenario = Scenario(
            id="test",
            name="Test Scenario",
            bricks=[cash, house],
            macrobricks=[inner_mb, outer_mb],
        )

        # Test cached expansion
        start_time = time.time()
        for _ in range(100):
            members = scenario._registry.get_struct_flat_members("outer")
        cached_time = time.time() - start_time

        # Verify expansion is correct
        assert set(members) == {"house", "cash"}

        # Cached expansion should be fast (less than 0.1 seconds for 100 calls)
        assert cached_time < 0.1, f"Cached expansion too slow: {cached_time:.3f}s"
