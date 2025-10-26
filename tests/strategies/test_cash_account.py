"""
Tests for cash account valuation strategy.
"""

from datetime import date

import numpy as np
import pytest
from finbricklab import ABrick, ScenarioContext, month_range
from finbricklab.strategies.valuation.cash import ValuationCash


class TestValuationCash:
    """Test cash account valuation strategy."""

    def test_cash_prepare(self):
        """Test cash account preparation."""
        brick = ABrick(
            id="cash",
            name="Test Cash",
            kind="a.cash",
            spec={"initial_balance": 1000.0, "interest_pa": 0.02},
        )

        ctx = ScenarioContext(
            t_index=month_range(date(2026, 1, 1), 12), currency="EUR", registry={}
        )

        strategy = ValuationCash()
        strategy.prepare(brick, ctx)

        # Check defaults are set
        assert "initial_balance" in brick.spec
        assert "interest_pa" in brick.spec
        assert "external_in" in brick.spec
        assert "external_out" in brick.spec
        assert "overdraft_limit" in brick.spec
        assert "min_buffer" in brick.spec

        assert brick.spec["initial_balance"] == 1000.0
        assert brick.spec["interest_pa"] == 0.02
        assert brick.spec["overdraft_limit"] is None  # Default is None (unlimited)
        assert brick.spec["overdraft_policy"] == "ignore"  # Default policy
        assert brick.spec["min_buffer"] == 0.0

    def test_cash_simulate_no_external_flows(self):
        """Test cash simulation with no external flows."""
        brick = ABrick(
            id="cash",
            name="Test Cash",
            kind="a.cash",
            spec={
                "initial_balance": 1000.0,
                "interest_pa": 0.02,
                "external_in": np.zeros(12),
                "external_out": np.zeros(12),
            },
        )

        ctx = ScenarioContext(
            t_index=month_range(date(2026, 1, 1), 12), currency="EUR", registry={}
        )

        strategy = ValuationCash()
        result = strategy.simulate(brick, ctx)

        # Check output structure
        assert "cash_in" in result
        assert "cash_out" in result
        assert "assets" in result
        assert "liabilities" in result
        assert "events" in result

        # Check that balance grows with interest
        balance = result["assets"]
        assert balance[0] > 1000.0  # Initial balance plus interest
        assert balance[-1] > balance[0]  # Balance grows over time

        # Check that cash flows are zero (cash account doesn't generate flows)
        assert np.all(result["cash_in"] == 0)
        assert np.all(result["cash_out"] == 0)

        # Check that debt balance is zero
        assert np.all(result["liabilities"] == 0)

    def test_cash_simulate_with_external_flows(self):
        """Test cash simulation with external flows."""
        # Create external flows: 500 inflow in month 0, 100 outflow in month 6
        external_in = np.zeros(12)
        external_in[0] = 500.0
        external_out = np.zeros(12)
        external_out[6] = 100.0

        brick = ABrick(
            id="cash",
            name="Test Cash",
            kind="a.cash",
            spec={
                "initial_balance": 1000.0,
                "interest_pa": 0.02,
                "external_in": external_in,
                "external_out": external_out,
            },
        )

        ctx = ScenarioContext(
            t_index=month_range(date(2026, 1, 1), 12), currency="EUR", registry={}
        )

        strategy = ValuationCash()
        result = strategy.simulate(brick, ctx)

        balance = result["assets"]

        # Check that balance reflects external flows
        # Month 0: 1000 + 500 + interest
        assert balance[0] > 1500.0

        # Month 6: should be lower due to 100 outflow
        assert balance[6] < balance[5]

        # Month 7: should recover and continue growing
        assert balance[7] > balance[6]

    def test_cash_overdraft_limit_validation(self):
        """Test overdraft limit validation."""
        brick = ABrick(
            id="cash",
            name="Test Cash",
            kind="a.cash",
            spec={"initial_balance": 1000.0, "overdraft_limit": -100.0},
        )

        ctx = ScenarioContext(
            t_index=month_range(date(2026, 1, 1), 12), currency="EUR", registry={}
        )

        strategy = ValuationCash()

        # Should raise ConfigError for negative overdraft limit
        from finbricklab.core.errors import ConfigError
        with pytest.raises(ConfigError, match="overdraft_limit must be >= 0"):
            strategy.prepare(brick, ctx)

    def test_cash_min_buffer_validation(self):
        """Test min buffer validation."""
        brick = ABrick(
            id="cash",
            name="Test Cash",
            kind="a.cash",
            spec={"initial_balance": 1000.0, "min_buffer": -50.0},
        )

        ctx = ScenarioContext(
            t_index=month_range(date(2026, 1, 1), 12), currency="EUR", registry={}
        )

        strategy = ValuationCash()

        # Should raise ValueError for negative min buffer
        with pytest.raises(ValueError, match="min_buffer must be >= 0"):
            strategy.prepare(brick, ctx)
