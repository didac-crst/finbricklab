#!/usr/bin/env python3
"""
FinScenLab Income Escalator Demo

This script demonstrates the enhanced income strategy with:
- Annual escalation with percentage increases
- Custom step months (e.g., June every year)
- Non-annual escalation (e.g., every 18 months)
- Anniversary-based escalation
- Escalation events and tracking
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

# Test Case 1: Basic annual escalation
print("\n🧪 Test Case 1: Basic annual escalation")
print("=" * 60)

cash = ABrick(
    id="cash:EUR", 
    name="Main Cash", 
    kind=K.A_CASH,
    spec={"initial_balance": 0.0, "overdraft_limit": 0.0, "min_buffer": 0.0}
)

# Salary with 3% annual escalation
salary1 = FBrick(
    id="salary1", 
    name="Escalating Salary", 
    kind=K.F_INCOME,
    start_date=date(2026, 3, 1),  # Start in March 2026
    spec={
        "amount_monthly": 5000,  # €5k/month base
        "annual_step_pct": 0.03  # 3% annual increase
    }
)

scen1 = Scenario(
    id="scen1", 
    name="Basic Escalation Test",
    bricks=[cash, salary1]
)

try:
    res1 = scen1.run(start=date(2026, 1, 1), months=36)
    validate_run(res1, scen1.bricks, mode="raise")
    print("✅ SUCCESS: Basic escalation scenario passed!")
    
    # Show income progression
    print(f"\n📊 Income progression:")
    salary1_out = res1['outputs']['salary1']
    for i in range(2, 36, 6):  # Every 6 months
        month = i
        income = salary1_out['cash_in'][i]
        year = (month - 2) // 12 + 1
        print(f"  Month {month} (Year {year}): €{income:,.2f}")
    
    # Show escalation events
    print(f"\n📝 Escalation events:")
    for event in salary1_out['events']:
        print(f"  {event.t}: {event.message}")
        
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 2: Custom step month (June every year)
print("\n🧪 Test Case 2: Custom step month (June)")
print("=" * 60)

# Salary with escalation in June every year
salary2 = FBrick(
    id="salary2", 
    name="June Escalation Salary", 
    kind=K.F_INCOME,
    start_date=date(2026, 3, 1),  # Start in March 2026
    spec={
        "amount_monthly": 4000,  # €4k/month base
        "annual_step_pct": 0.04,  # 4% annual increase
        "step_month": 6  # Escalate in June every year
    }
)

scen2 = Scenario(
    id="scen2", 
    name="June Escalation Test",
    bricks=[cash, salary2]
)

try:
    res2 = scen2.run(start=date(2026, 1, 1), months=36)
    validate_run(res2, scen2.bricks, mode="raise")
    print("✅ SUCCESS: June escalation scenario passed!")
    
    # Show income progression around June
    print(f"\n📊 Income progression around June:")
    salary2_out = res2['outputs']['salary2']
    for i in range(2, 36, 3):  # Every 3 months
        month = i
        income = salary2_out['cash_in'][i]
        month_name = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][(month - 1) % 12]
        print(f"  Month {month} ({month_name}): €{income:,.2f}")
    
    # Show escalation events
    print(f"\n📝 Escalation events:")
    for event in salary2_out['events']:
        print(f"  {event.t}: {event.message}")
        
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 3: Non-annual escalation (every 18 months)
print("\n🧪 Test Case 3: Non-annual escalation (every 18 months)")
print("=" * 60)

# Salary with escalation every 18 months
salary3 = FBrick(
    id="salary3", 
    name="18-Month Escalation Salary", 
    kind=K.F_INCOME,
    start_date=date(2026, 3, 1),  # Start in March 2026
    spec={
        "amount_monthly": 6000,  # €6k/month base
        "step_pct": 0.05,  # 5% increase every 18 months
        "step_every_m": 18  # Escalate every 18 months
    }
)

scen3 = Scenario(
    id="scen3", 
    name="18-Month Escalation Test",
    bricks=[cash, salary3]
)

try:
    res3 = scen3.run(start=date(2026, 1, 1), months=48)
    validate_run(res3, scen3.bricks, mode="raise")
    print("✅ SUCCESS: 18-month escalation scenario passed!")
    
    # Show income progression
    print(f"\n📊 Income progression (18-month cycles):")
    salary3_out = res3['outputs']['salary3']
    for i in range(2, 48, 6):  # Every 6 months
        month = i
        income = salary3_out['cash_in'][i]
        cycle = (month - 2) // 18 + 1
        print(f"  Month {month} (Cycle {cycle}): €{income:,.2f}")
    
    # Show escalation events
    print(f"\n📝 Escalation events:")
    for event in salary3_out['events']:
        print(f"  {event.t}: {event.message}")
        
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 4: Multiple income streams with different escalation patterns
print("\n🧪 Test Case 4: Multiple income streams")
print("=" * 60)

# Multiple income streams with different patterns
salary_base = FBrick(
    id="salary_base", 
    name="Base Salary", 
    kind=K.F_INCOME,
    start_date=date(2026, 1, 1),
    spec={
        "amount_monthly": 3000,
        "annual_step_pct": 0.025  # 2.5% annual
    }
)

bonus = FBrick(
    id="bonus", 
    name="Annual Bonus", 
    kind=K.F_INCOME,
    start_date=date(2026, 1, 1),
    spec={
        "amount_monthly": 500,  # €500/month average
        "annual_step_pct": 0.05,  # 5% annual
        "step_month": 12  # Escalate in December
    }
)

freelance = FBrick(
    id="freelance", 
    name="Freelance Income", 
    kind=K.F_INCOME,
    start_date=date(2026, 6, 1),  # Start in June
    spec={
        "amount_monthly": 2000,
        "step_pct": 0.08,  # 8% every 12 months
        "step_every_m": 12  # Every 12 months from start
    }
)

scen4 = Scenario(
    id="scen4", 
    name="Multiple Income Streams Test",
    bricks=[cash, salary_base, bonus, freelance]
)

try:
    res4 = scen4.run(start=date(2026, 1, 1), months=36)
    validate_run(res4, scen4.bricks, mode="raise")
    print("✅ SUCCESS: Multiple income streams scenario passed!")
    
    # Show combined income progression
    print(f"\n📊 Combined income progression:")
    for i in range(0, 36, 6):  # Every 6 months
        month = i
        total_income = res4['totals']['cash_in'].iloc[i]
        base_income = res4['outputs']['salary_base']['cash_in'][i]
        bonus_income = res4['outputs']['bonus']['cash_in'][i]
        freelance_income = res4['outputs']['freelance']['cash_in'][i]
        print(f"  Month {month}: Total €{total_income:,.2f} (Base: €{base_income:,.2f}, Bonus: €{bonus_income:,.2f}, Freelance: €{freelance_income:,.2f})")
    
    # Show escalation events
    print(f"\n📝 Escalation events (sample):")
    all_events = []
    for brick_id in ['salary_base', 'bonus', 'freelance']:
        all_events.extend(res4['outputs'][brick_id]['events'])
    
    # Sort by date and show first few
    all_events.sort(key=lambda e: e.t)
    for event in all_events[:6]:  # Show first 6 events
        print(f"  {event.t}: {event.message}")
        
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

# Test Case 5: No escalation (backward compatibility)
print("\n🧪 Test Case 5: No escalation (backward compatibility)")
print("=" * 60)

# Fixed income without escalation
salary_fixed = FBrick(
    id="salary_fixed", 
    name="Fixed Salary", 
    kind=K.F_INCOME,
    start_date=date(2026, 1, 1),
    spec={
        "amount_monthly": 4000  # No escalation parameters
    }
)

scen5 = Scenario(
    id="scen5", 
    name="Fixed Income Test",
    bricks=[cash, salary_fixed]
)

try:
    res5 = scen5.run(start=date(2026, 1, 1), months=24)
    validate_run(res5, scen5.bricks, mode="raise")
    print("✅ SUCCESS: Fixed income scenario passed!")
    
    # Show that income remains constant
    print(f"\n📊 Fixed income verification:")
    salary_fixed_out = res5['outputs']['salary_fixed']
    for i in range(0, 24, 6):  # Every 6 months
        month = i
        income = salary_fixed_out['cash_in'][i]
        print(f"  Month {month}: €{income:,.2f}")
    
    # Should have no escalation events
    print(f"\n📝 Escalation events: {len(salary_fixed_out['events'])}")
        
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

print("\n✅ Income escalator demo completed!")
print("\nThis demonstrates:")
print("- Annual escalation with percentage increases")
print("- Custom step months (e.g., June every year)")
print("- Non-annual escalation (e.g., every 18 months)")
print("- Anniversary-based escalation")
print("- Multiple income streams with different patterns")
print("- Backward compatibility with fixed income")
print("- Escalation events and proper tracking")
print("- Integration with activation windows")
