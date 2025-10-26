"""
Recurring transfer strategy.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np

from finbricklab.core.bricks import TBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.currency import create_amount
from finbricklab.core.events import Event
from finbricklab.core.interfaces import ITransferStrategy
from finbricklab.core.results import BrickOutput


class TransferRecurring(ITransferStrategy):
    """
    Recurring transfer strategy (kind: 't.transfer.recurring').

    This strategy models periodic transfers between internal accounts
    that occur at regular intervals. The transfers move money from one
    internal account to another without affecting net worth.

    Required Parameters:
        - amount: The amount to transfer each period
        - frequency: Transfer frequency ('MONTHLY', 'BIMONTHLY', 'QUARTERLY', 'SEMIANNUALLY', 'YEARLY', 'BIYEARLY')
        - currency: Currency code (default: 'EUR')

    Required Links:
        - from: Source account ID
        - to: Destination account ID

    Optional Parameters:
        - start_date: When to start transfers (default: scenario start)
        - end_date: When to stop transfers (default: scenario end)
        - day_of_month: Day of month for transfers (default: 1)
        - fees: Transfer fees (amount and account)
        - priority: Transfer priority for same-day ordering (default: 0)

    Note:
        This strategy generates recurring transfer events at the specified frequency.
        The actual account balance changes are handled by the journal system.
    """

    def prepare(self, brick: TBrick, ctx: ScenarioContext) -> None:
        """
        Prepare the recurring transfer strategy.

        Validates that required parameters and links are present.

        Args:
            brick: The transfer brick
            ctx: The simulation context

        Raises:
            AssertionError: If required parameters are missing
        """
        # Validate required parameters
        assert "amount" in brick.spec, "Missing required parameter: amount"
        assert "frequency" in brick.spec, "Missing required parameter: frequency"

        # Validate required links
        assert brick.links is not None, "Missing required links"
        assert "from" in brick.links, "Missing required link: from"
        assert "to" in brick.links, "Missing required link: to"

        # Validate amount is positive
        amount = brick.spec["amount"]
        if isinstance(amount, int | float):
            amount = Decimal(str(amount))
        assert amount > 0, "Transfer amount must be positive"

        # Validate frequency
        frequency = brick.spec["frequency"]
        valid_frequencies = [
            "MONTHLY",
            "BIMONTHLY",
            "QUARTERLY",
            "SEMIANNUALLY",
            "YEARLY",
            "BIYEARLY",
        ]
        assert (
            frequency in valid_frequencies
        ), f"Frequency must be one of {valid_frequencies}"

        # Validate accounts are different
        from_account = brick.links["from"]
        to_account = brick.links["to"]
        assert (
            from_account != to_account
        ), "Source and destination accounts must be different"

        # Validate optional parameters
        if "fees" in brick.spec:
            fees = brick.spec["fees"]
            assert "amount" in fees, "Fee amount is required"
            assert "account" in fees, "Fee account is required"

    def simulate(self, brick: TBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the recurring transfer.

        Generates transfer events at the specified frequency.

        Args:
            brick: The transfer brick
            ctx: The simulation context

        Returns:
            BrickOutput with recurring transfer events and zero cash flows
        """
        T = len(ctx.t_index)

        # Get transfer parameters
        amount = Decimal(str(brick.spec["amount"]))
        frequency = brick.spec["frequency"]
        currency = brick.spec.get("currency", "EUR")
        # day_of_month = brick.spec.get("day_of_month", 1)  # Not used in current implementation
        priority = brick.spec.get("priority", 0)

        # Create amount object
        amount_obj = create_amount(amount, currency)

        # Determine transfer frequency in months
        if frequency == "MONTHLY":
            interval_months = 1
        elif frequency == "BIMONTHLY":
            interval_months = 2
        elif frequency == "QUARTERLY":
            interval_months = 3
        elif frequency == "SEMIANNUALLY":
            interval_months = 6
        elif frequency == "YEARLY":
            interval_months = 12
        elif frequency == "BIYEARLY":
            interval_months = 24  # Used in loop below
        else:
            raise ValueError(f"Invalid frequency: {frequency}")

        # Initialize cash flow arrays
        cash_in = np.zeros(T, dtype=float)
        cash_out = np.zeros(T, dtype=float)

        # Generate transfer events and cash flows
        events = []

        # Normalize start_date to month precision and find index
        if brick.start_date:
            start_m = np.datetime64(brick.start_date, "M")
            start_idx = int(np.searchsorted(ctx.t_index, start_m))
        else:
            start_idx = 0

        # Normalize end_date to month precision
        end_date = brick.spec.get("end_date")
        scenario_end_m = ctx.t_index[-1]
        end_m = np.datetime64(end_date, "M") if end_date else scenario_end_m
        end_m = min(end_m, scenario_end_m)  # Don't go past scenario end

        # Build month sequence aligned to timeline
        current_month_idx = start_idx
        while current_month_idx < T and ctx.t_index[current_month_idx] <= end_m:
            # Use the canonical timeline month for this transfer
            month_idx = current_month_idx
            event_t = ctx.t_index[month_idx]

            if month_idx < T:
                # Record cash flows for the transfer
                # Money goes out from source account (cash_out)
                # Money comes in to destination account (cash_in)
                cash_out[month_idx] += float(amount)
                cash_in[month_idx] += float(amount)

            # Create transfer event using canonical timeline timestamp
            event = Event(
                event_t,
                "transfer",
                f"Recurring transfer: {amount_obj}",
                {
                    "amount": float(amount),
                    "currency": currency,
                    "from": brick.links["from"],
                    "to": brick.links["to"],
                    "frequency": frequency,
                    "priority": priority,
                },
            )
            events.append(event)

            # Add fee event if specified (using same event_t)
            if "fees" in brick.spec:
                fees = brick.spec["fees"]
                fee_amount = Decimal(str(fees["amount"]))
                fee_currency = fees.get("currency", currency)
                fee_amount_obj = create_amount(fee_amount, fee_currency)

                fee_event = Event(
                    event_t,
                    "transfer_fee",
                    f"Transfer fee: {fee_amount_obj}",
                    {
                        "amount": float(fee_amount),
                        "currency": fee_currency,
                        "account": fees["account"],
                        "priority": priority + 1,
                    },
                )
                events.append(fee_event)

            # Move to next transfer month by adding interval
            current_month_idx += interval_months

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            assets=np.zeros(T),
            liabilities=np.zeros(T),
            interest=np.zeros(T),  # Transfer bricks don't generate interest
            events=events,
        )
