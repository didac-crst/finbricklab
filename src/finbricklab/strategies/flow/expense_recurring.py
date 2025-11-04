"""
Fixed monthly expense flow strategy.
"""

from __future__ import annotations

import numpy as np

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


class FlowExpenseRecurring(IFlowStrategy):
    """
    Fixed monthly expense flow strategy (kind: 'f.expense.recurring').

    This strategy models a regular monthly expense with a constant amount (V2: shell behavior).
    Commonly used for living expenses, insurance, subscriptions, or other
    regular recurring costs.

    Required Parameters:
        - amount_monthly: The monthly expense amount

    Optional Parameters:
        - category: Expense category for boundary posting metadata (default: 'expense.recurring')

    Note:
        V2: This strategy generates journal entries for expenses (BOUNDARY↔INTERNAL).
        No balances emitted; only journal entries.
    """

    def prepare(self, brick: FBrick, ctx: ScenarioContext) -> None:
        """
        Prepare the fixed expense strategy.

        Validates that the amount_monthly parameter is present.

        Args:
            brick: The expense flow brick
            ctx: The simulation context

        Raises:
            AssertionError: If amount_monthly parameter is missing
        """
        assert (
            "amount_monthly" in brick.spec
        ), "Missing required parameter: amount_monthly"

    def simulate(self, brick: FBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the expense with fixed monthly amount (V2: shell behavior).

        Generates monthly journal entries for expenses (BOUNDARY↔INTERNAL).
        No balances emitted; only journal entries.

        Args:
            brick: The expense flow brick
            ctx: The simulation context

        Returns:
            BrickOutput with zero arrays (V2: balances not emitted by shells)
            Journal entries created for each month's expense
        """
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

        # Extract parameters
        amount = float(brick.spec["amount_monthly"])
        category = brick.spec.get("category", "expense.recurring")

        events = []

        # Calculate expense for each month
        for t in range(T):
            # V2: Create journal entry for expense (BOUNDARY↔INTERNAL: DR expense, CR cash)
            if amount > 0:
                expense_timestamp = ctx.t_index[t]
                if isinstance(expense_timestamp, np.datetime64):
                    import pandas as pd

                    expense_timestamp = pd.Timestamp(expense_timestamp).to_pydatetime()
                elif hasattr(expense_timestamp, "astype"):
                    import pandas as pd

                    expense_timestamp = pd.Timestamp(
                        expense_timestamp.astype("datetime64[D]")
                    ).to_pydatetime()
                else:
                    from datetime import datetime

                    expense_timestamp = datetime.fromisoformat(str(expense_timestamp))

                operation_id = create_operation_id(f"fs:{brick.id}", expense_timestamp)
                entry_id = create_entry_id(operation_id, 1)
                origin_id = generate_transaction_id(
                    brick.id,
                    expense_timestamp,
                    brick.spec or {},
                    brick.links or {},
                    sequence=t,
                )

                # DR expense (boundary), CR cash (internal)
                expense_entry = JournalEntry(
                    id=entry_id,
                    timestamp=expense_timestamp,
                    postings=[
                        Posting(
                            account_id=BOUNDARY_NODE_ID,
                            amount=create_amount(amount, ctx.currency),
                            metadata={},
                        ),
                        Posting(
                            account_id=cash_node_id,
                            amount=create_amount(-amount, ctx.currency),
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
            events=events,
        )
