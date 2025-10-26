"""
Currency and precision handling for FinBrickLab.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from enum import Enum


class RoundingPolicy(Enum):
    """Rounding policies for currency calculations."""

    BANKERS = ROUND_HALF_EVEN
    HALF_UP = ROUND_HALF_UP


class Currency:
    """
    Currency definition with precision and rounding rules.

    Attributes:
        code: ISO currency code (e.g., 'EUR', 'USD', 'JPY')
        decimals: Number of decimal places for this currency
        rounding: Rounding policy for calculations
    """

    def __init__(
        self,
        code: str,
        decimals: int = 2,
        rounding: RoundingPolicy = RoundingPolicy.BANKERS,
    ):
        self.code = code.upper()
        self.decimals = decimals
        self.rounding = rounding

    def quantize(self, amount: Decimal) -> Decimal:
        """Quantize amount to currency precision."""
        quantum = Decimal("1").scaleb(-self.decimals)  # e.g., 0.01 for 2 dp, 1 for 0 dp
        return amount.quantize(quantum, rounding=self.rounding.value)

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return f"Currency('{self.code}', decimals={self.decimals})"


class Amount:
    """
    Monetary amount with currency and precision.

    Attributes:
        value: Decimal amount value
        currency: Currency object
    """

    def __init__(self, value: Decimal | float | str | int, currency: Currency | str):
        # Forward reference: get_currency is defined later in this file
        if isinstance(currency, str):
            currency = Amount._get_currency(currency)

        if isinstance(value, (int, float, str)):
            value = Decimal(str(value))

        self.value = currency.quantize(value)
        self.currency = currency

    @staticmethod
    def _get_currency(code: str) -> Currency:
        """Get currency by code (forward reference helper)."""
        if code not in CURRENCIES:
            # Default to 2 decimal places for unknown currencies
            return Currency(code, decimals=2)
        return CURRENCIES[code]

    def __add__(self, other: Amount) -> Amount:
        if self.currency.code != other.currency.code:
            raise ValueError(
                f"Cannot add amounts in different currencies: {self.currency.code} + {other.currency.code}"
            )
        return Amount(self.value + other.value, self.currency)

    def __sub__(self, other: Amount) -> Amount:
        if self.currency.code != other.currency.code:
            raise ValueError(
                f"Cannot subtract amounts in different currencies: {self.currency.code} - {other.currency.code}"
            )
        return Amount(self.value - other.value, self.currency)

    def __neg__(self) -> Amount:
        return Amount(-self.value, self.currency)

    def __pos__(self) -> Amount:
        return Amount(+self.value, self.currency)

    def __abs__(self) -> Amount:
        return Amount(abs(self.value), self.currency)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Amount):
            return False
        return self.value == other.value and self.currency.code == other.currency.code

    def __lt__(self, other: Amount) -> bool:
        if self.currency.code != other.currency.code:
            raise ValueError(
                f"Cannot compare amounts in different currencies: {self.currency.code} < {other.currency.code}"
            )
        return self.value < other.value

    def __le__(self, other: Amount) -> bool:
        return self == other or self < other

    def __gt__(self, other: Amount) -> bool:
        return not self <= other

    def __ge__(self, other: Amount) -> bool:
        return not self < other

    def __str__(self) -> str:
        return f"{self.value} {self.currency.code}"

    def __repr__(self) -> str:
        return f"Amount({self.value}, {self.currency})"


# Standard currency definitions
EUR = Currency("EUR", decimals=2)
USD = Currency("USD", decimals=2)
JPY = Currency("JPY", decimals=0)
GBP = Currency("GBP", decimals=2)

# Currency registry
CURRENCIES: dict[str, Currency] = {
    "EUR": EUR,
    "USD": USD,
    "JPY": JPY,
    "GBP": GBP,
}


def get_currency(code: str) -> Currency:
    """Get currency by code."""
    if code not in CURRENCIES:
        # Default to 2 decimal places for unknown currencies
        return Currency(code, decimals=2)
    return CURRENCIES[code]


def create_amount(value: Decimal | float | str, currency_code: str) -> Amount:
    """Create an Amount with the specified currency."""
    currency = get_currency(currency_code)
    return Amount(value, currency)
