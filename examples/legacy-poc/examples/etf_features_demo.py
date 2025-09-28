#!/usr/bin/env python3
"""
FinScenLab ETF Features Demo

This script demonstrates the enhanced ETF strategy with:
- One-shot buy at start
- Dollar-cost averaging (DCA) by amount and units
- Dividend reinvestment
- Cash flow impacts and liquidity validation
"""

# Fix the import path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the core components
from datetime import date
from finscenlab.core import Scenario, ABrick, FBrick, validate_run
from finscenlab.kinds import K
import finscenlab.strategies  # This registers the default strategies

print("✅ All imports successful!")

# Test Case 1: One-shot buy at start
print("\n🧪 Test Case 1: One-shot buy at start")
print("=" * 60)

cash = ABrick(
    id="cash:EUR", 
    name="Main Cash", 
    kind=K.A_CASH,
    spec={"initial_balance": 0.0, "overdraft_limit": 0.0, "min_buffer": 0.0}
)

seed = FBrick(
    id="seed", 
    name="Initial Capital", 
    kind=K.F_TRANSFER, 
    spec={"amount": 15000}
)

etf = ABrick(
    id="etf", 
    name="S&P 500 ETF", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 3, 1),
    spec={
        "price0": 100,
        "drift_pa": 0.05,  # 5% annual growth
        "div_yield_pa": 0.015,  # 1.5% dividend yield
        "initial_units": 0,
        "buy_at_start": {"amount": 10000},  # One-shot buy
        "events_level": "major"
    }
)

scen1 = Scenario(
    id="scen1", 
    name="ETF One-shot Buy",
    bricks=[cash, seed, etf]
)

try:
    res1 = scen1.run(start=date(2026, 1, 1), months=12)
    validate_run(res1, scen1.bricks, mode="raise")
    print("✅ SUCCESS: One-shot buy scenario passed!")
    
    # Show cash flow impact
    print(f"\n📊 Cash flow impact:")
    print(f"  Month 0 (seed): €{res1['totals']['cash'].iloc[0]:,.2f}")
    print(f"  Month 2 (after ETF buy): €{res1['totals']['cash'].iloc[2]:,.2f}")
    print(f"  Month 11: €{res1['totals']['cash'].iloc[11]:,.2f}")
    
    # Show ETF value progression
    etf_out = res1['outputs']['etf']
    print(f"\n📈 ETF value progression:")
    print(f"  Month 2: €{etf_out['asset_value'][2]:,.2f}")
    print(f"  Month 11: €{etf_out['asset_value'][11]:,.2f}")
    
    # Show events
    print(f"\n📝 Events:")
    for event in etf_out['events']:
        print(f"  {event.t}: {event.message}")
        
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 2: DCA by amount with annual step-up
print("\n🧪 Test Case 2: DCA by amount with annual step-up")
print("=" * 60)

# Update seed for DCA
seed.spec["amount"] = 25000  # More seed for DCA

etf2 = ABrick(
    id="etf2", 
    name="DCA ETF", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 3, 1),
    spec={
        "price0": 100,
        "drift_pa": 0.05,
        "div_yield_pa": 0.015,
        "initial_units": 0,
        "dca": {
            "mode": "amount",
            "amount": 500,  # €500/month
            "start_offset_m": 1,  # Start next month
            "months": 24,  # 24 months of DCA
            "annual_step_pct": 0.02  # +2% per year
        },
        "events_level": "all"  # Show all DCA events
    }
)

scen2 = Scenario(
    id="scen2", 
    name="ETF DCA by Amount",
    bricks=[cash, seed, etf2]
)

try:
    res2 = scen2.run(start=date(2026, 1, 1), months=36)
    validate_run(res2, scen2.bricks, mode="raise")
    print("✅ SUCCESS: DCA by amount scenario passed!")
    
    # Show DCA progression
    print(f"\n📊 DCA progression:")
    etf2_out = res2['outputs']['etf2']
    for i in range(2, min(8, len(res2['totals']))):
        month = i
        cash_bal = res2['totals']['cash'].iloc[i]
        etf_val = etf2_out['asset_value'][i]
        dca_out = etf2_out['cash_out'][i]
        print(f"  Month {month}: Cash €{cash_bal:,.2f}, ETF €{etf_val:,.2f}, DCA €{dca_out:,.2f}")
    
    # Show step-up effect (year 2)
    print(f"\n📈 Step-up effect (Year 2):")
    print(f"  Month 14 (Year 1): DCA €{etf2_out['cash_out'][14]:,.2f}")
    print(f"  Month 26 (Year 2): DCA €{etf2_out['cash_out'][26]:,.2f}")
    
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 3: DCA by units
print("\n🧪 Test Case 3: DCA by units")
print("=" * 60)

