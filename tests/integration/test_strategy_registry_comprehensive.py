"""
Comprehensive tests for strategy registry alignment and transfer functionality.
"""

from datetime import date

import pytest
from finbricklab import Entity
from finbricklab.core.bricks import FlowRegistry, ScheduleRegistry, ValuationRegistry
from finbricklab.core.kinds import K


class TestStrategyRegistryAlignment:
    """Test that all registered strategies align with the new kind taxonomy."""

    def test_all_registered_keys_are_valid_kinds(self):
        """Ensure all registered keys belong to the new taxonomy."""
        valid_kinds = set(K.all_kinds())

        for registry in (ValuationRegistry, ScheduleRegistry, FlowRegistry):
            for key in registry.keys():
                assert key in valid_kinds, f"Registry key '{key}' not in K.all_kinds()"

    def test_no_legacy_kinds_registered(self):
        """Ensure no legacy kind names remain in registries."""
        legacy_kinds = {
            "a.etf_unitized",
            "a.property_discrete",
            "f.income.fixed",
            "f.expense.fixed",
            "l.mortgage.annuity",
        }

        for registry in (ValuationRegistry, ScheduleRegistry, FlowRegistry):
            for key in registry.keys():
                assert key not in legacy_kinds, f"Legacy kind '{key}' still registered"

    def test_all_new_kinds_have_strategies(self):
        """Ensure all new kinds have corresponding strategies."""
        # These are the kinds we expect to have strategies for
        expected_kinds = {
            K.A_CASH,
            K.A_SECURITY_UNITIZED,
            K.A_PROPERTY,
            K.L_LOAN_ANNUITY,
            K.F_INCOME_RECURRING,
            K.F_EXPENSE_RECURRING,
            K.F_INCOME_ONE_TIME,
            K.F_EXPENSE_ONE_TIME,
            K.T_TRANSFER_RECURRING,
            K.T_TRANSFER_LUMP_SUM,
            K.T_TRANSFER_SCHEDULED,
        }

        all_registered = set()
        for registry in (ValuationRegistry, ScheduleRegistry, FlowRegistry):
            all_registered.update(registry.keys())

        for kind in expected_kinds:
            assert kind in all_registered, f"Expected kind '{kind}' not registered"

    def test_kind_prefix_semantics(self):
        """Test that kind prefixes match their registry assignments."""
        # Assets should be in ValuationRegistry
        for kind in [K.A_CASH, K.A_SECURITY_UNITIZED, K.A_PROPERTY]:
            assert (
                kind in ValuationRegistry
            ), f"Asset kind '{kind}' not in ValuationRegistry"
            assert kind.split(".")[0] == "a"

        # Liabilities should be in ScheduleRegistry
        for kind in [K.L_LOAN_ANNUITY]:
            assert (
                kind in ScheduleRegistry
            ), f"Liability kind '{kind}' not in ScheduleRegistry"
            assert kind.split(".")[0] == "l"

        # Flows and Transfers should be in FlowRegistry
        for kind in [
            K.F_INCOME_RECURRING,
            K.F_EXPENSE_RECURRING,
            K.F_INCOME_ONE_TIME,
            K.F_EXPENSE_ONE_TIME,
        ]:
            assert kind in FlowRegistry, f"Flow kind '{kind}' not in FlowRegistry"
            assert kind.split(".")[0] == "f"

        for kind in [
            K.T_TRANSFER_RECURRING,
            K.T_TRANSFER_LUMP_SUM,
            K.T_TRANSFER_SCHEDULED,
        ]:
            assert kind in FlowRegistry, f"Transfer kind '{kind}' not in FlowRegistry"
            assert kind.split(".")[0] == "t"


