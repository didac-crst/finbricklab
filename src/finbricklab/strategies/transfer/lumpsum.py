"""
Lump sum transfer strategy.
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


class TransferLumpSum(ITransferStrategy):
    """
    Lump sum transfer strategy (kind: 't.transfer.lumpsum').

    This strategy models a one-time transfer between internal accounts
    that occurs at a specific point in time. The transfer moves money
    from one internal account to another without affecting net worth.

    Required Parameters:
        - amount: The lump sum amount to transfer
        - currency: Currency code (default: 'EUR')

    Required Links:
        - from: Source account ID
        - to: Destination account ID

    Optional Parameters:
        - fees: Transfer fees (amount and account)
        - fx: Foreign exchange details (rate, pair, pnl_account)

    Note:
        This strategy generates a single transfer event at the specified time.
        The actual account balance changes are handled by the journal system.
    """

    def prepare(self, brick: TBrick, ctx: ScenarioContext) -> None:
        """
        Prepare the lump sum transfer strategy.

        Validates that required parameters and links are present.

        Args:
            brick: The transfer brick
            ctx: The simulation context

        Raises:
            AssertionError: If required parameters are missing
        """
        # Validate required parameters
        assert "amount" in brick.spec, "Missing required parameter: amount"

        # Validate required links
        assert brick.links is not None, "Missing required links"
        assert "from" in brick.links, "Missing required link: from"
        assert "to" in brick.links, "Missing required link: to"

        # Validate amount is positive
        amount = brick.spec["amount"]
        if isinstance(amount, int | float):
            amount = Decimal(str(amount))
        assert amount > 0, "Transfer amount must be positive"

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
        Simulate the lump sum transfer.

        Generates a single transfer event at the specified time.

        Args:
            brick: The transfer brick
            ctx: The simulation context

        Returns:
            BrickOutput with transfer event and zero cash flows
        """
        T = len(ctx.t_index)

        # Get transfer amount and currency
        amount = Decimal(str(brick.spec["amount"]))
        currency = brick.spec.get("currency", "EUR")

        # Create amount object
        amount_obj = create_amount(amount, currency)

        # Find transfer time
        transfer_time = None
        if brick.start_date is not None:
            # Find the index for the start date
            for t in ctx.t_index:
                if t >= brick.start_date:
                    transfer_time = t
                    break

        if transfer_time is None:
            transfer_time = ctx.t_index[0]

        # Initialize cash flow arrays
        cash_in = np.zeros(T, dtype=float)
        cash_out = np.zeros(T, dtype=float)

        # Find the month index for this transfer
        month_idx = None
        for i, t in enumerate(ctx.t_index):
            if t >= transfer_time:
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
            np.datetime64(transfer_time, "M"),
            "transfer",
            f"Lump sum transfer: {amount_obj}",
            {
                "amount": float(amount),
                "currency": currency,
                "from": brick.links["from"],
                "to": brick.links["to"],
            },
        )

        # Add fee event if specified
        events = [event]
        if "fees" in brick.spec:
            fees = brick.spec["fees"]
            fee_amount = Decimal(str(fees["amount"]))
            fee_currency = fees.get("currency", currency)
            fee_amount_obj = create_amount(fee_amount, fee_currency)

            fee_event = Event(
                np.datetime64(transfer_time, "M"),
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
                np.datetime64(transfer_time, "M"),
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
