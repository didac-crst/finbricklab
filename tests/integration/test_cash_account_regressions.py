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
from finbricklab.core.transfer_visibility import TransferVisibility


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


def _run_transfer_scenario(*, include_transfer: bool, months: int = 24) -> dict:
    """
    Helper that configures a checking/savings setup with optional recurring transfer.
    """

    entity = Entity(name="John Muster")

    entity.new_ABrick(
        name="Checking Account",
        kind=K.A_CASH,
        start_date=date(2026, 2, 1),
        spec={"initial_balance": 100_000.0, "interest_pa": 0.0},
    )
    entity.new_ABrick(
        name="Savings Account",
        kind=K.A_CASH,
        start_date=date(2026, 3, 1),
        spec={"initial_balance": 1_000.0, "interest_pa": 0.02},
    )

    entity.new_FBrick(
        name="Salary",
        kind=K.F_INCOME_RECURRING,
        start_date=date(2026, 5, 1),
        spec={"amount_monthly": 5_000.0, "step_pct": 0.022, "step_every_m": 12},
        links={"route": {"to": "checking_account"}},
    )

    brick_ids = ["checking_account", "savings_account", "salary"]

    if include_transfer:
        entity.new_TBrick(
            name="Savings Transfer",
            kind=K.T_TRANSFER_RECURRING,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 12, 1),
            spec={"amount": 10_000.0, "frequency": "MONTHLY"},
            links={"from": "checking_account", "to": "savings_account"},
        )
        brick_ids.append("savings_transfer")

    entity.create_scenario(
        name="Transfer Regression",
        brick_ids=brick_ids,
        settlement_default_cash_id="checking_account",
    )

    return entity.run_scenario(
        "transfer_regression", start=date(2026, 1, 1), months=months
    )


def test_single_cash_account_keeps_initial_balance_without_interest():
    """Baseline regression: equity should stay flat when interest is disabled."""

    results = _run_cash_scenario(interest_pa=0.0, months=24)
    monthly = results["views"].monthly()

    expected = np.full(len(monthly), 50_000.0)
    assert monthly["equity"].to_numpy() == pytest.approx(expected)
    assert monthly["cash"].to_numpy() == pytest.approx(expected)
    assert monthly["net_cf"].to_numpy() == pytest.approx(np.zeros(len(monthly)))

    assert {"cash_delta", "equity_delta", "capitalized_cf", "cash_rebalancing"} <= set(
        monthly.columns
    )
    cash_delta = monthly["cash_delta"].to_numpy()
    equity_delta = monthly["equity_delta"].to_numpy()
    capitalized_cf = monthly["capitalized_cf"].to_numpy()
    cash_rebalancing = monthly["cash_rebalancing"].to_numpy()
    net_cf = monthly["net_cf"].to_numpy()

    deposit_mask = np.abs(capitalized_cf) > 1e-3
    assert deposit_mask.any()
    assert capitalized_cf[deposit_mask] == pytest.approx(
        cash_delta[deposit_mask] - net_cf[deposit_mask], rel=1e-6
    )
    assert equity_delta[deposit_mask] == pytest.approx(
        capitalized_cf[deposit_mask] + net_cf[deposit_mask], rel=1e-6
    )

    post_mask = ~deposit_mask
    assert cash_delta[post_mask] == pytest.approx(net_cf[post_mask], rel=1e-6)
    assert equity_delta[post_mask] == pytest.approx(net_cf[post_mask], rel=1e-6)
    assert capitalized_cf[post_mask] == pytest.approx(
        np.zeros(post_mask.sum()), abs=1e-9
    )
    assert cash_rebalancing[post_mask] == pytest.approx(
        np.zeros(post_mask.sum()), abs=1e-9
    )

    eps = 1e-9
    float_values = np.abs(monthly.select_dtypes(include=["float"]).to_numpy().ravel())
    assert float_values.size > 0
    assert np.all((float_values == 0.0) | (float_values >= eps))


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

    cash_delta = monthly["cash_delta"].to_numpy()
    capitalized_cf = monthly["capitalized_cf"].to_numpy()
    cash_rebalancing = monthly["cash_rebalancing"].to_numpy()
    net_cf = monthly["net_cf"].to_numpy()

    deposit_mask = np.abs(capitalized_cf) > 1e-3
    assert deposit_mask.any()
    assert capitalized_cf[deposit_mask] == pytest.approx(
        cash_delta[deposit_mask] - net_cf[deposit_mask], rel=1e-6
    )

    post_mask = ~deposit_mask
    assert cash_delta[post_mask] == pytest.approx(net_cf[post_mask], rel=1e-6)
    assert capitalized_cf[post_mask] == pytest.approx(
        np.zeros(post_mask.sum()), abs=1e-9
    )
    assert cash_rebalancing[post_mask] == pytest.approx(
        np.zeros(post_mask.sum()), abs=1e-9
    )


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

    cash_delta = monthly["cash_delta"].to_numpy()
    capitalized_cf = monthly["capitalized_cf"].to_numpy()
    cash_rebalancing = monthly["cash_rebalancing"].to_numpy()
    net_cf = monthly["net_cf"].to_numpy()

    deposit_mask = np.abs(capitalized_cf) > 1e-3
    assert deposit_mask.any()
    assert capitalized_cf[deposit_mask] == pytest.approx(
        cash_delta[deposit_mask] - net_cf[deposit_mask], rel=1e-6
    )

    post_mask = ~deposit_mask
    assert cash_delta[post_mask] == pytest.approx(net_cf[post_mask], rel=1e-6)
    assert capitalized_cf[post_mask] == pytest.approx(
        np.zeros(post_mask.sum()), abs=1e-9
    )
    assert cash_rebalancing[post_mask] == pytest.approx(
        np.zeros(post_mask.sum()), abs=1e-9
    )


