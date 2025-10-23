"""
Loan balloon schedule strategy for balloon payment loans.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from finbricklab.core.bricks import LBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.interfaces import IScheduleStrategy
from finbricklab.core.results import BrickOutput


class ScheduleLoanBalloon(IScheduleStrategy):
    """
    Loan balloon schedule strategy (kind: 'l.loan.balloon').

    Models balloon payment loans with either interest-only periods or
    partial amortization followed by a balloon payment at maturity.

    Required Parameters:
        - principal: Total loan amount
        - rate_pa: Annual interest rate
        - term_months: Loan term in months
        - amortization: Amortization configuration
        - balloon_at_maturity: Balloon payment type

    Optional Parameters:
        - start_date: Start date for the loan (defaults to scenario start)
    """

    def simulate(
        self, brick: LBrick, ctx: ScenarioContext, months: int | None = None
    ) -> BrickOutput:
        """
        Simulate balloon loan schedule.

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
        amortization = brick.spec["amortization"]
        balloon_type = brick.spec["balloon_at_maturity"]
        
        # Get start date from brick attribute or context
        if brick.start_date:
            start_date = brick.start_date
        else:
            start_date = ctx.t_index[0].astype("datetime64[D]").astype(date)

        # Get months from context if not provided
        if months is None:
            months = len(ctx.t_index)

        # Calculate monthly interest rate
        i_m = rate_pa / Decimal("12")

        # Initialize arrays
        debt_balance = np.zeros(months, dtype=float)
        cash_out = np.zeros(months, dtype=float)

        # Track running balance
        current_balance = principal

        # Calculate amortization parameters
        amort_type = amortization["type"]
        amort_months = amortization.get("amort_months", 0)

        if amort_type == "interest_only":
            # Pure interest-only until balloon
            principal_payment = Decimal("0")
        elif amort_type == "linear":
            if amort_months > 0:
                # Linear amortization for specified months
                principal_payment = principal / Decimal(str(amort_months))
            else:
                # Pure interest-only (amort_months = 0)
                principal_payment = Decimal("0")
        else:
            raise ValueError(f"Unknown amortization type: {amort_type}")

        for month_idx in range(months):
            # Get the date for this month - convert from numpy datetime64 to Python date
            month_date = ctx.t_index[month_idx].astype("datetime64[D]").astype(date)

            # Check if this is a payment month
            is_payment_month = self._is_payment_month(month_date, start_date)

            if is_payment_month and current_balance > 0:
                # Calculate interest on outstanding balance
                interest = current_balance * i_m
                interest = interest.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                # Determine if this is the final month (balloon payment)
                is_final_month = month_idx >= term_months - 1

                if is_final_month:
                    # Balloon payment
                    if balloon_type == "full":
                        # Pay entire remaining balance
                        balloon_payment = current_balance
                    elif balloon_type == "residual":
                        # Pay remaining balance (same as full in this case)
                        balloon_payment = current_balance
                    else:
                        raise ValueError(f"Unknown balloon type: {balloon_type}")

                    total_payment = balloon_payment + interest
                    current_balance = Decimal("0")

                else:
                    # Regular payment
                    if amort_type == "interest_only" or (
                        amort_type == "linear" and month_idx >= amort_months
                    ):
                        # Interest-only payment
                        principal_payment_this_month = Decimal("0")
                    else:
                        # Linear amortization payment
                        principal_payment_this_month = principal_payment

                    total_payment = principal_payment_this_month + interest
                    current_balance -= principal_payment_this_month
                    current_balance = max(
                        Decimal("0"), current_balance
                    )  # Never go negative

                # Record cash outflow
                cash_out[month_idx] = float(total_payment)

            # Store current balance
            debt_balance[month_idx] = float(current_balance)

        return BrickOutput(
            cash_in=np.zeros(months, dtype=float),
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
