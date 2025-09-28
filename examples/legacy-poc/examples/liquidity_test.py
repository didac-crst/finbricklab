#!/usr/bin/env python3
"""
FinScenLab Liquidity Test

This script demonstrates the new liquidity discipline feature that prevents
economically impossible runs (negative cash paying principal) and makes
cash availability explicit in results.
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

# Test Case 1: Should FAIL - Insufficient seed money
print("\n🧪 Test Case 1: Insufficient seed (should FAIL)")
print("=" * 60)

cash = ABrick(
    id="cash:EUR", 
    name="Main Cash", 
    kind=K.A_CASH,
    spec={"initial_balance": 0.0, "overdraft_limit": 0.0, "min_buffer": 0.0}
)

seed = FBrick(
    id="seed", 
    name="Owner Equity", 
    kind=K.F_TRANSFER, 
    spec={"amount": 50_000}  # Only 50k seed
)

house = ABrick(
    id="house_tls", 
    name="Toulouse Flat", 
    kind=K.A_PROPERTY,
    start_date=date(2026, 2, 1),
    spec={
        "price": 400_000, 
        "fees_pct": 0.10,  # 40k fees
        "appreciation_pa": 0.0,
        "down_payment": 50_000, 
        "finance_fees": False  # Fees paid from cash
    }
)

mort = LBrick(
    id="mort_25y", 
    name="25y Mortgage", 
    kind=K.L_MORT_ANN,
    start_date=date(2026, 2, 1),
    links={"auto_principal_from": "house_tls"},
    spec={
        "rate_pa": 0.034,  # 3.4% APR
        "term_months": 300,  # 25 years
        "first_payment_offset": 1
    }
)

scen1 = Scenario(
    id="scen1", 
    name="Liquidity Test (insufficient seed)",
    bricks=[cash, seed, house, mort]
)

print("Scenario setup:")
print(f"  Seed: €{seed.spec['amount']:,}")
print(f"  House price: €{house.spec['price']:,}")
print(f"  Fees: €{house.spec['price'] * house.spec['fees_pct']:,} (paid from cash)")
print(f"  Down payment: €{house.spec['down_payment']:,}")
print(f"  Expected t0 cash need: €{house.spec['down_payment'] + house.spec['price'] * house.spec['fees_pct']:,}")
print(f"  Available cash: €{seed.spec['amount']:,}")
print(f"  Shortfall: €{house.spec['down_payment'] + house.spec['price'] * house.spec['fees_pct'] - seed.spec['amount']:,}")

try:
    res1 = scen1.run(start=date(2026, 1, 1), months=24)
    validate_run(res1, scen1.bricks, mode="raise")
    print("❌ UNEXPECTED: Scenario should have failed!")
except AssertionError as e:
    print("✅ EXPECTED FAILURE:")
    print(f"   {str(e)}")

# Test Case 2: Should PASS - Sufficient seed money
print("\n🧪 Test Case 2: Sufficient seed (should PASS)")
print("=" * 60)

# Update seed to sufficient amount (need extra for first few mortgage payments)
seed.spec["amount"] = 110_000  # 110k seed (down + fees = 90k + buffer for payments)

scen2 = Scenario(
    id="scen2", 
    name="Liquidity Test (sufficient seed)",
    bricks=[cash, seed, house, mort]
)

print("Updated scenario:")
print(f"  Seed: €{seed.spec['amount']:,}")
print(f"  Expected t0 cash need: €{house.spec['down_payment'] + house.spec['price'] * house.spec['fees_pct']:,}")
print(f"  Available cash: €{seed.spec['amount']:,}")
print(f"  Excess: €{seed.spec['amount'] - (house.spec['down_payment'] + house.spec['price'] * house.spec['fees_pct']):,}")
print(f"  (Extra buffer for initial mortgage payments)")

try:
    res2 = scen2.run(start=date(2026, 1, 1), months=24)
    validate_run(res2, scen2.bricks, mode="raise")
    print("✅ SUCCESS: Scenario passed validation!")
    
    # Show cash column in results
    print(f"\n📊 Cash visibility in results:")
    print(f"  Cash column included: {'cash' in res2['totals'].columns}")
    if 'cash' in res2['totals'].columns:
        print(f"  Cash at t0: €{res2['totals']['cash'].iloc[0]:,.2f}")
        print(f"  Cash at t1 (after purchase): €{res2['totals']['cash'].iloc[1]:,.2f}")
        print(f"  Cash at t2: €{res2['totals']['cash'].iloc[2]:,.2f}")
    
except AssertionError as e:
    print("❌ UNEXPECTED FAILURE:")
    print(f"   {str(e)}")

# Test Case 3: Should PASS - Finance fees instead of cash payment
print("\n🧪 Test Case 3: Finance fees (should PASS)")
print("=" * 60)

# Reset seed to original amount but finance the fees
seed.spec["amount"] = 60_000  # 60k seed (down payment + buffer for payments)
house.spec["finance_fees"] = True  # Finance the fees

scen3 = Scenario(
    id="scen3", 
    name="Liquidity Test (finance fees)",
    bricks=[cash, seed, house, mort]
)

print("Updated scenario:")
print(f"  Seed: €{seed.spec['amount']:,}")
print(f"  House price: €{house.spec['price']:,}")
print(f"  Fees: €{house.spec['price'] * house.spec['fees_pct']:,} (FINANCED)")
print(f"  Down payment: €{house.spec['down_payment']:,}")
print(f"  Expected t0 cash need: €{house.spec['down_payment']:,} (fees financed)")
print(f"  Available cash: €{seed.spec['amount']:,}")
print(f"  Excess: €{seed.spec['amount'] - house.spec['down_payment']:,}")
print(f"  (Extra buffer for initial mortgage payments)")

try:
    res3 = scen3.run(start=date(2026, 1, 1), months=24)
    validate_run(res3, scen3.bricks, mode="raise")
    print("✅ SUCCESS: Scenario passed validation with fees financing!")
    
    # Show the difference in mortgage principal
    mort_principal = mort.spec.get("principal", 0)
    print(f"\n📊 Mortgage impact:")
    print(f"  Mortgage principal: €{mort_principal:,.2f}")
    print(f"  (Includes €{house.spec['price'] * house.spec['fees_pct']:,.2f} in financed fees)")
    
except AssertionError as e:
    print("❌ UNEXPECTED FAILURE:")
    print(f"   {str(e)}")

# Test Case 4: Should PASS - Large buffer for mortgage payments
print("\n🧪 Test Case 4: Large buffer (should PASS)")
print("=" * 60)

# Use a much larger seed to cover all mortgage payments
seed.spec["amount"] = 150_000  # Large buffer
house.spec["finance_fees"] = False  # Back to cash fees

scen4 = Scenario(
    id="scen4", 
    name="Liquidity Test (large buffer)",
    bricks=[cash, seed, house, mort]
)

print("Updated scenario:")
print(f"  Seed: €{seed.spec['amount']:,}")
print(f"  Expected t0 cash need: €{house.spec['down_payment'] + house.spec['price'] * house.spec['fees_pct']:,}")
print(f"  Available cash: €{seed.spec['amount']:,}")
print(f"  Buffer: €{seed.spec['amount'] - (house.spec['down_payment'] + house.spec['price'] * house.spec['fees_pct']):,}")
print(f"  (Large buffer to cover mortgage payments)")

try:
    res4 = scen4.run(start=date(2026, 1, 1), months=24)
    validate_run(res4, scen4.bricks, mode="raise")
    print("✅ SUCCESS: Scenario passed validation with large buffer!")
    
    # Show cash progression
    print(f"\n📊 Cash progression:")
    for i in range(min(6, len(res4['totals']))):
        print(f"  Month {i}: €{res4['totals']['cash'].iloc[i]:,.2f}")
    
except AssertionError as e:
    print("❌ UNEXPECTED FAILURE:")
    print(f"   {str(e)}")

print("\n✅ Liquidity test completed!")
print("\nThis demonstrates:")
print("- Liquidity discipline prevents impossible runs")
print("- Cash availability is explicit in results")
print("- Actionable suggestions help fix liquidity issues")
print("- Multiple solutions: increase seed, finance fees, or reduce outflows")
print("- Small negative amounts indicate realistic mortgage payment pressure")
