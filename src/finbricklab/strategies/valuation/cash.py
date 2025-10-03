"""
Cash account valuation strategy.
"""

from __future__ import annotations

import numpy as np

from finbricklab.core.bricks import ABrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.interfaces import IValuationStrategy
from finbricklab.core.results import BrickOutput


class ValuationCash(IValuationStrategy):
    """
    Cash account valuation strategy (kind: 'a.cash').

    This strategy models a simple cash account that receives external cash flows
    and earns interest on the balance. The balance is computed by accumulating
    all routed cash flows plus interest earned each month.

    Required Parameters:
        - initial_balance: Starting cash balance (default: 0.0)
        - interest_pa: Annual interest rate (default: 0.0)

    External Parameters (set by scenario engine):
        - external_in: Monthly cash inflows from other bricks
        - external_out: Monthly cash outflows to other bricks

    Note:
        Supports scenarios with one or multiple cash accounts. The Scenario engine must
        populate `spec.external_in` and `spec.external_out` per cash brick; they are not
        derived here.
    """

    def prepare(self, brick: ABrick, ctx: ScenarioContext) -> None:
        """
        Prepare the cash account strategy.

        Sets up default parameters, liquidity policy, and validates the configuration.

        Args:
            brick: The cash account brick
            ctx: The simulation context
        """
        brick.spec.setdefault("initial_balance", 0.0)
        brick.spec.setdefault("interest_pa", 0.0)
        brick.spec.setdefault("external_in", np.zeros(len(ctx.t_index)))
        brick.spec.setdefault("external_out", np.zeros(len(ctx.t_index)))

        # Set liquidity policy defaults
        brick.spec.setdefault(
            "overdraft_limit", 0.0
        )  # how far below 0 cash may go (EUR)
        brick.spec.setdefault("min_buffer", 0.0)  # desired minimum cash balance (EUR)

        # Validate non-negative constraints
        assert brick.spec["overdraft_limit"] >= 0, "overdraft_limit must be >= 0"
        assert brick.spec["min_buffer"] >= 0, "min_buffer must be >= 0"

        # Warn if min_buffer > initial_balance (policy breach, not config error)
        initial_balance = brick.spec.get("initial_balance", 0.0)
        if brick.spec["min_buffer"] > initial_balance:
            print(
                f"[WARN] {brick.id}: min_buffer ({brick.spec['min_buffer']:,.2f}) > initial_balance ({initial_balance:,.2f})."
            )

    def simulate(self, brick: ABrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the cash account over the time period.

        Calculates the monthly balance by accumulating cash flows and applying
        monthly interest. The balance serves as both the asset value and the
        cash flow source/sink.

        Args:
            brick: The cash account brick
            ctx: The simulation context

        Returns:
            BrickOutput with cash flows, balance as asset value, and no events
        """
        T = len(ctx.t_index)
        bal = np.zeros(T)
        r_m = brick.spec["interest_pa"] / 12.0  # Monthly interest rate
        cash_in = brick.spec["external_in"].copy()
        cash_out = brick.spec["external_out"].copy()

        # Calculate balance for first month
        bal[0] = brick.spec["initial_balance"] + cash_in[0] - cash_out[0]
        bal[0] += bal[0] * r_m  # Apply interest

        # Calculate balance for remaining months
        for t in range(1, T):
            bal[t] = bal[t - 1] + cash_in[t] - cash_out[t]
            bal[t] += bal[t] * r_m  # Apply interest

        return BrickOutput(
            cash_in=np.zeros(
                T
            ),  # Cash account doesn't generate cash flows, only receives them
            cash_out=np.zeros(T),  # Cash account doesn't generate cash outflows
            asset_value=bal,
            debt_balance=np.zeros(T),
            events=[],
        )
