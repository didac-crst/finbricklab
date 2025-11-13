"""
Real estate property valuation strategy.
"""

from __future__ import annotations

import numpy as np

from finbricklab.core.bricks import ABrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.events import Event
from finbricklab.core.interfaces import IValuationStrategy
from finbricklab.core.results import BrickOutput
from finbricklab.core.utils import active_mask


class ValuationProperty(IValuationStrategy):
    """
    Real estate property valuation strategy (kind: 'a.property').

    This strategy models a discrete property purchase with upfront costs and
    simple appreciation over time. The property is purchased at t=0 with
    the specified price and fees, then appreciates at a constant annual rate.

    Required Parameters:
        - initial_value: Purchase price of the property
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
        # Validate required parameters
        required_params = ["initial_value", "fees_pct", "appreciation_pa"]
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
        cash_in = np.zeros(T)
        cash_out = np.zeros(T)
        value = np.zeros(T)
        fees_series = np.zeros(T)

        # Extract parameters
        initial_value = float(brick.spec["initial_value"])
        fees = initial_value * float(brick.spec["fees_pct"])

        # Calculate fees financing (new logic with percentage support)
        fees_fin_pct = float(
            brick.spec.get(
                "fees_financed_pct", 1.0 if brick.spec.get("finance_fees") else 0.0
            )
        )
        fees_fin_pct = max(0.0, min(1.0, fees_fin_pct))  # Clamp to [0,1]
        fees_cash = fees * (1.0 - fees_fin_pct)
        fees_series[0] += fees

        # t0 settlement: pay seller + cash portion of fees ONCE
        cash_out[0] = initial_value + fees_cash

        # Calculate monthly appreciation rate
        r_m = (1 + float(brick.spec["appreciation_pa"])) ** (1 / 12) - 1

        # Set initial value and calculate appreciation
        value[0] = initial_value
        for t in range(1, T):
            value[t] = value[t - 1] * (1 + r_m)

        # Create time-stamped events
        events = [
            Event(
                ctx.t_index[0],
                "purchase",
                f"Purchase {brick.name}",
                {"price": initial_value},
            ),
        ]
        if fees_cash > 0:
            events.append(
                Event(
                    ctx.t_index[0],
                    "fees_cash",
                    f"Fees paid from cash: €{fees_cash:,.2f}",
                    {"fees": fees, "fees_cash": fees_cash},
                )
            )
        if fees_fin_pct > 0:
            events.append(
                Event(
                    ctx.t_index[0],
                    "fees_financed",
                    f"Fees financed: €{fees * fees_fin_pct:,.2f}",
                    {"fees": fees, "fees_financed": fees * fees_fin_pct},
                )
            )

        # Auto-dispose on window end (equity-neutral)
        mask = active_mask(
            ctx.t_index, brick.start_date, brick.end_date, brick.duration_m
        )
        dispose = bool(brick.spec.get("sell_on_window_end", False))  # DEFAULT: False
        fees_pct = float(brick.spec.get("sell_fees_pct", 0.0))

        if dispose and mask.any():
            t_stop = int(np.where(mask)[0].max())
            gross = value[t_stop]
            fees = gross * fees_pct
            proceeds = gross - fees

            cash_in[t_stop] += proceeds  # book sale
            value[t_stop] = 0.0  # explicit zero on the sale month
            # Set all future values to 0 (property is sold)
            value[t_stop + 1 :] = 0.0
            fees_series[t_stop] += fees
            events.append(
                Event(
                    ctx.t_index[t_stop],
                    "asset_dispose",
                    f"Property sold for €{proceeds:,.2f}",
                    {"gross": gross, "fees": fees, "fees_pct": fees_pct},
                )
            )

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            assets=value,
            liabilities=np.zeros(T),
            interest=np.zeros(T),  # Property doesn't generate interest/dividends
            property_value=value.copy(),
            owner_equity=value.copy(),  # Updated later when mortgages linked
            mortgage_balance=np.zeros(T),
            fees=fees_series,
            taxes=np.zeros(T),
            events=events,
        )
