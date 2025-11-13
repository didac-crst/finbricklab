from __future__ import annotations

from datetime import date

import pytest
from finbricklab.core.accounts import (
    Account,
    AccountRegistry,
    AccountScope,
    AccountType,
)
from finbricklab.core.bricks import FBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.journal import Journal
from finbricklab.core.utils import month_range
from finbricklab.strategies.flow.expense_recurring import FlowExpenseRecurring


def _make_context(months: int = 6):
    t_index = month_range(date(2026, 1, 1), months)
    account_registry = AccountRegistry()
    journal = Journal(account_registry)

    cash_account_id = "a:cash"
    account_registry.register_account(
        Account(
            id=cash_account_id,
            name="Cash",
            scope=AccountScope.INTERNAL,
            account_type=AccountType.ASSET,
        )
    )

    cash_stub = type("CashStub", (), {"id": "cash", "kind": "a.cash"})
    registry = {"cash": cash_stub()}

    ctx = ScenarioContext(
        t_index=t_index,
        currency="EUR",
        registry=registry,
        journal=journal,
        settlement_default_cash_id="cash",
    )
    return ctx, journal


def _simulate(spec: dict, months: int = 6):
    ctx, journal = _make_context(months=months)
    brick = FBrick(id="rent", name="Rent", kind="f.expense.recurring", spec=spec)
    strategy = FlowExpenseRecurring()
    strategy.prepare(brick, ctx)
    strategy.simulate(brick, ctx)
    return journal


def _boundary_amounts(journal: Journal) -> list[float]:
    amounts = []
    for entry in journal.entries:
        boundary_posting = next(
            posting for posting in entry.postings if posting.account_id == "b:boundary"
        )
        amounts.append(float(boundary_posting.amount.value))
    return amounts


def test_expense_recurring_flat_amount():
    journal = _simulate({"amount_monthly": 100.0}, months=3)
    amounts = _boundary_amounts(journal)
    assert amounts == [100.0, 100.0, 100.0]


def test_expense_recurring_steps_at_cadence():
    journal = _simulate(
        {"amount_monthly": 100.0, "step_pct": 0.10, "step_every_m": 2}, months=5
    )
    amounts = _boundary_amounts(journal)
    assert amounts == pytest.approx([100.0, 100.0, 110.0, 110.0, 121.0])


def test_expense_recurring_step_cap_limits_growth():
    journal = _simulate(
        {
            "amount_monthly": 100.0,
            "step_pct": 0.10,
            "step_every_m": 1,
            "step_cap": 1,
        },
        months=4,
    )
    amounts = _boundary_amounts(journal)
    assert amounts == pytest.approx([100.0, 110.0, 110.0, 110.0])


def test_invalid_step_every_raises():
    ctx, _ = _make_context()
    brick = FBrick(
        id="rent",
        name="Rent",
        kind="f.expense.recurring",
        spec={"amount_monthly": 100.0, "step_every_m": 0},
    )
    strategy = FlowExpenseRecurring()
    with pytest.raises(ValueError):
        strategy.prepare(brick, ctx)
