"""
Specification classes and utilities for FinBrickLab.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class LMortgageSpec:
    """Enhanced mortgage specification with rate fix windows and amortization options."""

    rate_pa: float  # annual interest rate
    term_months: int | None = None  # months to amortize to zero (loan term)
    amortization_pa: float | None = None  # initial annual amortization rate
    fix_rate_months: int | None = (
        None  # months the current rate applies (fixed-rate window)
    )
    finance_fees: bool = False  # if fees are rolled into principal


def term_from_amort(rate_pa: float, amort_pa: float) -> int:
    """
    Calculate loan term in months from annual interest rate and amortization rate.

    Uses the exact closed-form formula for annuity loans where:
    M = P * (rate_pa + amort_pa) / 12

    Args:
        rate_pa: Annual interest rate (e.g., 0.034 for 3.4%)
        amort_pa: Annual amortization rate (e.g., 0.02 for 2%)

    Returns:
        Number of months to fully amortize the loan

    Raises:
        ValueError: If parameters are invalid
    """
    if amort_pa <= 0:
        raise ValueError("amortization_pa must be > 0")
    if rate_pa + amort_pa >= 1:
        raise ValueError("rate_pa + amort_pa must be < 1")

    if rate_pa == 0.0:
        # Linear amortization: M = P / n, so n = 12 / amort_pa
        return math.ceil(12 / amort_pa)

    # Annuity formula: solve for n where balance → 0
    r = rate_pa / 12.0
    num = math.log(amort_pa / (rate_pa + amort_pa))
    den = math.log(1 + r)
    n = -num / den
    return int(math.ceil(n))
