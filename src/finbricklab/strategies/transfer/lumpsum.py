"""
Lump sum transfer strategy.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np

from finbricklab.core.bricks import TBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.currency import create_amount
from finbricklab.core.errors import ConfigError
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
            ConfigError: If required parameters are missing
        """
        # Validate required parameters
        if "amount" not in brick.spec:
            raise ConfigError(f"{brick.id}: Missing required parameter 'amount'")

        # Validate required links
        if not brick.links:
            raise ConfigError(f"{brick.id}: Missing required links")
        if "from" not in brick.links:
            raise ConfigError(f"{brick.id}: Missing required link 'from'")
        if "to" not in brick.links:
            raise ConfigError(f"{brick.id}: Missing required link 'to'")

        # Validate amount is positive
        amount = brick.spec["amount"]
        # Fix: Use tuple for isinstance (PEP 604 union not compatible pre-3.10)
        if isinstance(amount, (int, float, Decimal, str)):
            amount = Decimal(str(amount))
        if not isinstance(amount, Decimal) or amount <= 0:
            raise ConfigError(
                f"{brick.id}: Transfer amount must be positive, got {amount!r}"
            )

        # Validate accounts are different
        from_account = brick.links["from"]
        to_account = brick.links["to"]
        if from_account == to_account:
            raise ConfigError(
                f"{brick.id}: Source and destination accounts must be different (got {from_account})"
            )

        # Validate optional parameters
        if "fees" in brick.spec:
            fees = brick.spec["fees"]
            if "amount" not in fees:
                raise ConfigError(f"{brick.id}: Fee amount is required")
            if "account" not in fees:
                raise ConfigError(f"{brick.id}: Fee account is required")

        if "fx" in brick.spec:
            fx = brick.spec["fx"]
            if "rate" not in fx:
                raise ConfigError(f"{brick.id}: FX rate is required")
            if "pair" not in fx:
                raise ConfigError(f"{brick.id}: FX pair is required")

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

        # Convert start_date to month precision and find exact match in timeline
        transfer_time = None
        month_idx = None

        if brick.start_date is not None:
            # Normalize to month precision
            transfer_m = np.datetime64(brick.start_date, "M")
            # Find the exact month index using binary search
            month_idx = int(np.searchsorted(ctx.t_index, transfer_m))

            # Check if transfer date is within the scenario window
            if month_idx < T and ctx.t_index[month_idx] == transfer_m:
                transfer_time = ctx.t_index[month_idx]
            else:
                # Out of window, skip transfer
                transfer_time = None
        else:
            # No start_date, default to first month
            transfer_time = ctx.t_index[0]
            month_idx = 0

        # Initialize cash flow arrays
        cash_in = np.zeros(T, dtype=float)
        cash_out = np.zeros(T, dtype=float)

        # Only record cash flows if transfer is in window
        if transfer_time is not None and month_idx is not None and month_idx < T:
            # Record cash flows for the transfer
            # Money goes out from source account (cash_out)
            # Money comes in to destination account (cash_in)
            cash_out[month_idx] += float(amount)
            cash_in[month_idx] += float(amount)

            # Create transfer event
            event = Event(
                transfer_time,  # Use canonical timeline timestamp
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
                    transfer_time,  # Use canonical timeline timestamp
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
                    transfer_time,  # Use canonical timeline timestamp
                    "fx_transfer",
                    f"FX transfer: {fx['pair']} @ {fx['rate']}",
                    {
                        "rate": fx["rate"],
                        "pair": fx["pair"],
                        "pnl_account": fx.get("pnl_account", "P&L:FX"),
                    },
                )
                events.append(fx_event)
        else:
            # No transfer (out of window)
            events = []

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            assets=np.zeros(T),
            liabilities=np.zeros(T),
            interest=np.zeros(T),  # Transfer bricks don't generate interest
            events=events,
        )
