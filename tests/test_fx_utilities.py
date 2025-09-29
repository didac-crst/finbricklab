"""
Tests for FX (Foreign Exchange) utilities.
"""

import sys

import pandas as pd
import pytest

sys.path.insert(0, "src")

from finbricklab.fx import (  # noqa: E402
    FXConverter,
    create_fx_converter,
    validate_entity_currencies,
)


class TestFXUtilities:
    """Test FX conversion utilities."""

    def test_fx_converter_initialization(self):
        """Test FXConverter initialization."""
        converter = FXConverter("EUR")
        assert converter.base_currency == "EUR"
        assert converter.rates == {}

        # Test with rates
        rates = {("USD", "EUR"): 0.85, ("EUR", "USD"): 1.18}
        converter_with_rates = FXConverter("EUR", rates)
        assert converter_with_rates.base_currency == "EUR"
        assert converter_with_rates.rates == rates

    def test_get_rate_same_currency(self):
        """Test getting rate for same currency."""
        converter = FXConverter("EUR")
        assert converter.get_rate("EUR", "EUR") == 1.0
        assert converter.get_rate("USD", "USD") == 1.0

    def test_get_rate_direct(self):
        """Test getting direct exchange rate."""
        rates = {("USD", "EUR"): 0.85}
        converter = FXConverter("EUR", rates)

        assert converter.get_rate("USD", "EUR") == 0.85

    def test_get_rate_inverse(self):
        """Test getting inverse exchange rate."""
        rates = {("USD", "EUR"): 0.85}
        converter = FXConverter("EUR", rates)

        rate = converter.get_rate("EUR", "USD")
        assert rate is not None
        assert abs(rate - 1.176) < 0.01

    def test_get_rate_missing(self):
        """Test getting rate when not available."""
        converter = FXConverter("EUR")
        assert converter.get_rate("USD", "EUR") is None

    def test_add_rate(self):
        """Test adding exchange rate."""
        converter = FXConverter("EUR")
        converter.add_rate("USD", "EUR", 0.85)

        assert converter.get_rate("USD", "EUR") == 0.85

    def test_convert_frame_same_currency(self):
        """Test converting DataFrame with same currency."""
        converter = FXConverter("EUR")

        df = pd.DataFrame(
            {
                "cash": [1000, 2000],
                "date": ["2026-01-01", "2026-02-01"],
            }
        )

        result = converter.convert_frame(df, "EUR", "EUR")
        pd.testing.assert_frame_equal(result, df)

    def test_convert_frame_different_currency(self):
        """Test converting DataFrame with different currency."""
        rates = {("USD", "EUR"): 0.85}
        converter = FXConverter("EUR", rates)

        df = pd.DataFrame(
            {
                "cash": [1000, 2000],
                "date": ["2026-01-01", "2026-02-01"],
            }
        )

        result = converter.convert_frame(df, "USD", "EUR")

        expected = pd.DataFrame(
            {
                "cash": [850.0, 1700.0],  # 1000 * 0.85, 2000 * 0.85
                "date": ["2026-01-01", "2026-02-01"],
            }
        )

        pd.testing.assert_frame_equal(result, expected)

    def test_convert_frame_missing_rate(self):
        """Test converting DataFrame with missing rate."""
        converter = FXConverter("EUR")

        df = pd.DataFrame(
            {
                "cash": [1000, 2000],
                "date": ["2026-01-01", "2026-02-01"],
            }
        )

        with pytest.raises(ValueError, match="No exchange rate available"):
            converter.convert_frame(df, "USD", "EUR")

    def test_convert_frame_preserves_non_numeric(self):
        """Test that non-numeric columns are preserved."""
        rates = {("USD", "EUR"): 0.85}
        converter = FXConverter("EUR", rates)

        df = pd.DataFrame(
            {
                "cash": [1000, 2000],
                "date": ["2026-01-01", "2026-02-01"],
                "scenario_id": ["A", "B"],
            }
        )

        result = converter.convert_frame(df, "USD", "EUR")

        # Check that numeric columns were converted
        assert result["cash"].tolist() == [850, 1700]

        # Check that non-numeric columns were preserved
        pd.testing.assert_series_equal(result["date"], df["date"])
        pd.testing.assert_series_equal(result["scenario_id"], df["scenario_id"])

    def test_create_fx_converter(self):
        """Test create_fx_converter helper function."""
        converter = create_fx_converter("USD")
        assert converter.base_currency == "USD"
        assert converter.rates == {}

        # Test with rates
        rates = {("EUR", "USD"): 1.18}
        converter_with_rates = create_fx_converter("USD", rates)
        assert converter_with_rates.base_currency == "USD"
        assert converter_with_rates.rates == rates

    def test_validate_entity_currencies_same_currency(self):
        """Test currency validation with same currencies."""

        # Mock Entity and scenarios
        class MockEntity:
            def __init__(self):
                self.base_currency = "EUR"

        class MockScenario:
            def __init__(self, scenario_id):
                self.id = scenario_id

        entity = MockEntity()
        scenarios = [MockScenario("A"), MockScenario("B")]

        # Should not raise an error
        result = validate_entity_currencies(entity, scenarios)

        # Should return currency mapping
        assert result == {"A": "EUR", "B": "EUR"}

    def test_validate_entity_currencies_different_currencies(self):
        """Test currency validation with different currencies."""
        # This test would need to be updated when we implement actual currency
        # attributes on scenarios. For now, it tests the placeholder logic.

        class MockEntity:
            def __init__(self):
                self.base_currency = "EUR"

        class MockScenario:
            def __init__(self, scenario_id):
                self.id = scenario_id

        entity = MockEntity()
        scenarios = [MockScenario("A"), MockScenario("B")]

        # Current implementation assumes all scenarios use entity's base currency
        # So this should not raise an error
        result = validate_entity_currencies(entity, scenarios)
        assert result == {"A": "EUR", "B": "EUR"}

    def test_fx_converter_edge_cases(self):
        """Test edge cases for FX converter."""
        converter = FXConverter("EUR")

        # Test with empty DataFrame
        empty_df = pd.DataFrame()
        result = converter.convert_frame(empty_df, "EUR", "EUR")
        assert result.empty

        # Test with DataFrame containing only non-numeric columns
        text_df = pd.DataFrame(
            {
                "scenario_name": ["A", "B"],
                "description": ["Test", "Test2"],
            }
        )
        result = converter.convert_frame(text_df, "EUR", "EUR")
        pd.testing.assert_frame_equal(result, text_df)

    def test_rate_calculation_via_base_currency(self):
        """Test rate calculation via base currency."""
        # Set up rates: USD -> EUR and EUR -> GBP
        rates = {
            ("USD", "EUR"): 0.85,  # 1 USD = 0.85 EUR
            ("EUR", "GBP"): 0.86,  # 1 EUR = 0.86 GBP
        }
        converter = FXConverter("EUR", rates)

        # Calculate USD -> GBP via EUR
        # 1 USD = 0.85 EUR, 1 EUR = 0.86 GBP
        # So 1 USD = 0.85 * 0.86 = 0.731 GBP
        rate = converter.get_rate("USD", "GBP")
        assert rate is not None
        expected_rate = 0.85 * 0.86
        assert abs(rate - expected_rate) < 0.001
