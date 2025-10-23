"""
Balloon loan schedule strategy for balloon payment loans.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from finbricklab.core.bricks import LBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.events import Event
from finbricklab.core.interfaces import IScheduleStrategy
from finbricklab.core.results import BrickOutput


class ScheduleLoanBalloon(IScheduleStrategy):
    """
    Balloon loan schedule strategy (kind: 'l.loan.balloon').

    Models balloon payment loans with configurable amortization periods,
    balloon payments, and post-balloon interest-only periods.

    Required Parameters:
        - principal: Total loan amount
        - rate_pa: Annual interest rate
        - balloon_after_months: When to make balloon payment (months from start)
        - amortization_rate_pa: Annual amortization rate (e.g., 0.02 for 2% p.a.)

    Optional Parameters:
        - start_date: Start date for the loan (defaults to scenario start)
        - balloon_type: Type of balloon payment ("residual" or "fixed_amount")
        - balloon_amount: Fixed balloon amount (if balloon_type="fixed_amount")

    Note:
        The loan continues with interest-only payments after the balloon payment
        until the simulation ends. No fixed term is required.
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
        balloon_after_months = int(brick.spec["balloon_after_months"])
        amortization_rate_pa = Decimal(str(brick.spec["amortization_rate_pa"]))
        balloon_type = brick.spec.get("balloon_type", "residual")
        balloon_amount = brick.spec.get("balloon_amount", 0)

        # Get start date from brick attribute or context
        if brick.start_date:
            start_date = brick.start_date
        else:
            start_date = ctx.t_index[0].astype("datetime64[D]").astype(date)

        # Get months from context if not provided
        if months is None:
            months = len(ctx.t_index)

        # Calculate monthly rates
        i_m = rate_pa / Decimal("12")
        amort_rate_m = amortization_rate_pa / Decimal("12")

        # Initialize arrays
        debt_balance = np.zeros(months, dtype=float)
        cash_in = np.zeros(months, dtype=float)
        cash_out = np.zeros(months, dtype=float)
        events: list[Event] = []

        # Track running balance
        current_balance = principal

        # Find start month index
        start_month_idx = None
        for i, t in enumerate(ctx.t_index):
            if t.astype("datetime64[D]").astype(date) >= start_date:
                start_month_idx = i
                break

        if start_month_idx is None:
            # Loan starts after simulation period
            return BrickOutput(
                cash_in=np.zeros(months, dtype=float),
                cash_out=np.zeros(months, dtype=float),
                assets=np.zeros(months, dtype=float),
                liabilities=np.zeros(months, dtype=float),
                events=events,
            )

        # Record loan disbursement event and cash flow
        if start_month_idx < months:
            events.append(
                Event(
                    ctx.t_index[start_month_idx],
                    "loan_disbursement",
                    f"Loan disbursed: €{principal:,.2f}",
                    {"amount": float(principal), "type": "disbursement"},
                )
            )

            # Generate cash flow for loan disbursement
            cash_in[start_month_idx] = float(principal)

        # Calculate monthly amortization amount
        monthly_amortization = principal * amort_rate_m

        for month_idx in range(months):
            # Get the date for this month
            month_date = ctx.t_index[month_idx].astype("datetime64[D]").astype(date)

            # Check if this is a payment month
            is_payment_month = self._is_payment_month(month_date, start_date)

            if is_payment_month and current_balance > 0:
                # Calculate interest on outstanding balance
                interest = current_balance * i_m
                interest = interest.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                # Determine if this is the balloon payment month
                months_since_start = month_idx - start_month_idx
                is_balloon_month = months_since_start == balloon_after_months

                if is_balloon_month:
                    # Balloon payment
                    if balloon_type == "residual":
                        balloon_payment = current_balance
                    elif balloon_type == "fixed_amount":
                        balloon_payment = Decimal(str(balloon_amount))
                    else:
                        raise ValueError(f"Unknown balloon type: {balloon_type}")

                    # Pay off the loan
                    current_balance -= balloon_payment
                    current_balance = max(Decimal("0"), current_balance)

                    # Record balloon payment event
                    events.append(
                        Event(
                            month_date,
                            "balloon_payment",
                            f"Balloon payment: €{balloon_payment:,.2f}",
                            {"amount": float(balloon_payment), "type": "balloon"},
                        )
                    )

                    # Generate cash flow for balloon payment
                    cash_out[month_idx] = float(balloon_payment)

                elif months_since_start < balloon_after_months:
                    # Amortization period - pay interest + principal
                    principal_payment = min(monthly_amortization, current_balance)
                    current_balance -= principal_payment
                    current_balance = max(Decimal("0"), current_balance)

                    # Record regular payment event
                    events.append(
                        Event(
                            month_date,
                            "loan_payment",
                            f"Loan payment: €{principal_payment + interest:,.2f}",
                            {
                                "principal": float(principal_payment),
                                "interest": float(interest),
                                "type": "payment",
                            },
                        )
                    )

                    # Generate cash flow for regular payment
                    total_payment = principal_payment + interest
                    cash_out[month_idx] = float(total_payment)

                else:
                    # Post-balloon interest-only period (continues indefinitely)
                    # Note: current_balance remains unchanged during interest-only period

                    # Record interest-only payment event
                    events.append(
                        Event(
                            month_date,
                            "interest_payment",
                            f"Interest payment: €{interest:,.2f}",
                            {"interest": float(interest), "type": "interest_only"},
                        )
                    )

                    # Generate cash flow for interest-only payment
                    cash_out[month_idx] = float(interest)

            # Store current balance
            debt_balance[month_idx] = float(current_balance)

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            assets=np.zeros(months, dtype=float),
            liabilities=debt_balance,
            events=events,
        )

    def _is_payment_month(self, month_date: date, start_date: date) -> bool:
        """Check if this month is a payment month."""
        # For now, assume payments happen every month
        # TODO: Implement proper day-of-month logic
        return True
