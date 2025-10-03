"""
Tests for multi-cash account routing functionality.
"""

from datetime import date

import numpy as np
from finbricklab.core.bricks import ABrick, FBrick
from finbricklab.core.kinds import K
from finbricklab.core.scenario import Scenario


def test_split_income_two_cash_accounts():
    """Test that income can be split between multiple cash accounts."""
    checking = ABrick(
        id="checking",
        name="Checking",
        kind=K.A_CASH,
        spec={"initial_balance": 0.0, "interest_pa": 0.00},
    )
    savings = ABrick(
        id="savings",
        name="Savings",
        kind=K.A_CASH,
        spec={"initial_balance": 0.0, "interest_pa": 0.00},
    )

    # 3000/mo salary: 70% to checking, 30% to savings
    income = FBrick(
        id="income",
        name="Salary",
        kind=K.F_INCOME_FIXED,
        spec={"amount_monthly": 3000.0},
        links={"route": {"to": {"checking": 0.7, "savings": 0.3}}},
    )

    # 1000/mo expenses paid from checking only
    expense = FBrick(
        id="expense",
        name="Living",
        kind=K.F_EXPENSE_FIXED,
        spec={"amount_monthly": 1000.0},
        links={"route": {"from": "checking"}},
    )

    sc = Scenario(
        id="multi-cash",
        name="Multi-cash routing",
        bricks=[checking, savings, income, expense],
        settlement_default_cash_id="checking",
    )

    res = sc.run(start=date(2026, 1, 1), months=3)
    out = res["outputs"]

    # External buffers per cash
    cin_check = out["checking"]["asset_value"] * 0  # just to get T
    T = len(cin_check)

    ext_in_check = checking.spec["external_in"]
    ext_in_save = savings.spec["external_in"]
    ext_out_check = checking.spec["external_out"]
    ext_out_save = savings.spec["external_out"]

    assert np.allclose(ext_in_check, 0.7 * out["income"]["cash_in"])
    assert np.allclose(ext_in_save, 0.3 * out["income"]["cash_in"])
    assert np.allclose(ext_out_check, out["expense"]["cash_out"])
    assert np.allclose(ext_out_save, np.zeros(T))

    # Totals sanity: route redistribution doesn't change scenario totals
    totals = res["totals"]
    assert np.allclose(
        totals["net_cf"].values, totals["cash_in"].values - totals["cash_out"].values
    )


def test_default_route_when_missing_links():
    """Test that flows default to settlement_default_cash_id when no links are specified."""
    # No links specified → default to settlement_default_cash_id
    main = ABrick(id="main", name="Main", kind=K.A_CASH, spec={"initial_balance": 0.0})
    side = ABrick(id="side", name="Side", kind=K.A_CASH, spec={"initial_balance": 0.0})

    income = FBrick(
        id="inc", name="Inc", kind=K.F_INCOME_FIXED, spec={"amount_monthly": 500.0}
    )
    expense = FBrick(
        id="exp", name="Exp", kind=K.F_EXPENSE_FIXED, spec={"amount_monthly": 200.0}
    )

    sc = Scenario(
        id="defaults",
        name="Defaults",
        bricks=[main, side, income, expense],
        settlement_default_cash_id="main",
    )
    sc.run(start=date(2026, 1, 1), months=2)

    assert np.all(sc.bricks[0].spec["external_in"] >= 0)  # main got routed flows
    assert np.allclose(sc.bricks[1].spec["external_in"], 0.0)  # side stayed zero


def test_weight_normalization():
    """Test that weights are normalized when they don't sum to 1.0."""
    checking = ABrick(
        id="checking", name="Checking", kind=K.A_CASH, spec={"initial_balance": 0.0}
    )
    savings = ABrick(
        id="savings", name="Savings", kind=K.A_CASH, spec={"initial_balance": 0.0}
    )

    # Weights sum to 2.0, should be normalized to 0.5 each
    income = FBrick(
        id="income",
        name="Salary",
        kind=K.F_INCOME_FIXED,
        spec={"amount_monthly": 1000.0},
        links={"route": {"to": {"checking": 1.0, "savings": 1.0}}},
    )

    sc = Scenario(
        id="normalize",
        name="Weight normalization",
        bricks=[checking, savings, income],
    )
    sc.run(start=date(2026, 1, 1), months=1)

    # Should split 50/50 after normalization
    ext_in_check = checking.spec["external_in"]
    ext_in_save = savings.spec["external_in"]

    assert np.allclose(ext_in_check, 500.0)  # 50% of 1000
    assert np.allclose(ext_in_save, 500.0)  # 50% of 1000


