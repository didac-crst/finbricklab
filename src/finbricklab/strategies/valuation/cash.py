"""
Cash account valuation strategy.
"""

from __future__ import annotations

import warnings

import numpy as np

from finbricklab.core.accounts import BOUNDARY_NODE_ID, get_node_id
from finbricklab.core.bricks import ABrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.currency import create_amount
from finbricklab.core.errors import ConfigError
from finbricklab.core.interfaces import IValuationStrategy
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


class ValuationCash(IValuationStrategy):
    """
    Cash account valuation strategy for modeling liquid cash holdings.

    This strategy models a simple cash account that receives external cash flows
    and earns interest on the balance. The balance is computed by accumulating
    all routed cash flows plus interest earned each month.

    **Use Cases:**
    - Checking accounts, savings accounts, money market accounts
    - Base currency holdings in multi-currency scenarios
    - Settlement accounts for cash flow routing

    **Required Parameters:**
        - initial_balance: Starting cash balance (default: 0.0)
        - interest_pa: Annual interest rate (default: 0.0)

    **External Parameters (set by scenario engine):**
        - external_in: Monthly cash inflows from other bricks
        - external_out: Monthly cash outflows to other bricks

    **Example:**
        ```python
        cash_account = ABrick(
            id="checking",
            name="Checking Account",
            kind="a.cash",
            spec={
                "initial_balance": 5000.0,
                "interest_pa": 0.02  # 2% annual interest
            }
        )
        ```

    **Note:**
        Supports scenarios with one or multiple cash accounts. The Scenario engine must
        populate `spec.external_in` and `spec.external_out` per cash brick; they are not
        derived here.
    """

    def prepare(self, brick: ABrick, ctx: ScenarioContext) -> None:
        """
        Prepare the cash account strategy.

        Sets up default parameters, liquidity policy, and validates the configuration.

        Args:
            brick: The cash account brick
            ctx: The simulation context
        """
        brick.spec.setdefault("initial_balance", 0.0)
        brick.spec.setdefault("interest_pa", 0.0)
        brick.spec.setdefault("external_in", np.zeros(len(ctx.t_index)))
        brick.spec.setdefault("external_out", np.zeros(len(ctx.t_index)))

        # Coerce numerics to float for robustness
        brick.spec["initial_balance"] = float(brick.spec["initial_balance"])
        brick.spec["interest_pa"] = float(brick.spec["interest_pa"])

        # Coerce and validate external arrays
        T = len(ctx.t_index)
        for key in ("external_in", "external_out"):
            arr = np.asarray(brick.spec[key], dtype=float)
            if len(arr) != T:
                raise ValueError(
                    f"{brick.id}: '{key}' length {len(arr)} != t_index length {T}"
                )
            brick.spec[key] = arr

        # Set liquidity policy defaults
        # overdraft_limit: None = unlimited (default for backward compatibility)
        if "overdraft_limit" not in brick.spec:
            brick.spec["overdraft_limit"] = None
        brick.spec.setdefault("min_buffer", 0.0)  # desired minimum cash balance (EUR)
        brick.spec.setdefault("overdraft_policy", "ignore")  # ignore|warn|raise

        # Validate overdraft_limit if provided
        if brick.spec["overdraft_limit"] is not None:
            if brick.spec["overdraft_limit"] < 0:
                raise ConfigError(
                    f"{brick.id}: overdraft_limit must be >= 0, got {brick.spec['overdraft_limit']}"
                )
            # Validate overdraft_policy
            policy = brick.spec["overdraft_policy"].lower()
            if policy not in {"ignore", "warn", "raise"}:
                raise ConfigError(
                    f"{brick.id}: overdraft_policy must be 'ignore'|'warn'|'raise', got {policy!r}"
                )
            brick.spec["overdraft_policy"] = policy
        if brick.spec["min_buffer"] < 0:
            raise ValueError("min_buffer must be >= 0")

        # Warn if min_buffer > initial_balance (policy breach, not config error)
        initial_balance = brick.spec.get("initial_balance", 0.0)
        if brick.spec["min_buffer"] > initial_balance:
            warnings.warn(
                f"{brick.id}: min_buffer ({brick.spec['min_buffer']:,.2f}) > initial_balance ({initial_balance:,.2f}).",
                category=UserWarning,
                stacklevel=2,
            )

    def simulate(self, brick: ABrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the cash account over the time period (V2: journal-first pattern).

        Calculates the monthly balance by accumulating cash flows and applying
        monthly interest. Emits journal entries for interest earned.

        Args:
            brick: The cash account brick
            ctx: The simulation context

        Returns:
            BrickOutput with balance as asset value, interest array for KPIs,
            and zero cash flows (V2: cash_in/cash_out are zero; journal entries created instead)
        """
        T = len(ctx.t_index)

        # V2: Don't emit cash arrays - use journal entries instead
        cash_in = np.zeros(T)
        cash_out = np.zeros(T)

        # Get journal from context (V2)
        if ctx.journal is None:
            raise ValueError(
                "Journal must be provided in ScenarioContext for V2 postings model"
            )
        journal = ctx.journal

        # Get node ID for cash account
        cash_node_id = get_node_id(brick.id, "a")

        bal = np.zeros(T)
        r_m = brick.spec["interest_pa"] / 12.0  # Monthly interest rate
        # Don't copy the arrays - use them directly to allow runtime modifications
        external_in = brick.spec["external_in"]
        external_out = brick.spec["external_out"]

        # Support for post-interest adjustments (for maturity transfers)
        # Coerce and validate arrays
        post_interest_in = np.asarray(
            brick.spec.get("post_interest_in", np.zeros(T)), dtype=float
        )
        post_interest_out = np.asarray(
            brick.spec.get("post_interest_out", np.zeros(T)), dtype=float
        )

        # Validate length matches timeline
        if len(post_interest_in) != T or len(post_interest_out) != T:
            raise ValueError(f"{brick.id}: 'post_interest_in/out' must have length {T}")

        # Initialize interest tracking array (kept for KPIs)
        interest_earned = np.zeros(T)

        # Apply active mask to enforce start_date and end_date
        from finbricklab.core.utils import active_mask

        mask = active_mask(
            ctx.t_index, brick.start_date, brick.end_date, brick.duration_m
        )

        # Get overdraft limit and policy
        overdraft_limit = brick.spec.get("overdraft_limit")
        overdraft_policy = brick.spec.get("overdraft_policy", "ignore")

        # Calculate balance for first month
        if mask[0]:
            bal[0] = brick.spec["initial_balance"] + external_in[0] - external_out[0]
            # Calculate interest on the balance after cash flows
            interest_earned[0] = bal[0] * r_m
            # V2: Create journal entry for interest (DR cash, CR income.interest)
            if interest_earned[0] > 0:
                interest_timestamp = ctx.t_index[0]
                # Convert numpy datetime64 to Python datetime
                from datetime import datetime

                import pandas as pd

                if isinstance(interest_timestamp, np.datetime64):
                    interest_timestamp = pd.Timestamp(
                        interest_timestamp
                    ).to_pydatetime()
                elif hasattr(interest_timestamp, "astype"):
                    interest_timestamp = pd.Timestamp(
                        interest_timestamp.astype("datetime64[D]")
                    ).to_pydatetime()
                else:
                    interest_timestamp = datetime.fromisoformat(str(interest_timestamp))

                # Use unique parent_id that includes ":interest" to avoid conflict with opening entries
                parent_id = f"a:{brick.id}:interest"
                operation_id = create_operation_id(parent_id, interest_timestamp)
                # Use sequence=1 for first month's interest entry (only one entry per month)
                entry_id = create_entry_id(operation_id, 1)
                origin_id = generate_transaction_id(
                    brick.id,
                    interest_timestamp,
                    {"interest": interest_earned[0]},
                    brick.links or {},
                    sequence=0,  # Month index for origin_id uniqueness
                )

                interest_entry = JournalEntry(
                    id=entry_id,
                    timestamp=interest_timestamp,
                    postings=[
                        Posting(
                            account_id=cash_node_id,
                            amount=create_amount(interest_earned[0], ctx.currency),
                            metadata={},
                        ),
                        Posting(
                            account_id=BOUNDARY_NODE_ID,
                            amount=create_amount(-interest_earned[0], ctx.currency),
                            metadata={},
                        ),
                    ],
                    metadata={},
                )

                stamp_entry_metadata(
                    interest_entry,
                    parent_id=parent_id,  # Use same parent_id as operation_id
                    timestamp=interest_timestamp,
                    tags={"type": "interest"},
                    sequence=1,  # Sequence within operation (1 for single interest entry)
                    origin_id=origin_id,
                )

                # Set transaction_type for interest earned
                interest_entry.metadata["transaction_type"] = "income"

                stamp_posting_metadata(
                    interest_entry.postings[0],
                    node_id=cash_node_id,
                    type_tag="interest",
                )
                stamp_posting_metadata(
                    interest_entry.postings[1],
                    node_id=BOUNDARY_NODE_ID,
                    category="income.interest",
                    type_tag="interest",
                )

                # Guard: Skip posting if entry with same ID already exists (e.g., re-simulation)
                if not any(e.id == interest_entry.id for e in journal.entries):
                    journal.post(interest_entry)

            # Apply interest to balance
            bal[0] *= 1 + r_m
            # Apply post-interest adjustments (no interest on these)
            bal[0] += post_interest_in[0] - post_interest_out[0]

            # Enforce overdraft limit if configured
            if overdraft_limit is not None and bal[0] < -overdraft_limit:
                if overdraft_policy == "raise":
                    raise ConfigError(
                        f"{brick.id}: overdraft_limit exceeded at month 0: balance {bal[0]:.2f} < -{overdraft_limit:.2f}"
                    )
                elif overdraft_policy == "warn":
                    import logging

                    log = logging.getLogger(__name__)
                    log.warning(
                        "%s: overdraft_limit exceeded at month 0: balance %.2f < -%.2f",
                        brick.id,
                        bal[0],
                        overdraft_limit,
                    )
                # "ignore": do nothing; keep balance as computed
        else:
            bal[0] = 0.0
            interest_earned[0] = 0.0

        # Calculate balance for remaining months
        for t in range(1, T):
            # Apply active mask before interest calculations
            if mask[t]:
                # Start with previous month's balance
                bal[t] = bal[t - 1]
                # Add/subtract this month's cash flows
                bal[t] += external_in[t] - external_out[t]
                # Calculate interest on the full balance (including this month's flows)
                interest_earned[t] = bal[t] * r_m
                # V2: Create journal entry for interest (DR cash, CR income.interest)
                if interest_earned[t] > 0:
                    interest_timestamp = ctx.t_index[t]
                    # Convert numpy datetime64 to Python datetime
                    from datetime import datetime

                    import pandas as pd

                    if isinstance(interest_timestamp, np.datetime64):
                        interest_timestamp = pd.Timestamp(
                            interest_timestamp
                        ).to_pydatetime()
                    elif hasattr(interest_timestamp, "astype"):
                        interest_timestamp = pd.Timestamp(
                            interest_timestamp.astype("datetime64[D]")
                        ).to_pydatetime()
                    else:
                        interest_timestamp = datetime.fromisoformat(
                            str(interest_timestamp)
                        )

                    # Use unique parent_id that includes ":interest" to avoid conflict with opening entries
                    parent_id = f"a:{brick.id}:interest"
                    operation_id = create_operation_id(parent_id, interest_timestamp)
                    # Use sequence=1 for interest entry (only one entry per month)
                    entry_id = create_entry_id(operation_id, 1)
                    origin_id = generate_transaction_id(
                        brick.id,
                        interest_timestamp,
                        {"interest": interest_earned[t]},
                        brick.links or {},
                        sequence=t,  # Month index for origin_id uniqueness
                    )

                    interest_entry = JournalEntry(
                        id=entry_id,
                        timestamp=interest_timestamp,
                        postings=[
                            Posting(
                                account_id=cash_node_id,
                                amount=create_amount(interest_earned[t], ctx.currency),
                                metadata={},
                            ),
                            Posting(
                                account_id=BOUNDARY_NODE_ID,
                                amount=create_amount(-interest_earned[t], ctx.currency),
                                metadata={},
                            ),
                        ],
                        metadata={},
                    )

                    stamp_entry_metadata(
                        interest_entry,
                        parent_id=parent_id,  # Use same parent_id as operation_id
                        timestamp=interest_timestamp,
                        tags={"type": "interest"},
                        sequence=1,  # Sequence within operation (1 for single interest entry)
                        origin_id=origin_id,
                    )

                    # Set transaction_type for interest earned
                    interest_entry.metadata["transaction_type"] = "income"

                    stamp_posting_metadata(
                        interest_entry.postings[0],
                        node_id=cash_node_id,
                        type_tag="interest",
                    )
                    stamp_posting_metadata(
                        interest_entry.postings[1],
                        node_id=BOUNDARY_NODE_ID,
                        category="income.interest",
                        type_tag="interest",
                    )

                    # Guard: Skip posting if entry with same ID already exists (e.g., re-simulation)
                    if not any(e.id == interest_entry.id for e in journal.entries):
                        journal.post(interest_entry)

                # Apply interest to balance
                bal[t] *= 1 + r_m
                # Apply post-interest adjustments (no interest on these)
                bal[t] += post_interest_in[t] - post_interest_out[t]

                # Enforce overdraft limit if configured
                if overdraft_limit is not None and bal[t] < -overdraft_limit:
                    if overdraft_policy == "raise":
                        raise ConfigError(
                            f"{brick.id}: overdraft_limit exceeded at month {t}: balance {bal[t]:.2f} < -{overdraft_limit:.2f}"
                        )
                    elif overdraft_policy == "warn":
                        import logging

                        log = logging.getLogger(__name__)
                        log.warning(
                            "%s: overdraft_limit exceeded at month %d: balance %.2f < -%.2f",
                            brick.id,
                            t,
                            bal[t],
                            overdraft_limit,
                        )
                    # "ignore": do nothing; keep balance as computed
            else:
                bal[t] = 0.0
                interest_earned[t] = 0.0

        return BrickOutput(
            cash_in=cash_in,  # V2: Zero arrays (shell behavior)
            cash_out=cash_out,  # V2: Zero arrays (shell behavior)
            assets=bal,
            liabilities=np.zeros(T),
            interest=interest_earned,  # Interest earned on cash balance (kept for KPIs)
            events=[],
        )
