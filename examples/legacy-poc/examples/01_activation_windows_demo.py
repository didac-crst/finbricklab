#!/usr/bin/env python3
"""
FinScenLab Activation Windows Demo

This script demonstrates the new activation window feature that allows
bricks to have defined start and end periods.
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

# Test Case 1: Basic activation window with end_date
print("\n🧪 Test Case 1: Basic activation window with end_date")
print("=" * 60)

cash = ABrick(
    id="cash:EUR", 
    name="Main Cash", 
    kind=K.A_CASH,
    spec={"initial_balance": 0.0, "overdraft_limit": 0.0, "min_buffer": 0.0}
)

# Income that only runs for 12 months
salary = FBrick(
    id="salary", 
    name="Temporary Salary", 
    kind=K.F_INCOME,
    start_date=date(2026, 3, 1),  # Start in March 2026
    end_date=date(2027, 2, 1),    # End in February 2027 (12 months)
    spec={"amount_monthly": 5000}
)

scen1 = Scenario(
    id="scen1", 
    name="Temporary Salary Test",
    bricks=[cash, salary]
)

try:
    res1 = scen1.run(start=date(2026, 1, 1), months=24)
    validate_run(res1, scen1.bricks, mode="raise")
    print("✅ SUCCESS: Activation window with end_date works!")
    
    # Show cash flow pattern
    print(f"\n📊 Cash flow pattern:")
    for i in range(0, 24, 3):  # Every 3 months
        month = i
        cash_flow = res1['totals']['cash_in'].iloc[i]
        print(f"  Month {month}: €{cash_flow:,.2f}")
    
    # Show events
    salary_out = res1['outputs']['salary']
    print(f"\n📝 Events:")
    for event in salary_out['events']:
        print(f"  {event.t}: {event.message}")
        
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 2: Activation window with duration_m
print("\n🧪 Test Case 2: Activation window with duration_m")
print("=" * 60)

# ETF that runs for 18 months
etf = ABrick(
    id="etf", 
    name="Temporary ETF", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 6, 1),  # Start in June 2026
    duration_m=18,                # Run for 18 months
    spec={
        "price0": 100,
        "drift_pa": 0.05,
        "initial_units": 0,
        "buy_at_start": {"amount": 2000},
        "dca": {
            "mode": "amount",
            "amount": 500,
            "start_offset_m": 1,
            "months": 17  # DCA for 17 months (after initial buy)
        }
    }
)

scen2 = Scenario(
    id="scen2", 
    name="Temporary ETF Test",
    bricks=[cash, etf]
)

try:
    res2 = scen2.run(start=date(2026, 1, 1), months=36)
    validate_run(res2, scen2.bricks, mode="raise")
    print("✅ SUCCESS: Activation window with duration_m works!")
    
    # Show ETF value pattern
    print(f"\n📊 ETF value pattern:")
    etf_out = res2['outputs']['etf']
    for i in range(5, 25, 3):  # Every 3 months starting from month 5
        month = i
        etf_value = etf_out['asset_value'][i]
        print(f"  Month {month}: €{etf_value:,.2f}")
    
    # Show events
    print(f"\n📝 Events:")
    for event in etf_out['events']:
        print(f"  {event.t}: {event.message}")
        
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 3: Overlapping activation windows
print("\n🧪 Test Case 3: Overlapping activation windows")
print("=" * 60)

# Multiple income streams with different windows
salary1 = FBrick(
    id="salary1", 
    name="Job 1", 
    kind=K.F_INCOME,
    start_date=date(2026, 1, 1),
    end_date=date(2026, 12, 1),  # 12 months
    spec={"amount_monthly": 3000}
)

salary2 = FBrick(
    id="salary2", 
    name="Job 2", 
    kind=K.F_INCOME,
    start_date=date(2026, 7, 1),  # Overlaps with Job 1
    duration_m=18,                # 18 months
    spec={"amount_monthly": 4000}
)

scen3 = Scenario(
    id="scen3", 
    name="Overlapping Income Test",
    bricks=[cash, salary1, salary2]
)

try:
    res3 = scen3.run(start=date(2026, 1, 1), months=24)
    validate_run(res3, scen3.bricks, mode="raise")
    print("✅ SUCCESS: Overlapping activation windows work!")
    
    # Show combined income pattern
    print(f"\n📊 Combined income pattern:")
    for i in range(0, 24, 2):  # Every 2 months
        month = i
        total_income = res3['totals']['cash_in'].iloc[i]
        job1_income = res3['outputs']['salary1']['cash_in'][i]
        job2_income = res3['outputs']['salary2']['cash_in'][i]
        print(f"  Month {month}: Total €{total_income:,.2f} (Job1: €{job1_income:,.2f}, Job2: €{job2_income:,.2f})")
        
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

print("\n✅ Activation windows demo completed!")
print("\nThis demonstrates:")
print("- Bricks can have defined start and end periods")
print("- end_date and duration_m provide flexible window specification")
print("- Inactive periods show zero values in all outputs")
print("- Window end events are automatically generated")
print("- Multiple bricks can have overlapping activation windows")
print("- Backward compatibility: bricks without windows run for full simulation period")
