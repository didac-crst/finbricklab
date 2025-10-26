"""
Cash account valuation strategy.
"""

from __future__ import annotations

import warnings

import numpy as np

from finbricklab.core.bricks import ABrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.errors import ConfigError
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
        # overdraft_limit: None = unlimited (default for backward compatibility)
        if "overdraft_limit" not in brick.spec:
            brick.spec["overdraft_limit"] = None
        brick.spec.setdefault("min_buffer", 0.0)  # desired minimum cash balance (EUR)
        brick.spec.setdefault("overdraft_policy", "ignore")  # ignore|warn|raise

        # Validate overdraft_limit if provided
        if brick.spec["overdraft_limit"] is not None:
            if brick.spec["overdraft_limit"] < 0:
                raise ConfigError(
                    f"{brick.id}: overdraft_limit must be >= 0, got {brick.spec['overdraft_limit']}"
                )
            # Validate overdraft_policy
            policy = brick.spec["overdraft_policy"].lower()
            if policy not in {"ignore", "warn", "raise"}:
                raise ConfigError(
                    f"{brick.id}: overdraft_policy must be 'ignore'|'warn'|'raise', got {policy!r}"
                )
            brick.spec["overdraft_policy"] = policy
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
        # Don't copy the arrays - use them directly to allow runtime modifications
        cash_in = brick.spec["external_in"]
        cash_out = brick.spec["external_out"]

        # Support for post-interest adjustments (for maturity transfers)
        # Coerce and validate arrays
        post_interest_in = np.asarray(
            brick.spec.get("post_interest_in", np.zeros(T)), dtype=float
        )
        post_interest_out = np.asarray(
            brick.spec.get("post_interest_out", np.zeros(T)), dtype=float
        )

        # Validate length matches timeline
        if len(post_interest_in) != T or len(post_interest_out) != T:
            raise ValueError(f"{brick.id}: 'post_interest_in/out' must have length {T}")

        # Initialize interest tracking array
        interest_earned = np.zeros(T)

        # Apply active mask to enforce start_date and end_date
        from finbricklab.core.utils import active_mask

        mask = active_mask(
            ctx.t_index, brick.start_date, brick.end_date, brick.duration_m
        )

        # Get overdraft limit and policy
        overdraft_limit = brick.spec.get("overdraft_limit")
        overdraft_policy = brick.spec.get("overdraft_policy", "ignore")

        # Calculate balance for first month
        if mask[0]:
            bal[0] = brick.spec["initial_balance"] + cash_in[0] - cash_out[0]
            # Apply interest on the balance after cash flows
            interest_earned[0] = bal[0] * r_m
            bal[0] *= 1 + r_m
            # Apply post-interest adjustments (no interest on these)
            bal[0] += post_interest_in[0] - post_interest_out[0]

            # Enforce overdraft limit if configured
            if overdraft_limit is not None and bal[0] < -overdraft_limit:
                if overdraft_policy == "raise":
                    raise ConfigError(
                        f"{brick.id}: overdraft_limit exceeded at month 0: balance {bal[0]:.2f} < -{overdraft_limit:.2f}"
                    )
                elif overdraft_policy == "warn":
                    import logging

                    log = logging.getLogger(__name__)
                    log.warning(
                        "%s: overdraft_limit exceeded at month 0: balance %.2f < -%.2f",
                        brick.id,
                        bal[0],
                        overdraft_limit,
                    )
                # "ignore": do nothing; keep balance as computed
        else:
            bal[0] = 0.0
            interest_earned[0] = 0.0

        # Calculate balance for remaining months
        for t in range(1, T):
            # Apply active mask before interest calculations
            if mask[t]:
                # Start with previous month's balance
                bal[t] = bal[t - 1]
                # Add/subtract this month's cash flows
                bal[t] += cash_in[t] - cash_out[t]
                # Calculate interest on the full balance (including this month's flows)
                interest_earned[t] = bal[t] * r_m
                # Apply interest
                bal[t] *= 1 + r_m
                # Apply post-interest adjustments (no interest on these)
                bal[t] += post_interest_in[t] - post_interest_out[t]

                # Enforce overdraft limit if configured
                if overdraft_limit is not None and bal[t] < -overdraft_limit:
                    if overdraft_policy == "raise":
                        raise ConfigError(
                            f"{brick.id}: overdraft_limit exceeded at month {t}: balance {bal[t]:.2f} < -{overdraft_limit:.2f}"
                        )
                    elif overdraft_policy == "warn":
                        import logging

                        log = logging.getLogger(__name__)
                        log.warning(
                            "%s: overdraft_limit exceeded at month %d: balance %.2f < -%.2f",
                            brick.id,
                            t,
                            bal[t],
                            overdraft_limit,
                        )
                    # "ignore": do nothing; keep balance as computed
            else:
                bal[t] = 0.0
                interest_earned[t] = 0.0

        return BrickOutput(
            cash_in=np.zeros(
                T
            ),  # Cash account doesn't generate cash flows, only receives them
            cash_out=np.zeros(T),  # Cash account doesn't generate cash outflows
            assets=bal,
            liabilities=np.zeros(T),
            interest=interest_earned,  # Interest earned on cash balance
            events=[],
        )
