"""
Cash account valuation strategy.
"""

from __future__ import annotations

import warnings

import numpy as np

from finbricklab.core.bricks import ABrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.interfaces import IValuationStrategy
from finbricklab.core.results import BrickOutput


class ValuationCash(IValuationStrategy):
    """
    Cash account valuation strategy for modeling liquid cash holdings.

    This strategy models a simple cash account that receives external cash flows
    and earns interest on the balance. The balance is computed by accumulating
    all routed cash flows plus interest earned each month.

    **Use Cases:**
    - Checking accounts, savings accounts, money market accounts
    - Base currency holdings in multi-currency scenarios
    - Settlement accounts for cash flow routing

    **Required Parameters:**
        - initial_balance: Starting cash balance (default: 0.0)
        - interest_pa: Annual interest rate (default: 0.0)

    **External Parameters (set by scenario engine):**
        - external_in: Monthly cash inflows from other bricks
        - external_out: Monthly cash outflows to other bricks

    **Example:**
        ```python
        cash_account = ABrick(
            id="checking",
            name="Checking Account",
            kind="a.cash",
            spec={
                "initial_balance": 5000.0,
                "interest_pa": 0.02  # 2% annual interest
            }
        )
        ```

    **Note:**
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

        # Coerce numerics to float for robustness
        brick.spec["initial_balance"] = float(brick.spec["initial_balance"])
        brick.spec["interest_pa"] = float(brick.spec["interest_pa"])

        # Coerce and validate external arrays
        T = len(ctx.t_index)
        for key in ("external_in", "external_out"):
            arr = np.asarray(brick.spec[key], dtype=float)
            if len(arr) != T:
                raise ValueError(
                    f"{brick.id}: '{key}' length {len(arr)} != t_index length {T}"
                )
            brick.spec[key] = arr

        # Set liquidity policy defaults
        brick.spec.setdefault(
            "overdraft_limit", 0.0
        )  # how far below 0 cash may go (EUR)
        brick.spec.setdefault("min_buffer", 0.0)  # desired minimum cash balance (EUR)

        # Validate non-negative constraints
        if brick.spec["overdraft_limit"] < 0:
            raise ValueError("overdraft_limit must be >= 0")
        if brick.spec["min_buffer"] < 0:
            raise ValueError("min_buffer must be >= 0")

        # Warn if min_buffer > initial_balance (policy breach, not config error)
        initial_balance = brick.spec.get("initial_balance", 0.0)
        if brick.spec["min_buffer"] > initial_balance:
            warnings.warn(
                f"{brick.id}: min_buffer ({brick.spec['min_buffer']:,.2f}) > initial_balance ({initial_balance:,.2f}).",
                category=UserWarning,
                stacklevel=2,
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
        # Apply interest on the balance after cash flows
        bal[0] *= (1 + r_m)

        # Calculate balance for remaining months
        for t in range(1, T):
            # Start with previous month's balance
            bal[t] = bal[t - 1]
            # Add/subtract this month's cash flows
            bal[t] += cash_in[t] - cash_out[t]
            # Apply interest on the full balance (including this month's flows)
            bal[t] *= (1 + r_m)

        return BrickOutput(
            cash_in=np.zeros(
                T
            ),  # Cash account doesn't generate cash flows, only receives them
            cash_out=np.zeros(T),  # Cash account doesn't generate cash outflows
            assets=bal,
            liabilities=np.zeros(T),
            events=[],
        )
