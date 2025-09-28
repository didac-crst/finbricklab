#!/usr/bin/env python3
"""
FinScenLab Quickstart Example

This script demonstrates the basic usage of FinScenLab with a simple scenario.
"""

# Fix the import path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the core components
from datetime import date
from finscenlab.core import Scenario, ABrick, LBrick, FBrick, validate_run
from finscenlab.kinds import K
import finscenlab.strategies  # This registers the default strategies

print("✅ All imports successful!")

# Create a simple scenario with just cash and seed money
print("\n🏗️  Creating financial bricks...")

# Cash account - this will receive all routed cash flows
cash = ABrick(
    id="cash:EUR", 
    name="Main Cash Account", 
    kind=K.A_CASH,  # Using kind constants!
    spec={
        "initial_balance": 0.0, 
        "interest_pa": 0.02  # 2% annual interest
    }
)

# Seed money - initial capital injection
seed = FBrick(
    id="seed", 
    name="Owner Equity Seed", 
    kind=K.F_TRANSFER,  # Using kind constants!
    spec={"amount": 100_000}
)

print(f"✅ Created cash account: {cash.name}")
print(f"✅ Created seed money: €{seed.spec['amount']:,}")

# Create the scenario
print("\n🎯 Creating scenario...")
scenario = Scenario(
    id="simple_demo", 
    name="Simple Cash + Seed Demo", 
    bricks=[cash, seed]
)

print(f"✅ Scenario created: {scenario.name}")
print(f"   Bricks: {[b.name for b in scenario.bricks]}")

# Run the simulation for 12 months
print("\n🚀 Running simulation...")
results = scenario.run(start=date(2026, 1, 1), months=12)

print("✅ Simulation completed!")
print(f"   Period: {results['totals'].index[0]} to {results['totals'].index[-1]}")
print(f"   Months: {len(results['totals'])}")

# Validate the results
print("\n🔍 Validating results...")
try:
    validate_run(results, mode="raise")
    print("✅ All validation checks passed!")
except AssertionError as e:
    print(f"❌ Validation failed: {e}")

# Show the results
print("\n📊 Results Summary:")
print("=" * 50)

# First month (should show 100k seed money)
first_month = results["totals"].iloc[0]
print(f"Month 1:")
print(f"  Cash In:  €{first_month['cash_in']:,.2f}")
print(f"  Cash Out: €{first_month['cash_out']:,.2f}")
print(f"  Net CF:   €{first_month['net_cf']:,.2f}")
print(f"  Assets:   €{first_month['assets']:,.2f}")
print(f"  Equity:   €{first_month['equity']:,.2f}")

# Last month (should show accumulated interest)
last_month = results["totals"].iloc[-1]
print(f"\nMonth 12:")
print(f"  Cash In:  €{last_month['cash_in']:,.2f}")
print(f"  Cash Out: €{last_month['cash_out']:,.2f}")
print(f"  Net CF:   €{last_month['net_cf']:,.2f}")
print(f"  Assets:   €{last_month['assets']:,.2f}")
print(f"  Equity:   €{last_month['equity']:,.2f}")

# Show the seed money event
print(f"\n📝 Time-Stamped Events:")
for brick_id, output in results['outputs'].items():
    if output['events']:
        for event in output['events']:
            print(f"  {event.t}: {brick_id} [{event.kind}] - {event.message}")

print("\n✅ Demo completed successfully!")
print("\nThis shows:")
print("- 100k seed money injected at t=0")
print("- 2% annual interest earned on the balance")
print("- No other cash flows (as expected)")