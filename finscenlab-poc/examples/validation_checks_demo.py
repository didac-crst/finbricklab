#!/usr/bin/env python3
"""
FinScenLab Enhanced Validation Checks Demo

This script demonstrates the new validation checks for:
- Balloon payment consistency
- ETF units never negative
- Income escalator monotonicity
- All existing validation checks
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

# Test Case 1: Balloon payment validation (should pass)
print("\n🧪 Test Case 1: Balloon payment validation (should pass)")
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

# Mortgage with proper balloon payoff
mortgage = LBrick(
    id="mortgage", 
    name="Balloon Mortgage", 
    kind=K.L_MORT_ANN,
    start_date=date(2026, 2, 1),
    end_date=date(2031, 1, 1),  # 5 years
    links={"auto_principal_from": "house"},
    spec={
        "rate_pa": 0.034,
        "term_months": 300,  # 25-year amortization
        "first_payment_offset": 1,
        "balloon_policy": "payoff"  # Should pay off remaining balance
    }
)

scen1 = Scenario(
    id="scen1", 
    name="Balloon Validation Test",
    bricks=[cash, seed, house, mortgage]
)

try:
    res1 = scen1.run(start=date(2026, 1, 1), months=72)
    validate_run(res1, scen1.bricks, mode="raise")
    print("✅ SUCCESS: Balloon payment validation passed!")
    
    # Show balloon event
    mort_out = res1['outputs']['mortgage']
    for event in mort_out['events']:
        if "balloon" in event.message.lower():
            print(f"  📝 {event.t}: {event.message}")
            
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 2: ETF units validation (should pass)
print("\n🧪 Test Case 2: ETF units validation (should pass)")
print("=" * 60)

# ETF with proper sell logic (never negative units)
etf = ABrick(
    id="etf", 
    name="ETF with Sells", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 3, 1),
    spec={
        "price0": 100,
        "drift_pa": 0.05,
        "initial_units": 0,
        "buy_at_start": {"amount": 10000},
        "sell": [
            {"t": "2028-06", "amount": 5000}  # Sell €5k worth (should be safe)
        ],
        "events_level": "major"
    }
)

scen2 = Scenario(
    id="scen2", 
    name="ETF Units Validation Test",
    bricks=[cash, seed, etf]
)

try:
    res2 = scen2.run(start=date(2026, 1, 1), months=36)
    validate_run(res2, scen2.bricks, mode="raise")
    print("✅ SUCCESS: ETF units validation passed!")
    
    # Show ETF progression
    etf_out = res2['outputs']['etf']
    print(f"  📊 ETF value progression:")
    for i in range(2, 36, 6):
        month = i
        etf_value = etf_out['asset_value'][i]
        print(f"    Month {month}: €{etf_value:,.2f}")
        
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 3: Income escalator monotonicity (should pass)
print("\n🧪 Test Case 3: Income escalator monotonicity (should pass)")
print("=" * 60)

# Income with proper escalation
salary = FBrick(
    id="salary", 
    name="Escalating Salary", 
    kind=K.F_INCOME,
    start_date=date(2026, 3, 1),
    spec={
        "amount_monthly": 5000,
        "annual_step_pct": 0.03  # 3% annual increase
    }
)

scen3 = Scenario(
    id="scen3", 
    name="Income Escalator Validation Test",
    bricks=[cash, salary]
)

try:
    res3 = scen3.run(start=date(2026, 1, 1), months=36)
    validate_run(res3, scen3.bricks, mode="raise")
    print("✅ SUCCESS: Income escalator monotonicity validation passed!")
    
    # Show income progression
    salary_out = res3['outputs']['salary']
    print(f"  📊 Income progression:")
    for i in range(2, 36, 6):
        month = i
        income = salary_out['cash_in'][i]
        print(f"    Month {month}: €{income:,.2f}")
        
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 4: Multiple validation checks together
print("\n🧪 Test Case 4: Multiple validation checks together")
print("=" * 60)

# Complex scenario with multiple features
house2 = ABrick(
    id="house2", 
    name="Family Home", 
    kind=K.A_PROPERTY,
    start_date=date(2026, 2, 1),
    spec={
        "price": 400000,
        "fees_pct": 0.08,
        "appreciation_pa": 0.02,
        "down_payment": 80000,
        "finance_fees": True
    }
)

mortgage2 = LBrick(
    id="mortgage2", 
    name="Family Mortgage", 
    kind=K.L_MORT_ANN,
    start_date=date(2026, 2, 1),
    end_date=date(2036, 1, 1),  # 10 years
    links={"auto_principal_from": "house2"},
    spec={
        "rate_pa": 0.034,
        "term_months": 300,
        "first_payment_offset": 1,
        "balloon_policy": "payoff",
        "prepayments": [
            {"t": "2028-06", "amount": 10000}  # One prepayment
        ]
    }
)

etf2 = ABrick(
    id="etf2", 
    name="Investment Portfolio", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 4, 1),
    spec={
        "price0": 100,
        "drift_pa": 0.06,
        "initial_units": 0,
        "buy_at_start": {"amount": 20000},
        "dca": {
            "mode": "amount",
            "amount": 2000,
            "start_offset_m": 1,
            "months": 24
        },
        "sdca": {
            "mode": "amount",
            "amount": 1000,
            "start_offset_m": 18,
            "months": 12
        }
    }
)

salary2 = FBrick(
    id="salary2", 
    name="Career Salary", 
    kind=K.F_INCOME,
    start_date=date(2026, 1, 1),
    spec={
        "amount_monthly": 6000,
        "annual_step_pct": 0.04,  # 4% annual increase
        "step_month": 6  # Escalate in June
    }
)

scen4 = Scenario(
    id="scen4", 
    name="Comprehensive Validation Test",
    bricks=[cash, seed, house2, mortgage2, etf2, salary2]
)

try:
    res4 = scen4.run(start=date(2026, 1, 1), months=60)
    validate_run(res4, scen4.bricks, mode="raise")
    print("✅ SUCCESS: Comprehensive validation passed!")
    
    # Show key metrics
    print(f"  📊 Final metrics:")
    print(f"    Cash balance: €{res4['totals']['cash'].iloc[-1]:,.2f}")
    print(f"    Total assets: €{res4['totals']['assets'].iloc[-1]:,.2f}")
    print(f"    Total debt: €{res4['totals']['debt'].iloc[-1]:,.2f}")
    print(f"    Net worth: €{res4['totals']['equity'].iloc[-1]:,.2f}")
    
    # Show events summary
    total_events = 0
    for brick_id, output in res4['outputs'].items():
        total_events += len(output['events'])
    print(f"    Total events: {total_events}")
        
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

print("\n✅ Enhanced validation checks demo completed!")
print("\nThis demonstrates:")
print("- Balloon payment consistency validation")
print("- ETF units never negative validation")
print("- Income escalator monotonicity validation")
print("- Integration with existing validation checks")
print("- Comprehensive scenario validation")
print("- All new features working together harmoniously")
