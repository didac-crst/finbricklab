"""
Fixed monthly income flow strategy with escalation.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from finbricklab.core.accounts import BOUNDARY_NODE_ID, get_node_id
from finbricklab.core.bricks import FBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.currency import create_amount
from finbricklab.core.events import Event
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


class FlowIncomeRecurring(IFlowStrategy):
    """
    Fixed monthly income flow strategy with escalation (kind: 'f.income.salary').

    This strategy models a regular monthly income stream with optional annual escalation.
    Commonly used for salary, pension, rental income, or other regular income sources.

    Required Parameters:
        - amount_monthly: The base monthly income amount

    Optional Parameters:
        - annual_step_pct: Annual escalation percentage (default: 0.0)
        - step_month: Month when escalation occurs (default: None = anniversary of start_date)
        - step_every_m: Alternative to annual escalation - step every N months (default: None)

    Note:
        - If annual_step_pct > 0, income increases by that percentage each year
        - step_month overrides calendar anniversary (e.g., step_month=6 for June every year)
        - step_every_m provides non-annual escalation (e.g., step_every_m=18 for 18-month steps)
        - annual_step_pct and step_every_m are mutually exclusive
    """

    def prepare(self, brick: FBrick, ctx: ScenarioContext) -> None:
        """
        Prepare the income strategy with escalation.

        Validates parameters and sets up escalation configuration.

        Args:
            brick: The income flow brick
            ctx: The simulation context

        Raises:
            AssertionError: If required parameters are missing or configuration is invalid
        """
        assert (
            "amount_monthly" in brick.spec
        ), "Missing required parameter: amount_monthly"

        # Set defaults for escalation
        brick.spec.setdefault("annual_step_pct", 0.0)
        brick.spec.setdefault("step_month", None)
        brick.spec.setdefault("step_every_m", None)

        # Validate escalation configuration
        annual_step = brick.spec["annual_step_pct"]
        step_every_m = brick.spec["step_every_m"]

        if annual_step != 0.0 and step_every_m is not None:
            raise ValueError("Cannot specify both annual_step_pct and step_every_m")

        if step_every_m is not None:
            if step_every_m < 1:
                raise ValueError("step_every_m must be >= 1")
            # For step_every_m, we need a step percentage
            if "step_pct" not in brick.spec:
                brick.spec["step_pct"] = annual_step  # Use annual_step_pct as default

    def simulate(self, brick: FBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the income with optional escalation (V2: shell behavior).

        Generates monthly journal entries for income (BOUNDARY↔INTERNAL).
        No balances emitted; only journal entries.

        Args:
            brick: The income flow brick
            ctx: The simulation context

        Returns:
            BrickOutput with zero arrays (V2: balances not emitted by shells)
            Journal entries created for each month's income
        """
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

        # Extract parameters
        base_amount = float(brick.spec["amount_monthly"])
        annual_step_pct = float(brick.spec["annual_step_pct"])
        step_month = brick.spec.get("step_month")
        step_every_m = brick.spec.get("step_every_m")
        step_pct = float(
            brick.spec.get("step_pct", annual_step_pct)
        )  # For step_every_m

        # Determine start date for anniversary calculations
        start_date = brick.start_date or ctx.t_index[0].astype("datetime64[D]").astype(
            date
        )

        events = []

        # Calculate escalated amounts for each month
        prev_amount = (
            None  # Track previous month's computed amount for escalation detection
        )
        for t in range(T):
            current_date = ctx.t_index[t].astype("datetime64[D]").astype(date)

            if step_every_m is not None:
                # Non-annual escalation
                months_since_start = t
                steps = months_since_start // step_every_m
                amount = base_amount * ((1 + step_pct) ** steps)
            else:
                # Annual escalation
                years_since_start = current_date.year - start_date.year

                # Check if we've passed the step month in the current year
                if step_month is not None:
                    # Use specified month (e.g., June every year)
                    if current_date.month >= step_month:
                        years_since_start += 1
                else:
                    # Use anniversary of start date
                    if current_date.month > start_date.month or (
                        current_date.month == start_date.month
                        and current_date.day >= start_date.day
                    ):
                        years_since_start += 1

                amount = base_amount * ((1 + annual_step_pct) ** years_since_start)

            # V2: Create journal entry for income (BOUNDARY↔INTERNAL: CR income, DR cash)
            if amount > 0:
                income_timestamp = ctx.t_index[t]
                if isinstance(income_timestamp, np.datetime64):
                    import pandas as pd

                    income_timestamp = pd.Timestamp(income_timestamp).to_pydatetime()
                elif hasattr(income_timestamp, "astype"):
                    import pandas as pd

                    income_timestamp = pd.Timestamp(
                        income_timestamp.astype("datetime64[D]")
                    ).to_pydatetime()
                else:
                    from datetime import datetime

                    income_timestamp = datetime.fromisoformat(str(income_timestamp))

                operation_id = create_operation_id(f"fs:{brick.id}", income_timestamp)
                entry_id = create_entry_id(operation_id, 1)
                origin_id = generate_transaction_id(
                    brick.id,
                    income_timestamp,
                    brick.spec or {},
                    brick.links or {},
                    sequence=t,
                )

                # CR income (boundary), DR cash (internal)
                income_entry = JournalEntry(
                    id=entry_id,
                    timestamp=income_timestamp,
                    postings=[
                        Posting(
                            account_id=cash_node_id,
                            amount=create_amount(amount, ctx.currency),
                            metadata={},
                        ),
                        Posting(
                            account_id=BOUNDARY_NODE_ID,
                            amount=create_amount(-amount, ctx.currency),
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
                    category="income.salary",
                    type_tag="income",
                )

                journal.post(income_entry)

            # Add escalation event for the first month of each new amount
            # V2: cash_in is a shell array (zeros); compare against previously computed amount
            if t == 0 or (t > 0 and prev_amount is not None and amount != prev_amount):
                if annual_step_pct > 0 or step_every_m is not None:
                    events.append(
                        Event(
                            ctx.t_index[t],
                            "income_escalation",
                            f"Income escalated to €{amount:,.2f}/month",
                            {"amount": amount, "annual_step_pct": annual_step_pct},
                        )
                    )
            prev_amount = amount

        # V2: Shell behavior - return zero arrays (no balances)
        return BrickOutput(
            cash_in=cash_in,  # Zero - deprecated
            cash_out=np.zeros(T),  # Zero - deprecated
            assets=np.zeros(T),
            liabilities=np.zeros(T),
            interest=np.zeros(T),  # Flow bricks don't generate interest
            events=events,
        )
