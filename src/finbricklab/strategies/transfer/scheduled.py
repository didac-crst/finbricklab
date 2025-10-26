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
from finbricklab.core.errors import ConfigError
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
            ConfigError: If required parameters are missing or invalid
        """
        # Validate required parameters
        if "schedule" not in brick.spec:
            raise ConfigError(f"{brick.id}: Missing required parameter 'schedule'")

        # Validate required links
        if not brick.links:
            raise ConfigError(f"{brick.id}: Missing required links")
        if "from" not in brick.links:
            raise ConfigError(f"{brick.id}: Missing required link 'from'")
        if "to" not in brick.links:
            raise ConfigError(f"{brick.id}: Missing required link 'to'")

        # Validate schedule format
        schedule = brick.spec["schedule"]
        if not isinstance(schedule, list):
            raise ConfigError(
                f"{brick.id}: 'schedule' must be a list, got {type(schedule).__name__}"
            )
        if len(schedule) == 0:
            raise ConfigError(f"{brick.id}: Schedule cannot be empty")

        for i, entry in enumerate(schedule):
            if "date" not in entry:
                raise ConfigError(f"{brick.id}: Schedule entry {i} missing 'date'")
            if "amount" not in entry:
                raise ConfigError(f"{brick.id}: Schedule entry {i} missing 'amount'")

            # Validate amount is positive
            amount = entry["amount"]
            if isinstance(amount, (int, float)):
                amount = Decimal(str(amount))
            if amount <= 0:
                raise ConfigError(
                    f"{brick.id}: Schedule entry {i} amount must be positive, got {amount!r}"
                )

            # Validate date format
            date_str = entry["date"]
            try:
                date.fromisoformat(date_str)
            except ValueError as e:
                raise ConfigError(
                    f"{brick.id}: Schedule entry {i} has invalid date format: {date_str}"
                ) from e

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
                raise ConfigError(f"{brick.id}: Fee 'amount' is required")
            if "account" not in fees:
                raise ConfigError(f"{brick.id}: Fee 'account' is required")

        if "fx" in brick.spec:
            fx = brick.spec["fx"]
            if "rate" not in fx:
                raise ConfigError(f"{brick.id}: FX 'rate' is required")
            if "pair" not in fx:
                raise ConfigError(f"{brick.id}: FX 'pair' is required")

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

            # Convert transfer date to month precision and find exact match in timeline
            transfer_m = np.datetime64(transfer_date, "M")
            # Find the exact month index using binary search
            month_idx = np.searchsorted(ctx.t_index, transfer_m)

            # Check if transfer date is within the scenario window
            # If month_idx >= T, the date is after the scenario end
            # If month_idx < T but ctx.t_index[month_idx] != transfer_m, the date doesn't match exactly
            if month_idx >= T or (
                month_idx < T and ctx.t_index[month_idx] != transfer_m
            ):
                # Transfer date is out of window - skip this transfer
                # No postings, events, fees, or FX for out-of-window transfers
                continue

            # Use the canonical timeline timestamp for all postings (transfer, fees, FX)
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
                    },
                )
                events.append(fee_event)

            # Add FX event if specified (using same event_t)
            if "fx" in brick.spec:
                fx = brick.spec["fx"]
                fx_event = Event(
                    event_t,
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
