"""
Tests for Entity-centric builder API.

This module tests the new Entity builder methods that allow creating
bricks, MacroBricks, and scenarios through the Entity class.
"""

from datetime import date

import pytest
from finbricklab.core.entity import Entity
from finbricklab.core.exceptions import ScenarioValidationError
from finbricklab.core.kinds import K
from finbricklab.core.links import RouteLink
from finbricklab.core.scenario import Scenario


class TestEntityBuilder:
    """Test Entity builder methods."""

    def test_entity_builder_minimal(self):
        """Test basic Entity builder functionality."""
        entity = Entity(id="person", name="John")

        # Create bricks
        entity.new_ABrick(
            id="checking",
            name="Checking",
            kind=K.A_CASH,
            spec={"initial_balance": 5000.0, "interest_pa": 0.02},
        )
        entity.new_FBrick(
            id="salary",
            name="Salary",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 6000.0},
            links={"route": {"to": "checking"}},
        )

        # Create MacroBrick
        entity.new_MacroBrick(id="portfolio", name="Portfolio", member_ids=["checking"])

        # Create scenario
        scenario = entity.create_scenario(
            id="base_case",
            name="Base Case",
            brick_ids=[
                "salary",
                "portfolio",
            ],  # mix of direct bricks and macrobrick expansion
            settlement_default_cash_id="checking",
        )

        # Run scenario
        results = scenario.run(start=date(2026, 1, 1), months=3)
        assert "totals" in results and not results["totals"].empty

    def test_deep_copy_isolation(self):
        """Test that deep copying prevents cross-scenario state bleed."""
        entity = Entity(id="person", name="John")

        # Create a brick with mutable spec
        entity.new_ABrick(
            id="cash",
            name="Cash",
            kind=K.A_CASH,
            spec={"initial_balance": 1000.0, "interest_pa": 0.02},
        )

        # Create first scenario
        scenario1 = entity.create_scenario(
            id="scenario1", name="Scenario 1", brick_ids=["cash"]
        )

        # Mutate the brick in the scenario
        scenario1.bricks[0].spec["initial_balance"] = 9999.0

        # Create second scenario
        scenario2 = entity.create_scenario(
            id="scenario2", name="Scenario 2", brick_ids=["cash"]
        )

        # Verify original entity brick is unchanged
        original_brick = entity.get_brick("cash")
        assert original_brick.spec["initial_balance"] == 1000.0

        # Verify scenario bricks are independent
        assert scenario1.bricks[0].spec["initial_balance"] == 9999.0
        assert scenario2.bricks[0].spec["initial_balance"] == 1000.0

    def test_macro_expansion(self):
        """Test MacroBrick expansion in scenarios."""
        entity = Entity(id="person", name="John")

        # Create individual bricks
        entity.new_ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )
        entity.new_ABrick(
            id="etf",
            name="ETF",
            kind=K.A_SECURITY_UNITIZED,
            spec={"initial_units": 100.0},
        )
        entity.new_FBrick(
            id="salary",
            name="Salary",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 5000.0},
        )

        # Create nested MacroBricks
        entity.new_MacroBrick(id="investments", name="Investments", member_ids=["etf"])
        entity.new_MacroBrick(
            id="portfolio", name="Portfolio", member_ids=["cash", "investments"]
        )

        # Create scenario using outer MacroBrick
        scenario = entity.create_scenario(
            id="nested_test",
            name="Nested Test",
            brick_ids=["salary", "portfolio"],  # salary is separate from portfolio
        )

        # Verify expansion includes all individual bricks
        brick_ids = {brick.id for brick in scenario.bricks}
        expected_ids = {"cash", "etf", "salary"}
        assert brick_ids == expected_ids

        # Verify MacroBrick definitions are preserved (including nested ones)
        macro_ids = {mb.id for mb in scenario.macrobricks}
        assert macro_ids == {
            "investments",
            "portfolio",
        }  # Both parent and child MacroBricks

    def test_auto_id_generation_for_entity_and_scenario(self):
        """Entity and Scenario derive IDs from names when omitted."""

        entity = Entity(id=None, name="Family Portfolio")
        assert entity.id == "family_portfolio"

        cash_brick = entity.new_ABrick(
            id=None,
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 1000.0},
        )

        scenario = entity.create_scenario(
            id=None,
            name="Retirement Strategy",
            brick_ids=[cash_brick.id],
            settlement_default_cash_id=cash_brick.id,
        )

        assert scenario.id == "retirement_strategy"
        assert scenario is entity.get_scenario("retirement_strategy")
        assert "retirement_strategy" in entity.list_scenarios()

        standalone = Scenario(id=None, name="Standalone Plan", bricks=[])
        assert standalone.id == "standalone_plan"

        macro = entity.new_MacroBrick(
            id=None, name="Savings Cluster", member_ids=[cash_brick.id]
        )
        assert macro.id == "savings_cluster"
        assert entity.get_macrobrick("savings_cluster") is macro

    def test_macrobrick_with_shell_bricks_executes_members(self):
        """MacroBricks can include shell bricks and execute them once."""

        entity = Entity(id="pkg", name="Package")
        entity.new_ABrick(
            id="checking",
            name="Checking",
            kind=K.A_CASH,
            spec={"initial_balance": 0.0},
        )
        entity.new_ABrick(
            id="savings",
            name="Savings",
            kind=K.A_CASH,
            spec={"initial_balance": 0.0},
        )
        entity.new_FBrick(
            id="salary",
            name="Salary",
            kind=K.F_INCOME_RECURRING,
            start_date=date(2026, 1, 1),
            spec={"amount_monthly": 5_000.0},
            links={"route": {"to": "checking"}},
        )
        entity.new_TBrick(
            id="auto_transfer",
            name="Auto Transfer",
            kind=K.T_TRANSFER_RECURRING,
            start_date=date(2026, 1, 1),
            spec={"amount": 1_000.0, "frequency": "MONTHLY"},
            links={"from": "checking", "to": "savings"},
        )

        entity.new_MacroBrick(
            id="cash_bundle",
            name="Cash Bundle",
            member_ids=["checking", "savings", "salary", "auto_transfer"],
        )

        scenario = entity.create_scenario(
            id="bundle_scenario",
            name="Bundle Scenario",
            brick_ids=["cash_bundle"],
            settlement_default_cash_id="checking",
        )

        results = scenario.run(start=date(2026, 1, 1), months=3)
        checking_view = results["views"].filter(brick_ids=["checking"]).monthly()
        savings_view = results["views"].filter(brick_ids=["savings"]).monthly()

        assert checking_view.loc["2026-01", "cash_in"] == pytest.approx(5_000.0)
        assert checking_view.loc["2026-01", "cash_out"] == pytest.approx(1_000.0)
        assert savings_view.loc["2026-01", "cash_in"] == pytest.approx(1_000.0)

    def test_macrobrick_overlap_deduplicates_shell_execution(self):
        """Overlapping MacroBricks share shell bricks without duplicate execution."""

        entity = Entity(id="pkg2", name="Package Two")
        entity.new_ABrick(
            id="primary_cash",
            name="Primary Cash",
            kind=K.A_CASH,
            spec={"initial_balance": 0.0},
        )
        entity.new_ABrick(
            id="reserve_cash",
            name="Reserve Cash",
            kind=K.A_CASH,
            spec={"initial_balance": 0.0},
        )
        entity.new_FBrick(
            id="salary",
            name="Salary",
            kind=K.F_INCOME_RECURRING,
            start_date=date(2026, 1, 1),
            spec={"amount_monthly": 4_000.0},
            links={"route": {"to": "primary_cash"}},
        )
        entity.new_TBrick(
            id="monthly_sweep",
            name="Monthly Sweep",
            kind=K.T_TRANSFER_RECURRING,
            start_date=date(2026, 1, 1),
            spec={"amount": 1_500.0, "frequency": "MONTHLY"},
            links={"from": "primary_cash", "to": "reserve_cash"},
        )

        entity.new_MacroBrick(
            id="income_bundle",
            name="Income Bundle",
            member_ids=["primary_cash", "salary", "monthly_sweep"],
        )
        entity.new_MacroBrick(
            id="reserve_bundle",
            name="Reserve Bundle",
            member_ids=["reserve_cash", "monthly_sweep"],
        )

        scenario = entity.create_scenario(
            id="overlap_scenario",
            name="Overlap Scenario",
            brick_ids=["income_bundle", "reserve_bundle"],
            settlement_default_cash_id="primary_cash",
        )

        results = scenario.run(start=date(2026, 1, 1), months=2)
        primary_view = results["views"].filter(brick_ids=["primary_cash"]).monthly()
        reserve_view = results["views"].filter(brick_ids=["reserve_cash"]).monthly()

        # Salary appears once, transfer executed once per month
        assert primary_view.loc["2026-01", "cash_in"] == pytest.approx(4_000.0)
        assert primary_view.loc["2026-01", "cash_out"] == pytest.approx(1_500.0)
        assert reserve_view.loc["2026-01", "cash_in"] == pytest.approx(1_500.0)

    def test_validation_error_handling(self):
        """Test validation error handling with detailed error information."""
        entity = Entity(id="person", name="John")

        # Create MacroBrick with non-existent member (this will fail Registry validation)
        entity.new_ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )

        # Create MacroBrick with invalid member reference
        with pytest.raises(ValueError, match="Member ID 'nonexistent' not found"):
            entity.new_MacroBrick(
                id="portfolio", name="Portfolio", member_ids=["cash", "nonexistent"]
            )

        # Test scenario creation with non-existent brick ID
        with pytest.raises(ScenarioValidationError) as exc_info:
            entity.create_scenario(
                id="invalid_scenario",
                name="Invalid Scenario",
                brick_ids=["nonexistent_brick"],
            )

        error = exc_info.value
        assert error.scenario_id == "invalid_scenario"
        assert "nonexistent_brick" in error.problem_ids

    def test_unique_id_enforcement(self):
        """Test that duplicate IDs are rejected."""
        entity = Entity(id="person", name="John")

        # Create first brick
        entity.new_ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )

        # Attempt to create brick with same ID should fail
        with pytest.raises(ValueError, match="ID 'cash' already exists in catalog"):
            entity.new_ABrick(
                id="cash",
                name="Another Cash",
                kind=K.A_CASH,
                spec={"initial_balance": 2000.0},
            )

        # Same for MacroBrick
        entity.new_MacroBrick(id="portfolio", name="Portfolio", member_ids=["cash"])

        with pytest.raises(
            ValueError, match="ID 'portfolio' already exists in catalog"
        ):
            entity.new_MacroBrick(
                id="portfolio", name="Another Portfolio", member_ids=["cash"]
            )

    def test_links_normalization(self):
        """Test that links are properly normalized to dict format."""
        entity = Entity(id="person", name="John")

        # Create brick with RouteLink object
        route_link = RouteLink(to="cash", from_=None)
        entity.new_FBrick(
            id="income",
            name="Income",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 5000.0},
            links=route_link,
        )

        # Verify links were normalized to dict
        brick = entity.get_brick("income")
        assert isinstance(brick.links, dict)
        assert brick.links == {"route": {"to": "cash", "from": None}}

        # Create brick with dict links
        entity.new_FBrick(
            id="expense",
            name="Expense",
            kind=K.F_EXPENSE_RECURRING,
            spec={"amount_monthly": 2000.0},
            links={"route": {"from": "cash"}},
        )

        # Verify dict links are preserved
        brick = entity.get_brick("expense")
        assert isinstance(brick.links, dict)
        assert brick.links == {"route": {"from": "cash"}}

    def test_catalog_helpers(self):
        """Test catalog helper methods."""
        entity = Entity(id="person", name="John")

        # Create various objects
        entity.new_ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )
        entity.new_FBrick(
            id="salary",
            name="Salary",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 5000.0},
        )
        entity.new_MacroBrick(id="portfolio", name="Portfolio", member_ids=["cash"])
        entity.create_scenario(id="test", name="Test", brick_ids=["cash", "salary"])

        # Test getters
        assert entity.get_brick("cash") is not None
        assert entity.get_brick("nonexistent") is None
        assert entity.get_macrobrick("portfolio") is not None
        assert entity.get_macrobrick("nonexistent") is None
        assert entity.get_scenario("test") is not None
        assert entity.get_scenario("nonexistent") is None

        # Test listers
        assert entity.list_bricks() == ["cash", "salary"]
        assert entity.list_macrobricks() == ["portfolio"]
        assert entity.list_scenarios() == ["test"]

    def test_scenario_duplicate_id(self):
        """Test that duplicate scenario IDs are rejected."""
        entity = Entity(id="person", name="John")

        entity.new_ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )

        # Create first scenario
        entity.create_scenario(id="test", name="Test", brick_ids=["cash"])

        # Attempt to create scenario with same ID should fail
        with pytest.raises(ValueError, match="Scenario ID 'test' already exists"):
            entity.create_scenario(id="test", name="Another Test", brick_ids=["cash"])

    def test_missing_member_validation(self):
        """Test validation of MacroBrick member IDs."""
        entity = Entity(id="person", name="John")

        # Attempt to create MacroBrick with non-existent member should fail
        with pytest.raises(ValueError, match="Member ID 'nonexistent' not found"):
            entity.new_MacroBrick(
                id="portfolio", name="Portfolio", member_ids=["nonexistent"]
            )

    def test_unknown_brick_id_in_scenario(self):
        """Test that unknown brick IDs in scenario creation are caught."""
        entity = Entity(id="person", name="John")

        # Attempt to create scenario with non-existent brick should fail
        with pytest.raises(ScenarioValidationError) as exc_info:
            entity.create_scenario(id="test", name="Test", brick_ids=["nonexistent"])

        error = exc_info.value
        assert error.scenario_id == "test"
        assert "nonexistent" in error.problem_ids

    def test_unknown_macrobrick_id_in_scenario(self):
        """Test that unknown MacroBrick IDs in scenario creation are caught."""
        entity = Entity(id="person", name="John")

        # Attempt to create scenario with non-existent MacroBrick should fail
        with pytest.raises(ScenarioValidationError) as exc_info:
            entity.create_scenario(id="test", name="Test", brick_ids=["nonexistent"])

        error = exc_info.value
        assert error.scenario_id == "test"
        assert "nonexistent" in error.problem_ids

    def test_mixed_brick_and_macrobrick_selection(self):
        """Test scenarios with both individual bricks and MacroBricks."""
        entity = Entity(id="person", name="John")

        # Create bricks
        entity.new_ABrick(
            id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 1000.0}
        )
        entity.new_ABrick(
            id="etf",
            name="ETF",
            kind=K.A_SECURITY_UNITIZED,
            spec={"initial_units": 100.0},
        )
        entity.new_FBrick(
            id="salary",
            name="Salary",
            kind=K.F_INCOME_RECURRING,
            spec={"amount_monthly": 5000.0},
        )

        # Create MacroBrick
        entity.new_MacroBrick(id="investments", name="Investments", member_ids=["etf"])

        # Create scenario with mixed selection
        scenario = entity.create_scenario(
            id="mixed",
            name="Mixed Scenario",
            brick_ids=[
                "cash",
                "salary",
                "investments",
            ],  # Individual bricks and MacroBrick
        )

        # Verify all expected bricks are included
        brick_ids = {brick.id for brick in scenario.bricks}
        expected_ids = {
            "cash",
            "salary",
            "etf",
        }  # etf comes from investments MacroBrick
        assert brick_ids == expected_ids

        # Verify MacroBrick is preserved
        macro_ids = {mb.id for mb in scenario.macrobricks}
        assert macro_ids == {"investments"}