def test_transfer_shell_excluded_has_no_effect_on_savings():
    """Leaving the transfer brick out means savings only accrues interest."""

    results = _run_transfer_scenario(include_transfer=False, months=18)
    savings_assets = results["outputs"]["savings_account"]["assets"]
    checking_assets = results["outputs"]["checking_account"]["assets"]

    monthly_rate = 0.02 / 12.0
    first_active_idx = 2  # March 2026

    assert savings_assets[first_active_idx] == pytest.approx(
        1_000.0 * (1 + monthly_rate), rel=1e-6
    )

    for idx in range(first_active_idx + 1, first_active_idx + 6):
        expected = savings_assets[idx - 1] * (1 + monthly_rate)
        assert savings_assets[idx] == pytest.approx(expected, rel=1e-6)

    salary_start_idx = 4  # May 2026
    for idx in range(salary_start_idx, salary_start_idx + 4):
        assert checking_assets[idx] - checking_assets[idx - 1] == pytest.approx(5_000.0)

    monthly = results["views"].monthly()
    cash_delta = monthly["cash_delta"].to_numpy()
    capitalized_cf = monthly["capitalized_cf"].to_numpy()
    cash_rebalancing = monthly["cash_rebalancing"].to_numpy()
    net_cf = monthly["net_cf"].to_numpy()

    deposit_mask = np.abs(capitalized_cf) > 1e-3
    assert deposit_mask.any()
    assert capitalized_cf[deposit_mask] == pytest.approx(
        cash_delta[deposit_mask] - net_cf[deposit_mask], rel=1e-6
    )

    post_mask = ~deposit_mask
    assert cash_delta[post_mask] == pytest.approx(net_cf[post_mask], rel=1e-6)
    assert capitalized_cf[post_mask] == pytest.approx(
        np.zeros(post_mask.sum()), abs=1e-9
    )
    assert cash_rebalancing[post_mask] == pytest.approx(
        np.zeros(post_mask.sum()), abs=1e-9
    )