etf3 = ABrick(
    id="etf3", 
    name="Units DCA ETF", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 3, 1),
    spec={
        "price0": 100,
        "drift_pa": 0.05,
        "div_yield_pa": 0.015,
        "initial_units": 0,
        "dca": {
            "mode": "units",
            "units": 5.0,  # Buy 5 units per month
            "start_offset_m": 0,  # Start immediately
            "months": 12
        },
        "events_level": "major"
    }
)

scen3 = Scenario(
    id="scen3", 
    name="ETF DCA by Units",
    bricks=[cash, seed, etf3]
)

try:
    res3 = scen3.run(start=date(2026, 1, 1), months=24)
    validate_run(res3, scen3.bricks, mode="raise")
    print("✅ SUCCESS: DCA by units scenario passed!")
    
    # Show units progression
    print(f"\n📊 Units progression:")
    etf3_out = res3['outputs']['etf3']
    for i in range(2, min(8, len(res3['totals']))):
        month = i
        cash_bal = res3['totals']['cash'].iloc[i]
        # Calculate units from asset value / price
        units = etf3_out['asset_value'][i] / (100 * (1.05 ** (i/12)))
        dca_out = etf3_out['cash_out'][i]
        print(f"  Month {month}: Cash €{cash_bal:,.2f}, ~{units:.1f} units, DCA €{dca_out:,.2f}")
        
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 4: Dividend reinvestment
print("\n🧪 Test Case 4: Dividend reinvestment")
print("=" * 60)

etf4 = ABrick(
    id="etf4", 
    name="Dividend ETF", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 3, 1),
    spec={
        "price0": 100,
        "drift_pa": 0.05,
        "div_yield_pa": 0.03,  # 3% dividend yield
        "initial_units": 100,  # Start with some units
        "reinvest_dividends": True,  # Reinvest dividends
        "events_level": "major"
    }
)

scen4 = Scenario(
    id="scen4", 
    name="ETF Dividend Reinvestment",
    bricks=[cash, seed, etf4]
)

try:
    res4 = scen4.run(start=date(2026, 1, 1), months=12)
    validate_run(res4, scen4.bricks, mode="raise")
    print("✅ SUCCESS: Dividend reinvestment scenario passed!")
    
    # Show dividend impact
    print(f"\n📊 Dividend reinvestment impact:")
    etf4_out = res4['outputs']['etf4']
    print(f"  Month 2 (start): €{etf4_out['asset_value'][2]:,.2f}")
    print(f"  Month 11 (end): €{etf4_out['asset_value'][11]:,.2f}")
    
    # Show dividend events
    print(f"\n📝 Dividend events:")
    for event in etf4_out['events']:
        if "dividend" in event.message.lower():
            print(f"  {event.t}: {event.message}")
            
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 5: Liquidity constraint test
print("\n🧪 Test Case 5: Liquidity constraint test")
print("=" * 60)

# Use insufficient seed to trigger liquidity validation
seed.spec["amount"] = 5000  # Insufficient for large DCA

etf5 = ABrick(
    id="etf5", 
    name="Liquidity Test ETF", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 3, 1),
    spec={
        "price0": 100,
        "drift_pa": 0.05,
        "div_yield_pa": 0.015,
        "initial_units": 0,
        "buy_at_start": {"amount": 8000},  # Large initial buy
        "dca": {
            "mode": "amount",
            "amount": 1000,  # High DCA amount
            "start_offset_m": 1,
            "months": 12
        }
    }
)

scen5 = Scenario(
    id="scen5", 
    name="ETF Liquidity Test",
    bricks=[cash, seed, etf5]
)

try:
    res5 = scen5.run(start=date(2026, 1, 1), months=24)
    validate_run(res5, scen5.bricks, mode="raise")
    print("❌ UNEXPECTED: Should have failed due to insufficient liquidity!")
except AssertionError as e:
    print("✅ EXPECTED FAILURE: Liquidity constraint triggered!")
    print(f"   {str(e)}")

print("\n✅ ETF features demo completed!")
print("\nThis demonstrates:")
print("- One-shot buy at start with cash impact")
print("- DCA by amount with annual step-up")
print("- DCA by units (fixed units per month)")
print("- Dividend reinvestment vs cash distribution")
print("- Liquidity validation catches insufficient funds")
print("- Configurable event logging (none/major/all)")
print("- Proper integration with cash flow routing")
