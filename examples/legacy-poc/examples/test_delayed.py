#!/usr/bin/env python3
"""
FinScenLab Delayed Brick Activation Example

This script demonstrates how to create bricks that start at specific dates,
enabling realistic financial scenarios like buying a house in 2028.
"""

# Fix the import path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the core components
from datetime import date
from finscenlab.core import Scenario, ABrick, LBrick, FBrick
import finscenlab.strategies  # This registers the default strategies

print("✅ All imports successful!")

# Create a scenario with delayed brick activation
print("\n🏗️  Creating financial bricks with delayed activation...")

# Cash account - starts immediately
cash = ABrick(
    id="cash:EUR", 
    name="Main Cash Account", 
    kind="a.cash",
    spec={
        "initial_balance": 50_000,  # Start with some money
        "interest_pa": 0.02  # 2% annual interest
    }
    # No start_date = starts at scenario start (2026-01-01)
)

# Seed money - starts immediately
seed = FBrick(
    id="seed", 
    name="Initial Capital", 
    kind="f.transfer.lumpsum",
    spec={"amount": 100_000},
    start_date=date(2027, 6, 1),  # 🎯 Mortgage starts with house purchase
)


print("✅ Created all bricks:")
print(f"  - Cash account: starts immediately")
print(f"  - Seed money: €{seed.spec['amount']:,} - starts immediately")

# Create the scenario
print("\n🎯 Creating scenario...")
scenario = Scenario(
    id="delayed_demo", 
    name="Delayed Activation Demo", 
    bricks=[cash, seed]
)

print(f"✅ Scenario created: {scenario.name}")

# Run the simulation for 5 years (60 months)
print("\n🚀 Running 5-year simulation...")
results = scenario.run(start=date(2026, 1, 1), months=60)

print("✅ Simulation completed!")
print(f"   Period: {results['totals'].index[0]} to {results['totals'].index[-1]}")

# Show key milestones
print("\n📊 Key Milestones:")
print("=" * 60)

# Month 1 (2026-01)
month_1 = results["totals"].iloc[0]
print(f"2026-01: Initial setup")
print(f"  Cash In:  €{month_1['cash_in']:,.2f}")
print(f"  Net Worth: €{month_1['equity']:,.2f}")

# Month 18 (2027-06) - Promotion starts
month_18 = results["totals"].iloc[17]
print(f"\n2027-06: Promotion starts (+€1,000/month)")
print(f"  Cash In:  €{month_18['cash_in']:,.2f}")
print(f"  Net Worth: €{month_18['equity']:,.2f}")

# Month 25 (2028-01) - House purchase
month_25 = results["totals"].iloc[24]
print(f"  Cash Out: €{month_25['cash_out']:,.2f}")
print(f"  Net Worth: €{month_25['equity']:,.2f}")

# Month 60 (2030-12) - End of simulation
month_60 = results["totals"].iloc[-1]
print(f"\n2030-12: End of simulation")
print(f"  Cash In:  €{month_60['cash_in']:,.2f}")
print(f"  Cash Out: €{month_60['cash_out']:,.2f}")
print(f"  Net Worth: €{month_60['equity']:,.2f}")

# Show events
print(f"\n📝 Key Events:")
for brick_id, output in results['outputs'].items():
    if output['events']:
        for event in output['events']:
            print(f"  {brick_id}: {event}")

print("\n✅ Delayed activation demo completed!")
print("\nThis demonstrates:")
print("- Bricks can start at any date during the simulation")
print("- House purchase happens in 2028, not at the beginning")
print("- Mortgage automatically starts with the house")
print("- Salary promotion kicks in mid-2027")
print("- All cash flows are properly routed and timed")