def test_transfer_shell_included_moves_cash_between_accounts():
    """Including the transfer brick moves money from checking into savings."""

    results = _run_transfer_scenario(include_transfer=True, months=18)
    savings_assets = results["outputs"]["savings_account"]["assets"]
    checking_assets = results["outputs"]["checking_account"]["assets"]

    monthly_rate = 0.02 / 12.0
    first_transfer_idx = 3  # April 2026

    expected_after_first_transfer = (
        savings_assets[first_transfer_idx - 1] + 10_000.0
    ) * (1 + monthly_rate)
    assert savings_assets[first_transfer_idx] == pytest.approx(
        expected_after_first_transfer, rel=1e-6
    )

    for idx in range(first_transfer_idx + 1, first_transfer_idx + 6):
        expected = (savings_assets[idx - 1] + 10_000.0) * (1 + monthly_rate)
        assert savings_assets[idx] == pytest.approx(expected, rel=1e-6)

    assert checking_assets[first_transfer_idx] == pytest.approx(
        checking_assets[first_transfer_idx - 1] - 10_000.0, rel=1e-6
    )

    salary_start_idx = 4  # May 2026
    for idx in range(salary_start_idx, salary_start_idx + 4):
        assert checking_assets[idx] - checking_assets[idx - 1] == pytest.approx(
            -5_000.0
        )

    monthly = results["views"].monthly()
    cash_delta = monthly["cash_delta"].to_numpy()
    capitalized_cf = monthly["capitalized_cf"].to_numpy()
    cash_rebalancing = monthly["cash_rebalancing"].to_numpy()
    net_cf = monthly["net_cf"].to_numpy()

    deposit_mask = np.abs(capitalized_cf) > 1e-3
    assert deposit_mask.any()
    assert capitalized_cf[deposit_mask] == pytest.approx(
        cash_delta[deposit_mask] - net_cf[deposit_mask], rel=1e-6
    )

    post_mask = ~deposit_mask
    assert cash_delta[post_mask] == pytest.approx(net_cf[post_mask], rel=1e-6)
    assert capitalized_cf[post_mask] == pytest.approx(
        np.zeros(post_mask.sum()), abs=1e-9
    )
    assert cash_rebalancing[post_mask] == pytest.approx(
        np.zeros(post_mask.sum()), abs=1e-9
    )


def test_mortgage_principal_surfaces_in_capitalized_flows():
    """Principal amortization shows up as capitalized cash flow and cash rebalancing."""

    entity = Entity(name="Home Owner")
    entity.new_ABrick(
        name="Checking Account",
        kind=K.A_CASH,
        start_date=date(2026, 2, 1),
        spec={"initial_balance": 100_000.0, "interest_pa": 0.0},
    )
    entity.new_ABrick(
        name="House",
        kind=K.A_PROPERTY,
        start_date=date(2027, 1, 1),
        spec={
            "initial_value": 500_000.0,
            "appreciation_pa": 0.04,
            "fees_pct": 0.1,
        },
        links={"route": {"from": "checking_account", "to": "checking_account"}},
    )
    entity.new_LBrick(
        name="House Mortgage",
        kind=K.L_LOAN_BALLOON,
        start_date=date(2027, 1, 1),
        spec={
            "principal": 400_000.0,
            "rate_pa": 0.02,
            "balloon_after_months": 10 * 12,
            "amortization_rate_pa": 0.03,
            "balloon_type": "residual",
        },
        links={"route": {"from": "checking_account", "to": "checking_account"}},
    )

    entity.create_scenario(
        name="Home Financing",
        brick_ids=["checking_account", "house", "house_mortgage"],
        settlement_default_cash_id="checking_account",
    )

    results = entity.run_scenario("home_financing", start=date(2026, 1, 1), months=36)
    monthly = results["views"].monthly()

    # First amortization month: interest-only cashflow plus principal rebalancing
    first_amortization = monthly.loc["2027-02"]
    assert first_amortization["net_cf"] < 0.0
    assert first_amortization["cash_delta"] < 0.0

    principal_component = (
        first_amortization["cash_delta"] - first_amortization["net_cf"]
    )
    assert principal_component < 0.0

    assert first_amortization["cash_rebalancing"] == pytest.approx(
        principal_component, rel=1e-6
    )
    assert first_amortization["capitalized_cf"] > 0.0
    assert first_amortization["equity_delta"] == pytest.approx(
        first_amortization["net_cf"] + first_amortization["capitalized_cf"], rel=1e-9
    )


