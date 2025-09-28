"""
FinScenLab Strategies Module

This module contains all the concrete strategy implementations for the FinScenLab system.
Strategies implement the actual behavior for different types of financial instruments
based on their 'kind' discriminator.

Strategy Categories:
- Valuation Strategies: Handle asset valuation and cash flow generation
- Schedule Strategies: Handle liability payment schedules and balance tracking  
- Flow Strategies: Handle cash flow events like income, expenses, and transfers

Registry System:
The module automatically registers all default strategies in the global registries,
making them available for use by bricks with matching kind discriminators.

Key Features:
- Modular design allows easy addition of new strategies
- Consistent interface across all strategy types
- Automatic parameter validation and setup
- Support for complex interdependencies between bricks
"""

from __future__ import annotations
import numpy as np
from .core import *
from .kinds import K

# ---------- Asset Valuation Strategies ----------

class ValuationCash(IValuationStrategy):
    """
    Cash account valuation strategy (kind: 'a.cash').
    
    This strategy models a simple cash account that receives external cash flows
    and earns interest on the balance. The balance is computed by accumulating
    all routed cash flows plus interest earned each month.
    
    Required Parameters:
        - initial_balance: Starting cash balance (default: 0.0)
        - interest_pa: Annual interest rate (default: 0.0)
        
    External Parameters (set by scenario engine):
        - external_in: Monthly cash inflows from other bricks
        - external_out: Monthly cash outflows to other bricks
        
    Note:
        This strategy is designed to be the central cash account that receives
        all cash flows from other bricks in the scenario.
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
        brick.spec.setdefault("external_in",  np.zeros(len(ctx.t_index)))
        brick.spec.setdefault("external_out", np.zeros(len(ctx.t_index)))
        
        # Set liquidity policy defaults
        brick.spec.setdefault("overdraft_limit", 0.0)  # how far below 0 cash may go (EUR)
        brick.spec.setdefault("min_buffer", 0.0)       # desired minimum cash balance (EUR)
        
        # Validate non-negative constraints
        assert brick.spec["overdraft_limit"] >= 0, "overdraft_limit must be >= 0"
        assert brick.spec["min_buffer"] >= 0, "min_buffer must be >= 0"
        
        # Warn if min_buffer > initial_balance (policy breach, not config error)
        initial_balance = brick.spec.get("initial_balance", 0.0)
        if brick.spec["min_buffer"] > initial_balance:
            print(f"[WARN] {brick.id}: min_buffer ({brick.spec['min_buffer']:,.2f}) > initial_balance ({initial_balance:,.2f}).")

    def simulate(self, brick: ABrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the cash account over the time period.
        
        Calculates the monthly balance by accumulating cash flows and applying
        monthly interest. The balance serves as both the asset value and the
        cash flow source/sink.
        
        Args:
            brick: The cash account brick
            ctx: The simulation context
            
        Returns:
            BrickOutput with cash flows, balance as asset value, and no events
        """
        T = len(ctx.t_index)
        bal = np.zeros(T)
        r_m = brick.spec["interest_pa"] / 12.0  # Monthly interest rate
        cash_in  = brick.spec["external_in"].copy()
        cash_out = brick.spec["external_out"].copy()

        # Calculate balance for first month
        bal[0] = brick.spec["initial_balance"] + cash_in[0] - cash_out[0]
        bal[0] += bal[0] * r_m  # Apply interest
        
        # Calculate balance for remaining months
        for t in range(1, T):
            bal[t] = bal[t-1] + cash_in[t] - cash_out[t]
            bal[t] += bal[t] * r_m  # Apply interest

        return BrickOutput(
            cash_in=np.zeros(T),  # Cash account doesn't generate cash flows, only receives them
            cash_out=np.zeros(T), # Cash account doesn't generate cash outflows
            asset_value=bal, 
            debt_balance=np.zeros(T), 
            events=[]
        )