class TestTransferBalance:
    """Test that transfer strategies are properly registered and can be instantiated."""

    def test_transfer_strategies_registered(self):
        """Test that transfer strategies are properly registered."""
        from finbricklab.core.bricks import FlowRegistry

        # Check that transfer strategies are registered
        assert K.T_TRANSFER_RECURRING in FlowRegistry
        assert K.T_TRANSFER_LUMP_SUM in FlowRegistry
        assert K.T_TRANSFER_SCHEDULED in FlowRegistry

        # Check that they are the correct types
        assert hasattr(FlowRegistry[K.T_TRANSFER_RECURRING], "simulate")
        assert hasattr(FlowRegistry[K.T_TRANSFER_LUMP_SUM], "simulate")
        assert hasattr(FlowRegistry[K.T_TRANSFER_SCHEDULED], "simulate")

    def test_transfer_brick_creation(self):
        """Test that transfer bricks can be created with proper parameters."""
        entity = Entity(id="test", name="Test Entity")

        # Create two cash accounts
        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 1000.0}
        )
        entity.new_ABrick(
            "savings", "Savings Account", K.A_CASH, {"initial_balance": 5000.0}
        )

        # Create a lump sum transfer (just test creation, not execution)
        transfer = entity.new_TBrick(
            "transfer_test",
            "Test Transfer",
            K.T_TRANSFER_LUMP_SUM,
            {"amount": 1000.0},
            links={"from": "savings", "to": "checking"},
        )

        # Verify the transfer brick was created correctly
        assert transfer.id == "transfer_test"
        assert transfer.kind == K.T_TRANSFER_LUMP_SUM
        assert transfer.links["from"] == "savings"
        assert transfer.links["to"] == "checking"
        assert transfer.spec["amount"] == 1000.0


class TestOnetimeFlows:
    """Test the new onetime flow strategies."""

    def test_income_onetime_strategy(self):
        """Test that onetime income flows work correctly."""
        entity = Entity(id="test", name="Test Entity")

        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 1000.0}
        )

        # Create onetime income (bonus)
        entity.new_FBrick(
            "bonus",
            "Year-end Bonus",
            K.F_INCOME_ONE_TIME,
            start_date=date(2026, 6, 1),  # June bonus
            spec={"amount": 5000.0},
        )

        scenario = entity.create_scenario(
            id="bonus_scenario",
            name="Bonus Test",
            brick_ids=["checking", "bonus"],
            settlement_default_cash_id="checking",
        )

        results = scenario.run(start=date(2026, 1, 1), months=12)

        # V2: Use journal-first aggregation instead of totals
        monthly = results["views"].monthly()

        # V2: Check journal entries for one-time income
        journal = results["journal"]
        income_entries = [
            e for e in journal.entries if e.metadata.get("transaction_type") == "income"
        ]
        # V2: Income entries may not have brick_id set, check by parent_id
        # Filter for entries that match the bonus (one-time income in June)
        # parent_id format is "fs:bonus" for one-time income
        bonus_entries = [
            e
            for e in income_entries
            if "bonus" in e.metadata.get("parent_id", "")
            or e.metadata.get("brick_id") == "bonus"
        ]
        assert len(bonus_entries) >= 1, "Should have at least one bonus income entry"

        # V2: Check monthly aggregation for income
        # Month 0 (January) cash balance reflects opening amount; opening deposit excluded from cash_in
        assert monthly["cash"].iloc[0] == pytest.approx(
            1000.0, rel=1e-6
        ), "Month 0 cash balance should equal opening balance"
        assert monthly["cash_in"].iloc[0] == pytest.approx(
            0.0, abs=1e-9
        ), "Month 0 cash_in should not include opening balance"
        assert (
            monthly["cash_in"].iloc[5] == 5000.0
        ), "June (month 5) should have bonus income"

        # Other months (except 0 and 5) should have no income
        for i in range(12):
            if i not in (0, 5):
                assert (
                    monthly["cash_in"].iloc[i] == 0.0
                ), f"Month {i} should have no income"

    def test_expense_onetime_strategy(self):
        """Test that onetime expense flows work correctly."""
        entity = Entity(id="test", name="Test Entity")

        entity.new_ABrick(
            "checking", "Checking Account", K.A_CASH, {"initial_balance": 10000.0}
        )

        # Create onetime expense (major purchase)
        entity.new_FBrick(
            "car_purchase",
            "Car Purchase",
            K.F_EXPENSE_ONE_TIME,
            {"amount": 25000.0, "date": "2026-03-15"},  # March purchase
        )

        scenario = entity.create_scenario(
            id="purchase_scenario",
            name="Purchase Test",
            brick_ids=["checking", "car_purchase"],
            settlement_default_cash_id="checking",
        )

        results = scenario.run(start=date(2026, 1, 1), months=12)

        # Should have expense in March
        cash_out = results["totals"]["cash_out"]
        assert cash_out.iloc[2] == 25000.0  # March (0-indexed, so month 2)

        # Other months should have no expense
        for i in range(12):
            if i != 2:
                assert cash_out.iloc[i] == 0.0