def test_filtered_views_respect_cash_and_liability_semantics():
    """Cash selections surface routed flows; liability selections stay cash-neutral."""

    entity = Entity(name="Cash Loan Test")
    entity.new_ABrick(
        name="Checking Account",
        kind=K.A_CASH,
        start_date=date(2026, 1, 1),
        spec={"initial_balance": 50_000.0, "interest_pa": 0.0},
    )
    entity.new_FBrick(
        name="Salary",
        kind=K.F_INCOME_RECURRING,
        start_date=date(2026, 1, 1),
        spec={"amount_monthly": 5_000.0},
        links={"route": {"to": "checking_account"}},
    )
    entity.new_LBrick(
        name="Mortgage",
        kind=K.L_LOAN_BALLOON,
        start_date=date(2026, 1, 1),
        spec={
            "principal": 100_000.0,
            "rate_pa": 0.03,
            "balloon_after_months": 120,
            "amortization_rate_pa": 0.02,
            "balloon_type": "residual",
        },
        links={"route": {"from": "checking_account", "to": "checking_account"}},
    )

    entity.create_scenario(
        name="Cash Loan Scenario",
        brick_ids=["checking_account", "salary", "mortgage"],
        settlement_default_cash_id="checking_account",
    )

    results = entity.run_scenario(
        "cash_loan_scenario", start=date(2026, 1, 1), months=18
    )

    cash_view = results["views"].filter(brick_ids=["checking_account"]).monthly()
    loan_view = results["views"].filter(brick_ids=["mortgage"]).monthly()

    assert {"cash_in", "cash_out", "net_cf"} <= set(cash_view.columns)

    feb_cash = cash_view.loc["2026-02"]
    assert feb_cash["cash_in"] == pytest.approx(5_000.0)
    assert feb_cash["cash_out"] == pytest.approx(416.67, abs=1e-4)
    assert feb_cash["net_cf"] == pytest.approx(4_583.33, abs=1e-4)
    assert feb_cash["capitalized_cf"] == pytest.approx(0.0, abs=1e-9)

    feb_loan = loan_view.loc["2026-02"]
    assert feb_loan["cash_in"] == pytest.approx(0.0, abs=1e-9)
    assert feb_loan["cash_out"] == pytest.approx(0.0, abs=1e-9)
    assert feb_loan["net_cf"] == pytest.approx(0.0, abs=1e-9)
    assert feb_loan["interest"] == pytest.approx(-250.0, rel=1e-6)
    assert feb_loan["capitalized_cf"] == pytest.approx(166.6667, rel=1e-6)

    post_start_cash = cash_view.loc["2026-02":]
    assert (post_start_cash["cash_out"] > 0.0).all()

    post_start_loan = loan_view.loc["2026-02":]
    assert np.allclose(post_start_loan["cash_in"], 0.0, atol=1e-9)
    assert np.allclose(post_start_loan["cash_out"], 0.0, atol=1e-9)
    assert np.allclose(post_start_loan["net_cf"], 0.0, atol=1e-9)
    assert (np.abs(post_start_loan["interest"]) > 0.0).any()
    assert (np.abs(post_start_loan["capitalized_cf"]) > 0.0).any()

    cash_view_off = (
        results["views"]
        .filter(
            brick_ids=["checking_account"],
            transfer_visibility=TransferVisibility.OFF,
        )
        .monthly()
    )
    cash_view_all = (
        results["views"]
        .filter(
            brick_ids=["checking_account"],
            transfer_visibility=TransferVisibility.ALL,
        )
        .monthly()
    )

    assert cash_view_off.loc["2026-02", "cash_out"] == pytest.approx(250.0, rel=1e-6)
    assert (
        cash_view_off.loc["2026-02", "cash_out"] < cash_view.loc["2026-02", "cash_out"]
    )
    assert cash_view_all.loc["2026-02", "cash_out"] == pytest.approx(
        cash_view.loc["2026-02", "cash_out"], rel=1e-9
    )


