"""
Scheduled transfer strategy.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import numpy as np

from finbricklab.core.bricks import TBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.currency import create_amount
from finbricklab.core.events import Event
from finbricklab.core.interfaces import ITransferStrategy
from finbricklab.core.results import BrickOutput


class TransferScheduled(ITransferStrategy):
    """
    Scheduled transfer strategy (kind: 't.transfer.scheduled').

    This strategy models transfers between internal accounts that occur
    at specific scheduled dates. The transfers move money from one
    internal account to another without affecting net worth.

    Required Parameters:
        - schedule: List of transfer dates and amounts
        - currency: Currency code (default: 'EUR')

    Required Links:
        - from: Source account ID
        - to: Destination account ID

    Optional Parameters:
        - fees: Transfer fees (amount and account)
        - fx: Foreign exchange details (rate, pair, pnl_account)

    Schedule Format:
        schedule = [
            {"date": "2026-01-15", "amount": 1000.0},
            {"date": "2026-06-15", "amount": 2000.0},
            {"date": "2026-12-15", "amount": 1500.0}
        ]

    Note:
        This strategy generates transfer events at the specified dates.
        The actual account balance changes are handled by the journal system.
    """

    def prepare(self, brick: TBrick, ctx: ScenarioContext) -> None:
        """
        Prepare the scheduled transfer strategy.

        Validates that required parameters and links are present.

        Args:
            brick: The transfer brick
            ctx: The simulation context

        Raises:
            AssertionError: If required parameters are missing
        """
        # Validate required parameters
        assert "schedule" in brick.spec, "Missing required parameter: schedule"

        # Validate required links
        assert brick.links is not None, "Missing required links"
        assert "from" in brick.links, "Missing required link: from"
        assert "to" in brick.links, "Missing required link: to"

        # Validate schedule format
        schedule = brick.spec["schedule"]
        assert isinstance(schedule, list), "Schedule must be a list"
        assert len(schedule) > 0, "Schedule cannot be empty"

        for i, entry in enumerate(schedule):
            assert "date" in entry, f"Schedule entry {i} missing 'date'"
            assert "amount" in entry, f"Schedule entry {i} missing 'amount'"

            # Validate amount is positive
            amount = entry["amount"]
            if isinstance(amount, (int, float)):
                amount = Decimal(str(amount))
            assert amount > 0, f"Schedule entry {i} amount must be positive"

            # Validate date format
            date_str = entry["date"]
            try:
                date.fromisoformat(date_str)
            except ValueError:
                raise ValueError(
                    f"Schedule entry {i} has invalid date format: {date_str}"
                )

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

        if "fx" in brick.spec:
            fx = brick.spec["fx"]
            assert "rate" in fx, "FX rate is required"
            assert "pair" in fx, "FX pair is required"

    def simulate(self, brick: TBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the scheduled transfer.

        Generates transfer events at the specified dates.

        Args:
            brick: The transfer brick
            ctx: The simulation context

        Returns:
            BrickOutput with scheduled transfer events and zero cash flows
        """
        T = len(ctx.t_index)

        # Get transfer parameters
        schedule = brick.spec["schedule"]
        currency = brick.spec.get("currency", "EUR")

        # Initialize cash flow arrays
        cash_in = np.zeros(T, dtype=float)
        cash_out = np.zeros(T, dtype=float)

        # Generate transfer events and cash flows
        events = []

        for entry in schedule:
            transfer_date = date.fromisoformat(entry["date"])
            amount = Decimal(str(entry["amount"]))

            # Create amount object
            amount_obj = create_amount(amount, currency)

            # Find the month index for this transfer
            month_idx = None
            for i, t in enumerate(ctx.t_index):
                if t.astype("datetime64[D]").astype(date) >= transfer_date:
                    month_idx = i
                    break
            
            if month_idx is not None and month_idx < T:
                # Record cash flows for the transfer
                # Money goes out from source account (cash_out)
                # Money comes in to destination account (cash_in)
                cash_out[month_idx] += float(amount)
                cash_in[month_idx] += float(amount)

            # Create transfer event
            event = Event(
                transfer_date,
                "transfer",
                f"Scheduled transfer: {amount_obj}",
                {
                    "amount": float(amount),
                    "currency": currency,
                    "from": brick.links["from"],
                    "to": brick.links["to"],
                    "scheduled": True,
                },
            )
            events.append(event)

            # Add fee event if specified
            if "fees" in brick.spec:
                fees = brick.spec["fees"]
                fee_amount = Decimal(str(fees["amount"]))
                fee_currency = fees.get("currency", currency)
                fee_amount_obj = create_amount(fee_amount, fee_currency)

                fee_event = Event(
                    transfer_date,
                    "transfer_fee",
                    f"Transfer fee: {fee_amount_obj}",
                    {
                        "amount": float(fee_amount),
                        "currency": fee_currency,
                        "account": fees["account"],
                    },
                )
                events.append(fee_event)

            # Add FX event if specified
            if "fx" in brick.spec:
                fx = brick.spec["fx"]
                fx_event = Event(
                    transfer_date,
                    "fx_transfer",
                    f"FX transfer: {fx['pair']} @ {fx['rate']}",
                    {
                        "rate": fx["rate"],
                        "pair": fx["pair"],
                        "pnl_account": fx.get("pnl_account", "P&L:FX"),
                    },
                )
                events.append(fx_event)

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            assets=np.zeros(T),
            liabilities=np.zeros(T),
            interest=np.zeros(T),  # Transfer bricks don't generate interest
            events=events,
        )
