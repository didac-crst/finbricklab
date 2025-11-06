"""
Balloon loan schedule strategy for balloon payment loans.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd

from finbricklab.core.accounts import BOUNDARY_NODE_ID, get_node_id
from finbricklab.core.bricks import LBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.currency import create_amount
from finbricklab.core.events import Event
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


class ScheduleLoanBalloon(IScheduleStrategy):
    """
    Balloon loan schedule strategy (kind: 'l.loan.balloon').

    Models balloon payment loans with configurable amortization periods,
    balloon payments, and post-balloon interest-only periods.

    Required Parameters:
        - principal: Total loan amount
        - rate_pa: Annual interest rate
        - balloon_after_months: When to make balloon payment (months from start)
        - amortization_rate_pa: Annual amortization rate (e.g., 0.02 for 2% p.a.)

    Optional Parameters:
        - start_date: Start date for the loan (defaults to scenario start)
        - balloon_type: Type of balloon payment ("residual" or "fixed_amount")
        - balloon_amount: Fixed balloon amount (if balloon_type="fixed_amount")

    Note:
        The loan continues with interest-only payments after the balloon payment
        until the simulation ends. No fixed term is required.
    """

    def simulate(
        self, brick: LBrick, ctx: ScenarioContext, months: int | None = None
    ) -> BrickOutput:
        """
        Simulate balloon loan schedule (V2: journal-first pattern).

        Creates journal entries for disbursement, monthly payments (principal/interest),
        balloon payment, and post-balloon interest-only payments.

        Args:
            brick: The LBrick instance
            ctx: Scenario context
            months: Number of months to simulate

        Returns:
            BrickOutput with debt balance and zero cash flows
            (V2: cash_in/cash_out are zero; journal entries created instead)
        """
        # Extract parameters
        principal = Decimal(str(brick.spec["principal"]))
        rate_pa = Decimal(str(brick.spec["rate_pa"]))
        balloon_after_months = int(brick.spec["balloon_after_months"])
        amortization_rate_pa = Decimal(str(brick.spec["amortization_rate_pa"]))
        balloon_type = brick.spec.get("balloon_type", "residual")
        balloon_amount = brick.spec.get("balloon_amount", 0)

        # Get start date from brick attribute or context
        if brick.start_date:
            start_date = brick.start_date
        else:
            start_date = ctx.t_index[0].astype("datetime64[D]").astype(date)

        # Get months from context if not provided
        if months is None:
            months = len(ctx.t_index)

        T = len(ctx.t_index)

        # V2: Don't emit cash arrays - use journal entries instead
        cash_in = np.zeros(T, dtype=float)
        cash_out = np.zeros(T, dtype=float)
        debt_balance = np.zeros(T, dtype=float)
        interest_paid = np.zeros(T, dtype=float)

        # Get journal from context (V2)
        if ctx.journal is None:
            raise ValueError(
                "Journal must be provided in ScenarioContext for V2 postings model"
            )
        journal = ctx.journal

        # Get node IDs
        liability_node_id = get_node_id(brick.id, "l")
        # Find cash account node ID (use settlement_default_cash_id or find from registry)
        cash_node_id = None
        if ctx.settlement_default_cash_id:
            cash_node_id = get_node_id(ctx.settlement_default_cash_id, "a")
        else:
            # Find first cash account from registry
            for other_brick in ctx.registry.values():
                if hasattr(other_brick, "kind") and other_brick.kind == "a.cash":
                    cash_node_id = get_node_id(other_brick.id, "a")
                    break
        if cash_node_id is None:
            # Fallback: use default
            cash_node_id = "a:cash"  # Default fallback

        # Calculate monthly rates
        i_m = rate_pa / Decimal("12")
        amort_rate_m = amortization_rate_pa / Decimal("12")

        events: list[Event] = []

        # Track running balance
        current_balance = Decimal("0")

        # Find start month index
        start_month_idx = None
        for i, t in enumerate(ctx.t_index):
            if t.astype("datetime64[D]").astype(date) >= start_date:
                start_month_idx = i
                break

        if start_month_idx is None:
            # Loan starts after simulation period
            return BrickOutput(
                cash_in=cash_in,
                cash_out=cash_out,
                assets=np.zeros(T, dtype=float),
                liabilities=debt_balance,
                interest=interest_paid,
                events=events,
            )

        # V2: Create journal entry for disbursement (INTERNAL↔INTERNAL: DR cash, CR liability)
        if start_month_idx < T:
            # Set principal from start month onward
            current_balance = principal
            debt_balance[start_month_idx] = float(principal)

            # Create disbursement entry
            drawdown_timestamp = ctx.t_index[start_month_idx]
            # Convert numpy datetime64 to Python datetime
            if isinstance(drawdown_timestamp, np.datetime64):
                drawdown_timestamp = pd.Timestamp(drawdown_timestamp).to_pydatetime()
            elif hasattr(drawdown_timestamp, "astype"):
                drawdown_timestamp = pd.Timestamp(
                    drawdown_timestamp.astype("datetime64[D]")
                ).to_pydatetime()
            else:
                drawdown_timestamp = datetime.fromisoformat(str(drawdown_timestamp))

            operation_id = create_operation_id(f"l:{brick.id}", drawdown_timestamp)
            entry_id = create_entry_id(operation_id, 1)
            origin_id = generate_transaction_id(
                brick.id,
                drawdown_timestamp,
                brick.spec or {},
                brick.links or {},
                sequence=0,
            )

            # DR cash (increase cash), CR liability (increase debt)
            drawdown_entry = JournalEntry(
                id=entry_id,
                timestamp=drawdown_timestamp,
                postings=[
                    Posting(
                        account_id=cash_node_id,
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
                drawdown_entry,
                parent_id=f"l:{brick.id}",
                timestamp=drawdown_timestamp,
                tags={"type": "drawdown"},
                sequence=1,
                origin_id=origin_id,
            )

            # Set transaction_type for disbursements
            drawdown_entry.metadata["transaction_type"] = "disbursement"

            stamp_posting_metadata(
                drawdown_entry.postings[0],
                node_id=cash_node_id,
                type_tag="drawdown",
            )
            stamp_posting_metadata(
                drawdown_entry.postings[1],
                node_id=liability_node_id,
                type_tag="drawdown",
            )

            # Guard: Skip posting if entry with same ID already exists (e.g., re-simulation)
            if not journal.has_id(drawdown_entry.id):
                journal.post(drawdown_entry)

            events.append(
                Event(
                    ctx.t_index[start_month_idx],
                    "loan_disbursement",
                    f"Loan disbursed: €{principal:,.2f}",
                    {"amount": float(principal), "type": "disbursement"},
                )
            )

        # Calculate monthly payment for balloon loan
        # For balloon loans, monthly payments are typically interest + small principal
        # The balloon payment pays off the remaining balance
        if balloon_after_months > 0:
            # Calculate monthly payment as: interest + small principal amortization
            # This ensures the balloon payment is significant
            monthly_interest = principal * i_m  # Interest on full principal initially
            monthly_principal = principal * amort_rate_m  # Small principal payment
            monthly_payment = monthly_interest + monthly_principal
        else:
            # No balloon period, use simple amortization
            monthly_payment = principal * amort_rate_m

        for month_idx in range(T):
            # Get the date for this month
            month_date = ctx.t_index[month_idx].astype("datetime64[D]").astype(date)

            # Check if this is a payment month
            is_payment_month = self._is_payment_month(month_date, start_date)

            if is_payment_month and current_balance > 0:
                # Calculate interest on outstanding balance
                interest = current_balance * i_m
                interest = interest.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                # Determine if this is the balloon payment month
                months_since_start = month_idx - start_month_idx
                is_balloon_month = months_since_start == balloon_after_months

                # Convert timestamp to datetime
                payment_timestamp = ctx.t_index[month_idx]
                if isinstance(payment_timestamp, np.datetime64):
                    payment_timestamp = pd.Timestamp(payment_timestamp).to_pydatetime()
                elif hasattr(payment_timestamp, "astype"):
                    payment_timestamp = pd.Timestamp(
                        payment_timestamp.astype("datetime64[D]")
                    ).to_pydatetime()
                else:
                    payment_timestamp = datetime.fromisoformat(str(payment_timestamp))

                if is_balloon_month:
                    # Balloon payment: both principal and interest entries
                    if balloon_type == "residual":
                        balloon_payment = current_balance
                    elif balloon_type == "fixed_amount":
                        requested = Decimal(str(balloon_amount))
                        balloon_payment = min(requested, current_balance)
                    else:
                        raise ValueError(f"Unknown balloon type: {balloon_type}")

                    # V2: Create journal entries for balloon payment
                    # Principal payment (INTERNAL↔INTERNAL: DR liability, CR cash)
                    operation_id = create_operation_id(
                        f"l:{brick.id}", payment_timestamp
                    )
                    sequence = 1

                    if balloon_payment > 0:
                        entry_id = create_entry_id(operation_id, sequence)
                        # Use month_idx * 100 + sequence to ensure unique origin_id per entry
                        origin_id = generate_transaction_id(
                            brick.id,
                            payment_timestamp,
                            brick.spec or {},
                            brick.links or {},
                            sequence=month_idx * 100
                            + sequence,  # Unique per entry in same month
                        )

                        principal_entry = JournalEntry(
                            id=entry_id,
                            timestamp=payment_timestamp,
                            postings=[
                                Posting(
                                    account_id=liability_node_id,
                                    amount=create_amount(
                                        float(balloon_payment), ctx.currency
                                    ),
                                    metadata={},
                                ),
                                Posting(
                                    account_id=cash_node_id,
                                    amount=create_amount(
                                        -float(balloon_payment), ctx.currency
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
                            tags={"type": "balloon"},
                            sequence=sequence,
                            origin_id=origin_id,
                        )

                        principal_entry.metadata["transaction_type"] = "payment"

                        stamp_posting_metadata(
                            principal_entry.postings[0],
                            node_id=liability_node_id,
                            type_tag="balloon",
                        )
                        stamp_posting_metadata(
                            principal_entry.postings[1],
                            node_id=cash_node_id,
                            type_tag="balloon",
                        )

                        # Guard: Skip posting if entry with same ID already exists (e.g., re-simulation)
                        if not journal.has_id(principal_entry.id):
                            journal.post(principal_entry)
                        sequence += 1

                    # Interest payment (BOUNDARY↔INTERNAL: DR expense, CR cash)
                    if interest > 0:
                        entry_id = create_entry_id(operation_id, sequence)
                        # Use month_idx * 100 + sequence to ensure unique origin_id per entry
                        origin_id = generate_transaction_id(
                            brick.id,
                            payment_timestamp,
                            brick.spec or {},
                            brick.links or {},
                            sequence=month_idx * 100
                            + sequence,  # Unique per entry in same month
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
                                    account_id=cash_node_id,
                                    amount=create_amount(
                                        -float(interest), ctx.currency
                                    ),
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
                            node_id=cash_node_id,
                            type_tag="interest",
                        )

                        # Guard: Skip posting if entry with same ID already exists (e.g., re-simulation)
                        if not journal.has_id(interest_entry.id):
                            journal.post(interest_entry)

                    # Pay off the loan
                    current_balance -= balloon_payment
                    current_balance = max(Decimal("0"), current_balance)

                    # Record balloon payment event
                    events.append(
                        Event(
                            ctx.t_index[month_idx],
                            "balloon_payment",
                            f"Balloon payment: €{balloon_payment:,.2f}",
                            {"amount": float(balloon_payment), "type": "balloon"},
                        )
                    )

                    # Track interest paid
                    interest_paid[month_idx] = float(interest)

                elif months_since_start < balloon_after_months:
                    # Amortization period - constant monthly payment (annuity)
                    # Calculate principal payment as: total_payment - interest
                    principal_payment = monthly_payment - interest
                    principal_payment = min(
                        principal_payment, current_balance
                    )  # Don't overpay

                    # V2: Create journal entries for monthly payment
                    operation_id = create_operation_id(
                        f"l:{brick.id}", payment_timestamp
                    )
                    sequence = 1

                    # Principal payment (INTERNAL↔INTERNAL: DR liability, CR cash)
                    if principal_payment > 0:
                        entry_id = create_entry_id(operation_id, sequence)
                        # Use month_idx * 100 + sequence to ensure unique origin_id per entry
                        origin_id = generate_transaction_id(
                            brick.id,
                            payment_timestamp,
                            brick.spec or {},
                            brick.links or {},
                            sequence=month_idx * 100
                            + sequence,  # Unique per entry in same month
                        )

                        principal_entry = JournalEntry(
                            id=entry_id,
                            timestamp=payment_timestamp,
                            postings=[
                                Posting(
                                    account_id=liability_node_id,
                                    amount=create_amount(
                                        float(principal_payment), ctx.currency
                                    ),
                                    metadata={},
                                ),
                                Posting(
                                    account_id=cash_node_id,
                                    amount=create_amount(
                                        -float(principal_payment), ctx.currency
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

                        principal_entry.metadata["transaction_type"] = "payment"

                        stamp_posting_metadata(
                            principal_entry.postings[0],
                            node_id=liability_node_id,
                            type_tag="principal",
                        )
                        stamp_posting_metadata(
                            principal_entry.postings[1],
                            node_id=cash_node_id,
                            type_tag="principal",
                        )

                        # Guard: Skip posting if entry with same ID already exists (e.g., re-simulation)
                        if not journal.has_id(principal_entry.id):
                            journal.post(principal_entry)
                        sequence += 1

                    # Interest payment (BOUNDARY↔INTERNAL: DR expense, CR cash)
                    if interest > 0:
                        entry_id = create_entry_id(operation_id, sequence)
                        # Use month_idx * 100 + sequence to ensure unique origin_id per entry
                        origin_id = generate_transaction_id(
                            brick.id,
                            payment_timestamp,
                            brick.spec or {},
                            brick.links or {},
                            sequence=month_idx * 100
                            + sequence,  # Unique per entry in same month
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
                                    account_id=cash_node_id,
                                    amount=create_amount(
                                        -float(interest), ctx.currency
                                    ),
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
                            node_id=cash_node_id,
                            type_tag="interest",
                        )

                        # Guard: Skip posting if entry with same ID already exists (e.g., re-simulation)
                        if not journal.has_id(interest_entry.id):
                            journal.post(interest_entry)

                    current_balance -= principal_payment
                    current_balance = max(Decimal("0"), current_balance)

                    # Record regular payment event
                    events.append(
                        Event(
                            ctx.t_index[month_idx],
                            "loan_payment",
                            f"Loan payment: €{monthly_payment:,.2f}",
                            {
                                "principal": float(principal_payment),
                                "interest": float(interest),
                                "type": "payment",
                            },
                        )
                    )

                    # Track interest paid
                    interest_paid[month_idx] = float(interest)

                else:
                    # Post-balloon interest-only period (continues indefinitely)
                    # Note: current_balance remains unchanged during interest-only period

                    # V2: Create journal entry for interest-only payment
                    # Interest payment (BOUNDARY↔INTERNAL: DR expense, CR cash)
                    if interest > 0:
                        operation_id = create_operation_id(
                            f"l:{brick.id}", payment_timestamp
                        )
                        entry_id = create_entry_id(operation_id, 1)
                        # Use month_idx * 100 + 1 to ensure unique origin_id per entry
                        origin_id = generate_transaction_id(
                            brick.id,
                            payment_timestamp,
                            brick.spec or {},
                            brick.links or {},
                            sequence=month_idx * 100
                            + 1,  # Unique per entry in same month
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
                                    account_id=cash_node_id,
                                    amount=create_amount(
                                        -float(interest), ctx.currency
                                    ),
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
                            sequence=1,
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
                            node_id=cash_node_id,
                            type_tag="interest",
                        )

                        # Guard: Skip posting if entry with same ID already exists (e.g., re-simulation)
                        if not journal.has_id(interest_entry.id):
                            journal.post(interest_entry)

                    # Record interest-only payment event
                    events.append(
                        Event(
                            ctx.t_index[month_idx],
                            "interest_payment",
                            f"Interest payment: €{interest:,.2f}",
                            {"interest": float(interest), "type": "interest_only"},
                        )
                    )

                    # Track interest paid
                    interest_paid[month_idx] = float(interest)

            # Store current balance
            debt_balance[month_idx] = float(current_balance)

        # V2: Shell behavior - return zero arrays (no balances)
        return BrickOutput(
            cash_in=cash_in,  # Zero - deprecated
            cash_out=cash_out,  # Zero - deprecated
            assets=np.zeros(T, dtype=float),
            liabilities=debt_balance,
            interest=-interest_paid,  # Negative for interest expense
            events=events,
        )

    def _is_payment_month(self, month_date: date, start_date: date) -> bool:
        """Check if this month is a payment month."""
        # For balloon loans, payments start the month after disbursement
        # This matches the behavior of annuity loans
        return month_date > start_date
