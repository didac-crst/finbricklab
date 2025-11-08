"""
Fixed-term credit schedule strategy with linear amortization.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import numpy as np

from finbricklab.core.accounts import BOUNDARY_NODE_ID, get_node_id
from finbricklab.core.bricks import LBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.currency import create_amount
from finbricklab.core.interfaces import IScheduleStrategy
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

from ._loan_utils import resolve_loan_cash_nodes


class ScheduleCreditFixed(IScheduleStrategy):
    """
    Fixed-term credit schedule strategy (kind: 'l.credit.fixed').

    Models fixed-term credit with linear amortization (equal principal payments).
    Each month pays equal principal plus interest on outstanding balance.

    Required Parameters:
        - principal: Total loan amount
        - rate_pa: Annual interest rate
        - term_months: Loan term in months
        - start_date: Start date for the loan

    Cash routing honours ``links.route``:
        - ``route["to"]`` receives the loan drawdown.
        - ``route["from"]`` funds repayments.
      Missing legs fall back to the scenario settlement default cash account (or the
      first cash brick) for backward compatibility.
    """

    def simulate(
        self, brick: LBrick, ctx: ScenarioContext, months: int | None = None
    ) -> BrickOutput:
        """
        Simulate fixed-term credit with linear amortization.

        Args:
            brick: The LBrick instance
            ctx: Scenario context
            months: Number of months to simulate

        Returns:
            BrickOutput with debt balance and cash flows
        """
        # Extract parameters
        principal = Decimal(str(brick.spec["principal"]))
        rate_pa = Decimal(str(brick.spec["rate_pa"]))
        term_months = int(brick.spec["term_months"])
        if brick.start_date:
            start_date = brick.start_date
        else:
            start_date = ctx.t_index[0].astype("datetime64[D]").astype(date)

        # Get months from context if not provided
        if months is None:
            months = len(ctx.t_index)

        # Calculate monthly interest rate
        i_m = rate_pa / Decimal("12")

        # Calculate constant principal payment
        principal_payment = principal / Decimal(str(term_months))

        # Initialize arrays
        debt_balance = np.zeros(months, dtype=float)
        interest_paid = np.zeros(months, dtype=float)

        if ctx.journal is None:
            raise ValueError(
                "Journal must be provided in ScenarioContext for V2 postings model"
            )
        journal = ctx.journal

        liability_node_id = get_node_id(brick.id, "l")
        cash_draw_node_id, cash_pay_node_id = resolve_loan_cash_nodes(brick, ctx)

        # Track running balance (starts at 0, only becomes principal after disbursement)
        current_balance = Decimal("0")

        # Find the start month index
        start_month_idx = None
        for i, t in enumerate(ctx.t_index):
            if t.astype("datetime64[D]").astype(date) >= start_date:
                start_month_idx = i
                break

        for month_idx in range(months):
            # Record loan disbursement at start month (if we found one)
            if start_month_idx is not None and month_idx == start_month_idx:
                current_balance = principal
                draw_timestamp = ctx.t_index[month_idx]
                if isinstance(draw_timestamp, np.datetime64):
                    import pandas as pd

                    draw_timestamp = pd.Timestamp(draw_timestamp).to_pydatetime()
                elif hasattr(draw_timestamp, "astype"):
                    import pandas as pd

                    draw_timestamp = pd.Timestamp(
                        draw_timestamp.astype("datetime64[D]")
                    ).to_pydatetime()
                else:
                    from datetime import datetime

                    draw_timestamp = datetime.fromisoformat(str(draw_timestamp))

                operation_id = create_operation_id(f"l:{brick.id}", draw_timestamp)
                entry_id = create_entry_id(operation_id, 1)
                origin_id = generate_transaction_id(
                    brick.id,
                    draw_timestamp,
                    brick.spec or {},
                    brick.links or {},
                    sequence=0,
                )
                draw_entry = JournalEntry(
                    id=entry_id,
                    timestamp=draw_timestamp,
                    postings=[
                        Posting(
                            account_id=cash_draw_node_id,
                            amount=create_amount(float(principal), ctx.currency),
                            metadata={},
                        ),
                        Posting(
                            account_id=liability_node_id,
                            amount=create_amount(-float(principal), ctx.currency),
                            metadata={},
                        ),
                    ],
                    metadata={},
                )
                stamp_entry_metadata(
                    draw_entry,
                    parent_id=f"l:{brick.id}",
                    timestamp=draw_timestamp,
                    tags={"type": "drawdown"},
                    sequence=1,
                    origin_id=origin_id,
                )
                stamp_posting_metadata(
                    draw_entry.postings[0],
                    node_id=cash_draw_node_id,
                    type_tag="drawdown",
                )
                stamp_posting_metadata(
                    draw_entry.postings[1],
                    node_id=liability_node_id,
                    type_tag="drawdown",
                )
                if not journal.has_id(draw_entry.id):
                    journal.post(draw_entry)

            # Skip payments if we haven't reached the disbursement month yet
            if start_month_idx is not None and month_idx < start_month_idx:
                debt_balance[month_idx] = 0.0
                continue

            # Get the date for this month - convert from numpy datetime64 to Python date
            month_date = ctx.t_index[month_idx].astype("datetime64[D]").astype(date)

            # Calculate month delta from start for billing logic
            ms = (month_date.year * 12 + month_date.month) - (
                start_date.year * 12 + start_date.month
            )

            # Billing starts from ms >= 1 (month after disbursement)
            is_payment_month = ms >= 1

            if is_payment_month and current_balance > 0:
                # Calculate interest on outstanding balance
                interest = (current_balance * i_m).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

                # Calculate principal payment (constant, but adjust for final payment)
                remaining_term = term_months - (ms - 0)
                principal_payment_this_month = (
                    current_balance
                    if remaining_term <= 1
                    else principal_payment.quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                )

                # Total payment
                total_payment = principal_payment_this_month + interest

                # Update balance
                current_balance -= principal_payment_this_month
                current_balance = max(
                    Decimal("0"), current_balance
                )  # Never go negative

                # Track interest paid
                interest_paid[month_idx] = float(interest)

                payment_timestamp = ctx.t_index[month_idx]
                if isinstance(payment_timestamp, np.datetime64):
                    import pandas as pd

                    payment_timestamp = pd.Timestamp(payment_timestamp).to_pydatetime()
                elif hasattr(payment_timestamp, "astype"):
                    import pandas as pd

                    payment_timestamp = pd.Timestamp(
                        payment_timestamp.astype("datetime64[D]")
                    ).to_pydatetime()
                else:
                    from datetime import datetime

                    payment_timestamp = datetime.fromisoformat(str(payment_timestamp))

                operation_id = create_operation_id(f"l:{brick.id}", payment_timestamp)

                sequence = 1
                if principal_payment_this_month > 0:
                    entry_id = create_entry_id(operation_id, sequence)
                    origin_id = generate_transaction_id(
                        brick.id,
                        payment_timestamp,
                        brick.spec or {},
                        brick.links or {},
                        sequence=month_idx * 100 + sequence,
                    )
                    principal_entry = JournalEntry(
                        id=entry_id,
                        timestamp=payment_timestamp,
                        postings=[
                            Posting(
                                account_id=liability_node_id,
                                amount=create_amount(
                                    float(principal_payment_this_month), ctx.currency
                                ),
                                metadata={},
                            ),
                            Posting(
                                account_id=cash_pay_node_id,
                                amount=create_amount(
                                    -float(principal_payment_this_month), ctx.currency
                                ),
                                metadata={},
                            ),
                        ],
                        metadata={},
                    )
                    stamp_entry_metadata(
                        principal_entry,
                        parent_id=f"l:{brick.id}",
                        timestamp=payment_timestamp,
                        tags={"type": "principal"},
                        sequence=sequence,
                        origin_id=origin_id,
                    )
                    stamp_posting_metadata(
                        principal_entry.postings[0],
                        node_id=liability_node_id,
                        type_tag="principal",
                    )
                    stamp_posting_metadata(
                        principal_entry.postings[1],
                        node_id=cash_pay_node_id,
                        type_tag="principal",
                    )
                    if not journal.has_id(principal_entry.id):
                        journal.post(principal_entry)
                    sequence += 1

                if interest > 0:
                    entry_id = create_entry_id(operation_id, sequence)
                    origin_id = generate_transaction_id(
                        brick.id,
                        payment_timestamp,
                        brick.spec or {},
                        brick.links or {},
                        sequence=month_idx * 100 + sequence,
                    )
                    interest_entry = JournalEntry(
                        id=entry_id,
                        timestamp=payment_timestamp,
                        postings=[
                            Posting(
                                account_id=BOUNDARY_NODE_ID,
                                amount=create_amount(float(interest), ctx.currency),
                                metadata={},
                            ),
                            Posting(
                                account_id=cash_pay_node_id,
                                amount=create_amount(-float(interest), ctx.currency),
                                metadata={},
                            ),
                        ],
                        metadata={},
                    )
                    stamp_entry_metadata(
                        interest_entry,
                        parent_id=f"l:{brick.id}",
                        timestamp=payment_timestamp,
                        tags={"type": "interest"},
                        sequence=sequence,
                        origin_id=origin_id,
                    )
                    interest_entry.metadata["transaction_type"] = "payment"
                    stamp_posting_metadata(
                        interest_entry.postings[0],
                        node_id=BOUNDARY_NODE_ID,
                        category="expense.interest",
                        type_tag="interest",
                    )
                    stamp_posting_metadata(
                        interest_entry.postings[1],
                        node_id=cash_pay_node_id,
                        type_tag="interest",
                    )
                    if not journal.has_id(interest_entry.id):
                        journal.post(interest_entry)

            # Store current balance
            debt_balance[month_idx] = float(current_balance)

        return BrickOutput(
            cash_in=np.zeros(months, dtype=float),
            cash_out=np.zeros(months, dtype=float),
            assets=np.zeros(months, dtype=float),
            liabilities=debt_balance,
            interest=-interest_paid,  # Negative for interest expense
            events=[],
        )
