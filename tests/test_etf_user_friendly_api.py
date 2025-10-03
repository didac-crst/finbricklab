"""
Tests for the user-friendly ETF API improvements.
"""

from datetime import date

import pytest
import numpy as np

import finbricklab.strategies  # Ensure strategies are registered

from finbricklab.core.entity import Entity
from finbricklab.core.kinds import K


def test_initial_amount_conversion():
    """Test that initial_amount is converted to initial_units correctly."""
    entity = Entity(id="test", name="Test Entity")
    
    # Create cash account
    entity.new_ABrick(id="cash", name="Cash", kind=K.A_CASH, 
                      spec={"initial_balance": 10000.0})
    
    # Create ETF with initial_amount (should be converted to units)
    entity.new_ABrick(id="etf", name="ETF", kind=K.A_ETF_UNITIZED,
                      spec={
                            "initial_amount": 1000.0,  # €1000
                            "price0": 100.0,  # €100 per unit
                            "volatility_pa": 0.0,  # No volatility for testing
                            "drift_pa": 0.0,  # No drift for testing
                            "sell": []
                        })
    
    # Create scenario
    entity.create_scenario(
        id="test_scenario", name="Test Scenario",
        brick_ids=["cash", "etf"],
        settlement_default_cash_id="cash"
    )
    
    # Run scenario
    results = entity.run_scenario("test_scenario", start=date(2026, 1, 1), months=1)
    
    # Check that ETF has 10 units (€1000 / €100 = 10 units)
    etf_output = results["outputs"]["etf"]
    assert etf_output["asset_value"][0] == 1000.0  # 10 units * €100 = €1000


def test_user_friendly_sell_date():
    """Test that Python date objects work in sell directives."""
    entity = Entity(id="test", name="Test Entity")
    
    # Create cash account
    entity.new_ABrick(id="cash", name="Cash", kind=K.A_CASH, 
                      spec={"initial_balance": 10000.0})
    
    # Create ETF with user-friendly sell date
    entity.new_ABrick(id="etf", name="ETF", kind=K.A_ETF_UNITIZED,
                      spec={
                            "initial_amount": 1000.0,
                            "price0": 100.0,
                            "volatility_pa": 0.0,
                            "drift_pa": 0.0,
                            "sell": [
                                {
                                    "date": date(2026, 2, 1),  # User-friendly date
                                    "amount": 500.0  # Sell €500 worth
                                }
                            ]
                        })
    
    # Create scenario
    entity.create_scenario(
        id="test_scenario", name="Test Scenario",
        brick_ids=["cash", "etf"],
        settlement_default_cash_id="cash"
    )
    
    # Run scenario for 3 months
    results = entity.run_scenario("test_scenario", start=date(2026, 1, 1), months=3)
    
    # Check that ETF was sold in February
    etf_output = results["outputs"]["etf"]
    # Should have cash inflow in February from the sale
    assert etf_output["cash_in"][1] > 0  # February (index 1)
    assert etf_output["cash_in"][0] == 0  # January (index 0)


def test_user_friendly_sell_percentage():
    """Test that percentage-based selling works."""
    entity = Entity(id="test", name="Test Entity")
    
    # Create cash account
    entity.new_ABrick(id="cash", name="Cash", kind=K.A_CASH, 
                      spec={"initial_balance": 10000.0})
    
    # Create ETF with percentage-based sell
    entity.new_ABrick(id="etf", name="ETF", kind=K.A_ETF_UNITIZED,
                      spec={
                            "initial_amount": 1000.0,
                            "price0": 100.0,
                            "volatility_pa": 0.0,
                            "drift_pa": 0.0,
                            "sell": [
                                {
                                    "date": date(2026, 2, 1),
                                    "percentage": 0.5  # Sell 50% of holdings
                                }
                            ]
                        })
    
    # Create scenario
    entity.create_scenario(
        id="test_scenario", name="Test Scenario",
        brick_ids=["cash", "etf"],
        settlement_default_cash_id="cash"
    )
    
    # Run scenario for 3 months
    results = entity.run_scenario("test_scenario", start=date(2026, 1, 1), months=3)
    
    # Check that 50% was sold (5 units out of 10, worth €500)
    etf_output = results["outputs"]["etf"]
    assert etf_output["cash_in"][1] == 500.0  # February sale proceeds
    assert etf_output["asset_value"][1] == 500.0  # Remaining value


def test_backward_compatibility():
    """Test that legacy parameters still work."""
    entity = Entity(id="test", name="Test Entity")
    
    # Create cash account
    entity.new_ABrick(id="cash", name="Cash", kind=K.A_CASH, 
                      spec={"initial_balance": 10000.0})
    
    # Create ETF with legacy parameters
    entity.new_ABrick(id="etf", name="ETF", kind=K.A_ETF_UNITIZED,
                      spec={
                                "initial_units": 10.0,  # Legacy parameter
                                "price0": 100.0,
                                "volatility_pa": 0.0,
                                "drift_pa": 0.0,
                            "sell": [
                                {
                                    "t": np.datetime64("2026-02"),  # Legacy date format
                                    "units": 5.0  # Legacy units parameter
                                }
                            ]
                        })
    
    # Create scenario
    entity.create_scenario(
        id="test_scenario", name="Test Scenario",
        brick_ids=["cash", "etf"],
        settlement_default_cash_id="cash"
    )
    
    # Run scenario for 3 months
    results = entity.run_scenario("test_scenario", start=date(2026, 1, 1), months=3)
    
    # Check that legacy format still works
    etf_output = results["outputs"]["etf"]
    assert etf_output["asset_value"][0] == 1000.0  # Initial value
    assert etf_output["cash_in"][1] == 500.0  # February sale proceeds


def test_combined_user_friendly_features():
    """Test combining multiple user-friendly features."""
    entity = Entity(id="test", name="Test Entity")
    
    # Create cash account
    entity.new_ABrick(id="cash", name="Cash", kind=K.A_CASH, 
                      spec={"initial_balance": 10000.0})
    
    # Create ETF with multiple user-friendly features
    entity.new_ABrick(id="etf", name="ETF", kind=K.A_ETF_UNITIZED,
                      spec={
                                "initial_amount": 2000.0,  # User-friendly initial investment
                                "price0": 100.0,
                                "volatility_pa": 0.0,
                                "drift_pa": 0.0,
                            "sell": [
                                {
                                    "date": date(2026, 3, 1),
                                    "percentage": 0.25  # Sell 25% of holdings
                                },
                                {
                                    "date": date(2026, 4, 1),
                                    "amount": 500.0  # Sell €500 worth
                                }
                            ]
                        })
    
    # Create scenario
    entity.create_scenario(
        id="test_scenario", name="Test Scenario",
        brick_ids=["cash", "etf"],
        settlement_default_cash_id="cash"
    )
    
    # Run scenario for 5 months
    results = entity.run_scenario("test_scenario", start=date(2026, 1, 1), months=5)
    
    # Check that both sales happened
    etf_output = results["outputs"]["etf"]
    
    # March: 25% of €2000 = €500
    assert etf_output["cash_in"][2] == 500.0  # March sale
    assert etf_output["asset_value"][2] == 1500.0  # Remaining after 25% sale
    
    # April: €500 sale
    assert etf_output["cash_in"][3] == 500.0  # April sale
    assert etf_output["asset_value"][3] == 1000.0  # Remaining after €500 sale
