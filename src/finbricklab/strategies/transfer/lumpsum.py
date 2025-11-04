"""
Lump sum transfer strategy.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from finbricklab.core.accounts import BOUNDARY_NODE_ID, get_node_id
from finbricklab.core.bricks import TBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.currency import create_amount
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
        Simulate the lump sum transfer (V2: journal-first pattern).

        Creates a single internal↔internal CDPair for the one-time transfer.

        Args:
            brick: The transfer brick
            ctx: The simulation context

        Returns:
            BrickOutput with transfer event and zero cash flows
            (V2: cash_in/cash_out are zero; journal entry created instead)
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

        # Get transfer amount and currency
        amount = Decimal(str(brick.spec["amount"]))
        currency = brick.spec.get("currency", ctx.currency)

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

        # Find the month index for this transfer
        month_idx = None
        for i, t in enumerate(ctx.t_index):
            if t >= transfer_time:
                month_idx = i
                break

        if month_idx is None:
            month_idx = 0

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

        events = []

        # V2: Create journal entry for internal transfer (INTERNAL↔INTERNAL)
        # DR destination asset, CR source asset
        if month_idx < T:
            operation_id = create_operation_id(f"ts:{brick.id}", transfer_timestamp)
            entry_id = create_entry_id(operation_id, 1)
            origin_id = generate_transaction_id(
                brick.id,
                transfer_timestamp,
                brick.spec or {},
                brick.links or {},
                sequence=0,
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
                f"Lump sum transfer: {create_amount(amount, currency)}",
                {
                    "amount": float(amount),
                    "currency": currency,
                    "from": from_account_id,
                    "to": to_account_id,
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
                    {"fee": float(fee_amount)},
                    brick.links or {},
                    sequence=0,
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

            # Add FX event if specified
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

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            assets=np.zeros(T),
            liabilities=np.zeros(T),
            interest=np.zeros(T),  # Transfer bricks don't generate interest
            events=events,
        )
