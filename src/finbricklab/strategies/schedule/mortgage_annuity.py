"""
Fixed-rate mortgage with annuity payment schedule.
"""

from __future__ import annotations

import warnings
from dataclasses import asdict, is_dataclass
from datetime import date

import numpy as np

from finbricklab.core.bricks import ABrick, LBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.events import Event
from finbricklab.core.interfaces import IScheduleStrategy
from finbricklab.core.links import PrincipalLink
from finbricklab.core.results import BrickOutput
from finbricklab.core.specs import term_from_amort
from finbricklab.core.utils import active_mask, resolve_prepayments_to_month_idx


class FinBrickWarning(UserWarning):
    """Warning for FinBrickLab configuration issues."""


class FinBrickDeprecationWarning(DeprecationWarning):
    """Deprecation warning for FinBrickLab."""


# Global set to track warnings per brick to avoid spam
_warned: set[tuple[str, str]] = set()


def warn_once(code: str, brick_id: str, msg: str, *, category=FinBrickWarning):
    """Warn once per (brick_id, code) to avoid spam."""
    key = (brick_id, code)
    if key not in _warned:
        _warned.add(key)
        warnings.warn(msg, category, stacklevel=3)


def normalize_spec(spec):
    """Normalize spec to a dict, handling both dict and LMortgageSpec objects."""
    if is_dataclass(spec):
        return asdict(spec)  # plain dict
    elif isinstance(spec, dict):
        return dict(spec)  # shallow copy
    else:
        raise TypeError("spec must be dict or LMortgageSpec")


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
    Fixed-rate mortgage with annuity payment schedule (kind: 'l.loan.annuity').

    This strategy models a traditional fixed-rate mortgage with equal monthly payments
    that include both principal and interest. It supports two independent concepts:

    **Amortization Term**: How long the loan would take to fully repay (drives payment calculation)
    **Credit Window**: How long the bank's fixed-rate commitment runs (when refinancing is needed)

    **Required Parameters (canonical names):**
        - rate_pa: Annual interest rate (e.g., 0.034 for 3.4%)
        - term_months OR amortization_pa: Total amortization term or initial amortization rate

    **User-Friendly Aliases:**
        - interest_rate_pa → rate_pa
        - amortization_rate_pa → amortization_pa
        - amortization_term_months → term_months
        - credit_end_date → end_date (highest priority)
        - credit_term_months → duration_m
        - fix_rate_months → duration_m (fallback)

    **Principal Specification (exactly one required):**
        - spec.principal: Direct principal amount, OR
        - links.principal: PrincipalLink dict with 'from_house' pointing to property brick ID

    **Credit Window Precedence:**
        credit_end_date → credit_term_months → fix_rate_months → existing brick fields

    **Balloon Policy (at end of credit window):**
        - "refinance" (default): Leave remaining debt outstanding for refinancing
        - "payoff": Pay off remaining debt with cash outflow

    **Example - German Mortgage Scenario:**
        ```python
        mortgage = entity.new_LBrick(
            id="german_mortgage",
            spec={
                "principal": 420_000.0,
                "interest_rate_pa": 0.013,        # 1.3% interest
                "amortization_rate_pa": 0.04,     # 4% amortization (25-year payoff)
                "credit_end_date": date(2028, 7, 1),  # 10-year credit term
                "balloon_policy": "refinance"
            }
        )
        # Results in ~€1,855 monthly payment, ~€240,769 residual after 10 years
        ```

    **Note:**
        If using links.principal, the principal will be calculated from the linked property's
        initial_value minus down_payment. This enables automatic mortgage sizing based on
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
        # Normalize spec to dict (handles both dict and LMortgageSpec)
        spec = normalize_spec(brick.spec)

        # --- Aliases ---
        alias_map = {
            "interest_rate_pa": "rate_pa",
            "amortization_rate_pa": "amortization_pa",
            "amortization_term_months": "term_months",
        }
        for new, old in alias_map.items():
            if new in spec:
                if old in spec and spec[old] != spec[new]:
                    warn_once(
                        "ALIAS_CLASH_" + old.upper(),
                        brick.id,
                        f"[{brick.id}] '{new}' ignored because '{old}' is set (precedence: {old}).",
                    )
                else:
                    spec.setdefault(old, spec[new])

        # Handle unknown/deprecated keys
        if "annual_rate" in spec:
            warnings.warn(
                f"[{brick.id}] 'annual_rate' is not supported. Use 'interest_rate_pa'.",
                FinBrickDeprecationWarning,
                stacklevel=3,
            )
            # Don't use annual_rate - it's deprecated

        # --- Credit window precedence ---
        credit_end = spec.get("credit_end_date")
        credit_term = spec.get("credit_term_months")
        fix_rate = spec.get("fix_rate_months")

        if credit_end is not None:
            if brick.end_date is not None:
                warn_once(
                    "CREDIT_WINDOW_OVERRIDE",
                    brick.id,
                    f"[{brick.id}] Overriding brick.end_date with credit_end_date.",
                )
            brick.end_date = credit_end
        elif credit_term is not None:
            if brick.duration_m is not None:
                warn_once(
                    "CREDIT_WINDOW_OVERRIDE",
                    brick.id,
                    f"[{brick.id}] Overriding brick.duration_m with credit_term_months.",
                )
            brick.duration_m = int(credit_term)
        elif (
            fix_rate is not None and brick.end_date is None and brick.duration_m is None
        ):
            brick.duration_m = int(fix_rate)

        # Push the normalized spec back
        brick.spec = spec

        # Check for conflicting principal specifications BEFORE resolving from links
        has_spec_principal = _get_spec_value(brick.spec, "principal") is not None
        has_link_principal = bool((brick.links or {}).get("principal"))

        if has_spec_principal and has_link_principal:
            raise AssertionError(
                "Provide either spec.principal or links.principal, not both."
            )

        if has_spec_principal:
            # Principal was provided directly in spec
            principal = brick.spec["principal"]
        else:
            # Calculate principal from PrincipalLink
            principal_link_data = (brick.links or {}).get("principal")
            if principal_link_data is None:
                raise AssertionError(
                    "Missing principal: specify spec.principal or links.principal (PrincipalLink)."
                )
            principal_link = PrincipalLink(**principal_link_data)

            if principal_link.from_house:
                # Calculate principal from house initial_value
                prop: ABrick = ctx.registry.get(principal_link.from_house)  # type: ignore
                if not prop:
                    raise AssertionError(
                        f"PrincipalLink.from_house '{principal_link.from_house}' not found"
                    )

                price = float(
                    prop.spec["initial_value"]
                )  # Use initial_value, not price
                down = float(_get_spec_value(prop.spec, "down_payment", 0.0))
                fees_pct = float(_get_spec_value(prop.spec, "fees_pct", 0.0))
                fees = price * fees_pct
                finance_fees = bool(_get_spec_value(prop.spec, "finance_fees", False))
                fees_fin_pct = float(
                    _get_spec_value(
                        prop.spec, "fees_financed_pct", 1.0 if finance_fees else 0.0
                    )
                )
                fees_fin_pct = max(0.0, min(1.0, fees_fin_pct))
                fees_financed = fees * fees_fin_pct
                principal = price - down + fees_financed
                brick.spec["principal"] = principal
                brick.spec["_derived"] = {
                    "price": price,
                    "initial_value": price,
                    "down_payment": down,
                    "fees": fees,
                    "fees_financed": fees_financed,
                }
            elif principal_link.nominal is not None:
                # Direct nominal amount
                brick.spec["principal"] = principal_link.nominal
            elif principal_link.remaining_of:
                # Not implemented yet; don't inject a bogus placeholder.
                from finbricklab.core.errors import ConfigError

                raise ConfigError(
                    "links.principal.remaining_of is not implemented yet. "
                    "Use links.principal.from_house or principal nominal."
                )
            else:
                raise AssertionError(
                    "PrincipalLink must specify from_house, nominal, or remaining_of"
                )

        # Ensure we have a principal after resolution
        if _get_spec_value(brick.spec, "principal") is None:
            raise AssertionError(
                "Missing principal: specify spec.principal or links.principal (PrincipalLink)."
            )

        # Validate required parameters
        rate_pa = _get_spec_value(brick.spec, "rate_pa")
        if rate_pa is None:
            raise AssertionError("Missing required parameter: rate_pa")

        # --- Derive amortization term if needed ---
        term_months = _get_spec_value(brick.spec, "term_months")
        amortization_pa = _get_spec_value(brick.spec, "amortization_pa")

        if term_months is None and amortization_pa is not None:
            # Calculate term from amortization
            brick.spec["term_months"] = term_from_amort(rate_pa, amortization_pa)
        elif term_months is None:
            raise AssertionError(
                "Missing required parameter: term_months or amortization_pa"
            )

        # Validate principal is available
        principal = _get_spec_value(brick.spec, "principal")
        if principal is None:
            raise AssertionError(
                "Principal not available - check links or provide explicitly"
            )

        # Default values
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
        T = len(ctx.t_index)
        cash_in = np.zeros(T)
        cash_out = np.zeros(T)
        debt = np.zeros(T)

        # Extract parameters
        principal = float(_get_spec_value(brick.spec, "principal", 0))
        rate_pa = float(_get_spec_value(brick.spec, "rate_pa", 0))
        n_total = int(_get_spec_value(brick.spec, "term_months", 300))
        offset = int(_get_spec_value(brick.spec, "first_payment_offset", 1))

        # Prepayment configuration
        prepayments = _get_spec_value(brick.spec, "prepayments", [])
        prepay_fee_pct = float(_get_spec_value(brick.spec, "prepay_fee_pct", 0.0))
        _get_spec_value(brick.spec, "balloon_policy", "payoff")

        # Resolve prepayments to month indices
        mortgage_start = brick.start_date or ctx.t_index[0].astype(
            "datetime64[D]"
        ).astype(date)
        prepay_map = resolve_prepayments_to_month_idx(
            ctx.t_index, prepayments, mortgage_start
        )

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
            debt[t] = debt[t - 1]

        # Calculate payment schedule with prepayments
        n_sched = min(n_total, max(0, T - offset))
        for k in range(n_sched):
            t = offset + k
            if t >= T:
                break

            prev_debt = debt[t - 1] if t > 0 else principal
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
            Event(
                ctx.t_index[0],
                "loan_draw",
                f"Mortgage drawdown: €{principal:,.2f}",
                {"principal": principal},
            )
        ]

        mask = active_mask(
            ctx.t_index, brick.start_date, brick.end_date, brick.duration_m
        )
        t_stop = int(np.where(mask)[0].max()) if mask.any() else None

        if t_stop is not None and debt[t_stop] > 0:
            residual = debt[t_stop]
            policy = _get_spec_value(
                brick.spec, "balloon_policy", "refinance"
            )  # DEFAULT

            if policy == "payoff":
                cash_out[t_stop] += residual
                debt[t_stop] = 0.0
                # Set all future debt to 0 (mortgage is paid off)
                debt[t_stop + 1 :] = 0.0
                events.append(
                    Event(
                        ctx.t_index[t_stop],
                        "balloon_payoff",
                        f"Balloon payoff €{residual:,.2f}",
                        {"residual": residual},
                    )
                )
            elif policy == "refinance":
                events.append(
                    Event(
                        ctx.t_index[t_stop],
                        "balloon_due",
                        f"Balloon due €{residual:,.2f}",
                        {"residual": residual},
                    )
                )
                # leave debt as computed; validator enforces presence of a new loan this month

        # Add derived info if available
        if _has_spec_key(brick.spec, "_derived"):
            derived = _get_spec_value(brick.spec, "_derived")
            events.append(
                Event(
                    ctx.t_index[0],
                    "loan_details",
                    f"Price: €{derived['price']:,.2f}, Down: €{derived['down_payment']:,.2f}, Fees financed: €{derived['fees_financed']:,.2f}",
                    derived,
                )
            )

        # Add prepayment events
        for t, prepay_spec in prepay_map.items():
            if isinstance(prepay_spec, tuple):
                pct, cap = prepay_spec[1], prepay_spec[2]
                events.append(
                    Event(
                        ctx.t_index[t],
                        "prepay",
                        f"Prepayment {pct*100:.1f}% of balance (capped at €{cap:,.2f})",
                        {"type": "percentage", "pct": pct, "cap": cap},
                    )
                )
            else:
                events.append(
                    Event(
                        ctx.t_index[t],
                        "prepay",
                        f"Prepayment: €{prepay_spec:,.2f}",
                        {"type": "amount", "amount": prepay_spec},
                    )
                )

        return BrickOutput(
            cash_in=cash_in,
            cash_out=cash_out,
            asset_value=np.zeros(T),
            debt_balance=debt,
            events=events,
        )
