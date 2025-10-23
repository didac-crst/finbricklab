"""
Fixed-term credit schedule strategy with linear amortization.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from finbricklab.core.bricks import LBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.interfaces import IScheduleStrategy
from finbricklab.core.results import BrickOutput


class ScheduleCreditFixed(IScheduleStrategy):
    """
    Fixed-term credit schedule strategy (kind: 'l.credit.fixed').

    Models fixed-term credit with linear amortization (equal principal payments).
    Each month pays equal principal plus interest on outstanding balance.

    Required Parameters:
        - principal: Total loan amount
        - rate_pa: Annual interest rate
        - term_months: Loan term in months
        - start_date: Start date for the loan
    """

    def simulate(
        self, brick: LBrick, ctx: ScenarioContext, months: int | None = None
    ) -> BrickOutput:
        """
        Simulate fixed-term credit with linear amortization.

        Args:
            brick: The LBrick instance
            ctx: Scenario context
            months: Number of months to simulate

        Returns:
            BrickOutput with debt balance and cash flows
        """
        # Extract parameters
        principal = Decimal(str(brick.spec["principal"]))
        rate_pa = Decimal(str(brick.spec["rate_pa"]))
        term_months = int(brick.spec["term_months"])
        if brick.start_date:
            start_date = brick.start_date
        else:
            start_date = ctx.t_index[0].astype("datetime64[D]").astype(date)

        # Get months from context if not provided
        if months is None:
            months = len(ctx.t_index)

        # Calculate monthly interest rate
        i_m = rate_pa / Decimal("12")

        # Calculate constant principal payment
        principal_payment = principal / Decimal(str(term_months))

        # Initialize arrays
        debt_balance = np.zeros(months, dtype=float)
        cash_in = np.zeros(months, dtype=float)
        cash_out = np.zeros(months, dtype=float)

        # Track running balance
        current_balance = principal

        # Generate initial disbursement cash flow
        if start_date <= ctx.t_index[0].astype("datetime64[D]").astype(date):
            cash_in[0] = float(principal)

        for month_idx in range(months):
            # Get the date for this month - convert from numpy datetime64 to Python date
            month_date = ctx.t_index[month_idx].astype("datetime64[D]").astype(date)

            # Check if this is a payment month
            is_payment_month = self._is_payment_month(month_date, start_date)

            if is_payment_month and current_balance > 0:
                # Calculate interest on outstanding balance
                interest = current_balance * i_m
                interest = interest.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                # Calculate principal payment (constant, but adjust for final payment)
                remaining_months = term_months - month_idx
                if remaining_months <= 1:
                    # Final payment: pay exact remaining balance
                    principal_payment_this_month = current_balance
                else:
                    principal_payment_this_month = principal_payment

                # Total payment
                total_payment = principal_payment_this_month + interest

                # Update balance
                current_balance -= principal_payment_this_month
                current_balance = max(
                    Decimal("0"), current_balance
                )  # Never go negative

                # Record cash outflow
                cash_out[month_idx] = float(total_payment)

            # Store current balance
            debt_balance[month_idx] = float(current_balance)

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            assets=np.zeros(months, dtype=float),
            liabilities=debt_balance,
            events=[],
        )

    def _is_payment_month(self, month_date: date, start_date: date) -> bool:
        """Check if this month is a payment month."""
        # For now, assume payments happen every month
        # TODO: Implement proper day-of-month logic
        return True