def test_filtered_views_multiple_cash_accounts_and_transfers():
    """Multiple cash selections handle internal transfers and visibility toggles."""

    entity = Entity(name="Two Cash Accounts")

    entity.new_ABrick(
        name="Checking",
        kind=K.A_CASH,
        start_date=date(2026, 1, 1),
        spec={"initial_balance": 10_000.0, "interest_pa": 0.0},
    )
    entity.new_ABrick(
        name="Savings",
        kind=K.A_CASH,
        start_date=date(2026, 1, 1),
        spec={"initial_balance": 1_000.0, "interest_pa": 0.0},
    )

    entity.new_FBrick(
        name="Salary",
        kind=K.F_INCOME_RECURRING,
        start_date=date(2026, 1, 1),
        spec={"amount_monthly": 5_000.0},
        links={"route": {"to": "checking"}},
    )

    entity.new_TBrick(
        name="Monthly Transfer",
        kind=K.T_TRANSFER_RECURRING,
        start_date=date(2026, 1, 1),
        spec={"amount": 1_000.0, "frequency": "MONTHLY"},
        links={"from": "checking", "to": "savings"},
    )

    entity.create_scenario(
        name="Two Cash Scenario",
        brick_ids=["checking", "savings", "salary", "monthly_transfer"],
        settlement_default_cash_id="checking",
    )

    results = entity.run_scenario("two_cash_scenario", start=date(2026, 1, 1), months=6)

    checking_view = results["views"].filter(brick_ids=["checking"]).monthly()
    savings_view = results["views"].filter(brick_ids=["savings"]).monthly()

    jan_checking = checking_view.loc["2026-01"]
    assert jan_checking["cash_in"] == pytest.approx(5_000.0)
    assert jan_checking["cash_out"] == pytest.approx(1_000.0)
    assert jan_checking["net_cf"] == pytest.approx(4_000.0)

    jan_savings = savings_view.loc["2026-01"]
    assert jan_savings["cash_in"] == pytest.approx(1_000.0)
    assert jan_savings["cash_out"] == pytest.approx(0.0, abs=1e-9)
    assert jan_savings["net_cf"] == pytest.approx(1_000.0)

    checking_off = (
        results["views"]
        .filter(brick_ids=["checking"], transfer_visibility=TransferVisibility.OFF)
        .monthly()
    )
    assert checking_off.loc["2026-01", "cash_out"] == pytest.approx(0.0, abs=1e-9)
    assert checking_off.loc["2026-01", "cash_in"] == pytest.approx(5_000.0)

    savings_off = (
        results["views"]
        .filter(brick_ids=["savings"], transfer_visibility=TransferVisibility.OFF)
        .monthly()
    )
    assert np.allclose(savings_off["cash_in"], 0.0, atol=1e-9)
    assert np.allclose(savings_off["cash_out"], 0.0, atol=1e-9)

    checking_all = (
        results["views"]
        .filter(brick_ids=["checking"], transfer_visibility=TransferVisibility.ALL)
        .monthly()
    )
    savings_all = (
        results["views"]
        .filter(brick_ids=["savings"], transfer_visibility=TransferVisibility.ALL)
        .monthly()
    )

    assert checking_all.loc["2026-01", "cash_out"] == pytest.approx(1_000.0)
    assert savings_all.loc["2026-01", "cash_in"] == pytest.approx(1_000.0)


