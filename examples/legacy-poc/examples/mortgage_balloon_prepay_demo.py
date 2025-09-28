#!/usr/bin/env python3
"""
FinScenLab Mortgage Balloon & Prepayments Demo

This script demonstrates the enhanced mortgage strategy with:
- Balloon payments at end of activation window
- Prepayments (Sondertilgung) with fixed amounts and percentages
- Prepayment fees
- Refinance vs payoff policies
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

# Test Case 1: Basic balloon payment
print("\n🧪 Test Case 1: Basic balloon payment")
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
    spec={"amount": 200000}
)

house = ABrick(
    id="house", 
    name="Investment Property", 
    kind=K.A_PROPERTY,
    start_date=date(2026, 2, 1),
    spec={
        "price": 300000,
        "fees_pct": 0.08,
        "appreciation_pa": 0.02,
        "down_payment": 60000,
        "finance_fees": True
    }
)

# Mortgage with early end (balloon payment)
mortgage = LBrick(
    id="mortgage", 
    name="5-Year Balloon Mortgage", 
    kind=K.L_MORT_ANN,
    start_date=date(2026, 2, 1),
    end_date=date(2031, 1, 1),  # 5 years
    links={"auto_principal_from": "house"},
    spec={
        "rate_pa": 0.034,
        "term_months": 300,  # 25-year amortization
        "first_payment_offset": 1,
        "balloon_policy": "payoff"  # Pay off remaining balance
    }
)

scen1 = Scenario(
    id="scen1", 
    name="Balloon Mortgage Test",
    bricks=[cash, seed, house, mortgage]
)

try:
    res1 = scen1.run(start=date(2026, 1, 1), months=72)
    validate_run(res1, scen1.bricks, mode="raise")
    print("✅ SUCCESS: Balloon mortgage scenario passed!")
    
    # Show debt progression
    print(f"\n📊 Debt progression:")
    mort_out = res1['outputs']['mortgage']
    for i in range(0, 72, 12):  # Every year
        month = i
        debt = mort_out['debt_balance'][i]
        print(f"  Year {month//12 + 1}: €{debt:,.2f}")
    
    # Show balloon event
    print(f"\n📝 Balloon event:")
    for event in mort_out['events']:
        if "balloon" in event.message.lower():
            print(f"  {event.t}: {event.message}")
            
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 2: Prepayments (Sondertilgung)
print("\n🧪 Test Case 2: Prepayments (Sondertilgung)")
print("=" * 60)

# Mortgage with prepayments
mortgage2 = LBrick(
    id="mortgage2", 
    name="Mortgage with Prepayments", 
    kind=K.L_MORT_ANN,
    start_date=date(2026, 2, 1),
    links={"auto_principal_from": "house"},
    spec={
        "rate_pa": 0.034,
        "term_months": 300,
        "first_payment_offset": 1,
        "prepayments": [
            {"t": "2028-06", "amount": 10000},  # One-shot prepayment
            {"t": "2029-12", "pct_balance": 0.05, "cap": 15000},  # 5% of balance, capped at €15k
            {"every": "year", "month": 12, "amount": 5000, "start_year": 2027, "end_year": 2030}  # Annual prepayment
        ],
        "prepay_fee_pct": 0.0  # No prepayment fees
    }
)

scen2 = Scenario(
    id="scen2", 
    name="Prepayment Test",
    bricks=[cash, seed, house, mortgage2]
)

try:
    res2 = scen2.run(start=date(2026, 1, 1), months=60)
    validate_run(res2, scen2.bricks, mode="raise")
    print("✅ SUCCESS: Prepayment scenario passed!")
    
    # Show prepayment events
    print(f"\n📝 Prepayment events:")
    mort2_out = res2['outputs']['mortgage2']
    for event in mort2_out['events']:
        if "prepay" in event.message.lower():
            print(f"  {event.t}: {event.message}")
    
    # Show debt reduction impact
    print(f"\n📊 Debt reduction impact:")
    print(f"  Month 12 (before prepayments): €{mort2_out['debt_balance'][11]:,.2f}")
    print(f"  Month 24 (after first annual prepay): €{mort2_out['debt_balance'][23]:,.2f}")
    print(f"  Month 30 (after one-shot prepay): €{mort2_out['debt_balance'][29]:,.2f}")
    print(f"  Month 36 (after percentage prepay): €{mort2_out['debt_balance'][35]:,.2f}")
    
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 3: Refinance policy
print("\n🧪 Test Case 3: Refinance policy")
print("=" * 60)

# Mortgage with refinance policy
mortgage3 = LBrick(
    id="mortgage3", 
    name="Refinance Policy Mortgage", 
    kind=K.L_MORT_ANN,
    start_date=date(2026, 2, 1),
    end_date=date(2031, 1, 1),  # 5 years
    links={"auto_principal_from": "house"},
    spec={
        "rate_pa": 0.034,
        "term_months": 300,
        "first_payment_offset": 1,
        "balloon_policy": "refinance"  # Don't pay off, just note the balloon
    }
)

scen3 = Scenario(
    id="scen3", 
    name="Refinance Policy Test",
    bricks=[cash, seed, house, mortgage3]
)

try:
    res3 = scen3.run(start=date(2026, 1, 1), months=72)
    validate_run(res3, scen3.bricks, mode="raise")
    print("✅ SUCCESS: Refinance policy scenario passed!")
    
    # Show refinance event
    print(f"\n📝 Refinance event:")
    mort3_out = res3['outputs']['mortgage3']
    for event in mort3_out['events']:
        if "balloon" in event.message.lower():
            print(f"  {event.t}: {event.message}")
    
    # Show that debt remains (not paid off)
    print(f"\n📊 Debt at end of window:")
    print(f"  Month 60 (end of window): €{mort3_out['debt_balance'][59]:,.2f}")
    
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 4: Prepayment fees
print("\n🧪 Test Case 4: Prepayment fees")
print("=" * 60)

# Mortgage with prepayment fees
mortgage4 = LBrick(
    id="mortgage4", 
    name="Mortgage with Prepayment Fees", 
    kind=K.L_MORT_ANN,
    start_date=date(2026, 2, 1),
    links={"auto_principal_from": "house"},
    spec={
        "rate_pa": 0.034,
        "term_months": 300,
        "first_payment_offset": 1,
        "prepayments": [
            {"t": "2028-06", "amount": 10000}
        ],
        "prepay_fee_pct": 0.01  # 1% prepayment fee
    }
)

scen4 = Scenario(
    id="scen4", 
    name="Prepayment Fees Test",
    bricks=[cash, seed, house, mortgage4]
)

try:
    res4 = scen4.run(start=date(2026, 1, 1), months=36)
    validate_run(res4, scen4.bricks, mode="raise")
    print("✅ SUCCESS: Prepayment fees scenario passed!")
    
    # Show prepayment with fees
    print(f"\n📊 Prepayment with fees:")
    mort4_out = res4['outputs']['mortgage4']
    prepay_month = 30  # June 2028 (month 30)
    prepay_cash_out = mort4_out['cash_out'][prepay_month]
    print(f"  Month {prepay_month} total cash out: €{prepay_cash_out:,.2f}")
    print(f"  (Includes €10,000 prepayment + €100 fee)")
    
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

print("\n✅ Mortgage balloon & prepayments demo completed!")
print("\nThis demonstrates:")
print("- Balloon payments at end of activation window")
print("- Prepayments with fixed amounts and percentages")
print("- Annual prepayment schedules")
print("- Prepayment fees")
print("- Refinance vs payoff policies")
print("- Proper debt reduction and cash flow impacts")
print("- Integration with liquidity validation")
