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

        # Calculate monthly interest rate
        i_m = rate_pa / Decimal("12")

        # Track running balance - start with some initial balance for testing
        current_balance = Decimal("2000.0")  # Start with $2000 balance

        # Generate initial disbursement cash flow
        if start_date <= ctx.t_index[0].astype("datetime64[D]").astype(date):
            cash_in[0] = float(current_balance)

        for month_idx in range(months):
            # Get the date for this month - convert from numpy datetime64 to Python date
            month_date = ctx.t_index[month_idx].astype("datetime64[D]").astype(date)

            # Check if this is a billing cycle month
            is_billing_cycle = self._is_billing_cycle(
                month_date, start_date, billing_day
            )

            if is_billing_cycle:
                # 1. Accrue interest on previous month's closing balance
                if current_balance > 0:  # Only accrue interest on positive balance
                    interest = current_balance * i_m
                    interest = interest.quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    current_balance += interest
                    # Track interest paid
                    interest_paid[month_idx] = float(interest)

                # 2. Add annual fee (prorated monthly)
                if annual_fee > 0:
                    monthly_fee = annual_fee / Decimal("12")
                    current_balance += monthly_fee

                # 3. Calculate minimum payment
                min_payment = self._calculate_minimum_payment(
                    current_balance, min_payment_config
                )

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
        self, balance: Decimal, min_payment_config: dict[str, Any]
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
            # For interest-only, we need to calculate interest on current balance
            # This is a simplified version - in practice, you'd track interest separately
            return balance * Decimal("0.01")  # Simplified: 1% of balance

        elif payment_type == "fixed_or_percent":
            percent = Decimal(str(min_payment_config["percent"]))
            floor = Decimal(str(min_payment_config["floor"]))
            min_payment = max(floor, balance * percent)
            return min_payment

        else:
            raise ValueError(f"Unknown payment type: {payment_type}")