def test_balloon_loan_routes_to_non_default_cash():
    """Balloon loan operations route entirely to the configured cash account."""

    entity = Entity(name="Balloon Loan Routing")
    entity.new_ABrick(
        name="Default Checking",
        kind=K.A_CASH,
        start_date=date(2026, 1, 1),
        spec={"initial_balance": 0.0, "interest_pa": 0.0},
    )
    entity.new_ABrick(
        name="Offset Account",
        kind=K.A_CASH,
        start_date=date(2026, 1, 1),
        spec={"initial_balance": 0.0, "interest_pa": 0.0},
    )
    entity.new_LBrick(
        name="Balloon Loan",
        kind=K.L_LOAN_BALLOON,
        start_date=date(2026, 1, 1),
        spec={
            "principal": 50_000.0,
            "rate_pa": 0.03,
            "balloon_after_months": 24,
            "amortization_rate_pa": 0.02,
            "balloon_type": "residual",
        },
        links={"route": {"from": "offset_account", "to": "offset_account"}},
    )

    entity.create_scenario(
        name="Balloon Loan Scenario",
        brick_ids=["default_checking", "offset_account", "balloon_loan"],
        settlement_default_cash_id="default_checking",
    )

    results = entity.run_scenario(
        "balloon_loan_scenario", start=date(2026, 1, 1), months=30
    )

    default_view = results["views"].filter(brick_ids=["default_checking"]).monthly()
    offset_view = results["views"].filter(brick_ids=["offset_account"]).monthly()

    assert np.allclose(default_view["cash_in"], 0.0, atol=1e-9)
    assert np.allclose(default_view["cash_out"], 0.0, atol=1e-9)

    assert offset_view.iloc[0]["cash_in"] == pytest.approx(50_000.0)
    assert offset_view.iloc[0]["cash_out"] == pytest.approx(0.0, abs=1e-9)
    assert (offset_view.iloc[1:]["cash_out"] > 0.0).any()


def test_annuity_loan_routes_to_non_default_cash():
    """Annuity loan drawdowns and payments honour explicit route configuration."""

    entity = Entity(name="Annuity Loan Routing")
    entity.new_ABrick(
        name="Primary Cash",
        kind=K.A_CASH,
        start_date=date(2026, 1, 1),
        spec={"initial_balance": 0.0, "interest_pa": 0.0},
    )
    entity.new_ABrick(
        name="Loan Offset",
        kind=K.A_CASH,
        start_date=date(2026, 1, 1),
        spec={"initial_balance": 0.0, "interest_pa": 0.0},
    )
    entity.new_LBrick(
        name="Annuity Loan",
        kind=K.L_LOAN_ANNUITY,
        start_date=date(2026, 1, 1),
        spec={
            "principal": 120_000.0,
            "rate_pa": 0.03,
            "term_months": 120,
            "first_payment_offset": 1,
        },
        links={"route": {"from": "loan_offset", "to": "loan_offset"}},
    )

    entity.create_scenario(
        name="Annuity Loan Scenario",
        brick_ids=["primary_cash", "loan_offset", "annuity_loan"],
        settlement_default_cash_id="primary_cash",
    )

    results = entity.run_scenario(
        "annuity_loan_scenario", start=date(2026, 1, 1), months=18
    )

    primary_view = results["views"].filter(brick_ids=["primary_cash"]).monthly()
    offset_view = results["views"].filter(brick_ids=["loan_offset"]).monthly()

    assert np.allclose(primary_view["cash_in"], 0.0, atol=1e-9)
    assert np.allclose(primary_view["cash_out"], 0.0, atol=1e-9)

    assert offset_view.iloc[0]["cash_in"] == pytest.approx(120_000.0)
    assert offset_view.iloc[0]["cash_out"] == pytest.approx(0.0, abs=1e-9)
    assert (offset_view.iloc[1:]["cash_out"] > 0.0).all()
