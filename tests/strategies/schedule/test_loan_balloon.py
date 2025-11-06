"""Tests for balloon loan schedule strategy."""

from datetime import date

import pytest
from finbricklab.core.bricks import ABrick, LBrick
from finbricklab.core.kinds import K
from finbricklab.core.scenario import Scenario


def test_balloon_fixed_amount_is_clamped_to_current_balance():
    """Fixed-amount balloon payments should never exceed the outstanding balance."""

    principal = 250_000.0
    rate_pa = 0.04
    amortization_rate_pa = 0.01
    balloon_after_months = 12

    cash = ABrick(
        id="cash",
        name="Cash",
        kind=K.A_CASH,
        spec={"initial_balance": 1_000_000.0, "interest_pa": 0.0},
    )

    balloon_loan = LBrick(
        id="balloon",
        name="Balloon Loan",
        kind=K.L_LOAN_BALLOON,
        spec={
            "principal": principal,
            "rate_pa": rate_pa,
            "amortization_rate_pa": amortization_rate_pa,
            "balloon_after_months": balloon_after_months,
            "balloon_type": "fixed_amount",
            "balloon_amount": principal * 10,  # Deliberately oversized to test clamp
        },
    )

    scenario = Scenario(id="balloon-test", name="Balloon Clamp", bricks=[cash, balloon_loan])

    months = balloon_after_months + 2
    results = scenario.run(start=date(2026, 1, 1), months=months)

    liabilities = results["outputs"]["balloon"]["liabilities"]
    journal = results["journal"]

    # Balloon month index matches configured offset because payments start one month after disbursement
    balloon_month_index = balloon_after_months
    pre_balloon_balance = liabilities[balloon_month_index - 1]

    balloon_entries = [
        entry
        for entry in journal.entries
        if entry.metadata.get("tags", {}).get("type") == "balloon"
    ]

    assert len(balloon_entries) == 1, "Expected a single balloon journal entry"

    principal_posting = next(
        posting
        for posting in balloon_entries[0].postings
        if posting.account_id.startswith("l:")
    )
    paid_amount = float(principal_posting.amount.value)

    assert paid_amount == pytest.approx(pre_balloon_balance, abs=1e-2)
    assert liabilities[balloon_month_index] == pytest.approx(0.0, abs=1e-6)

