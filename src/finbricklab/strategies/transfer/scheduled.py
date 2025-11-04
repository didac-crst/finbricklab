"""
Scheduled transfer strategy.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from finbricklab.core.accounts import BOUNDARY_NODE_ID, get_node_id
from finbricklab.core.bricks import TBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.currency import create_amount
from finbricklab.core.errors import ConfigError
from finbricklab.core.events import Event
from finbricklab.core.interfaces import ITransferStrategy
from finbricklab.core.journal import (
    JournalEntry,
    Posting,
    create_entry_id,
    create_operation_id,
    generate_transaction_id,
    stamp_entry_metadata,
    stamp_posting_metadata,
)
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
        Simulate the scheduled transfer (V2: journal-first pattern).

        Creates internal↔internal CDPairs for each scheduled transfer date.

        Args:
            brick: The transfer brick
            ctx: The simulation context

        Returns:
            BrickOutput with scheduled transfer events and zero cash flows
            (V2: cash_in/cash_out are zero; journal entries created instead)
        """
        T = len(ctx.t_index)

        # V2: Don't emit cash arrays - use journal entries instead
        cash_in = np.zeros(T, dtype=float)
        cash_out = np.zeros(T, dtype=float)

        # Get journal from context (V2)
        if ctx.journal is None:
            raise ValueError(
                "Journal must be provided in ScenarioContext for V2 postings model"
            )
        journal = ctx.journal

        # Get node IDs from links (both must be INTERNAL assets)
        from_account_id = brick.links["from"]
        to_account_id = brick.links["to"]
        from_node_id = get_node_id(from_account_id, "a")
        to_node_id = get_node_id(to_account_id, "a")

        # Validate accounts are different (already done in prepare, but double-check)
        if from_node_id == to_node_id:
            raise ValueError(
                f"{brick.id}: Source and destination accounts must be different"
            )

        # Get transfer parameters
        schedule = brick.spec["schedule"]
        currency = brick.spec.get("currency", ctx.currency)

        # Generate transfer events and journal entries
        events = []
        sequence = 0

        for entry in schedule:
            transfer_date = date.fromisoformat(entry["date"])
            amount = Decimal(str(entry["amount"]))

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
            transfer_timestamp = ctx.t_index[month_idx]

            # Convert timestamp to datetime
            if isinstance(transfer_timestamp, np.datetime64):
                transfer_timestamp = pd.Timestamp(transfer_timestamp).to_pydatetime()
            elif hasattr(transfer_timestamp, "astype"):
                transfer_timestamp = pd.Timestamp(
                    transfer_timestamp.astype("datetime64[D]")
                ).to_pydatetime()
            else:
                transfer_timestamp = datetime.fromisoformat(str(transfer_timestamp))

            # V2: Create journal entry for internal transfer (INTERNAL↔INTERNAL)
            # DR destination asset, CR source asset
            operation_id = create_operation_id(f"ts:{brick.id}", transfer_timestamp)
            entry_id = create_entry_id(operation_id, sequence + 1)
            origin_id = generate_transaction_id(
                brick.id,
                transfer_timestamp,
                {"schedule_entry": entry},
                brick.links or {},
                sequence=sequence,
            )

            transfer_entry = JournalEntry(
                id=entry_id,
                timestamp=transfer_timestamp,
                postings=[
                    Posting(
                        account_id=to_node_id,
                        amount=create_amount(float(amount), currency),
                        metadata={},
                    ),
                    Posting(
                        account_id=from_node_id,
                        amount=create_amount(-float(amount), currency),
                        metadata={},
                    ),
                ],
                metadata={},
            )

            stamp_entry_metadata(
                transfer_entry,
                parent_id=f"ts:{brick.id}",
                timestamp=transfer_timestamp,
                tags={"type": "transfer"},
                sequence=1,
                origin_id=origin_id,
            )

            # Set transaction_type for transfers
            transfer_entry.metadata["transaction_type"] = "transfer"

            # Stamp both postings with node_id and type_tag
            stamp_posting_metadata(
                transfer_entry.postings[0],
                node_id=to_node_id,
                type_tag="transfer",
            )
            stamp_posting_metadata(
                transfer_entry.postings[1],
                node_id=from_node_id,
                type_tag="transfer",
            )

            journal.post(transfer_entry)

            # Create transfer event
            event = Event(
                ctx.t_index[month_idx],
                "transfer",
                f"Scheduled transfer: {create_amount(amount, currency)}",
                {
                    "amount": float(amount),
                    "currency": currency,
                    "from": from_account_id,
                    "to": to_account_id,
                    "scheduled": True,
                },
            )
            events.append(event)

            # Handle fees if specified (create separate fee entry)
            if "fees" in brick.spec:
                fees = brick.spec["fees"]
                fee_amount = Decimal(str(fees["amount"]))
                fee_currency = fees.get("currency", currency)
                fee_account = fees.get("account")

                # Fee entry: DR expense (BOUNDARY), CR destination (INTERNAL)
                # If fee_account is a boundary account, use it; otherwise use BOUNDARY_NODE_ID
                if fee_account:
                    # Check if fee_account is boundary or internal
                    # For now, assume it's a boundary account if not a node_id pattern
                    if fee_account.startswith(("a:", "l:")):
                        fee_node_id = get_node_id(
                            fee_account.split(":")[1], fee_account[0]
                        )
                    else:
                        fee_node_id = BOUNDARY_NODE_ID
                else:
                    fee_node_id = BOUNDARY_NODE_ID

                fee_operation_id = create_operation_id(
                    f"ts:{brick.id}:fee", transfer_timestamp
                )
                fee_entry_id = create_entry_id(fee_operation_id, 1)
                fee_origin_id = generate_transaction_id(
                    brick.id,
                    transfer_timestamp,
                    {"fee": float(fee_amount), "schedule_entry": entry},
                    brick.links or {},
                    sequence=sequence,
                )

                fee_entry = JournalEntry(
                    id=fee_entry_id,
                    timestamp=transfer_timestamp,
                    postings=[
                        Posting(
                            account_id=fee_node_id,
                            amount=create_amount(float(fee_amount), fee_currency),
                            metadata={},
                        ),
                        Posting(
                            account_id=to_node_id,
                            amount=create_amount(-float(fee_amount), fee_currency),
                            metadata={},
                        ),
                    ],
                    metadata={},
                )

                stamp_entry_metadata(
                    fee_entry,
                    parent_id=f"ts:{brick.id}",
                    timestamp=transfer_timestamp,
                    tags={"type": "transfer_fee"},
                    sequence=2,
                    origin_id=fee_origin_id,
                )

                fee_entry.metadata["transaction_type"] = "transfer"

                stamp_posting_metadata(
                    fee_entry.postings[0],
                    node_id=fee_node_id,
                    category="expense.transfer_fee",
                    type_tag="fee",
                )
                stamp_posting_metadata(
                    fee_entry.postings[1],
                    node_id=to_node_id,
                    type_tag="fee",
                )

                journal.post(fee_entry)

                # Create fee event
                fee_event = Event(
                    ctx.t_index[month_idx],
                    "transfer_fee",
                    f"Transfer fee: {create_amount(fee_amount, fee_currency)}",
                    {
                        "amount": float(fee_amount),
                        "currency": fee_currency,
                        "account": fee_account,
                    },
                )
                events.append(fee_event)

            # Add FX event if specified (using same event_t)
            # Note: FX transfers will be handled separately in a future conversion
            if "fx" in brick.spec:
                fx = brick.spec["fx"]
                fx_event = Event(
                    ctx.t_index[month_idx],
                    "fx_transfer",
                    f"FX transfer: {fx['pair']} @ {fx['rate']}",
                    {
                        "rate": fx["rate"],
                        "pair": fx["pair"],
                        "pnl_account": fx.get("pnl_account", "P&L:FX"),
                    },
                )
                events.append(fx_event)

            sequence += 1

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            assets=np.zeros(T),
            liabilities=np.zeros(T),
            interest=np.zeros(T),  # Transfer bricks don't generate interest
            events=events,
        )
