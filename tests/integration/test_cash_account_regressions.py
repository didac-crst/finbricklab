"""
Integration tests covering cash-account scenarios with different activation windows
and attached flow bricks. These tests mirror common notebook examples so regressions
are caught immediately.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from finbricklab import Entity
from finbricklab.core.kinds import K


def _run_cash_scenario(
    *,
    interest_pa: float = 0.0,
    cash_start: date | None = None,
    include_salary: bool = False,
    salary_start: date | None = None,
    months: int = 36,
) -> dict:
    """
    Helper that wires a minimal Entity and returns Entity.run_scenario output.
    """

    entity = Entity(name="John Muster")
    entity.new_ABrick(
        name="Checking Account",
        kind=K.A_CASH,
        start_date=cash_start,
        spec={"initial_balance": 50_000.0, "interest_pa": interest_pa},
    )

    brick_ids = ["checking_account"]

    if include_salary:
        entity.new_FBrick(
            name="Salary",
            kind=K.F_INCOME_RECURRING,
            start_date=salary_start,
            spec={
                "amount_monthly": 5_000.0,
                "step_pct": 0.022,
                "step_every_m": 12,
            },
            links={"route": {"to": "checking_account"}},
        )
        brick_ids.append("salary")

    entity.create_scenario(
        name="Base Scenario",
        brick_ids=brick_ids,
        settlement_default_cash_id="checking_account",
    )

    return entity.run_scenario("base_scenario", start=date(2026, 1, 1), months=months)


def test_single_cash_account_keeps_initial_balance_without_interest():
    """Baseline regression: equity should stay flat when interest is disabled."""

    results = _run_cash_scenario(interest_pa=0.0, months=24)
    monthly = results["views"].monthly()

    expected = np.full(len(monthly), 50_000.0)
    assert monthly["equity"].to_numpy() == pytest.approx(expected)
    assert monthly["cash"].to_numpy() == pytest.approx(expected)
    assert monthly["net_cf"].to_numpy() == pytest.approx(np.zeros(len(monthly)))


def test_cash_account_compounds_monthly_interest():
    """Ensure monthly compounding at interest_pa=10%."""

    results = _run_cash_scenario(interest_pa=0.10, months=24)
    monthly = results["views"].monthly()

    monthly_rate = 0.10 / 12.0
    expected_last = 50_000.0 * pow(1 + monthly_rate, 24)
    assert monthly.iloc[-1]["equity"] == pytest.approx(expected_last, rel=1e-6)
    assert monthly.iloc[-1]["cash"] == pytest.approx(expected_last, rel=1e-6)

    # Net cashflow equals the interest earned every month.
    months = np.arange(len(monthly))
    expected_interest = 50_000.0 * np.power(1 + monthly_rate, months) * monthly_rate
    assert monthly["net_cf"].to_numpy() == pytest.approx(expected_interest, rel=1e-6)


def test_cash_account_respects_delayed_activation():
    """Regression for bricks whose start_date is after the scenario start."""

    results = _run_cash_scenario(
        interest_pa=0.10, cash_start=date(2026, 5, 1), months=18
    )
    monthly = results["views"].monthly()

    inactive = monthly.loc["2026-01":"2026-04", "equity"]
    assert (inactive == 0.0).all()

    monthly_rate = 0.10 / 12.0
    expected_first_active = 50_000.0 * (1 + monthly_rate)
    assert monthly.loc["2026-05", "equity"] == pytest.approx(
        expected_first_active, rel=1e-6
    )

    expected_interest = np.zeros(len(monthly))
    active_idx = monthly.index.get_loc("2026-05")
    active_count = len(monthly) - active_idx
    if active_count > 0:
        growth = np.power(1 + monthly_rate, np.arange(active_count))
        expected_interest[active_idx:] = 50_000.0 * growth * monthly_rate
    assert monthly["net_cf"].to_numpy() == pytest.approx(expected_interest, rel=1e-6)


def test_salary_flows_route_into_cash_account():
    """Flow bricks should increase equity month over month according to salary schedule."""

    results = _run_cash_scenario(interest_pa=0.0, include_salary=True, months=15)
    monthly = results["views"].monthly()

    jan_equity = monthly.loc["2026-01", "equity"]
    feb_equity = monthly.loc["2026-02", "equity"]
    dec_equity = monthly.loc["2026-12", "equity"]
    jan_next_year = monthly.loc["2027-01", "equity"]

    # Base salary grows equity by exactly 5,000 per month until the first step-up.
    assert jan_equity == pytest.approx(55_000.0)
    assert feb_equity - jan_equity == pytest.approx(5_000.0)

    # Validate the 2.2% salary step after 12 months.
    assert jan_next_year - dec_equity == pytest.approx(5_000.0 * 1.022, rel=1e-6)

    net_cf = monthly["net_cf"]
    assert net_cf.loc["2026-01":"2026-12"].to_numpy() == pytest.approx(
        np.full(12, 5_000.0)
    )
    assert net_cf.loc["2027-01"] == pytest.approx(5_000.0 * 1.022, rel=1e-6)


def test_salary_and_cash_with_staggered_start_dates():
    """Cash and salary bricks can start later without losing their initial balance."""

    results = _run_cash_scenario(
        interest_pa=0.0,
        cash_start=date(2026, 3, 1),
        include_salary=True,
        salary_start=date(2026, 5, 1),
        months=12,
    )
    monthly = results["views"].monthly()

    assert monthly.loc["2026-01", "equity"] == pytest.approx(0.0)
    assert monthly.loc["2026-02", "equity"] == pytest.approx(0.0)
    assert monthly.loc["2026-03", "equity"] == pytest.approx(50_000.0)
    assert monthly.loc["2026-04", "equity"] == pytest.approx(50_000.0)
    assert monthly.loc["2026-05", "equity"] == pytest.approx(55_000.0)
    assert monthly.loc["2026-06", "equity"] == pytest.approx(60_000.0)

    assert monthly["net_cf"].loc["2026-01":"2026-04"].to_numpy() == pytest.approx(
        np.zeros(4)
    )
    assert monthly["net_cf"].loc["2026-05"] == pytest.approx(5_000.0)
    assert monthly["net_cf"].loc["2026-06"] == pytest.approx(5_000.0)
