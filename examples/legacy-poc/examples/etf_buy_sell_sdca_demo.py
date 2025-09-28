#!/usr/bin/env python3
"""
FinScenLab ETF Buy/Sell/SDCA Demo

This script demonstrates the enhanced ETF strategy with:
- One-shot buys and sells
- Dollar-cost averaging (DCA) in and out
- Systematic DCA-out (SDCA) for regular withdrawals
- Dividend reinvestment
- Complete buy/sell lifecycle management
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

# Test Case 1: One-shot buy and sell
print("\n🧪 Test Case 1: One-shot buy and sell")
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
    spec={"amount": 50000}
)

# ETF with one-shot buy and sell
etf1 = ABrick(
    id="etf1", 
    name="Buy & Sell ETF", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 3, 1),
    spec={
        "price0": 100,
        "drift_pa": 0.05,  # 5% annual growth
        "div_yield_pa": 0.015,  # 1.5% dividend yield
        "initial_units": 0,
        "buy_at_start": {"amount": 20000},  # Buy €20k at start
        "sell": [
            {"t": "2028-06", "amount": 10000}  # Sell €10k worth in June 2028
        ],
        "reinvest_dividends": True,
        "events_level": "major"
    }
)

scen1 = Scenario(
    id="scen1", 
    name="Buy & Sell Test",
    bricks=[cash, seed, etf1]
)

try:
    res1 = scen1.run(start=date(2026, 1, 1), months=36)
    validate_run(res1, scen1.bricks, mode="raise")
    print("✅ SUCCESS: Buy & sell scenario passed!")
    
    # Show ETF progression
    print(f"\n📊 ETF progression:")
    etf1_out = res1['outputs']['etf1']
    for i in range(2, 36, 6):  # Every 6 months
        month = i
        etf_value = etf1_out['asset_value'][i]
        units = etf_value / (100 * (1.05 ** (i/12)))  # Approximate units
        print(f"  Month {month}: €{etf_value:,.2f} (~{units:.1f} units)")
    
    # Show sell event
    print(f"\n📝 Sell event:")
    for event in etf1_out['events']:
        if "sell" in event.message.lower():
            print(f"  {event.t}: {event.message}")
            
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 2: DCA in + SDCA out
print("\n🧪 Test Case 2: DCA in + SDCA out")
print("=" * 60)

# ETF with DCA in and SDCA out
etf2 = ABrick(
    id="etf2", 
    name="DCA In/Out ETF", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 3, 1),
    spec={
        "price0": 100,
        "drift_pa": 0.05,
        "div_yield_pa": 0.015,
        "initial_units": 0,
        "buy_at_start": {"amount": 10000},  # Initial €10k
        "dca": {
            "mode": "amount",
            "amount": 1000,  # €1k/month DCA in
            "start_offset_m": 1,
            "months": 24  # 24 months of DCA
        },
        "sdca": {
            "mode": "amount",
            "amount": 500,  # €500/month SDCA out
            "start_offset_m": 18,  # Start after 18 months
            "months": 12  # 12 months of SDCA
        },
        "reinvest_dividends": True,
        "events_level": "all"
    }
)

scen2 = Scenario(
    id="scen2", 
    name="DCA In/Out Test",
    bricks=[cash, seed, etf2]
)

try:
    res2 = scen2.run(start=date(2026, 1, 1), months=36)
    validate_run(res2, scen2.bricks, mode="raise")
    print("✅ SUCCESS: DCA in/out scenario passed!")
    
    # Show DCA and SDCA progression
    print(f"\n📊 DCA/SDCA progression:")
    etf2_out = res2['outputs']['etf2']
    for i in range(2, 36, 3):  # Every 3 months
        month = i
        etf_value = etf2_out['asset_value'][i]
        cash_out = etf2_out['cash_out'][i]
        cash_in = etf2_out['cash_in'][i]
        net_cash_flow = cash_in - cash_out
        print(f"  Month {month}: ETF €{etf_value:,.2f}, Net CF €{net_cash_flow:,.2f}")
    
    # Show DCA and SDCA events
    print(f"\n📝 DCA/SDCA events (sample):")
    dca_events = [e for e in etf2_out['events'] if 'dca' in e.message.lower()]
    sdca_events = [e for e in etf2_out['events'] if 'sdca' in e.message.lower()]
    print(f"  DCA events: {len(dca_events)}")
    print(f"  SDCA events: {len(sdca_events)}")
    if sdca_events:
        print(f"  First SDCA: {sdca_events[0].message}")
    
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 3: Units-based trading
print("\n🧪 Test Case 3: Units-based trading")
print("=" * 60)

# ETF with units-based DCA and sells
etf3 = ABrick(
    id="etf3", 
    name="Units-Based ETF", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 3, 1),
    spec={
        "price0": 100,
        "drift_pa": 0.05,
        "div_yield_pa": 0.015,
        "initial_units": 0,
        "buy_at_start": {"units": 100},  # Buy 100 units at start
        "dca": {
            "mode": "units",
            "units": 10,  # Buy 10 units/month
            "start_offset_m": 1,
            "months": 12  # 12 months
        },
        "sell": [
            {"t": "2027-06", "units": 50}  # Sell 50 units in June 2027
        ],
        "reinvest_dividends": False,  # Take dividends as cash
        "events_level": "major"
    }
)

scen3 = Scenario(
    id="scen3", 
    name="Units-Based Test",
    bricks=[cash, seed, etf3]
)

try:
    res3 = scen3.run(start=date(2026, 1, 1), months=24)
    validate_run(res3, scen3.bricks, mode="raise")
    print("✅ SUCCESS: Units-based trading scenario passed!")
    
    # Show units progression
    print(f"\n📊 Units progression:")
    etf3_out = res3['outputs']['etf3']
    for i in range(2, 24, 3):  # Every 3 months
        month = i
        etf_value = etf3_out['asset_value'][i]
        # Calculate approximate units from value and price
        price = 100 * (1.05 ** (i/12))
        units = etf_value / price
        print(f"  Month {month}: €{etf_value:,.2f} (~{units:.1f} units @ €{price:.2f})")
    
    # Show trading events
    print(f"\n📝 Trading events:")
    for event in etf3_out['events']:
        if any(keyword in event.message.lower() for keyword in ['buy', 'sell', 'dca']):
            print(f"  {event.t}: {event.message}")
            
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 4: Complete lifecycle (accumulation + decumulation)
print("\n🧪 Test Case 4: Complete lifecycle")
print("=" * 60)

# ETF with complete lifecycle: accumulate then decumulate
etf4 = ABrick(
    id="etf4", 
    name="Lifecycle ETF", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 3, 1),
    end_date=date(2036, 2, 1),  # 10-year window
    spec={
        "price0": 100,
        "drift_pa": 0.06,  # 6% annual growth
        "div_yield_pa": 0.02,  # 2% dividend yield
        "initial_units": 0,
        "buy_at_start": {"amount": 5000},
        "dca": {
            "mode": "amount",
            "amount": 2000,  # €2k/month accumulation
            "start_offset_m": 1,
            "months": 60,  # 5 years of accumulation
            "annual_step_pct": 0.03  # +3% per year
        },
        "sdca": {
            "mode": "amount",
            "amount": 3000,  # €3k/month decumulation
            "start_offset_m": 60,  # Start after 5 years
            "months": 60  # 5 years of decumulation
        },
        "reinvest_dividends": True,
        "events_level": "major"
    }
)

scen4 = Scenario(
    id="scen4", 
    name="Lifecycle Test",
    bricks=[cash, seed, etf4]
)

try:
    res4 = scen4.run(start=date(2026, 1, 1), months=120)
    validate_run(res4, scen4.bricks, mode="raise")
    print("✅ SUCCESS: Complete lifecycle scenario passed!")
    
    # Show lifecycle progression
    print(f"\n📊 Lifecycle progression:")
    etf4_out = res4['outputs']['etf4']
    for i in range(0, 120, 12):  # Every year
        year = i // 12 + 1
        etf_value = etf4_out['asset_value'][i]
        cash_out = etf4_out['cash_out'][i]
        cash_in = etf4_out['cash_in'][i]
        net_cf = cash_in - cash_out
        phase = "Accumulation" if i < 60 else "Decumulation"
        print(f"  Year {year} ({phase}): ETF €{etf_value:,.2f}, Net CF €{net_cf:,.2f}")
    
    # Show window end event
    print(f"\n📝 Window end event:")
    for event in etf4_out['events']:
        if "window_end" in event.message.lower():
            print(f"  {event.t}: {event.message}")
            
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

print("\n✅ ETF buy/sell/SDCA demo completed!")
print("\nThis demonstrates:")
print("- One-shot buys and sells by amount and units")
print("- Dollar-cost averaging (DCA) with annual step-up")
print("- Systematic DCA-out (SDCA) for regular withdrawals")
print("- Units-based trading for precise control")
print("- Complete lifecycle management (accumulate + decumulate)")
print("- Dividend reinvestment vs cash distribution")
print("- Activation windows with automatic termination")
print("- Proper cash flow impacts and liquidity validation")
