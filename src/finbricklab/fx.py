"""
Foreign Exchange (FX) conversion utilities for multi-currency scenarios.

This module provides a minimal interface for currency conversion to support
Entity-level comparisons across scenarios with different base currencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from finbricklab.core.entity import Entity


class FXConverter:
    """
    Minimal FX converter for currency normalization.

    This class provides a simple interface for converting financial data
    between currencies. For now, it's a placeholder that assumes 1:1 rates
    unless explicitly configured.

    Attributes:
        base_currency: Base currency for all conversions (e.g., "EUR", "USD")
        rates: Dictionary mapping (from_currency, to_currency) tuples to exchange rates
    """

    def __init__(
        self,
        base_currency: str,
        rates: dict[tuple[str, str], float] | None = None,
    ):
        """
        Initialize FX converter.

        Args:
            base_currency: Base currency for all conversions
            rates: Optional dictionary of exchange rates
                  Format: {(from_currency, to_currency): rate}
        """
        self.base_currency = base_currency
        self.rates = rates or {}

    def convert_frame(
        self,
        df: pd.DataFrame,
        from_currency: str,
        to_currency: str,
    ) -> pd.DataFrame:
        """
        Convert DataFrame values from one currency to another.

        Args:
            df: DataFrame with financial data
            from_currency: Source currency
            to_currency: Target currency

        Returns:
            DataFrame with converted values

        Raises:
            ValueError: If conversion rate is not available
        """
        if from_currency == to_currency:
            return df.copy()

        rate = self.get_rate(from_currency, to_currency)
        if rate is None:
            raise ValueError(
                f"No exchange rate available for {from_currency} -> {to_currency}. "
                f"Please provide rates or ensure all scenarios use {self.base_currency}."
            )

        # Convert numeric columns
        numeric_cols = df.select_dtypes(include=["number"]).columns
        converted_df = df.copy()

        for col in numeric_cols:
            if col != "date":  # Don't convert date columns
                converted_df[col] = df[col] * rate

        return converted_df

    def get_rate(self, from_currency: str, to_currency: str) -> float | None:
        """
        Get exchange rate between two currencies.

        Args:
            from_currency: Source currency
            to_currency: Target currency

        Returns:
            Exchange rate or None if not available
        """
        if from_currency == to_currency:
            return 1.0

        # Try direct rate
        direct_key = (from_currency, to_currency)
        if direct_key in self.rates:
            return self.rates[direct_key]

        # Try inverse rate
        inverse_key = (to_currency, from_currency)
        if inverse_key in self.rates:
            return 1.0 / self.rates[inverse_key]

        # Try via base currency
        if from_currency != self.base_currency and to_currency != self.base_currency:
            rate_from_base = self.get_rate(self.base_currency, to_currency)
            rate_to_base = self.get_rate(from_currency, self.base_currency)

            if rate_from_base is not None and rate_to_base is not None:
                return rate_to_base * rate_from_base

        return None

    def add_rate(self, from_currency: str, to_currency: str, rate: float) -> None:
        """
        Add an exchange rate.

        Args:
            from_currency: Source currency
            to_currency: Target currency
            rate: Exchange rate (1 unit of from_currency = rate units of to_currency)
        """
        self.rates[(from_currency, to_currency)] = rate

    def validate_currencies(
        self, scenarios: list, scenario_currencies: dict[str, str]
    ) -> None:
        """
        Validate that all scenario currencies can be converted to base currency.

        Args:
            scenarios: List of scenario objects
            scenario_currencies: Dictionary mapping scenario IDs to their currencies

        Raises:
            ValueError: If any scenario currency cannot be converted to base currency
        """
        missing_rates = []

        for scenario in scenarios:
            scenario_currency = scenario_currencies.get(scenario.id, self.base_currency)

            if scenario_currency != self.base_currency:
                rate = self.get_rate(scenario_currency, self.base_currency)
                if rate is None:
                    missing_rates.append((scenario.id, scenario_currency))

        if missing_rates:
            missing_list = ", ".join([f"{sid} ({curr})" for sid, curr in missing_rates])
            raise ValueError(
                f"Cannot convert scenarios to {self.base_currency}: {missing_list}. "
                f"Please provide exchange rates or ensure all scenarios use {self.base_currency}."
            )


def create_fx_converter(
    base_currency: str = "EUR",
    rates: dict[tuple[str, str], float] | None = None,
) -> FXConverter:
    """
    Create an FX converter with common rates.

    Args:
        base_currency: Base currency for conversions
        rates: Optional dictionary of exchange rates

    Returns:
        Configured FXConverter instance
    """
    return FXConverter(base_currency, rates)


def validate_entity_currencies(entity: Entity, scenarios: list) -> dict[str, str]:
    """
    Validate that all scenarios can be compared within an Entity.

    Args:
        entity: Entity object with base_currency
        scenarios: List of scenarios to validate

    Returns:
        Dictionary mapping scenario IDs to their currencies

    Raises:
        ValueError: If currencies are incompatible
    """
    # For now, assume all scenarios use the entity's base currency
    # In a real implementation, this would check each scenario's currency
    scenario_currencies = {}

    for scenario in scenarios:
        # This is a placeholder - in reality, scenarios would have a currency attribute
        scenario_currencies[scenario.id] = entity.base_currency

    # If we had an FX converter, we would validate here
    # For now, just ensure all scenarios use the same currency
    currencies = set(scenario_currencies.values())
    if len(currencies) > 1:
        raise ValueError(
            f"Multiple currencies found in Entity: {currencies}. "
            f"All scenarios must use the same currency ({entity.base_currency}) "
            f"or provide an FX converter."
        )

    return scenario_currencies
