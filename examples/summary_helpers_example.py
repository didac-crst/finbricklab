"""
Quick demonstration of the new summary() helpers for FinBrickLab core objects.
"""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
from finbricklab.core.bricks import ABrick, FBrick
from finbricklab.core.kinds import K
from finbricklab.core.macrobrick import MacroBrick
from finbricklab.core.results import ScenarioResults
from finbricklab.core.scenario import Scenario


def pretty(data: dict) -> str:
    """Return JSON formatted output."""
    return json.dumps(data, indent=2, sort_keys=True)


def build_sample_scenario() -> Scenario:
    cash = ABrick(
        name="Cash Account",
        kind=K.A_CASH,
        spec={"initial_balance": 5000},
        start_date=date(2024, 1, 1),
    )
    salary = FBrick(
        name="Salary",
        kind="f.income.salary",
        spec={"amount_monthly": 4000},
        links={"route": {"to": cash.id}},
        start_date=date(2024, 1, 1),
    )
    household = MacroBrick(name="Household", members=[cash.id, salary.id])

    scenario = Scenario(
        name="Summary Demo",
        bricks=[cash, salary],
        macrobricks=[household],
        currency="EUR",
    )

    # Seed faux results for last_run metadata.
    monthly = pd.DataFrame(
        {
            "cash": [5000.0, 7000.0],
            "non_cash": [0.0, 0.0],
            "liabilities": [0.0, 0.0],
        },
        index=pd.period_range("2024-01", periods=2, freq="M"),
    )
    scenario._last_results = {
        "totals": monthly,
        "meta": {"execution_order": [cash.id, salary.id], "overlaps": {}},
    }

    return scenario


def build_results_view(scenario: Scenario) -> ScenarioResults:
    assert scenario._last_results is not None
    monthly = scenario._last_results["totals"]
    return ScenarioResults(
        totals=monthly.assign(
            property_value=[0.0, 0.0],
            inflows=[4000.0, 4000.0],
            outflows=[2500.0, 2500.0],
            non_cash=monthly["non_cash"],
            cash=monthly["cash"],
            liabilities=monthly["liabilities"],
        ),
        registry=scenario._registry,
        default_selection={"household"},
    )


def main() -> None:
    scenario = build_sample_scenario()
    results_view = build_results_view(scenario)
    cash_brick = scenario.bricks[0]
    macro = scenario.macrobricks[0]

    print("Brick summary:")
    print(pretty(cash_brick.summary(include_spec=True)))

    print("\nMacroBrick summary:")
    print(pretty(macro.summary(registry=scenario._registry, flatten=True)))

    print("\nScenario summary:")
    print(pretty(scenario.summary(include_members=True, include_last_run=True)))

    print("\nResults view summary:")
    print(pretty(results_view.summary(selection={"household"})))


if __name__ == "__main__":
    main()
