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
from finscenlab.core import Scenario, ABrick, LBrick, FBrick, validate_run
from finscenlab.kinds import K
import finscenlab.strategies  # This registers the default strategies

print("✅ All imports successful!")

# Create a scenario with delayed brick activation
print("\n🏗️  Creating financial bricks with delayed activation...")

# Cash account - starts immediately
cash = ABrick(
    id="cash:EUR", 
    name="Main Cash Account", 
    kind=K.A_CASH,
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
    kind=K.F_TRANSFER,
    spec={"amount": 100_000}
    # No start_date = starts at scenario start
)

# Salary - starts immediately
salary = FBrick(
    id="salary", 
    name="Monthly Salary", 
    kind=K.F_INCOME,
    spec={"amount_monthly": 4_500}
    # No start_date = starts at scenario start
)

# Living expenses - starts immediately
living = FBrick(
    id="living", 
    name="Living Expenses", 
    kind=K.F_EXP_LIVING,
    spec={"amount_monthly": 1_800}
    # No start_date = starts at scenario start
)

# House purchase - starts in 2028!
house = ABrick(
    id="house_tls", 
    name="Toulouse Flat", 
    kind=K.A_PROPERTY,
    start_date=date(2028, 1, 1),  # 🎯 Buy house in 2028!
    spec={
        "price": 450_000,  # Price increased from 2026
        "fees_pct": 0.095,  # 9.5% fees
        "appreciation_pa": 0.02,  # 2% annual appreciation
        "down_payment": 60_000,  # Larger down payment
        "finance_fees": False
    }
)

# Mortgage - starts in 2028 (linked to house)
mortgage = LBrick(
    id="mort_10y", 
    name="25-Year Fixed Mortgage", 
    kind=K.L_MORT_ANN,
    start_date=date(2028, 1, 1),  # 🎯 Mortgage starts with house purchase
    links={"auto_principal_from": "house_tls"},
    spec={
        "rate_pa": 0.035,  # Slightly higher rate in 2028
        "term_months": 300  # 25 years
    }
)

# Promotion - salary increase in 2027!
promotion = FBrick(
    id="promotion", 
    name="Salary Promotion", 
    kind=K.F_INCOME,
    start_date=date(2027, 6, 1),  # 🎯 Promotion in June 2027
    spec={"amount_monthly": 1_000}  # Additional 1k/month
)

print("✅ Created all bricks:")
print(f"  - Cash account: starts immediately")
print(f"  - Seed money: €{seed.spec['amount']:,} - starts immediately")
print(f"  - Salary: €{salary.spec['amount_monthly']:,}/month - starts immediately")
print(f"  - Living expenses: €{living.spec['amount_monthly']:,}/month - starts immediately")
print(f"  - House: €{house.spec['price']:,} - starts {house.start_date}")
print(f"  - Mortgage: linked to house - starts {mortgage.start_date}")
print(f"  - Promotion: +€{promotion.spec['amount_monthly']:,}/month - starts {promotion.start_date}")

# Create the scenario
print("\n🎯 Creating scenario...")
scenario = Scenario(
    id="delayed_demo", 
    name="Delayed Activation Demo", 
    bricks=[cash, seed, salary, living, house, mortgage, promotion]
)

print(f"✅ Scenario created: {scenario.name}")

# Run the simulation for 5 years (60 months)
print("\n🚀 Running 5-year simulation...")
results = scenario.run(start=date(2026, 1, 1), months=60)

print("✅ Simulation completed!")
print(f"   Period: {results['totals'].index[0]} to {results['totals'].index[-1]}")

# Validate the results
print("\n🔍 Validating results...")
try:
    validate_run(results, mode="raise")
    print("✅ All validation checks passed!")
except AssertionError as e:
    print(f"❌ Validation failed: {e}")

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
print(f"\n2028-01: House purchase (€{house.spec['price']:,})")
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