class ValuationPropertyDiscrete(IValuationStrategy):
    """
    Real estate property valuation strategy (kind: 'a.property').
    
    This strategy models a discrete property purchase with upfront costs and
    simple appreciation over time. The property is purchased at t=0 with
    the specified price and fees, then appreciates at a constant annual rate.
    
    Required Parameters:
        - price: Purchase price of the property
        - fees_pct: Transaction fees as percentage of price (e.g., 0.095 for 9.5%)
        - appreciation_pa: Annual appreciation rate (e.g., 0.02 for 2%)
        
    Optional Parameters:
        - down_payment: Down payment amount (used by linked mortgages)
        - finance_fees: Whether to finance the fees (default: False)
        
    Note:
        This strategy is commonly linked to mortgage bricks that auto-calculate
        their principal from the property price minus down payment.
    """
    
    def prepare(self, brick: ABrick, ctx: ScenarioContext) -> None:
        """
        Prepare the property valuation strategy.
        
        Validates that all required parameters are present.
        
        Args:
            brick: The property brick
            ctx: The simulation context
            
        Raises:
            AssertionError: If required parameters are missing
        """
        required_params = ["price", "fees_pct", "appreciation_pa"]
        for param in required_params: 
            assert param in brick.spec, f"Missing required parameter: {param}"

    def simulate(self, brick: ABrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the property over the time period.
        
        Models the property purchase at t=0 and appreciation over time.
        The property value grows at the specified annual rate, while
        the purchase costs are paid upfront.
        
        Args:
            brick: The property brick
            ctx: The simulation context
            
        Returns:
            BrickOutput with purchase costs, appreciating asset value, and purchase event
        """
        T = len(ctx.t_index)
        cash_in  = np.zeros(T)
        cash_out = np.zeros(T)
        value    = np.zeros(T)

        # Extract parameters
        price = float(brick.spec["price"])
        fees  = price * float(brick.spec["fees_pct"])
        
        # Calculate fees financing (new logic with percentage support)
        fees_fin_pct = float(brick.spec.get("fees_financed_pct", 1.0 if brick.spec.get("finance_fees") else 0.0))
        fees_fin_pct = max(0.0, min(1.0, fees_fin_pct))  # Clamp to [0,1]
        fees_cash = fees * (1.0 - fees_fin_pct)

        # t0 settlement: pay seller + cash portion of fees ONCE
        cash_out[0] = price + fees_cash

        # Calculate monthly appreciation rate
        r_m = (1 + float(brick.spec["appreciation_pa"])) ** (1/12) - 1
        
        # Set initial value and calculate appreciation
        value[0] = price
        for t in range(1, T): 
            value[t] = value[t-1] * (1 + r_m)

        
        # Create time-stamped events
        events = [
            Event(ctx.t_index[0], "purchase", f"Purchase {brick.name}", {"price": price}),
        ]
        if fees_cash > 0:
            events.append(Event(ctx.t_index[0], "fees_cash", f"Fees paid from cash: €{fees_cash:,.2f}",
                                {"fees": fees, "fees_cash": fees_cash}))
        if fees_fin_pct > 0:
            events.append(Event(ctx.t_index[0], "fees_financed", f"Fees financed: €{fees * fees_fin_pct:,.2f}",
                                {"fees": fees, "fees_financed": fees * fees_fin_pct}))

        # Auto-dispose on window end (equity-neutral)
        from .core import active_mask
        mask = active_mask(ctx.t_index, brick.start_date, brick.end_date, brick.duration_m)
        dispose = bool(brick.spec.get("sell_on_window_end", True))  # DEFAULT: True
        fees_pct = float(brick.spec.get("sell_fees_pct", 0.0))
        
        if dispose and mask.any():
            t_stop = int(np.where(mask)[0].max())
            gross = value[t_stop]
            fees = gross * fees_pct
            proceeds = gross - fees
            
            cash_in[t_stop] += proceeds      # book sale
            value[t_stop] = 0.0              # explicit zero on the sale month
            # Set all future values to 0 (property is sold)
            value[t_stop+1:] = 0.0
            events.append(Event(ctx.t_index[t_stop], "asset_dispose",
                                f"Property sold for €{proceeds:,.2f}",
                                {"gross": gross, "fees": fees, "fees_pct": fees_pct}))

        return BrickOutput(
            cash_in=cash_in, 
            cash_out=cash_out,
            asset_value=value, 
            debt_balance=np.zeros(T),
            events=events
        )

class ValuationETFUnitized(IValuationStrategy):
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
        
    Parameters:
        - initial_units: Number of units held at start (default: 0.0)
        - price0: Initial price per unit (default: 100.0)
        - drift_pa: Annual price drift rate (default: 0.03 for 3%)
        - div_yield_pa: Annual dividend yield (default: 0.0)
        - reinvest_dividends: Whether to reinvest dividends (default: False)
        - buy_at_start: One-shot purchase {"amount": X} or {"units": Y}
        - dca: DCA configuration with mode, amount/units, timing, and step-up
        - sell: List of one-shot sells [{"t": "YYYY-MM", "amount": X} or {"units": Y}]
        - sdca: Systematic DCA-out configuration for regular withdrawals
        - round_units_to: Round units to N decimal places (optional)
        - events_level: Event verbosity "none"|"major"|"all" (default: "major")
        
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
        s.setdefault("initial_units", 0.0)
        s.setdefault("price0", 100.0)
        s.setdefault("drift_pa", 0.03)
        s.setdefault("div_yield_pa", 0.0)
        s.setdefault("reinvest_dividends", False)
        s.setdefault("buy_at_start", None)      # {"amount": >0} or {"units": >0}
        s.setdefault("dca", None)               # {"mode": "amount"|"units", ...}
        s.setdefault("sell", [])                # [{"t": "YYYY-MM", "amount": X} or {"units": Y}]
        s.setdefault("sdca", None)              # {"mode": "amount"|"units", ...}
        s.setdefault("round_units_to", None)
        s.setdefault("events_level", "major")   # "none"|"major"|"all"

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
            assert ("amount" in bas) ^ ("units" in bas), "buy_at_start: provide exactly one of {'amount','units'}"
            if "amount" in bas: 
                assert bas["amount"] >= 0, "buy_at_start.amount must be >= 0"
            if "units" in bas:  
                assert bas["units"] >= 0, "buy_at_start.units must be >= 0"

        # Validate sell configuration
        sell_directives = s["sell"]
        for sell_spec in sell_directives:
            assert "t" in sell_spec, "sell directive must include 't' (date)"
            assert ("amount" in sell_spec) ^ ("units" in sell_spec), "sell directive: provide exactly one of {'amount','units'}"
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
        cash_in  = np.zeros(T)    # dividends (if not reinvested)
        cash_out = np.zeros(T)    # purchases
        units    = np.zeros(T)
        price    = np.zeros(T)
        events   = []

        # Price path calculation
        r_m = (1 + float(s["drift_pa"])) ** (1/12) - 1
        price[0] = float(s["price0"])
        for t in range(1, T):
            price[t] = price[t-1] * (1 + r_m)

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
                    events.append(Event(ctx.t_index[0], "buy_start",
                                        f"ETF buy at start: €{amt:,.2f}",
                                        {"amount": amt, "units": add_u, "price": price[0]}))
            elif "units" in buy0 and buy0["units"] > 0:
                u = float(buy0["units"])
                amt = u * price[0]
                units[0] += u
                cash_out[0] += amt
                if s.get("events_level") in ("major", "all"):
                    events.append(Event(ctx.t_index[0], "buy_start",
                                        f"ETF buy at start: {u:,.6f}u",
                                        {"amount": amt, "units": u, "price": price[0]}))

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
                units[t] = units[t-1]

            # Dividends BEFORE DCA (based on units at start of month)
            if divm > 0:
                dv = units[t] * price[t] * divm
                if reinv and dv > 0:
                    add_u = dv / price[t]
                    units[t] += add_u
                    if ev_lvl in ("major", "all"):
                        events.append(Event(ctx.t_index[t], "div_reinvest",
                                            f"Dividends reinvested: €{dv:,.2f}",
                                            {"amount": dv, "units": add_u, "price": price[t]}))
                else:
                    cash_in[t] += dv
                    if ev_lvl in ("major", "all") and dv > 0:
                        events.append(Event(ctx.t_index[t], "div_cash",
                                            f"Dividends to cash: €{dv:,.2f}",
                                            {"amount": dv, "price": price[t]}))

            # DCA AFTER dividends
            if dca is not None:
                start_off = int(dca.get("start_offset_m", 0))
                months = dca.get("months", None)
                m_rel = t - start_off
                if m_rel >= 0 and (months is None or m_rel < int(months)):
                    if dca["mode"] == "amount":
                        step_blocks = max(0, m_rel // 12)
                        amt = float(dca["amount"]) * ((1 + float(dca.get("annual_step_pct", 0.0))) ** step_blocks)
                        if amt > 0:
                            add_u = amt / price[t]
                            units[t] += add_u
                            cash_out[t] += amt
                            if ev_lvl == "all":
                                events.append(Event(ctx.t_index[t], "dca_amount",
                                                    f"DCA (amount): €{amt:,.2f}",
                                                    {"amount": amt, "units": add_u, "price": price[t]}))
                    else:  # units mode
                        u = float(dca["units"])
                        if u > 0:
                            amt = u * price[t]  # Use current month's price
                            units[t] += u
                            cash_out[t] += amt
                            if ev_lvl == "all":
                                events.append(Event(ctx.t_index[t], "dca_units",
                                                    f"DCA (units): {u:,.6f}u",
                                                    {"amount": amt, "units": u, "price": price[t]}))

            # SELLS AFTER DCA (one-shot and SDCA)
            # One-shot sells
            sell_directives = s.get("sell", [])
            for sell_spec in sell_directives:
                sell_date = np.datetime64(sell_spec["t"], 'M')
                if ctx.t_index[t] == sell_date:
                    if "amount" in sell_spec:
                        # Sell by cash target
                        sell_units = min(units[t], sell_spec["amount"] / price[t])
                    else:
                        # Sell by units
                        sell_units = min(units[t], sell_spec["units"])
                    
                    if sell_units > 0:
                        units[t] -= sell_units
                        cash_in[t] += sell_units * price[t]
                        if ev_lvl in ("major", "all"):
                            events.append(Event(ctx.t_index[t], "sell",
                                                f"Sell {sell_units:,.6f}u for €{sell_units * price[t]:,.2f}",
                                                {"units": sell_units, "amount": sell_units * price[t], "price": price[t]}))

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
                            events.append(Event(ctx.t_index[t], "sdca",
                                                f"SDCA: {sell_units:,.6f}u for €{sell_units * price[t]:,.2f}",
                                                {"units": sell_units, "amount": sell_units * price[t], "price": price[t]}))

            # Round units after all operations for the month
            if round_to is not None:
                units[t] = np.round(units[t], int(round_to))

        # Calculate final asset values
        asset_value = units * price

        # Auto-dispose on window end (equity-neutral)
        from .core import active_mask
        mask = active_mask(ctx.t_index, brick.start_date, brick.end_date, brick.duration_m)
        dispose = bool(brick.spec.get("liquidate_on_window_end", True))  # DEFAULT: True
        fees_pct = float(brick.spec.get("sell_fees_pct", 0.0))
        
        if dispose and mask.any():
            t_stop = int(np.where(mask)[0].max())
            gross = asset_value[t_stop]
            fees = gross * fees_pct
            proceeds = gross - fees
            
            cash_in[t_stop] += proceeds      # book sale
            asset_value[t_stop] = 0.0        # explicit zero on the sale month
            # Set all future values to 0 (ETF is liquidated)
            asset_value[t_stop+1:] = 0.0
            events.append(Event(ctx.t_index[t_stop], "asset_dispose",
                                f"ETF liquidated for €{proceeds:,.2f}",
                                {"gross": gross, "fees": fees, "fees_pct": fees_pct}))

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            asset_value=asset_value,
            debt_balance=np.zeros(T),
            events=events
        )

# ---------- Liability Schedule Strategies ----------

def _get_spec_value(spec, key, default=None):
    """Get a value from spec, handling both dict and LMortgageSpec objects."""
    if hasattr(spec, key):
        return getattr(spec, key, default)
    elif isinstance(spec, dict):
        return spec.get(key, default)
    else:
        return getattr(spec, key, default)

def _has_spec_key(spec, key):
    """Check if spec has a key, handling both dict and LMortgageSpec objects."""
    if isinstance(spec, dict):
        return key in spec
    else:
        return hasattr(spec, key)

class ScheduleMortgageAnnuity(IScheduleStrategy):
    """
    Fixed-rate mortgage with annuity payment schedule (kind: 'l.mortgage.annuity').
    
    This strategy models a traditional fixed-rate mortgage with equal monthly payments
    that include both principal and interest. The principal can be provided directly
    or automatically calculated from a linked property minus the down payment.
    
    Required Parameters:
        - rate_pa: Annual interest rate (e.g., 0.034 for 3.4%)
        - term_months: Total term in months (e.g., 300 for 25 years)
        - principal: Loan principal amount (can be auto-calculated)
        
    Optional Parameters (for auto-calculation):
        - links: Dictionary with 'auto_principal_from' key pointing to property brick ID
        
    Note:
        If principal is not provided, it will be calculated from the linked property's
        price minus down_payment. This enables automatic mortgage sizing based on
        property purchases.
    """
    
    def prepare(self, brick: LBrick, ctx: ScenarioContext) -> None:
        """
        Prepare the mortgage strategy.
        
        Validates parameters and optionally calculates principal from linked property.
        
        Args:
            brick: The mortgage brick
            ctx: The simulation context
            
        Raises:
            AssertionError: If required parameters are missing or auto-calculation fails
        """
        # Handle resolved principal from mortgage resolution
        if "principal" in brick.spec:
            # Principal was resolved by the mortgage resolution system
            principal = brick.spec["principal"]
        # Auto-calculate principal from linked property if not provided
        elif _get_spec_value(brick.spec, "principal") is None:
            # Check for new PrincipalLink format first
            principal_link_data = (brick.links or {}).get("principal")
            if principal_link_data:
                from .core import PrincipalLink
                principal_link = PrincipalLink(**principal_link_data)
                
                if principal_link.from_house:
                    # Calculate principal from house
                    auto_from = principal_link.from_house
                    if auto_from in ctx.registry:
                        prop: ABrick = ctx.registry[auto_from]  # type: ignore
                        price = float(prop.spec["price"])
                        down = float(_get_spec_value(prop.spec, "down_payment", 0.0))
                        fees_pct = float(_get_spec_value(prop.spec, "fees_pct", 0.0))
                        fees = price * fees_pct
                        
                        # Handle fees financing
                        finance_fees = bool(_get_spec_value(prop.spec, "finance_fees", False))
                        fees_fin_pct = float(_get_spec_value(prop.spec, "fees_financed_pct", 1.0 if finance_fees else 0.0))
                        fees_fin_pct = max(0.0, min(1.0, fees_fin_pct))  # Clamp to [0,1]
                        fees_financed = fees * fees_fin_pct
                        
                        # Calculate principal: price - down_payment + financed_fees
                        principal = price - down + fees_financed
                        
                        brick.spec["principal"] = principal
                        # Store derived values for logging/validation
                        brick.spec["_derived"] = {
                            "price": price,
                            "down_payment": down,
                            "fees": fees,
                            "fees_financed": fees_financed
                        }
                    else:
                        raise AssertionError(f"PrincipalLink references unknown house: {auto_from}")
                        
                elif principal_link.nominal is not None:
                    # Direct nominal amount
                    brick.spec["principal"] = principal_link.nominal
                    
                elif principal_link.remaining_of:
                    # This will be handled by settlement buckets during simulation
                    # For now, we'll defer the principal calculation
                    brick.spec["_deferred_principal"] = True
                    
                else:
                    raise AssertionError("PrincipalLink must specify from_house, nominal, or remaining_of")
            else:
                # Fallback to legacy format
                auto_from = (brick.links or {}).get("auto_principal_from")
                if auto_from and auto_from in ctx.registry:
                    prop: ABrick = ctx.registry[auto_from]  # type: ignore
                    price = float(prop.spec["price"])
                    down = float(_get_spec_value(prop.spec, "down_payment", 0.0))
                    fees_pct = float(_get_spec_value(prop.spec, "fees_pct", 0.0))
                    fees = price * fees_pct
                    
                    # Handle fees financing
                    finance_fees = bool(_get_spec_value(prop.spec, "finance_fees", False))
                    fees_fin_pct = float(_get_spec_value(prop.spec, "fees_financed_pct", 1.0 if finance_fees else 0.0))
                    fees_fin_pct = max(0.0, min(1.0, fees_fin_pct))  # Clamp to [0,1]
                    fees_financed = fees * fees_fin_pct
                    
                    # Calculate principal: price - down_payment + financed_fees
                    principal = price - down + fees_financed
                    
                    brick.spec["principal"] = principal
                    # Store derived values for logging/validation
                    brick.spec["_derived"] = {
                        "price": price,
                        "down_payment": down,
                        "fees": fees,
                        "fees_financed": fees_financed
                    }
                else:
                    raise AssertionError("Principal link missing or invalid - check PrincipalLink or auto_principal_from")
        
        # Validate required parameters
        rate_pa = _get_spec_value(brick.spec, "rate_pa")
        if rate_pa is None:
            raise AssertionError("Missing required parameter: rate_pa")
        
        # Handle term calculation from amortization if needed
        term_months = _get_spec_value(brick.spec, "term_months")
        amortization_pa = _get_spec_value(brick.spec, "amortization_pa")
        
        if term_months is None and amortization_pa is not None:
            # Calculate term from amortization
            from .core import term_from_amort
            term_months = term_from_amort(rate_pa, amortization_pa)
            brick.spec["term_months"] = term_months
        elif term_months is None:
            raise AssertionError("Missing required parameter: term_months or amortization_pa")
        
        # Validate principal is available
        principal = _get_spec_value(brick.spec, "principal")
        if principal is None and not brick.spec.get("_deferred_principal", False):
            raise AssertionError("Principal not available - check links or provide explicitly")
        
        # Set default first payment offset (1 month is standard)
        brick.spec.setdefault("first_payment_offset", 1)

    def simulate(self, brick: LBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the mortgage over the time period.
        
        Calculates the annuity payment schedule with equal monthly payments
        that include both principal and interest. Supports prepayments (Sondertilgung)
        and balloon payments at the end of the activation window.
        
        Args:
            brick: The mortgage brick
            ctx: The simulation context
            
        Returns:
            BrickOutput with loan drawdown, payment schedule, debt balance, and events
        """
        from .core import resolve_prepayments_to_month_idx, active_mask
        
        T = len(ctx.t_index)
        cash_in  = np.zeros(T)
        cash_out = np.zeros(T)
        debt     = np.zeros(T)

        # Extract parameters
        principal = float(_get_spec_value(brick.spec, "principal", 0))
        if principal == 0 and brick.spec.get("_deferred_principal", False):
            # For deferred principals (remaining_of), use a placeholder
            # This will be resolved by settlement buckets in a future implementation
            principal = 100000  # Placeholder amount
        rate_pa   = float(_get_spec_value(brick.spec, "rate_pa", 0))
        n_total   = int(_get_spec_value(brick.spec, "term_months", 300))
        offset = int(_get_spec_value(brick.spec, "first_payment_offset", 1))
        
        # Prepayment configuration
        prepayments = _get_spec_value(brick.spec, "prepayments", [])
        prepay_fee_pct = float(_get_spec_value(brick.spec, "prepay_fee_pct", 0.0))
        balloon_policy = _get_spec_value(brick.spec, "balloon_policy", "payoff")
        
        # Resolve prepayments to month indices
        mortgage_start = brick.start_date or ctx.t_index[0].astype('datetime64[D]').astype(date)
        prepay_map = resolve_prepayments_to_month_idx(ctx.t_index, prepayments, mortgage_start)

        # Initial loan drawdown at t=0
        cash_in[0] += principal
        debt[0] = principal

        # Calculate monthly payment using annuity formula
        r_m = rate_pa / 12.0
        if r_m > 0:
            A = principal * (r_m * (1 + r_m) ** n_total) / ((1 + r_m) ** n_total - 1)
        else:
            A = principal / n_total  # Handle zero interest rate case
        
        # Carry forward debt unchanged until first payment
        for t in range(1, min(offset, T)):
            debt[t] = debt[t-1]
        
        # Calculate payment schedule with prepayments
        n_sched = min(n_total, max(0, T - offset))
        for k in range(n_sched):
            t = offset + k
            if t >= T:
                break
                
            prev_debt = debt[t-1] if t > 0 else principal
            if prev_debt > 0:
                # 1. Accrue interest
                interest = prev_debt * r_m
                
                # 2. Scheduled annuity payment
                principal_pay = min(A - interest, prev_debt)
                bal_after_sched = max(prev_debt - principal_pay, 0.0)
                
                # 3. Prepayment (Sondertilgung)
                prepay_amt = 0.0
                if t in prepay_map:
                    prepay_spec = prepay_map[t]
                    if isinstance(prepay_spec, tuple):  # Percentage-based
                        pct, cap = prepay_spec[1], prepay_spec[2]
                        prepay_amt = min(pct * bal_after_sched, cap, bal_after_sched)
                    else:  # Fixed amount
                        prepay_amt = min(prepay_spec, bal_after_sched)
                
                # Apply prepayment
                if prepay_amt > 0:
                    prepay_fee = prepay_amt * prepay_fee_pct
                    cash_out[t] += interest + principal_pay + prepay_amt + prepay_fee
                    debt[t] = max(bal_after_sched - prepay_amt, 0.0)
                else:
                    cash_out[t] += interest + principal_pay
                    debt[t] = bal_after_sched
            else:
                debt[t] = 0.0

        # Create time-stamped events
        events = [
            Event(ctx.t_index[0], "loan_draw", f"Mortgage drawdown: €{principal:,.2f}", 
                  {"principal": principal})
        ]
        
        # Balloon payoff on window end (equity-neutral)
        mask = active_mask(ctx.t_index, brick.start_date, brick.end_date, brick.duration_m)
        t_stop = int(np.where(mask)[0].max()) if mask.any() else None
        
        if t_stop is not None and debt[t_stop] > 0:
            residual = debt[t_stop]
            policy = _get_spec_value(brick.spec, "balloon_policy", "payoff")  # DEFAULT
            
            if policy == "payoff":
                cash_out[t_stop] += residual
                debt[t_stop] = 0.0
                # Set all future debt to 0 (mortgage is paid off)
                debt[t_stop+1:] = 0.0
                events.append(Event(ctx.t_index[t_stop], "balloon_payoff",
                                    f"Balloon payoff €{residual:,.2f}", {"residual": residual}))
            elif policy == "refinance":
                events.append(Event(ctx.t_index[t_stop], "balloon_due",
                                    f"Balloon due €{residual:,.2f}", {"residual": residual}))
                # leave debt as computed; validator enforces presence of a new loan this month
        
        # Add derived info if available
        if _has_spec_key(brick.spec, "_derived"):
            derived = _get_spec_value(brick.spec, "_derived")
            events.append(Event(ctx.t_index[0], "loan_details", 
                                f"Price: €{derived['price']:,.2f}, Down: €{derived['down_payment']:,.2f}, Fees financed: €{derived['fees_financed']:,.2f}",
                                derived))
        
        # Add prepayment events
        for t, prepay_spec in prepay_map.items():
            if isinstance(prepay_spec, tuple):
                pct, cap = prepay_spec[1], prepay_spec[2]
                events.append(Event(ctx.t_index[t], "prepay", 
                                    f"Prepayment {pct*100:.1f}% of balance (capped at €{cap:,.2f})",
                                    {"type": "percentage", "pct": pct, "cap": cap}))
            else:
                events.append(Event(ctx.t_index[t], "prepay", 
                                    f"Prepayment: €{prepay_spec:,.2f}",
                                    {"type": "amount", "amount": prepay_spec}))
        

        return BrickOutput(
            cash_in=cash_in, 
            cash_out=cash_out,
            asset_value=np.zeros(T), 
            debt_balance=debt,
            events=events
        )

# ---------- Cash Flow Strategies ----------

class FlowTransferLumpSum(IFlowStrategy):
    """
    Lump sum transfer flow strategy (kind: 'f.transfer.lumpsum').
    
    This strategy models a one-time cash transfer that occurs at t=0.
    Commonly used for initial capital injections, windfalls, or large
    one-time payments.
    
    Required Parameters:
        - amount: The lump sum amount to transfer at t=0
        
    Note:
        This strategy generates a single cash inflow at the beginning
        of the simulation period.
    """
    
    def prepare(self, brick: FBrick, ctx: ScenarioContext) -> None:
        """
        Prepare the lump sum transfer strategy.
        
        Validates that the amount parameter is present.
        
        Args:
            brick: The transfer flow brick
            ctx: The simulation context
            
        Raises:
            AssertionError: If amount parameter is missing
        """
        assert "amount" in brick.spec, "Missing required parameter: amount"

    def simulate(self, brick: FBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the lump sum transfer.
        
        Generates a single cash inflow at t=0 with the specified amount.
        
        Args:
            brick: The transfer flow brick
            ctx: The simulation context
            
        Returns:
            BrickOutput with single cash inflow at t=0 and transfer event
        """
        T = len(ctx.t_index)
        cash_in = np.zeros(T)
        cash_in[0] = float(brick.spec["amount"])
        
        return BrickOutput(
            cash_in=cash_in, 
            cash_out=np.zeros(T),
            asset_value=np.zeros(T), 
            debt_balance=np.zeros(T), 
            events=[Event(ctx.t_index[0], "transfer", f"Lump sum transfer: €{cash_in[0]:,.2f}", 
                          {"amount": cash_in[0]})]
        )


class FlowIncomeFixed(IFlowStrategy):
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
        assert "amount_monthly" in brick.spec, "Missing required parameter: amount_monthly"
        
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
        Simulate the income with optional escalation.
        
        Generates monthly cash inflows with annual or periodic escalation.
        
        Args:
            brick: The income flow brick
            ctx: The simulation context
            
        Returns:
            BrickOutput with escalated monthly cash inflows and escalation events
        """
        T = len(ctx.t_index)
        cash_in = np.zeros(T)
        
        # Extract parameters
        base_amount = float(brick.spec["amount_monthly"])
        annual_step_pct = float(brick.spec["annual_step_pct"])
        step_month = brick.spec.get("step_month")
        step_every_m = brick.spec.get("step_every_m")
        step_pct = float(brick.spec.get("step_pct", annual_step_pct))  # For step_every_m
        
        # Determine start date for anniversary calculations
        start_date = brick.start_date or ctx.t_index[0].astype('datetime64[D]').astype(date)
        
        events = []
        
        # Calculate escalated amounts for each month
        for t in range(T):
            current_date = ctx.t_index[t].astype('datetime64[D]').astype(date)
            
            if step_every_m is not None:
                # Non-annual escalation
                months_since_start = t
                steps = months_since_start // step_every_m
                amount = base_amount * ((1 + step_pct) ** steps)
            else:
                # Annual escalation
                years_since_start = (current_date.year - start_date.year)
                
                # Check if we've passed the step month in the current year
                if step_month is not None:
                    # Use specified month (e.g., June every year)
                    if current_date.month >= step_month:
                        years_since_start += 1
                else:
                    # Use anniversary of start date
                    if (current_date.month > start_date.month or 
                        (current_date.month == start_date.month and current_date.day >= start_date.day)):
                        years_since_start += 1
                
                amount = base_amount * ((1 + annual_step_pct) ** years_since_start)
            
            cash_in[t] = amount
            
            # Add escalation event for the first month of each new amount
            if t == 0 or cash_in[t] != cash_in[t-1]:
                if annual_step_pct > 0 or step_every_m is not None:
                    events.append(Event(ctx.t_index[t], "income_escalation",
                                        f"Income escalated to €{amount:,.2f}/month",
                                        {"amount": amount, "annual_step_pct": annual_step_pct}))
        
        return BrickOutput(
            cash_in=cash_in, 
            cash_out=np.zeros(T),
            asset_value=np.zeros(T), 
            debt_balance=np.zeros(T), 
            events=events
        )


class FlowExpenseFixed(IFlowStrategy):
    """
    Fixed monthly expense flow strategy (kind: 'f.expense.living').
    
    This strategy models a regular monthly expense with a constant amount.
    Commonly used for living expenses, insurance, subscriptions, or other
    regular recurring costs.
    
    Required Parameters:
        - amount_monthly: The monthly expense amount
        
    Note:
        This strategy generates the same cash outflow every month throughout
        the simulation period.
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
        assert "amount_monthly" in brick.spec, "Missing required parameter: amount_monthly"

    def simulate(self, brick: FBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the fixed monthly expense.
        
        Generates a constant monthly cash outflow throughout the simulation period.
        
        Args:
            brick: The expense flow brick
            ctx: The simulation context
            
        Returns:
            BrickOutput with constant monthly cash outflows and no events
        """
        T = len(ctx.t_index)
        cash_out = np.full(T, float(brick.spec["amount_monthly"]))
        
        return BrickOutput(
            cash_in=np.zeros(T), 
            cash_out=cash_out,
            asset_value=np.zeros(T), 
            debt_balance=np.zeros(T), 
            events=[]  # No events for regular expense flows
        )

# ---------- Strategy Registry Setup ----------

def register_defaults():
    """
    Register all default strategy implementations in the global registries.
    
    This function populates the global strategy registries with the default
    implementations provided by FinScenLab. These strategies are automatically
    available for use by bricks with matching kind discriminators.
    
    Registered Strategies:
        Assets:
            - 'a.cash': Cash account with interest
            - 'a.property': Real estate with appreciation
            - 'a.invest.etf': ETF investment with price drift
            
        Liabilities:
            - 'l.mortgage.annuity': Fixed-rate mortgage with annuity payments
            
        Flows:
            - 'f.transfer.lumpsum': One-time lump sum transfer
            - 'f.income.salary': Fixed monthly income
            - 'f.expense.living': Fixed monthly expenses
            
    Note:
        This function is automatically called when the module is imported.
        Additional strategies can be registered by calling the registry
        dictionaries directly.
    """
    # Register asset valuation strategies
    ValuationRegistry[K.A_CASH]      = ValuationCash()
    ValuationRegistry[K.A_PROPERTY]  = ValuationPropertyDiscrete()
    ValuationRegistry[K.A_INV_ETF]   = ValuationETFUnitized()
    
    # Register liability schedule strategies
    ScheduleRegistry[K.L_MORT_ANN]   = ScheduleMortgageAnnuity()
    
    # Register cash flow strategies
    FlowRegistry[K.F_TRANSFER]       = FlowTransferLumpSum()
    FlowRegistry[K.F_INCOME]         = FlowIncomeFixed()
    FlowRegistry[K.F_EXP_LIVING]     = FlowExpenseFixed()


# Automatically register default strategies when module is imported
register_defaults()
