"""
Tests for currency quantization and rounding.
"""

from decimal import Decimal

from finbricklab.core.currency import (
    Amount,
    Currency,
    RoundingPolicy,
    create_amount,
    get_currency,
)


class TestCurrencyQuantization:
    """Test currency quantization with different rounding policies."""

    def test_jpy_quantization_to_integers(self):
        """JPY has 0 decimal places - should round to integers."""
        jpy = Currency("JPY", decimals=0, rounding=RoundingPolicy.BANKERS)

        # Test various values
        assert jpy.quantize(Decimal("123.5")) == Decimal("124")  # Round to even
        assert jpy.quantize(Decimal("123.4")) == Decimal("123")
        assert jpy.quantize(Decimal("125.5")) == Decimal("126")
        assert jpy.quantize(Decimal("124.5")) == Decimal(
            "124"
        )  # Banker's rounding to even

    def test_eur_quantization_to_two_decimals(self):
        """EUR has 2 decimal places."""
        eur = Currency("EUR", decimals=2, rounding=RoundingPolicy.BANKERS)

        assert eur.quantize(Decimal("1.235")) == Decimal("1.24")  # Banker's rounding
        assert eur.quantize(Decimal("1.234")) == Decimal("1.23")
        assert eur.quantize(Decimal("1.225")) == Decimal("1.22")  # Round to even

    def test_eur_half_up_rounding(self):
        """Test HALF_UP rounding policy."""
        eur_half_up = Currency("EUR", decimals=2, rounding=RoundingPolicy.HALF_UP)

        assert eur_half_up.quantize(Decimal("1.235")) == Decimal("1.24")
        assert eur_half_up.quantize(Decimal("1.225")) == Decimal(
            "1.23"
        )  # Always rounds up
        assert eur_half_up.quantize(Decimal("1.234")) == Decimal("1.23")

    def test_negative_rounding(self):
        """Test rounding of negative values."""
        eur = Currency("EUR", decimals=2, rounding=RoundingPolicy.BANKERS)

        assert eur.quantize(Decimal("-1.235")) == Decimal("-1.24")
        assert eur.quantize(Decimal("-1.234")) == Decimal("-1.23")

    def test_string_currency_lookup(self):
        """Test that string currency codes resolve via get_currency."""
        # JPY should have 0 decimals
        amount = Amount("123.5", "JPY")
        assert amount.currency.decimals == 0
        assert amount.value == Decimal("124")  # Rounded to integer

        # EUR should have 2 decimals
        amount_eur = Amount("1.239", "EUR")
        assert amount_eur.currency.decimals == 2
        assert amount_eur.value == Decimal("1.24")  # Banker's rounding

    def test_get_currency_registry(self):
        """Test get_currency function."""
        # Known currencies should have correct decimals
        assert get_currency("JPY").decimals == 0
        assert get_currency("EUR").decimals == 2
        assert get_currency("USD").decimals == 2
        assert get_currency("GBP").decimals == 2

        # Unknown currency should default to 2 decimals
        unknown = get_currency("XYZ")
        assert unknown.decimals == 2

    def test_create_amount_convenience(self):
        """Test create_amount convenience function."""
        amount = create_amount("100.50", "USD")
        assert isinstance(amount, Amount)
        assert amount.currency.code == "USD"
        assert amount.value == Decimal("100.50")

    def test_amount_quantization_applied(self):
        """Test that Amount construction applies quantization."""
        # Create amount that needs rounding
        amount = Amount("123.456", "EUR")
        assert amount.value == Decimal("123.46")  # Quantized to 2 decimals

        amount_jpy = Amount("123.6", "JPY")
        assert amount_jpy.value == Decimal("124")  # Quantized to 0 decimals

    def test_currency_repr(self):
        """Test currency representation."""
        eur = Currency("EUR", decimals=2)
        assert repr(eur) == "Currency('EUR', decimals=2)"

    def test_amount_repr(self):
        """Test amount representation."""
        amount = create_amount("100.50", "EUR")
        assert "100.50" in repr(amount)
        assert "EUR" in repr(amount)
