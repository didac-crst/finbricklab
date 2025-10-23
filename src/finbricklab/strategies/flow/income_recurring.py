"""
Fixed monthly income flow strategy with escalation.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from finbricklab.core.bricks import FBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.events import Event
from finbricklab.core.interfaces import IFlowStrategy
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
        step_pct = float(
            brick.spec.get("step_pct", annual_step_pct)
        )  # For step_every_m

        # Determine start date for anniversary calculations
        start_date = brick.start_date or ctx.t_index[0].astype("datetime64[D]").astype(
            date
        )

        events = []

        # Calculate escalated amounts for each month
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

            cash_in[t] = amount

            # Add escalation event for the first month of each new amount
            if t == 0 or cash_in[t] != cash_in[t - 1]:
                if annual_step_pct > 0 or step_every_m is not None:
                    events.append(
                        Event(
                            ctx.t_index[t],
                            "income_escalation",
                            f"Income escalated to €{amount:,.2f}/month",
                            {"amount": amount, "annual_step_pct": annual_step_pct},
                        )
                    )

        return BrickOutput(
            cash_in=cash_in,
            cash_out=np.zeros(T),
            asset_value=np.zeros(T),
            debt_balance=np.zeros(T),
            events=events,
        )
