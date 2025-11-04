"""
One-time expense flow strategy.
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


class FlowExpenseOneTime(IFlowStrategy):
    """
    One-time expense flow strategy (kind: 'f.expense.onetime').

    This strategy models a single one-time expense event.
    Commonly used for major purchases, emergency expenses,
    one-time fees, or other irregular cash outflows.

    Required Parameters:
        - amount: The one-time expense amount
        - date: The date when the expense occurs (YYYY-MM-DD format)

    Optional Parameters:
        - tax_deductible: Whether this expense is tax deductible (default: False)
        - tax_rate: Tax rate for deduction (default: 0.0)
    """

    def simulate(self, brick: FBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate one-time expense flow (V2: journal-first pattern).

        Creates a single journal entry for the expense event on the specified date.

        Args:
            brick: The FBrick instance
            ctx: Scenario context

        Returns:
            BrickOutput with zero arrays (V2: shell behavior)
            Journal entry created for the expense event
        """
        # Extract parameters
        amount = brick.spec["amount"]
        date_str = brick.spec["date"]
        tax_deductible = brick.spec.get("tax_deductible", False)
        tax_rate = brick.spec.get("tax_rate", 0.0)
        category = brick.spec.get("category", "expense.onetime")

        # Parse the date
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        # Calculate net amount (with potential tax deduction)
        if tax_deductible:
            net_amount = float(amount * (1 - tax_rate))
        else:
            net_amount = float(amount)

        # Get the number of months from the context
        T = len(ctx.t_index)

        # V2: Shell behavior - no cash arrays emitted
        cash_out = np.zeros(T)

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
        # Convert the event date to a string format that matches the time index
        event_month_str = event_date.strftime("%Y-%m")
        event_month_idx = None

        for month_idx in range(T):
            # Convert the time index to string format for comparison
            current_month_str = str(ctx.t_index[month_idx])

            # Check if this is the month of the event
            if current_month_str == event_month_str:
                event_month_idx = month_idx
                break

        # V2: Create journal entry for one-time expense (BOUNDARY↔INTERNAL: DR expense, CR cash)
        if event_month_idx is not None and net_amount > 0:
            expense_timestamp = ctx.t_index[event_month_idx]
            # Convert numpy datetime64 to Python datetime
            if isinstance(expense_timestamp, np.datetime64):
                expense_timestamp = pd.Timestamp(expense_timestamp).to_pydatetime()
            elif hasattr(expense_timestamp, "astype"):
                expense_timestamp = pd.Timestamp(
                    expense_timestamp.astype("datetime64[D]")
                ).to_pydatetime()
            else:
                expense_timestamp = datetime.fromisoformat(str(expense_timestamp))

            operation_id = create_operation_id(f"fs:{brick.id}", expense_timestamp)
            entry_id = create_entry_id(operation_id, 1)
            origin_id = generate_transaction_id(
                brick.id,
                expense_timestamp,
                brick.spec or {},
                brick.links or {},
                sequence=0,
            )

            # DR expense (boundary), CR cash (internal)
            expense_entry = JournalEntry(
                id=entry_id,
                timestamp=expense_timestamp,
                postings=[
                    Posting(
                        account_id=BOUNDARY_NODE_ID,
                        amount=create_amount(net_amount, ctx.currency),
                        metadata={},
                    ),
                    Posting(
                        account_id=cash_node_id,
                        amount=create_amount(-net_amount, ctx.currency),
                        metadata={},
                    ),
                ],
                metadata={},
            )

            stamp_entry_metadata(
                expense_entry,
                parent_id=f"fs:{brick.id}",
                timestamp=expense_timestamp,
                tags={"type": "expense"},
                sequence=1,
                origin_id=origin_id,
            )

            # Set transaction_type for expense flows
            expense_entry.metadata["transaction_type"] = "expense"

            stamp_posting_metadata(
                expense_entry.postings[0],
                node_id=BOUNDARY_NODE_ID,
                category=category,
                type_tag="expense",
            )
            stamp_posting_metadata(
                expense_entry.postings[1],
                node_id=cash_node_id,
                type_tag="expense",
            )

            journal.post(expense_entry)

        # V2: Shell behavior - return zero arrays (no balances)
        return BrickOutput(
            cash_in=np.zeros(T),  # Zero - deprecated
            cash_out=cash_out,  # Zero - deprecated
            assets=np.zeros(T),
            liabilities=np.zeros(T),
            interest=np.zeros(T),  # Flow bricks don't generate interest
            events=[],
        )
