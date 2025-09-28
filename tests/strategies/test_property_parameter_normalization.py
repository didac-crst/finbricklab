"""
Tests for property parameter normalization (initial_value vs price).
"""

import pytest
import warnings
import numpy as np
from datetime import date
from finbricklab.core.scenario import Scenario
from finbricklab.core.bricks import ABrick, LBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.strategies.valuation.property_discrete import ValuationPropertyDiscrete
from finbricklab.core.kinds import K


class TestPropertyParameterNormalization:
    """Test property parameter normalization between initial_value and price."""
    
    def test_initial_value_parameter_works(self):
        """Test that initial_value parameter works correctly."""
        house = ABrick(
            id="house",
            name="Test House",
            kind=K.A_PROPERTY_DISCRETE,
            spec={
                "initial_value": 400000.0,
                "fees_pct": 0.05,
                "appreciation_pa": 0.03
            }
        )
        
        t_index = np.arange('2026-01', '2027-01', dtype='datetime64[M]')
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})
        
        strategy = ValuationPropertyDiscrete()
        strategy.prepare(house, ctx)
        result = strategy.simulate(house, ctx)
        
        # Should work without warnings
        assert result["asset_value"][0] == 400000.0
        assert result["cash_out"][0] > 0  # Should have purchase cost
    
    def test_price_parameter_works_with_deprecation_warning(self):
        """Test that price parameter works but shows deprecation warning."""
        house = ABrick(
            id="house",
            name="Test House",
            kind=K.A_PROPERTY_DISCRETE,
            spec={
                "price": 400000.0,
                "fees_pct": 0.05,
                "appreciation_pa": 0.03
            }
        )
        
        t_index = np.arange('2026-01', '2027-01', dtype='datetime64[M]')
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})
        
        strategy = ValuationPropertyDiscrete()
        
        # Should show deprecation warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            strategy.prepare(house, ctx)
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "price" in str(w[0].message)
            assert "initial_value" in str(w[0].message)
        
        result = strategy.simulate(house, ctx)
        
        # Should work the same as initial_value
        assert result["asset_value"][0] == 400000.0
        assert result["cash_out"][0] > 0  # Should have purchase cost
    
    def test_both_parameters_produce_identical_results(self):
        """Test that both parameter names produce identical results."""
        # House with initial_value
        house_iv = ABrick(
            id="house_iv",
            name="House with initial_value",
            kind=K.A_PROPERTY_DISCRETE,
            spec={
                "initial_value": 300000.0,
                "fees_pct": 0.04,
                "appreciation_pa": 0.025
            }
        )
        
        # House with price (legacy)
        house_price = ABrick(
            id="house_price",
            name="House with price",
            kind=K.A_PROPERTY_DISCRETE,
            spec={
                "price": 300000.0,
                "fees_pct": 0.04,
                "appreciation_pa": 0.025
            }
        )
        
        t_index = np.arange('2026-01', '2027-01', dtype='datetime64[M]')
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})
        
        strategy = ValuationPropertyDiscrete()
        
        # Prepare both (suppress warnings for price)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            strategy.prepare(house_iv, ctx)
            strategy.prepare(house_price, ctx)
        
        result_iv = strategy.simulate(house_iv, ctx)
        result_price = strategy.simulate(house_price, ctx)
        
        # Results should be identical
        assert np.allclose(result_iv["asset_value"], result_price["asset_value"])
        assert np.allclose(result_iv["cash_out"], result_price["cash_out"])
        assert np.allclose(result_iv["cash_in"], result_price["cash_in"])
        assert len(result_iv["events"]) == len(result_price["events"])
    
    def test_missing_parameter_raises_error(self):
        """Test that missing both parameters raises an error."""
        house = ABrick(
            id="house",
            name="Test House",
            kind=K.A_PROPERTY_DISCRETE,
            spec={
                "fees_pct": 0.05,
                "appreciation_pa": 0.03
                # Missing both initial_value and price
            }
        )
        
        t_index = np.arange('2026-01', '2027-01', dtype='datetime64[M]')
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})
        
        strategy = ValuationPropertyDiscrete()
        
        with pytest.raises(AssertionError, match="Property needs 'initial_value'"):
            strategy.prepare(house, ctx)
    
    def test_initial_value_preferred_over_price(self):
        """Test that initial_value is preferred when both are present."""
        house = ABrick(
            id="house",
            name="Test House",
            kind=K.A_PROPERTY_DISCRETE,
            spec={
                "initial_value": 500000.0,
                "price": 400000.0,  # This should be ignored
                "fees_pct": 0.05,
                "appreciation_pa": 0.03
            }
        )
        
        t_index = np.arange('2026-01', '2027-01', dtype='datetime64[M]')
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})
        
        strategy = ValuationPropertyDiscrete()
        strategy.prepare(house, ctx)
        result = strategy.simulate(house, ctx)
        
        # Should use initial_value (500000), not price (400000)
        assert result["asset_value"][0] == 500000.0
        assert result["asset_value"][0] != 400000.0


