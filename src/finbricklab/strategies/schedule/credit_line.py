"""
Credit line schedule strategy for revolving credit.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import numpy as np

from finbricklab.core.bricks import LBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.errors import ConfigError
from finbricklab.core.interfaces import IScheduleStrategy
from finbricklab.core.results import BrickOutput


class ScheduleCreditLine(IScheduleStrategy):
    """
    Credit line schedule strategy (kind: 'l.credit.line').

    Models revolving credit like credit cards, HELOCs, and business lines of credit.
    Handles interest accrual, minimum payments, and credit limit enforcement.

    Required Parameters:
        - credit_limit: Maximum credit limit (absolute value)
        - rate_pa: Annual percentage rate (APR)
        - min_payment: Payment policy configuration
        - billing_day: Day of month for billing cycle
        - start_date: Start date for the credit line

    Optional Parameters:
        - fees: Fee structure (currently only annual fee supported)
        - initial_draw: Initial debt balance (default: 0). Set explicitly to avoid surprises.
    """

    def prepare(self, brick: LBrick, ctx: ScenarioContext) -> None:
        """
        Prepare and validate credit line strategy.

        Args:
            brick: The LBrick instance
            ctx: Scenario context

        Raises:
            ConfigError: If required parameters are missing or invalid
        """
        # Validate required parameters
        if "credit_limit" not in brick.spec:
            raise ConfigError(f"{brick.id}: Missing required parameter 'credit_limit'")
        if "rate_pa" not in brick.spec:
            raise ConfigError(f"{brick.id}: Missing required parameter 'rate_pa'")
        if "min_payment" not in brick.spec:
            raise ConfigError(f"{brick.id}: Missing required parameter 'min_payment'")
        if "billing_day" not in brick.spec:
            raise ConfigError(f"{brick.id}: Missing required parameter 'billing_day'")

        # Validate and coerce credit_limit
        credit_limit = brick.spec["credit_limit"]
        if isinstance(credit_limit, (int, float, str)):
            credit_limit = Decimal(str(credit_limit))
        if credit_limit <= 0:
            raise ConfigError(f"{brick.id}: credit_limit must be > 0, got {credit_limit!r}")

        # Validate and coerce rate_pa
        rate_pa = brick.spec["rate_pa"]
        if isinstance(rate_pa, (int, float, str)):
            rate_pa = Decimal(str(rate_pa))
        if rate_pa < 0:
            raise ConfigError(f"{brick.id}: rate_pa must be >= 0, got {rate_pa!r}")

        # Validate initial_draw if provided
        initial_draw = brick.spec.get("initial_draw")
        if initial_draw is not None:
            if isinstance(initial_draw, (int, float, str)):
                initial_draw = Decimal(str(initial_draw))
            if initial_draw < 0:
                raise ConfigError(
                    f"{brick.id}: initial_draw must be >= 0, got {initial_draw!r}"
                )
            if initial_draw > credit_limit:
                raise ConfigError(
                    f"{brick.id}: initial_draw {initial_draw!r} exceeds credit_limit {credit_limit!r}"
                )

        # billing_day is reserved for future calendar-accurate cycles
        # No validation needed yet as it's not used in current implementation

    def simulate(
        self, brick: LBrick, ctx: ScenarioContext, months: int | None = None
    ) -> BrickOutput:
        """
        Simulate credit line schedule with interest accrual and minimum payments.

        Args:
            brick: The LBrick instance
            ctx: Scenario context
            months: Number of months to simulate

        Returns:
            BrickOutput with debt balance and cash flows
        """
        # Extract parameters
        rate_pa = Decimal(str(brick.spec["rate_pa"]))
        min_payment_config = brick.spec["min_payment"]
        billing_day = brick.spec["billing_day"]
        if brick.start_date:
            start_date = brick.start_date
        else:
            start_date = ctx.t_index[0].astype("datetime64[D]").astype(date)

        # Optional parameters
        fees = brick.spec.get("fees", {})
        annual_fee = Decimal(str(fees.get("annual", 0.0)))

        # Get months from context if not provided
        if months is None:
            months = len(ctx.t_index)

        # Initialize arrays
        debt_balance = np.zeros(months, dtype=float)
        cash_in = np.zeros(months, dtype=float)
        cash_out = np.zeros(months, dtype=float)
        interest_paid = np.zeros(months, dtype=float)

        # Extract credit limit and initial draw
        credit_limit = Decimal(str(brick.spec["credit_limit"]))

        # Default to 0 (no initial draw) - users must explicitly set initial_draw
        # Log warning if initial_draw is None to alert users to the default behavior
        initial_draw_value = brick.spec.get("initial_draw")
        if initial_draw_value is None:
            initial_draw = Decimal("0")
            # Note: Could add logging here in the future if desired
            # import logging
            # logging.warning(f"credit_line {brick.id}: initial_draw not specified, defaulting to 0. Set explicitly to avoid surprises.")
        else:
            initial_draw = Decimal(str(initial_draw_value))

        # Validate initial draw
        if initial_draw < 0:
            raise ValueError("initial_draw must be >= 0")
        if initial_draw > credit_limit:
            raise ValueError("initial_draw exceeds credit_limit")

        # Calculate monthly interest rate
        i_m = rate_pa / Decimal("12")

        # Track running balance (no balance before start)
        current_balance = Decimal("0")

        for month_idx in range(months):
            # Get the date for this month - convert from numpy datetime64 to Python date
            month_date = ctx.t_index[month_idx].astype("datetime64[D]").astype(date)

            # Month delta from start_date (month granularity)
            ms = (month_date.year * 12 + month_date.month) - (
                start_date.year * 12 + start_date.month
            )

            # Record initial draw at start month (ms == 0)
            if ms == 0 and initial_draw > 0:
                current_balance = initial_draw
                cash_in[month_idx] = float(initial_draw)

            # Bill monthly starting month after start (ms >= 1)
            if ms >= 1:
                # 1. Accrue interest on previous month's closing balance
                if current_balance > 0:  # Only accrue interest on positive balance
                    interest = current_balance * i_m
                    interest = interest.quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    current_balance += interest
                    # Track interest paid
                    interest_paid[month_idx] = float(interest)

                # 2. Add annual fee (prorated monthly) - quantized
                if annual_fee > 0:
                    monthly_fee = (annual_fee / Decimal("12")).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    current_balance += monthly_fee

                # 3. Calculate minimum payment (with i_m)
                min_payment = self._calculate_minimum_payment(
                    current_balance, min_payment_config, i_m
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                # 4. Apply minimum payment
                if min_payment > 0:
                    payment_amount = min(min_payment, current_balance)
                    current_balance -= payment_amount
                    cash_out[month_idx] = float(payment_amount)

            # Store current balance
            debt_balance[month_idx] = float(current_balance)

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            assets=np.zeros(months, dtype=float),
            liabilities=debt_balance,
            interest=-interest_paid,  # Negative for interest expense
            events=[],
        )

    def _is_billing_cycle(
        self, month_date: date, start_date: date, billing_day: int
    ) -> bool:
        """Check if this month is a billing cycle month."""
        # Since month_date is the first day of the month, we'll trigger billing
        # on the first day of each month for simplicity
        return True  # Simplified: bill every month

    def _calculate_minimum_payment(
        self, balance: Decimal, min_payment_config: dict[str, Any], i_m: Decimal
    ) -> Decimal:
        """Calculate minimum payment based on policy."""
        if balance <= 0:
            return Decimal("0")

        payment_type = min_payment_config["type"]

        if payment_type == "percent":
            percent = Decimal(str(min_payment_config["percent"]))
            min_payment = balance * percent
            floor = min_payment_config.get("floor")
            if floor:
                min_payment = max(min_payment, Decimal(str(floor)))
            return min_payment

        elif payment_type == "interest_only":
            # Pay exactly the accrued monthly interest
            return balance * i_m

        elif payment_type == "fixed_or_percent":
            percent = Decimal(str(min_payment_config["percent"]))
            floor = Decimal(str(min_payment_config["floor"]))
            min_payment = max(floor, balance * percent)
            return min_payment

        else:
            raise ValueError(f"Unknown payment type: {payment_type}")
