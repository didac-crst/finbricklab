"""
Recurring transfer strategy.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np

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
            ConfigError: If required parameters are missing or invalid
        """
        # Validate required parameters
        if "amount" not in brick.spec:
            raise ConfigError(f"{brick.id}: Missing required parameter 'amount'")
        if "frequency" not in brick.spec:
            raise ConfigError(f"{brick.id}: Missing required parameter 'frequency'")

        # Validate required links
        if not brick.links:
            raise ConfigError(f"{brick.id}: Missing required links")
        if "from" not in brick.links:
            raise ConfigError(f"{brick.id}: Missing required link 'from'")
        if "to" not in brick.links:
            raise ConfigError(f"{brick.id}: Missing required link 'to'")

        # Validate amount is positive
        amount = brick.spec["amount"]
        if isinstance(amount, (int, float)):
            amount = Decimal(str(amount))
        if amount <= 0:
            raise ConfigError(
                f"{brick.id}: Transfer amount must be positive, got {amount!r}"
            )

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
        if frequency not in valid_frequencies:
            raise ConfigError(
                f"{brick.id}: Frequency must be one of {valid_frequencies}, got {frequency!r}"
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
                raise ConfigError(f"{brick.id}: Fee 'amount' is required")
            if "account" not in fees:
                raise ConfigError(f"{brick.id}: Fee 'account' is required")

    def simulate(self, brick: TBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the recurring transfer (V2: journal-first pattern).

        Creates internal↔internal CDPairs for each transfer period.

        Args:
            brick: The transfer brick
            ctx: The simulation context

        Returns:
            BrickOutput with recurring transfer events and zero cash flows
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
        amount = Decimal(str(brick.spec["amount"]))
        frequency = brick.spec["frequency"]
        currency = brick.spec.get("currency", ctx.currency)
        priority = brick.spec.get("priority", 0)

        # Map frequency to interval in months
        freq_map = {
            "MONTHLY": 1,
            "BIMONTHLY": 2,
            "QUARTERLY": 3,
            "SEMIANNUALLY": 6,
            "YEARLY": 12,
            "BIYEARLY": 24,
        }
        try:
            interval_months = freq_map[frequency]
        except KeyError as e:
            raise ValueError(f"Invalid frequency: {frequency}") from e

        # Generate transfer events and journal entries
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
        sequence = 0
        while current_month_idx < T and ctx.t_index[current_month_idx] <= end_m:
            # Use the canonical timeline month for this transfer
            month_idx = current_month_idx
            transfer_timestamp = ctx.t_index[month_idx]

            # Convert timestamp to datetime
            if hasattr(transfer_timestamp, "astype"):
                transfer_timestamp = transfer_timestamp.astype("datetime64[D]").astype(
                    "datetime"
                )
            else:
                from datetime import datetime

                transfer_timestamp = datetime.fromisoformat(str(transfer_timestamp))

            # V2: Create journal entry for internal transfer (INTERNAL↔INTERNAL)
            # DR destination asset, CR source asset
            operation_id = create_operation_id(f"ts:{brick.id}", transfer_timestamp)
            entry_id = create_entry_id(operation_id, 1)
            origin_id = generate_transaction_id(
                brick.id,
                transfer_timestamp,
                brick.spec or {},
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
                f"Recurring transfer: {create_amount(amount, currency)}",
                {
                    "amount": float(amount),
                    "currency": currency,
                    "from": from_account_id,
                    "to": to_account_id,
                    "frequency": frequency,
                    "priority": priority,
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
                        "priority": priority + 1,
                    },
                )
                events.append(fee_event)

            # Move to next transfer month by adding interval
            current_month_idx += interval_months
            sequence += 1

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            assets=np.zeros(T),
            liabilities=np.zeros(T),
            interest=np.zeros(T),  # Transfer bricks don't generate interest
            events=events,
        )
