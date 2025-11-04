"""
ETF investment valuation strategy.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from finbricklab.core.accounts import BOUNDARY_NODE_ID, get_node_id
from finbricklab.core.bricks import ABrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.currency import create_amount
from finbricklab.core.events import Event
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
from finbricklab.core.utils import active_mask


class ValuationSecurityUnitized(IValuationStrategy):
    """
    ETF investment valuation strategy (kind: 'a.invest.etf').

    This strategy models a unitized investment (like an ETF) with constant
    price drift, optional dividend yield, and support for purchasing and
    selling shares through various mechanisms.

    Key Features:
        - Initial holdings (pre-owned units with no cash impact)
        - One-shot buy at start (buy_at_start by amount or units)
        - DCA plan by amount or units, with optional annual step-up
        - One-shot sells by date (sell by amount or units)
        - Systematic DCA-out (SDCA) for regular withdrawals
        - Dividend reinvestment or cash distribution
        - Configurable event logging

    Spec
    ----
        initial_units: Number of units held at start (default: 0.0)
        initial_amount: User-friendly alternative to initial_units (converted to units using price0)
        price0: Initial price per unit (default: 100.0)
        drift_pa: Annual price drift rate (default: 0.03 for 3%)
        div_yield_pa: Annual dividend yield (default: 0.0)
        reinvest_dividends: Whether to reinvest dividends (default: False)
        buy_at_start: One-shot purchase {"amount": X} or {"units": Y}
        dca: DCA configuration with mode, amount/units, timing, and step-up
        sell: List of one-shot sells with user-friendly options:
            - {"date": date(2026, 10, 1), "amount": 500.0}  # Sell €500 worth
            - {"date": date(2026, 10, 1), "percentage": 0.5}  # Sell 50% of holdings
            - {"date": date(2026, 10, 1), "units": 10.0}  # Sell 10 units
            - {"t": "2026-10", "amount": 500.0}  # Legacy format still supported
        sdca: Systematic DCA-out configuration for regular withdrawals
        round_units_to: Round units to N decimal places (optional)
        events_level: Event verbosity "none"|"major"|"all" (default: "major")

    Monthly Processing Order:
        1. Dividends (reinvest or cash)
        2. DCA buys (buy_at_start + monthly DCA)
        3. One-shot sells
        4. SDCA sells
        5. Round units
    """

    def prepare(self, brick: ABrick, ctx: ScenarioContext) -> None:
        """
        Prepare the ETF valuation strategy.

        Sets up default parameters and validates the configuration.

        Args:
            brick: The ETF investment brick
            ctx: The simulation context
        """
        s = brick.spec

        # Handle user-friendly initial_amount parameter
        if "initial_amount" in s and "initial_units" not in s:
            # Convert initial_amount to initial_units
            price0 = s.get("price0", 100.0)
            s["initial_units"] = s["initial_amount"] / price0
            # Remove the user-friendly parameter to avoid confusion
            del s["initial_amount"]
        else:
            s.setdefault("initial_units", 0.0)

        s.setdefault("price0", 100.0)
        s.setdefault("drift_pa", 0.03)
        s.setdefault("volatility_pa", 0.0)
        s.setdefault("seed", 0)
        s.setdefault("div_yield_pa", 0.0)
        s.setdefault("reinvest_dividends", False)
        s.setdefault("buy_at_start", None)  # {"amount": >0} or {"units": >0}
        s.setdefault("dca", None)  # {"mode": "amount"|"units", ...}
        s.setdefault("sell", [])  # [{"t": "YYYY-MM", "amount": X} or {"units": Y}]
        s.setdefault("sdca", None)  # {"mode": "amount"|"units", ...}
        s.setdefault("round_units_to", None)
        s.setdefault("events_level", "major")  # "none"|"major"|"all"

        # Validate DCA configuration
        dca = s["dca"]
        if dca is not None:
            mode = dca.get("mode")
            assert mode in ("amount", "units"), "dca.mode must be 'amount' or 'units'"
            if mode == "amount":
                assert dca.get("amount", 0) >= 0, "dca.amount must be >= 0"
            else:
                assert dca.get("units", 0) >= 0, "dca.units must be >= 0"

            # Normalize offsets
            off = int(dca.get("start_offset_m", 0))
            if off < 0:
                dca["start_offset_m"] = 0
                print(f"[WARN] {brick.id}: dca.start_offset_m < 0 -> clamped to 0")
            dca.setdefault("months", None)
            dca.setdefault("annual_step_pct", 0.0)

        # Validate buy_at_start configuration
        if s["buy_at_start"]:
            bas = s["buy_at_start"]
            assert ("amount" in bas) ^ (
                "units" in bas
            ), "buy_at_start: provide exactly one of {'amount','units'}"
            if "amount" in bas:
                assert bas["amount"] >= 0, "buy_at_start.amount must be >= 0"
            if "units" in bas:
                assert bas["units"] >= 0, "buy_at_start.units must be >= 0"

        # Validate and normalize sell configuration
        sell_directives = s["sell"]
        for sell_spec in sell_directives:
            # Handle user-friendly date parameter
            if "date" in sell_spec and "t" not in sell_spec:
                from datetime import date

                if isinstance(sell_spec["date"], date):
                    # Convert Python date to numpy datetime64
                    import numpy as np

                    sell_spec["t"] = np.datetime64(sell_spec["date"].strftime("%Y-%m"))
                else:
                    sell_spec["t"] = sell_spec["date"]
                # Remove the user-friendly parameter
                del sell_spec["date"]

            assert "t" in sell_spec, "sell directive must include 't' (date) or 'date'"

            # Handle user-friendly percentage parameter
            if "percentage" in sell_spec:
                percentage = sell_spec["percentage"]
                assert 0 <= percentage <= 1, "sell.percentage must be between 0 and 1"
                # Convert percentage to a special marker that will be resolved at runtime
                sell_spec["_percentage"] = percentage
                # Remove the user-friendly parameter
                del sell_spec["percentage"]

            # Validate that we have exactly one of the supported parameters
            valid_params = ["amount", "units", "_percentage"]
            param_count = sum(1 for param in valid_params if param in sell_spec)
            assert (
                param_count == 1
            ), f"sell directive: provide exactly one of {valid_params}"

            if "amount" in sell_spec:
                assert sell_spec["amount"] >= 0, "sell.amount must be >= 0"
            if "units" in sell_spec:
                assert sell_spec["units"] >= 0, "sell.units must be >= 0"

        # Validate SDCA configuration
        sdca = s["sdca"]
        if sdca is not None:
            mode = sdca.get("mode")
            assert mode in ("amount", "units"), "sdca.mode must be 'amount' or 'units'"
            if mode == "amount":
                assert sdca.get("amount", 0) >= 0, "sdca.amount must be >= 0"
            else:
                assert sdca.get("units", 0) >= 0, "sdca.units must be >= 0"

            # Normalize offsets
            off = int(sdca.get("start_offset_m", 0))
            if off < 0:
                sdca["start_offset_m"] = 0
                print(f"[WARN] {brick.id}: sdca.start_offset_m < 0 -> clamped to 0")
            sdca.setdefault("months", None)

    def simulate(self, brick: ABrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the ETF investment over the time period (V2: journal-first pattern).

        Creates journal entries for dividends (cash), buys, and sells.
        Handles initial holdings, one-shot purchases, DCA contributions,
        dividend payments/reinvestment, and price appreciation.

        Args:
            brick: The ETF investment brick
            ctx: The simulation context

        Returns:
            BrickOutput with asset value, zero cash flows, and events
            (V2: cash_in/cash_out are zero; journal entries created instead)
        """
        T = len(ctx.t_index)
        s = brick.spec

        # V2: Don't emit cash arrays - use journal entries instead
        cash_in = np.zeros(T)
        cash_out = np.zeros(T)
        units = np.zeros(T)
        price = np.zeros(T)
        dividends_earned = np.zeros(T)  # Track dividends/yield earned
        events = []

        # Get journal from context (V2)
        if ctx.journal is None:
            raise ValueError(
                "Journal must be provided in ScenarioContext for V2 postings model"
            )
        journal = ctx.journal

        # Get node IDs
        etf_node_id = get_node_id(brick.id, "a")
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

        # Price path calculation with volatility
        price[0] = float(s["price0"])
        mu = float(s["drift_pa"])
        sigma = float(s["volatility_pa"])
        rng = np.random.default_rng(int(s["seed"]))

        for t in range(1, T):
            if sigma > 0:
                z = rng.standard_normal()
                ret = (mu / 12.0) + (sigma / np.sqrt(12.0)) * z
            else:
                ret = mu / 12.0
            price[t] = price[t - 1] * np.exp(ret)

        # Initial holdings (pre-owned, no cash impact)
        units[0] = float(s["initial_units"])

        # One-shot buy at start (cash impact)
        # V2: Create journal entry for buy (INTERNAL↔INTERNAL: DR a:etf, CR a:cash)
        buy0 = s.get("buy_at_start")
        if buy0:
            if "amount" in buy0 and buy0["amount"] > 0:
                amt = float(buy0["amount"])
                add_u = amt / price[0]
                units[0] += add_u

                # Create journal entry for buy
                buy_timestamp = ctx.t_index[0]
                if isinstance(buy_timestamp, np.datetime64):
                    buy_timestamp = pd.Timestamp(buy_timestamp).to_pydatetime()
                elif hasattr(buy_timestamp, "astype"):
                    buy_timestamp = pd.Timestamp(
                        buy_timestamp.astype("datetime64[D]")
                    ).to_pydatetime()
                else:
                    buy_timestamp = datetime.fromisoformat(str(buy_timestamp))

                operation_id = create_operation_id(f"a:{brick.id}", buy_timestamp)
                entry_id = create_entry_id(operation_id, 1)
                origin_id = generate_transaction_id(
                    brick.id,
                    buy_timestamp,
                    {"buy_at_start": amt},
                    brick.links or {},
                    sequence=0,
                )

                # DR a:etf (increase asset), CR a:cash (decrease cash)
                buy_entry = JournalEntry(
                    id=entry_id,
                    timestamp=buy_timestamp,
                    postings=[
                        Posting(
                            account_id=etf_node_id,
                            amount=create_amount(amt, ctx.currency),
                            metadata={},
                        ),
                        Posting(
                            account_id=cash_node_id,
                            amount=create_amount(-amt, ctx.currency),
                            metadata={},
                        ),
                    ],
                    metadata={},
                )

                stamp_entry_metadata(
                    buy_entry,
                    parent_id=f"a:{brick.id}",
                    timestamp=buy_timestamp,
                    tags={"type": "buy"},
                    sequence=1,
                    origin_id=origin_id,
                )

                buy_entry.metadata["transaction_type"] = "transfer"

                stamp_posting_metadata(
                    buy_entry.postings[0],
                    node_id=etf_node_id,
                    type_tag="buy",
                )
                stamp_posting_metadata(
                    buy_entry.postings[1],
                    node_id=cash_node_id,
                    type_tag="buy",
                )

                journal.post(buy_entry)

                if s.get("events_level") in ("major", "all"):
                    events.append(
                        Event(
                            ctx.t_index[0],
                            "buy_start",
                            f"ETF buy at start: €{amt:,.2f}",
                            {"amount": amt, "units": add_u, "price": price[0]},
                        )
                    )
            elif "units" in buy0 and buy0["units"] > 0:
                u = float(buy0["units"])
                amt = u * price[0]
                units[0] += u

                # Create journal entry for buy
                buy_timestamp = ctx.t_index[0]
                if isinstance(buy_timestamp, np.datetime64):
                    buy_timestamp = pd.Timestamp(buy_timestamp).to_pydatetime()
                elif hasattr(buy_timestamp, "astype"):
                    buy_timestamp = pd.Timestamp(
                        buy_timestamp.astype("datetime64[D]")
                    ).to_pydatetime()
                else:
                    buy_timestamp = datetime.fromisoformat(str(buy_timestamp))

                operation_id = create_operation_id(f"a:{brick.id}", buy_timestamp)
                entry_id = create_entry_id(operation_id, 1)
                origin_id = generate_transaction_id(
                    brick.id,
                    buy_timestamp,
                    {"buy_at_start": u},
                    brick.links or {},
                    sequence=0,
                )

                # DR a:etf (increase asset), CR a:cash (decrease cash)
                buy_entry = JournalEntry(
                    id=entry_id,
                    timestamp=buy_timestamp,
                    postings=[
                        Posting(
                            account_id=etf_node_id,
                            amount=create_amount(amt, ctx.currency),
                            metadata={},
                        ),
                        Posting(
                            account_id=cash_node_id,
                            amount=create_amount(-amt, ctx.currency),
                            metadata={},
                        ),
                    ],
                    metadata={},
                )

                stamp_entry_metadata(
                    buy_entry,
                    parent_id=f"a:{brick.id}",
                    timestamp=buy_timestamp,
                    tags={"type": "buy"},
                    sequence=1,
                    origin_id=origin_id,
                )

                buy_entry.metadata["transaction_type"] = "transfer"

                stamp_posting_metadata(
                    buy_entry.postings[0],
                    node_id=etf_node_id,
                    type_tag="buy",
                )
                stamp_posting_metadata(
                    buy_entry.postings[1],
                    node_id=cash_node_id,
                    type_tag="buy",
                )

                journal.post(buy_entry)

                if s.get("events_level") in ("major", "all"):
                    events.append(
                        Event(
                            ctx.t_index[0],
                            "buy_start",
                            f"ETF buy at start: {u:,.6f}u",
                            {"amount": amt, "units": u, "price": price[0]},
                        )
                    )

        # Extract configuration for monthly loop
        divm = float(s["div_yield_pa"]) / 12.0
        reinv = bool(s["reinvest_dividends"])
        round_to = s.get("round_units_to")
        dca = s.get("dca")
        ev_lvl = s.get("events_level")

        # Monthly loop for dividends & DCA
        for t in range(T):
            # Carry forward units
            if t > 0:
                units[t] = units[t - 1]

            # Dividends BEFORE DCA (based on units at start of month)
            if divm > 0:
                dv = units[t] * price[t] * divm
                # Track dividends earned (regardless of reinvestment)
                dividends_earned[t] = dv
                if reinv and dv > 0:
                    # Reinvest: no cash CDPair, just increase units
                    add_u = dv / price[t]
                    units[t] += add_u
                    if ev_lvl in ("major", "all"):
                        events.append(
                            Event(
                                ctx.t_index[t],
                                "div_reinvest",
                                f"Dividends reinvested: €{dv:,.2f}",
                                {"amount": dv, "units": add_u, "price": price[t]},
                            )
                        )
                elif dv > 0:
                    # Cash dividend: V2: Create journal entry (BOUNDARY↔INTERNAL: CR income.dividend, DR cash)
                    dividend_timestamp = ctx.t_index[t]
                    if isinstance(dividend_timestamp, np.datetime64):
                        dividend_timestamp = pd.Timestamp(
                            dividend_timestamp
                        ).to_pydatetime()
                    elif hasattr(dividend_timestamp, "astype"):
                        dividend_timestamp = pd.Timestamp(
                            dividend_timestamp.astype("datetime64[D]")
                        ).to_pydatetime()
                    else:
                        dividend_timestamp = datetime.fromisoformat(
                            str(dividend_timestamp)
                        )

                    operation_id = create_operation_id(
                        f"a:{brick.id}", dividend_timestamp
                    )
                    entry_id = create_entry_id(operation_id, 1)
                    origin_id = generate_transaction_id(
                        brick.id,
                        dividend_timestamp,
                        {"dividend": dv},
                        brick.links or {},
                        sequence=t,
                    )

                    # CR income.dividend (boundary), DR cash (internal)
                    dividend_entry = JournalEntry(
                        id=entry_id,
                        timestamp=dividend_timestamp,
                        postings=[
                            Posting(
                                account_id=cash_node_id,
                                amount=create_amount(dv, ctx.currency),
                                metadata={},
                            ),
                            Posting(
                                account_id=BOUNDARY_NODE_ID,
                                amount=create_amount(-dv, ctx.currency),
                                metadata={},
                            ),
                        ],
                        metadata={},
                    )

                    stamp_entry_metadata(
                        dividend_entry,
                        parent_id=f"a:{brick.id}",
                        timestamp=dividend_timestamp,
                        tags={"type": "dividend"},
                        sequence=1,
                        origin_id=origin_id,
                    )

                    dividend_entry.metadata["transaction_type"] = "income"

                    stamp_posting_metadata(
                        dividend_entry.postings[0],
                        node_id=cash_node_id,
                        type_tag="dividend",
                    )
                    stamp_posting_metadata(
                        dividend_entry.postings[1],
                        node_id=BOUNDARY_NODE_ID,
                        category="income.dividend",
                        type_tag="dividend",
                    )

                    journal.post(dividend_entry)

                    if ev_lvl in ("major", "all"):
                        events.append(
                            Event(
                                ctx.t_index[t],
                                "div_cash",
                                f"Dividends to cash: €{dv:,.2f}",
                                {"amount": dv, "price": price[t]},
                            )
                        )

            # DCA AFTER dividends
            # V2: Create journal entries for DCA buys (INTERNAL↔INTERNAL: DR a:etf, CR a:cash)
            if dca is not None:
                start_off = int(dca.get("start_offset_m", 0))
                months = dca.get("months", None)
                m_rel = t - start_off
                if m_rel >= 0 and (months is None or m_rel < int(months)):
                    dca_timestamp = ctx.t_index[t]
                    if isinstance(dca_timestamp, np.datetime64):
                        dca_timestamp = pd.Timestamp(dca_timestamp).to_pydatetime()
                    elif hasattr(dca_timestamp, "astype"):
                        dca_timestamp = pd.Timestamp(
                            dca_timestamp.astype("datetime64[D]")
                        ).to_pydatetime()
                    else:
                        dca_timestamp = datetime.fromisoformat(str(dca_timestamp))

                    if dca["mode"] == "amount":
                        step_blocks = max(0, m_rel // 12)
                        amt = float(dca["amount"]) * (
                            (1 + float(dca.get("annual_step_pct", 0.0))) ** step_blocks
                        )
                        if amt > 0:
                            add_u = amt / price[t]
                            units[t] += add_u

                            # Create journal entry for DCA buy
                            operation_id = create_operation_id(
                                f"a:{brick.id}", dca_timestamp
                            )
                            entry_id = create_entry_id(operation_id, 1)
                            origin_id = generate_transaction_id(
                                brick.id,
                                dca_timestamp,
                                {"dca": amt, "month": m_rel},
                                brick.links or {},
                                sequence=t,
                            )

                            # DR a:etf (increase asset), CR a:cash (decrease cash)
                            dca_entry = JournalEntry(
                                id=entry_id,
                                timestamp=dca_timestamp,
                                postings=[
                                    Posting(
                                        account_id=etf_node_id,
                                        amount=create_amount(amt, ctx.currency),
                                        metadata={},
                                    ),
                                    Posting(
                                        account_id=cash_node_id,
                                        amount=create_amount(-amt, ctx.currency),
                                        metadata={},
                                    ),
                                ],
                                metadata={},
                            )

                            stamp_entry_metadata(
                                dca_entry,
                                parent_id=f"a:{brick.id}",
                                timestamp=dca_timestamp,
                                tags={"type": "buy"},
                                sequence=1,
                                origin_id=origin_id,
                            )

                            dca_entry.metadata["transaction_type"] = "transfer"

                            stamp_posting_metadata(
                                dca_entry.postings[0],
                                node_id=etf_node_id,
                                type_tag="buy",
                            )
                            stamp_posting_metadata(
                                dca_entry.postings[1],
                                node_id=cash_node_id,
                                type_tag="buy",
                            )

                            # Guard: Skip posting if entry with same ID already exists (e.g., re-simulation)
                            if not any(e.id == dca_entry.id for e in journal.entries):
                                journal.post(dca_entry)

                            if ev_lvl == "all":
                                events.append(
                                    Event(
                                        ctx.t_index[t],
                                        "dca_amount",
                                        f"DCA (amount): €{amt:,.2f}",
                                        {
                                            "amount": amt,
                                            "units": add_u,
                                            "price": price[t],
                                        },
                                    )
                                )
                    else:  # units mode
                        u = float(dca["units"])
                        if u > 0:
                            amt = u * price[t]  # Use current month's price
                            units[t] += u

                            # Create journal entry for DCA buy
                            operation_id = create_operation_id(
                                f"a:{brick.id}", dca_timestamp
                            )
                            entry_id = create_entry_id(operation_id, 1)
                            origin_id = generate_transaction_id(
                                brick.id,
                                dca_timestamp,
                                {"dca": u, "month": m_rel},
                                brick.links or {},
                                sequence=t,
                            )

                            # DR a:etf (increase asset), CR a:cash (decrease cash)
                            dca_entry = JournalEntry(
                                id=entry_id,
                                timestamp=dca_timestamp,
                                postings=[
                                    Posting(
                                        account_id=etf_node_id,
                                        amount=create_amount(amt, ctx.currency),
                                        metadata={},
                                    ),
                                    Posting(
                                        account_id=cash_node_id,
                                        amount=create_amount(-amt, ctx.currency),
                                        metadata={},
                                    ),
                                ],
                                metadata={},
                            )

                            stamp_entry_metadata(
                                dca_entry,
                                parent_id=f"a:{brick.id}",
                                timestamp=dca_timestamp,
                                tags={"type": "buy"},
                                sequence=1,
                                origin_id=origin_id,
                            )

                            dca_entry.metadata["transaction_type"] = "transfer"

                            stamp_posting_metadata(
                                dca_entry.postings[0],
                                node_id=etf_node_id,
                                type_tag="buy",
                            )
                            stamp_posting_metadata(
                                dca_entry.postings[1],
                                node_id=cash_node_id,
                                type_tag="buy",
                            )

                            # Guard: Skip posting if entry with same ID already exists (e.g., re-simulation)
                            if not any(e.id == dca_entry.id for e in journal.entries):
                                journal.post(dca_entry)

                            if ev_lvl == "all":
                                events.append(
                                    Event(
                                        ctx.t_index[t],
                                        "dca_units",
                                        f"DCA (units): {u:,.6f}u",
                                        {"amount": amt, "units": u, "price": price[t]},
                                    )
                                )

            # SELLS AFTER DCA (one-shot and SDCA)
            # V2: Create journal entries for sells (INTERNAL↔INTERNAL: DR a:cash, CR a:etf)
            # One-shot sells
            sell_directives = s.get("sell", [])
            for sell_spec in sell_directives:
                sell_date = np.datetime64(sell_spec["t"], "M")
                if ctx.t_index[t] == sell_date:
                    if "amount" in sell_spec:
                        # Sell by cash target
                        sell_units = min(units[t], sell_spec["amount"] / price[t])
                    elif "_percentage" in sell_spec:
                        # Sell by percentage of current holdings
                        sell_units = units[t] * sell_spec["_percentage"]
                    else:
                        # Sell by units
                        sell_units = min(units[t], sell_spec["units"])

                    if sell_units > 0:
                        sell_amt = sell_units * price[t]
                        units[t] -= sell_units

                        # Create journal entry for sell
                        sell_timestamp = ctx.t_index[t]
                        if isinstance(sell_timestamp, np.datetime64):
                            sell_timestamp = pd.Timestamp(
                                sell_timestamp
                            ).to_pydatetime()
                        elif hasattr(sell_timestamp, "astype"):
                            sell_timestamp = pd.Timestamp(
                                sell_timestamp.astype("datetime64[D]")
                            ).to_pydatetime()
                        else:
                            sell_timestamp = datetime.fromisoformat(str(sell_timestamp))

                        operation_id = create_operation_id(
                            f"a:{brick.id}", sell_timestamp
                        )
                        entry_id = create_entry_id(operation_id, 1)
                        origin_id = generate_transaction_id(
                            brick.id,
                            sell_timestamp,
                            {"sell": sell_units},
                            brick.links or {},
                            sequence=t,
                        )

                        # DR a:cash (increase cash), CR a:etf (decrease asset)
                        sell_entry = JournalEntry(
                            id=entry_id,
                            timestamp=sell_timestamp,
                            postings=[
                                Posting(
                                    account_id=cash_node_id,
                                    amount=create_amount(sell_amt, ctx.currency),
                                    metadata={},
                                ),
                                Posting(
                                    account_id=etf_node_id,
                                    amount=create_amount(-sell_amt, ctx.currency),
                                    metadata={},
                                ),
                            ],
                            metadata={},
                        )

                        stamp_entry_metadata(
                            sell_entry,
                            parent_id=f"a:{brick.id}",
                            timestamp=sell_timestamp,
                            tags={"type": "sell"},
                            sequence=1,
                            origin_id=origin_id,
                        )

                        sell_entry.metadata["transaction_type"] = "transfer"

                        stamp_posting_metadata(
                            sell_entry.postings[0],
                            node_id=cash_node_id,
                            type_tag="sell",
                        )
                        stamp_posting_metadata(
                            sell_entry.postings[1],
                            node_id=etf_node_id,
                            type_tag="sell",
                        )

                        # Guard: Skip posting if entry with same ID already exists (e.g., re-simulation)
                        if not any(e.id == sell_entry.id for e in journal.entries):
                            journal.post(sell_entry)

                        if ev_lvl in ("major", "all"):
                            events.append(
                                Event(
                                    ctx.t_index[t],
                                    "sell",
                                    f"Sell {sell_units:,.6f}u for €{sell_amt:,.2f}",
                                    {
                                        "units": sell_units,
                                        "amount": sell_amt,
                                        "price": price[t],
                                    },
                                )
                            )

            # SDCA (Systematic DCA-out)
            # V2: Create journal entries for SDCA sells (INTERNAL↔INTERNAL: DR a:cash, CR a:etf)
            sdca = s.get("sdca")
            if sdca is not None:
                start_off = int(sdca.get("start_offset_m", 0))
                months = sdca.get("months", None)
                m_rel = t - start_off
                if m_rel >= 0 and (months is None or m_rel < int(months)):
                    sdca_timestamp = ctx.t_index[t]
                    if isinstance(sdca_timestamp, np.datetime64):
                        sdca_timestamp = pd.Timestamp(sdca_timestamp).to_pydatetime()
                    elif hasattr(sdca_timestamp, "astype"):
                        sdca_timestamp = pd.Timestamp(
                            sdca_timestamp.astype("datetime64[D]")
                        ).to_pydatetime()
                    else:
                        sdca_timestamp = datetime.fromisoformat(str(sdca_timestamp))

                    if sdca["mode"] == "amount":
                        amt = float(sdca["amount"])
                        sell_units = min(units[t], amt / price[t])
                    else:  # units mode
                        sell_units = min(units[t], float(sdca["units"]))

                    if sell_units > 0:
                        sell_amt = sell_units * price[t]
                        units[t] -= sell_units

                        # Create journal entry for SDCA sell
                        operation_id = create_operation_id(
                            f"a:{brick.id}", sdca_timestamp
                        )
                        entry_id = create_entry_id(operation_id, 1)
                        origin_id = generate_transaction_id(
                            brick.id,
                            sdca_timestamp,
                            {"sdca": sell_units, "month": m_rel},
                            brick.links or {},
                            sequence=t,
                        )

                        # DR a:cash (increase cash), CR a:etf (decrease asset)
                        sdca_entry = JournalEntry(
                            id=entry_id,
                            timestamp=sdca_timestamp,
                            postings=[
                                Posting(
                                    account_id=cash_node_id,
                                    amount=create_amount(sell_amt, ctx.currency),
                                    metadata={},
                                ),
                                Posting(
                                    account_id=etf_node_id,
                                    amount=create_amount(-sell_amt, ctx.currency),
                                    metadata={},
                                ),
                            ],
                            metadata={},
                        )

                        stamp_entry_metadata(
                            sdca_entry,
                            parent_id=f"a:{brick.id}",
                            timestamp=sdca_timestamp,
                            tags={"type": "sell"},
                            sequence=1,
                            origin_id=origin_id,
                        )

                        sdca_entry.metadata["transaction_type"] = "transfer"

                        stamp_posting_metadata(
                            sdca_entry.postings[0],
                            node_id=cash_node_id,
                            type_tag="sell",
                        )
                        stamp_posting_metadata(
                            sdca_entry.postings[1],
                            node_id=etf_node_id,
                            type_tag="sell",
                        )

                        journal.post(sdca_entry)

                        if ev_lvl == "all":
                            events.append(
                                Event(
                                    ctx.t_index[t],
                                    "sdca",
                                    f"SDCA: {sell_units:,.6f}u for €{sell_amt:,.2f}",
                                    {
                                        "units": sell_units,
                                        "amount": sell_amt,
                                        "price": price[t],
                                    },
                                )
                            )

            # Round units after all operations for the month
            if round_to is not None:
                units[t] = np.round(units[t], int(round_to))

        # Calculate final asset values
        asset_value = units * price

        # Auto-dispose on window end (equity-neutral)
        # V2: Create journal entries for liquidation (INTERNAL↔INTERNAL: DR a:cash, CR a:etf)
        # Fees handled as separate boundary entry if applicable
        mask = active_mask(
            ctx.t_index, brick.start_date, brick.end_date, brick.duration_m
        )
        dispose = bool(
            brick.spec.get("liquidate_on_window_end", False)
        )  # DEFAULT: False
        fees_pct = float(brick.spec.get("sell_fees_pct", 0.0))

        if dispose and mask.any():
            t_stop = int(np.where(mask)[0].max())
            gross = asset_value[t_stop]
            fees = gross * fees_pct
            proceeds = gross - fees

            if gross > 0:
                # Create journal entries for liquidation
                liquidate_timestamp = ctx.t_index[t_stop]
                if isinstance(liquidate_timestamp, np.datetime64):
                    liquidate_timestamp = pd.Timestamp(
                        liquidate_timestamp
                    ).to_pydatetime()
                elif hasattr(liquidate_timestamp, "astype"):
                    liquidate_timestamp = pd.Timestamp(
                        liquidate_timestamp.astype("datetime64[D]")
                    ).to_pydatetime()
                else:
                    liquidate_timestamp = datetime.fromisoformat(
                        str(liquidate_timestamp)
                    )

                operation_id = create_operation_id(f"a:{brick.id}", liquidate_timestamp)
                sequence = 1

                # Main liquidation entry: DR a:cash (gross), CR a:etf (gross)
                # Fees handled separately below
                entry_id = create_entry_id(operation_id, sequence)
                origin_id = generate_transaction_id(
                    brick.id,
                    liquidate_timestamp,
                    {"liquidate": gross},
                    brick.links or {},
                    sequence=t_stop,
                )

                # DR a:cash (gross received), CR a:etf (full asset value)
                liquidate_entry = JournalEntry(
                    id=entry_id,
                    timestamp=liquidate_timestamp,
                    postings=[
                        Posting(
                            account_id=cash_node_id,
                            amount=create_amount(gross, ctx.currency),
                            metadata={},
                        ),
                        Posting(
                            account_id=etf_node_id,
                            amount=create_amount(-gross, ctx.currency),
                            metadata={},
                        ),
                    ],
                    metadata={},
                )

                stamp_entry_metadata(
                    liquidate_entry,
                    parent_id=f"a:{brick.id}",
                    timestamp=liquidate_timestamp,
                    tags={"type": "sell"},
                    sequence=sequence,
                    origin_id=origin_id,
                )

                liquidate_entry.metadata["transaction_type"] = "transfer"

                stamp_posting_metadata(
                    liquidate_entry.postings[0],
                    node_id=cash_node_id,
                    type_tag="sell",
                )
                stamp_posting_metadata(
                    liquidate_entry.postings[1],
                    node_id=etf_node_id,
                    type_tag="sell",
                )

                journal.post(liquidate_entry)
                sequence += 1

                # Fee entry (if any): DR expense.fee (BOUNDARY), CR a:cash (INTERNAL)
                if fees > 0:
                    fee_entry_id = create_entry_id(operation_id, sequence)
                    fee_origin_id = generate_transaction_id(
                        brick.id,
                        liquidate_timestamp,
                        {"fee": fees},
                        brick.links or {},
                        sequence=t_stop,
                    )

                    fee_entry = JournalEntry(
                        id=fee_entry_id,
                        timestamp=liquidate_timestamp,
                        postings=[
                            Posting(
                                account_id=BOUNDARY_NODE_ID,
                                amount=create_amount(fees, ctx.currency),
                                metadata={},
                            ),
                            Posting(
                                account_id=cash_node_id,
                                amount=create_amount(-fees, ctx.currency),
                                metadata={},
                            ),
                        ],
                        metadata={},
                    )

                    stamp_entry_metadata(
                        fee_entry,
                        parent_id=f"a:{brick.id}",
                        timestamp=liquidate_timestamp,
                        tags={"type": "fee"},
                        sequence=sequence,
                        origin_id=fee_origin_id,
                    )

                    fee_entry.metadata["transaction_type"] = "transfer"

                    stamp_posting_metadata(
                        fee_entry.postings[0],
                        node_id=BOUNDARY_NODE_ID,
                        category="expense.fee",
                        type_tag="fee",
                    )
                    stamp_posting_metadata(
                        fee_entry.postings[1],
                        node_id=cash_node_id,
                        type_tag="fee",
                    )

                    journal.post(fee_entry)

            asset_value[t_stop] = 0.0  # explicit zero on the sale month
            # Set all future values to 0 (ETF is liquidated)
            asset_value[t_stop + 1 :] = 0.0
            events.append(
                Event(
                    ctx.t_index[t_stop],
                    "asset_dispose",
                    f"ETF liquidated for €{proceeds:,.2f}",
                    {"gross": gross, "fees": fees, "fees_pct": fees_pct},
                )
            )

        # V2: Shell behavior - return zero arrays (no balances)
        return BrickOutput(
            cash_in=cash_in,  # Zero - deprecated
            cash_out=cash_out,  # Zero - deprecated
            assets=asset_value,
            liabilities=np.zeros(T),
            interest=dividends_earned,  # Positive for dividend income
            events=events,
        )