class TestMortgageStartDateNormalization:
    """Test mortgage start_date normalization to activation window."""
    
    def test_mortgage_start_date_normalization(self):
        """Test that mortgage start_date is normalized to activation window."""
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 100000.0}
        )
        
        mortgage = LBrick(
            id="mortgage",
            name="Test Mortgage",
            kind=K.L_MORT_ANN,
            spec={
                "principal": 200000.0,
                "rate_pa": 0.04,
                "term_months": 240,
                "start_date": "2026-03-01"  # Should be normalized to activation window
            }
        )
        
        scenario = Scenario(
            id="start_date_test",
            name="Start Date Normalization Test",
            bricks=[cash, mortgage]
        )
        
        results = scenario.run(start=date(2026, 1, 1), months=6)
        
        # Mortgage should start in month 4 (March 1st falls in month 4 of the simulation)
        mortgage_output = results["outputs"]["mortgage"]
        cash_out = mortgage_output["cash_out"]
        
        # First three months should have no mortgage payments
        assert cash_out[0] == 0, "Month 1 (Jan) should have no mortgage payment"
        assert cash_out[1] == 0, "Month 2 (Feb) should have no mortgage payment"
        assert cash_out[2] == 0, "Month 3 (Mar) should have no mortgage payment"
        
        # Month 4 onwards should have mortgage payments (March 1st start)
        assert cash_out[3] > 0, "Month 4 (Apr) should have mortgage payment"
        assert cash_out[4] > 0, "Month 5 (May) should have mortgage payment"
    
    def test_mortgage_start_date_string_format(self):
        """Test that string start_date formats are handled correctly."""
        cash = ABrick(
            id="cash",
            name="Cash Account",
            kind=K.A_CASH,
            spec={"initial_balance": 50000.0}
        )
        
        mortgage = LBrick(
            id="mortgage",
            name="Test Mortgage",
            kind=K.L_MORT_ANN,
            spec={
                "principal": 150000.0,
                "rate_pa": 0.035,
                "term_months": 180,
                "start_date": "2026-06-15"  # Mid-month date
            }
        )
        
        scenario = Scenario(
            id="start_date_string_test",
            name="Start Date String Test",
            bricks=[cash, mortgage]
        )
        
        results = scenario.run(start=date(2026, 1, 1), months=12)
        
        # Mortgage should start in month 7 (June 15th falls in month 7)
        mortgage_output = results["outputs"]["mortgage"]
        cash_out = mortgage_output["cash_out"]
        
        # First 6 months should have no mortgage payments
        for i in range(6):
            assert cash_out[i] == 0, f"Month {i+1} should have no mortgage payment"
        
        # Month 7 onwards should have mortgage payments
        assert cash_out[6] > 0, "Month 7 should have mortgage payment"
