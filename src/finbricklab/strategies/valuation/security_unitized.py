"""
ETF investment valuation strategy.
"""

from __future__ import annotations

import numpy as np

from finbricklab.core.bricks import ABrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.events import Event
from finbricklab.core.interfaces import IValuationStrategy
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
        Simulate the ETF investment over the time period.

        Handles initial holdings, one-shot purchases, DCA contributions,
        dividend payments/reinvestment, and price appreciation.

        Args:
            brick: The ETF investment brick
            ctx: The simulation context

        Returns:
            BrickOutput with cash flows, asset value, and events
        """
        T = len(ctx.t_index)
        s = brick.spec
        cash_in = np.zeros(T)  # dividends (if not reinvested)
        cash_out = np.zeros(T)  # purchases
        units = np.zeros(T)
        price = np.zeros(T)
        events = []

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
        buy0 = s.get("buy_at_start")
        if buy0:
            if "amount" in buy0 and buy0["amount"] > 0:
                amt = float(buy0["amount"])
                add_u = amt / price[0]
                units[0] += add_u
                cash_out[0] += amt
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
                cash_out[0] += amt
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
                if reinv and dv > 0:
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
                else:
                    cash_in[t] += dv
                    if ev_lvl in ("major", "all") and dv > 0:
                        events.append(
                            Event(
                                ctx.t_index[t],
                                "div_cash",
                                f"Dividends to cash: €{dv:,.2f}",
                                {"amount": dv, "price": price[t]},
                            )
                        )

            # DCA AFTER dividends
            if dca is not None:
                start_off = int(dca.get("start_offset_m", 0))
                months = dca.get("months", None)
                m_rel = t - start_off
                if m_rel >= 0 and (months is None or m_rel < int(months)):
                    if dca["mode"] == "amount":
                        step_blocks = max(0, m_rel // 12)
                        amt = float(dca["amount"]) * (
                            (1 + float(dca.get("annual_step_pct", 0.0))) ** step_blocks
                        )
                        if amt > 0:
                            add_u = amt / price[t]
                            units[t] += add_u
                            cash_out[t] += amt
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
                            cash_out[t] += amt
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
                        units[t] -= sell_units
                        cash_in[t] += sell_units * price[t]
                        if ev_lvl in ("major", "all"):
                            events.append(
                                Event(
                                    ctx.t_index[t],
                                    "sell",
                                    f"Sell {sell_units:,.6f}u for €{sell_units * price[t]:,.2f}",
                                    {
                                        "units": sell_units,
                                        "amount": sell_units * price[t],
                                        "price": price[t],
                                    },
                                )
                            )

            # SDCA (Systematic DCA-out)
            sdca = s.get("sdca")
            if sdca is not None:
                start_off = int(sdca.get("start_offset_m", 0))
                months = sdca.get("months", None)
                m_rel = t - start_off
                if m_rel >= 0 and (months is None or m_rel < int(months)):
                    if sdca["mode"] == "amount":
                        amt = float(sdca["amount"])
                        sell_units = min(units[t], amt / price[t])
                    else:  # units mode
                        sell_units = min(units[t], float(sdca["units"]))

                    if sell_units > 0:
                        units[t] -= sell_units
                        cash_in[t] += sell_units * price[t]
                        if ev_lvl == "all":
                            events.append(
                                Event(
                                    ctx.t_index[t],
                                    "sdca",
                                    f"SDCA: {sell_units:,.6f}u for €{sell_units * price[t]:,.2f}",
                                    {
                                        "units": sell_units,
                                        "amount": sell_units * price[t],
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

            cash_in[t_stop] += proceeds  # book sale
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

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            assets=asset_value,
            liabilities=np.zeros(T),
            events=events,
        )
