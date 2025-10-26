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
    """

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
        # Default to 10% of credit limit if not specified (typical credit card usage)
        credit_limit = Decimal(str(brick.spec["credit_limit"]))
        initial_draw = Decimal(
            str(brick.spec.get("initial_draw", float(credit_limit) * 0.1))
        )

        # Validate initial draw
        if initial_draw < 0:
            raise ValueError("initial_draw must be >= 0")
        if initial_draw > credit_limit:
            raise ValueError("initial_draw exceeds credit_limit")

        # Calculate monthly interest rate
        i_m = rate_pa / Decimal("12")

        # Track running balance
        current_balance = initial_draw

        for month_idx in range(months):
            # Get the date for this month - convert from numpy datetime64 to Python date
            month_date = ctx.t_index[month_idx].astype("datetime64[D]").astype(date)

            # Month delta from start_date (month granularity)
            ms = (month_date.year * 12 + month_date.month) - (
                start_date.year * 12 + start_date.month
            )

            # Record initial draw at start month (ms == 0)
            if ms == 0 and initial_draw > 0:
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
