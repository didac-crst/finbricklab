"""
Tests for summary() helpers on bricks, macrobricks, scenarios and results.
"""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
import pytest
from finbricklab.core.bricks import ABrick, FBrick
from finbricklab.core.kinds import K
from finbricklab.core.macrobrick import MacroBrick
from finbricklab.core.registry import Registry
from finbricklab.core.results import ScenarioResults
from finbricklab.core.scenario import Scenario


@pytest.fixture()
def simple_bricks():
    salary = FBrick(
        id="salary",
        name="Salary",
        kind="f.income.salary",
        spec={"amount_monthly": 4000, "irrelevant": "ignored"},
        links={"route": {"to": "cash"}},
        start_date=date(2024, 1, 1),
    )
    cash = ABrick(
        id="cash",
        name="Cash Account",
        kind=K.A_CASH,
        spec={"initial_balance": 1000, "secret": "hidden"},
        start_date=date(2024, 1, 1),
    )
    return cash, salary


def test_brick_summary_keeps_core_fields(simple_bricks):
    cash, salary = simple_bricks

    summary = cash.summary()
    assert summary["type"] == "brick"
    assert summary["family"] == "a"
    assert summary["window"]["start"] == "2024-01-01"
    assert "spec_summary" not in summary
    json.dumps(summary)  # ensure JSON serializable

    with_spec = salary.summary(include_spec=True)
    assert with_spec["links"]["route_to"] == "cash"
    assert with_spec["spec_summary"] == {"amount_monthly": 4000}
    assert "irrelevant" not in with_spec["spec_summary"]
    json.dumps(with_spec)


def test_macrobrick_summary_handles_flags(simple_bricks):
    cash, salary = simple_bricks
    macro = MacroBrick(name="Household", members=[cash.id, salary.id])
    registry = Registry({cash.id: cash, salary.id: salary}, {macro.id: macro})

    base = macro.summary()
    assert base["n_direct"] == 2
    assert "direct_members" not in base
    json.dumps(base)

    expanded = macro.summary(registry=registry, flatten=True, include_members=True)
    assert expanded["flat_members"] == [cash.id, salary.id]
    assert expanded["contains_macros"] == 0
    assert expanded["direct_members"] == [cash.id, salary.id]
    json.dumps(expanded)


def test_scenario_summary_variants(simple_bricks):
    cash, salary = simple_bricks
    macro = MacroBrick(name="Household", members=[cash.id, salary.id])

    scenario = Scenario(
        name="Baseline",
        bricks=[cash, salary],
        macrobricks=[macro],
        currency="EUR",
    )

    basic = scenario.summary()
    assert basic["n_bricks"] == 2
    assert basic["families"] == {"a": 1, "l": 0, "f": 1, "t": 0}
    assert basic["last_run"]["has_run"] is False

    members = scenario.summary(include_members=True, include_validation=True)
    assert set(members["brick_ids"]) == {cash.id, salary.id}
    assert "validation" in members
    assert isinstance(members["validation"], dict)

    # Inject faux last-run metadata to exercise last_run block
    periods = pd.period_range("2024-01", periods=3, freq="M")
    totals = pd.DataFrame(
        {
            "cash": [1000, 1200, 1500],
            "non_cash": [0, 0, 0],
            "liabilities": [0, 0, 0],
        },
        index=periods,
    )
    scenario._last_results = {
        "totals": totals,
        "meta": {"execution_order": ["cash", "salary"], "overlaps": {}},
    }
    with_run = scenario.summary(include_last_run=True)
    assert with_run["last_run"]["has_run"] is True
    assert with_run["last_run"]["months"] == 3
    assert with_run["last_run"]["execution_order_len"] == 2
    json.dumps(with_run)


def test_results_summary_selection_and_kpis(simple_bricks):
    cash, salary = simple_bricks
    macro = MacroBrick(name="Household", members=[cash.id, salary.id])
    registry = Registry({cash.id: cash, salary.id: salary}, {macro.id: macro})

    monthly = pd.DataFrame(
        {
            "cash": [1000.0, 1200.0, 1500.0],
            "non_cash": [0.0, 0.0, 100.0],
            "liabilities": [0.0, 0.0, 0.0],
            "property_value": [0.0, 0.0, 50.0],
            "inflows": [4000.0, 4000.0, 4000.0],
            "outflows": [2000.0, 2000.0, 2000.0],
        },
        index=pd.period_range("2024-01", periods=3, freq="M"),
    )

    results = ScenarioResults(
        totals=monthly,
        registry=registry,
        default_selection={macro.id},
    )

    summary = results.summary(selection={macro.id})
    assert summary["selection_resolved"] == [cash.id, salary.id]
    assert summary["families"] == {"a": 1, "l": 0, "f": 1, "t": 0}
    assert summary["kpis"]["last_net_worth"] == pytest.approx(1600.0)
    assert summary["kpis"]["total_inflows"] == pytest.approx(12000.0)
    json.dumps(summary)
