"""
One-time income flow strategy.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from finbricklab.core.accounts import BOUNDARY_NODE_ID, get_node_id
from finbricklab.core.bricks import FBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.currency import create_amount
from finbricklab.core.interfaces import IFlowStrategy
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


class FlowIncomeOneTime(IFlowStrategy):
    """
    One-time income flow strategy (kind: 'f.income.onetime').

    This strategy models a single one-time income event.
    Commonly used for bonuses, inheritance, tax refunds, or other
    one-time cash inflows.

    Required Parameters:
        - amount: The one-time income amount
        - start_date: The date when the income occurs (set on the brick)

    Optional Parameters:
        - tax_rate: Tax rate on this income (default: 0.0)
    """

    def simulate(self, brick: FBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate one-time income flow (V2: journal-first pattern).

        Creates a single journal entry for the income event on the specified date.

        Args:
            brick: The FBrick instance
            ctx: Scenario context

        Returns:
            BrickOutput with zero arrays (V2: shell behavior)
            Journal entry created for the income event
        """
        # Extract parameters
        amount = brick.spec["amount"]
        tax_rate = brick.spec.get("tax_rate", 0.0)

        # Use the brick's start_date for the event date
        if not brick.start_date:
            raise ValueError(
                f"One-time income brick '{brick.id}' must have a start_date"
            )

        event_date = brick.start_date

        # Calculate net amount after tax
        net_amount = float(amount * (1 - tax_rate))

        # Get the number of months from the context
        T = len(ctx.t_index)

        # V2: Shell behavior - no cash arrays emitted
        cash_in = np.zeros(T)

        # Get journal from context (V2)
        if ctx.journal is None:
            raise ValueError(
                "Journal must be provided in ScenarioContext for V2 postings model"
            )
        journal = ctx.journal

        # Find cash account node ID (use routing or settlement_default_cash_id)
        cash_node_id = None
        # Check for explicit routing in brick links
        if brick.links and "route" in brick.links and "to" in brick.links["route"]:
            route_to = brick.links["route"]["to"]
            if isinstance(route_to, str):
                cash_node_id = get_node_id(route_to, "a")
        # Fallback to settlement_default_cash_id
        if cash_node_id is None and ctx.settlement_default_cash_id:
            cash_node_id = get_node_id(ctx.settlement_default_cash_id, "a")
        # Fallback to first cash account
        if cash_node_id is None:
            for other_brick in ctx.registry.values():
                if hasattr(other_brick, "kind") and other_brick.kind == "a.cash":
                    cash_node_id = get_node_id(other_brick.id, "a")
                    break
        if cash_node_id is None:
            # Final fallback
            cash_node_id = "a:cash"  # Default fallback

        # Find the month when this event occurs
        event_month_str = event_date.strftime("%Y-%m")
        event_month_idx = None

        for month_idx in range(T):
            # Convert the time index to string format for comparison
            current_month_str = str(ctx.t_index[month_idx])

            # Check if this is the month of the event
            if current_month_str == event_month_str:
                event_month_idx = month_idx
                break

        # V2: Create journal entry for one-time income (BOUNDARY↔INTERNAL: CR income, DR cash)
        if event_month_idx is not None and net_amount > 0:
            income_timestamp = ctx.t_index[event_month_idx]
            # Convert numpy datetime64 to Python datetime
            if isinstance(income_timestamp, np.datetime64):
                income_timestamp = pd.Timestamp(income_timestamp).to_pydatetime()
            elif hasattr(income_timestamp, "astype"):
                income_timestamp = pd.Timestamp(
                    income_timestamp.astype("datetime64[D]")
                ).to_pydatetime()
            else:
                income_timestamp = datetime.fromisoformat(str(income_timestamp))

            operation_id = create_operation_id(f"fs:{brick.id}", income_timestamp)
            entry_id = create_entry_id(operation_id, 1)
            origin_id = generate_transaction_id(
                brick.id,
                income_timestamp,
                brick.spec or {},
                brick.links or {},
                sequence=0,
            )

            # CR income (boundary), DR cash (internal)
            income_entry = JournalEntry(
                id=entry_id,
                timestamp=income_timestamp,
                postings=[
                    Posting(
                        account_id=cash_node_id,
                        amount=create_amount(net_amount, ctx.currency),
                        metadata={},
                    ),
                    Posting(
                        account_id=BOUNDARY_NODE_ID,
                        amount=create_amount(-net_amount, ctx.currency),
                        metadata={},
                    ),
                ],
                metadata={},
            )

            stamp_entry_metadata(
                income_entry,
                parent_id=f"fs:{brick.id}",
                timestamp=income_timestamp,
                tags={"type": "income"},
                sequence=1,
                origin_id=origin_id,
            )

            # Set transaction_type for income flows
            income_entry.metadata["transaction_type"] = "income"

            stamp_posting_metadata(
                income_entry.postings[0],
                node_id=cash_node_id,
                type_tag="income",
            )
            stamp_posting_metadata(
                income_entry.postings[1],
                node_id=BOUNDARY_NODE_ID,
                category="income.onetime",
                type_tag="income",
            )

            journal.post(income_entry)

        # V2: Shell behavior - return zero arrays (no balances)
        return BrickOutput(
            cash_in=cash_in,  # Zero - deprecated
            cash_out=np.zeros(T),  # Zero - deprecated
            assets=np.zeros(T),
            liabilities=np.zeros(T),
            interest=np.zeros(T),  # Flow bricks don't generate interest
            events=[],
        )
