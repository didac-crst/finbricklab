"""
Recurring transfer strategy.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np

from finbricklab.core.accounts import (
    FX_CLEAR_NODE_ID,
    Account,
    AccountScope,
    AccountType,
    get_node_id,
)
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

from ._validation import validate_fee_account, validate_fx_spec


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

            fee_node_id = validate_fee_account(brick.id, fees.get("account"))
            fees["_account_node_id"] = fee_node_id

        if "fx" in brick.spec:
            fx = brick.spec["fx"]
            if "rate" not in fx or "pair" not in fx:
                raise ConfigError(f"{brick.id}: FX requires 'rate' and 'pair'")
            transfer_currency = brick.spec.get("currency", ctx.currency)
            validate_fx_spec(brick.id, fx, transfer_currency)

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
        fees_series = np.zeros(T, dtype=float)
        taxes_series = np.zeros(T, dtype=float)

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
        end_date = brick.end_date or brick.spec.get("end_date")
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
            if isinstance(transfer_timestamp, np.datetime64):
                import pandas as pd

                transfer_timestamp = pd.Timestamp(transfer_timestamp).to_pydatetime()
            elif hasattr(transfer_timestamp, "astype"):
                import pandas as pd

                transfer_timestamp = pd.Timestamp(
                    transfer_timestamp.astype("datetime64[D]")
                ).to_pydatetime()
            else:
                from datetime import datetime

                transfer_timestamp = datetime.fromisoformat(str(transfer_timestamp))

            # Check if FX is specified
            has_fx = "fx" in brick.spec

            # V2: Create journal entry for internal transfer (INTERNAL↔INTERNAL)
            # DR destination asset, CR source asset
            # Skip regular transfer entry if FX is present (FX entries replace it)
            if not has_fx:
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
                fee_node_id = fees.get("_account_node_id") or validate_fee_account(
                    brick.id, fees.get("account")
                )

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
                        "account": fees.get("account"),
                        "priority": priority + 1,
                    },
                )
                events.append(fee_event)
                fees_series[month_idx] += float(fee_amount)

            # Handle FX if specified (V2: create FX journal entries)
            if has_fx:
                fx = brick.spec["fx"]
                if "_pair_codes" in fx:
                    pair_source, pair_dest = fx["_pair_codes"]
                else:
                    pair_parts = fx["pair"].split("/")
                    if len(pair_parts) != 2:
                        raise ConfigError(
                            f"{brick.id}: FX 'pair' must contain exactly two ISO codes"
                        )
                    pair_source, pair_dest = pair_parts[0], pair_parts[1]

                source_currency = pair_source
                dest_currency = pair_dest

                # Get P&L account (default to "P&L:FX")
                pnl_account = fx.get("pnl_account", "P&L:FX")
                pnl_node_id = pnl_account  # Use as-is (will be registered as boundary)

                # Ensure FX clearing and P&L accounts are registered
                account_registry = ctx.journal.account_registry if ctx.journal else None
                if account_registry:
                    # Register P&L account if not already registered
                    if not account_registry.get_account(pnl_node_id):
                        account_registry.register_account(
                            Account(
                                pnl_node_id,
                                "FX P&L",
                                AccountScope.BOUNDARY,
                                AccountType.PNL,
                            )
                        )

                # Calculate destination amount
                fx_rate = fx.get("_rate_decimal")
                if fx_rate is None:
                    fx_rate = (
                        fx["rate"]
                        if isinstance(fx["rate"], Decimal)
                        else Decimal(str(fx["rate"]))
                    )
                amount_source = amount
                amount_dest = amount_source * fx_rate

                # Get explicit destination amount if provided (for P&L calculation)
                amount_dest_explicit = fx.get("_amount_dest_decimal")
                if amount_dest_explicit is None and "amount_dest" in fx:
                    raw_amount_dest = fx["amount_dest"]
                    if isinstance(raw_amount_dest, Decimal):
                        amount_dest_explicit = raw_amount_dest
                    elif raw_amount_dest is not None:
                        amount_dest_explicit = Decimal(str(raw_amount_dest))

                if amount_dest_explicit is not None:
                    amount_dest = amount_dest_explicit

                # Calculate P&L (residual between rate-derived and explicit amounts)
                # If no explicit amount, P&L is zero (rounding differences only)
                amount_dest_rate_based = amount_source * fx_rate
                if amount_dest_explicit is not None:
                    pnl_amount = amount_dest_explicit - amount_dest_rate_based
                else:
                    pnl_amount = Decimal("0")

                # Entry 1: Source leg (source currency)
                # DR b:fx_clear (source currency), CR a:<from> (source currency)
                fx_operation_id = create_operation_id(
                    f"ts:{brick.id}:fx", transfer_timestamp
                )
                fx_entry_id_1 = create_entry_id(fx_operation_id, 1)
                fx_origin_id_1 = generate_transaction_id(
                    brick.id,
                    transfer_timestamp,
                    {**(brick.spec or {}), "fx_leg": "source"},
                    brick.links or {},
                    sequence=sequence * 100 + 1,
                )

                fx_entry_1 = JournalEntry(
                    id=fx_entry_id_1,
                    timestamp=transfer_timestamp,
                    postings=[
                        Posting(
                            account_id=FX_CLEAR_NODE_ID,
                            amount=create_amount(float(amount_source), source_currency),
                            metadata={},
                        ),
                        Posting(
                            account_id=from_node_id,
                            amount=create_amount(
                                -float(amount_source), source_currency
                            ),
                            metadata={},
                        ),
                    ],
                    metadata={},
                )

                stamp_entry_metadata(
                    fx_entry_1,
                    parent_id=f"ts:{brick.id}",
                    timestamp=transfer_timestamp,
                    tags={"type": "fx_transfer", "fx_leg": "source"},
                    sequence=1,
                    origin_id=fx_origin_id_1,
                )
                fx_entry_1.metadata["transaction_type"] = "fx_transfer"

                stamp_posting_metadata(
                    fx_entry_1.postings[0],
                    node_id=FX_CLEAR_NODE_ID,
                    type_tag="fx_clear",
                    category="fx.clearing",
                )
                stamp_posting_metadata(
                    fx_entry_1.postings[1],
                    node_id=from_node_id,
                    type_tag="fx_transfer",
                )

                # Guard: Skip posting if entry with same ID already exists
                if not journal.has_id(fx_entry_1.id):
                    journal.post(fx_entry_1)

                # Entry 2: Destination leg (destination currency)
                # DR a:<to> (destination currency), CR b:fx_clear (destination currency)
                fx_entry_id_2 = create_entry_id(fx_operation_id, 2)
                fx_origin_id_2 = generate_transaction_id(
                    brick.id,
                    transfer_timestamp,
                    {**(brick.spec or {}), "fx_leg": "dest"},
                    brick.links or {},
                    sequence=sequence * 100 + 2,
                )

                fx_entry_2 = JournalEntry(
                    id=fx_entry_id_2,
                    timestamp=transfer_timestamp,
                    postings=[
                        Posting(
                            account_id=to_node_id,
                            amount=create_amount(float(amount_dest), dest_currency),
                            metadata={},
                        ),
                        Posting(
                            account_id=FX_CLEAR_NODE_ID,
                            amount=create_amount(-float(amount_dest), dest_currency),
                            metadata={},
                        ),
                    ],
                    metadata={},
                )

                stamp_entry_metadata(
                    fx_entry_2,
                    parent_id=f"ts:{brick.id}",
                    timestamp=transfer_timestamp,
                    tags={"type": "fx_transfer", "fx_leg": "dest"},
                    sequence=2,
                    origin_id=fx_origin_id_2,
                )
                fx_entry_2.metadata["transaction_type"] = "fx_transfer"

                stamp_posting_metadata(
                    fx_entry_2.postings[0],
                    node_id=to_node_id,
                    type_tag="fx_transfer",
                )
                stamp_posting_metadata(
                    fx_entry_2.postings[1],
                    node_id=FX_CLEAR_NODE_ID,
                    type_tag="fx_clear",
                    category="fx.clearing",
                )

                # Guard: Skip posting if entry with same ID already exists
                if not journal.has_id(fx_entry_2.id):
                    journal.post(fx_entry_2)

                # Entry 3: P&L entry (if non-zero)
                if abs(pnl_amount) > Decimal("1e-6"):  # Only create if significant
                    fx_entry_id_3 = create_entry_id(fx_operation_id, 3)
                    fx_origin_id_3 = generate_transaction_id(
                        brick.id,
                        transfer_timestamp,
                        {**(brick.spec or {}), "fx_leg": "pnl"},
                        brick.links or {},
                        sequence=sequence * 100 + 3,
                    )

                    # P&L: DR/CR between b:fx_clear and P&L:FX with correct debit/credit alignment
                    abs_pnl = abs(pnl_amount)
                    if pnl_amount > 0:
                        pnl_postings = [
                            Posting(
                                account_id=FX_CLEAR_NODE_ID,
                                amount=create_amount(float(abs_pnl), dest_currency),
                                metadata={},
                            ),
                            Posting(
                                account_id=pnl_node_id,
                                amount=create_amount(-float(abs_pnl), dest_currency),
                                metadata={},
                            ),
                        ]
                        pnl_categories = ["fx.clearing", "income.fx"]
                    else:
                        pnl_postings = [
                            Posting(
                                account_id=pnl_node_id,
                                amount=create_amount(float(abs_pnl), dest_currency),
                                metadata={},
                            ),
                            Posting(
                                account_id=FX_CLEAR_NODE_ID,
                                amount=create_amount(-float(abs_pnl), dest_currency),
                                metadata={},
                            ),
                        ]
                        pnl_categories = ["expense.fx", "fx.clearing"]

                    fx_entry_3 = JournalEntry(
                        id=fx_entry_id_3,
                        timestamp=transfer_timestamp,
                        postings=pnl_postings,
                        metadata={},
                    )

                    stamp_entry_metadata(
                        fx_entry_3,
                        parent_id=f"ts:{brick.id}",
                        timestamp=transfer_timestamp,
                        tags={"type": "fx_transfer", "fx_leg": "pnl"},
                        sequence=3,
                        origin_id=fx_origin_id_3,
                    )
                    fx_entry_3.metadata["transaction_type"] = "fx_transfer"

                    for posting, category in zip(
                        fx_entry_3.postings, pnl_categories, strict=True
                    ):
                        stamp_posting_metadata(
                            posting,
                            node_id=posting.account_id,
                            type_tag="fx_transfer",
                            category=category,
                        )

                    # Guard: Skip posting if entry with same ID already exists
                    if not journal.has_id(fx_entry_3.id):
                        journal.post(fx_entry_3)

                # Create FX event
                fx_event = Event(
                    ctx.t_index[month_idx],
                    "fx_transfer",
                    f"FX transfer: {fx['pair']} @ {fx['rate']}",
                    {
                        "rate": float(fx_rate),
                        "pair": fx["pair"],
                        "pnl_account": pnl_account,
                        "amount_source": float(amount_source),
                        "amount_dest": float(amount_dest),
                        "pnl_amount": float(pnl_amount),
                    },
                )
                events.append(fx_event)

            # Move to next transfer month by adding interval
            current_month_idx += interval_months
            sequence += 1

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            assets=np.zeros(T),
            liabilities=np.zeros(T),
            interest=np.zeros(T),  # Transfer bricks don't generate interest
            fees=fees_series,
            taxes=taxes_series,
            events=events,
        )