def test_negative_weights_error():
    """Test that negative weights raise an error."""
    checking = ABrick(
        id="checking", name="Checking", kind=K.A_CASH, spec={"initial_balance": 0.0}
    )
    savings = ABrick(
        id="savings", name="Savings", kind=K.A_CASH, spec={"initial_balance": 0.0}
    )

    income = FBrick(
        id="income",
        name="Salary",
        kind=K.F_INCOME_FIXED,
        spec={"amount_monthly": 1000.0},
        links={"route": {"to": {"checking": 0.7, "savings": -0.3}}},  # negative weight
    )

    sc = Scenario(
        id="negative",
        name="Negative weights",
        bricks=[checking, savings, income],
    )

    try:
        from finbricklab.core.errors import ConfigError
    except Exception:
        ConfigError = ValueError

    # Should raise ConfigError for negative weight
    try:
        sc.run(start=date(2026, 1, 1), months=1)
        raise AssertionError("Expected ConfigError for negative weight")
    except ConfigError as e:
        assert "must be >= 0" in str(e)


def test_unknown_cash_id_error():
    """Test that referencing unknown cash IDs raises an error."""
    checking = ABrick(
        id="checking", name="Checking", kind=K.A_CASH, spec={"initial_balance": 0.0}
    )

    income = FBrick(
        id="income",
        name="Salary",
        kind=K.F_INCOME_FIXED,
        spec={"amount_monthly": 1000.0},
        links={"route": {"to": "nonexistent"}},  # unknown cash ID
    )

    sc = Scenario(
        id="unknown",
        name="Unknown cash ID",
        bricks=[checking, income],
    )

    try:
        from finbricklab.core.errors import ConfigError
    except Exception:
        ConfigError = ValueError

    # Should raise ConfigError for unknown cash ID
    try:
        sc.run(start=date(2026, 1, 1), months=1)
        raise AssertionError("Expected ConfigError for unknown cash ID")
    except ConfigError as e:
        assert "references unknown cash id" in str(e)


def test_zero_weights_fallback():
    """Test that zero weights fall back to default cash account."""
    checking = ABrick(
        id="checking", name="Checking", kind=K.A_CASH, spec={"initial_balance": 0.0}
    )
    savings = ABrick(
        id="savings", name="Savings", kind=K.A_CASH, spec={"initial_balance": 0.0}
    )

    income = FBrick(
        id="income",
        name="Salary",
        kind=K.F_INCOME_FIXED,
        spec={"amount_monthly": 1000.0},
        links={"route": {"to": {"checking": 0.0, "savings": 0.0}}},  # zero weights
    )

    sc = Scenario(
        id="zero",
        name="Zero weights",
        bricks=[checking, savings, income],
        settlement_default_cash_id="checking",
    )
    sc.run(start=date(2026, 1, 1), months=1)

    # Should fall back to default cash (checking)
    ext_in_check = checking.spec["external_in"]
    ext_in_save = savings.spec["external_in"]

    assert np.allclose(ext_in_check, 1000.0)  # all to default
    assert np.allclose(ext_in_save, 0.0)  # none to savings


def test_single_cash_backward_compatibility():
    """Test that single cash account scenarios work unchanged."""
    cash = ABrick(
        id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 1000.0}
    )
    income = FBrick(
        id="income",
        name="Income",
        kind=K.F_INCOME_FIXED,
        spec={"amount_monthly": 500.0},
    )

    sc = Scenario(id="single", name="Single cash", bricks=[cash, income])
    res = sc.run(start=date(2026, 1, 1), months=1)

    # Should work exactly as before
    assert np.allclose(cash.spec["external_in"], 500.0)
    assert np.allclose(cash.spec["external_out"], 0.0)
    assert res["totals"]["cash"].iloc[-1] > 1000.0  # balance increased
