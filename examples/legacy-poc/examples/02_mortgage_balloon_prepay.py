#!/usr/bin/env python3
"""
FinScenLab Example 02: Mortgage Balloon & Prepayments

This example demonstrates the enhanced mortgage strategy with:
- Balloon payments at end of activation window
- Prepayments (Sondertilgung) with fixed amounts and percentages
- Annual prepayment schedules
- Prepayment fees
- Refinance vs payoff policies

This is a comprehensive example showing realistic German mortgage scenarios.
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

print("🏠 FinScenLab Example 02: Mortgage Balloon & Prepayments")
print("=" * 70)

# =============================================================================
# SCENARIO SETUP
# =============================================================================

# Cash account with sufficient liquidity
cash = ABrick(
    id="cash:EUR", 
    name="Main Cash Account", 
    kind=K.A_CASH,
    spec={
        "initial_balance": 0.0, 
        "overdraft_limit": 0.0, 
        "min_buffer": 0.0
    }
)

# Initial capital injection
seed = FBrick(
    id="seed", 
    name="Initial Capital", 
    kind=K.F_TRANSFER, 
    spec={"amount": 300000}  # €300k seed money
)

# Investment property
house = ABrick(
    id="house", 
    name="Investment Property", 
    kind=K.A_PROPERTY,
    start_date=date(2026, 2, 1),  # Purchase in February 2026
    spec={
        "price": 500000,  # €500k property
        "fees_pct": 0.08,  # 8% fees (€40k)
        "appreciation_pa": 0.02,  # 2% annual appreciation
        "down_payment": 100000,  # €100k down payment
        "finance_fees": True  # Finance the fees
    }
)

# Enhanced mortgage with balloon and prepayments
mortgage = LBrick(
    id="mortgage", 
    name="Investment Property Mortgage", 
    kind=K.L_MORT_ANN,
    start_date=date(2026, 2, 1),
    end_date=date(2031, 1, 1),  # 5-year balloon mortgage
    links={"auto_principal_from": "house"},
    spec={
        "rate_pa": 0.034,  # 3.4% APR
        "term_months": 300,  # 25-year amortization
        "first_payment_offset": 1,
        "balloon_policy": "payoff",  # Pay off remaining balance
        "prepayments": [
            # One-shot prepayment in year 2
            {"t": "2028-06", "amount": 15000},
            # Percentage-based prepayment in year 3
            {"t": "2029-12", "pct_balance": 0.05, "cap": 20000},  # 5% of balance, capped at €20k
            # Annual prepayment every December
            {"every": "year", "month": 12, "amount": 10000, "start_year": 2027, "end_year": 2030}
        ],
        "prepay_fee_pct": 0.005  # 0.5% prepayment fee
    }
)

# Create the scenario
scenario = Scenario(
    id="mortgage_balloon_prepay", 
    name="Investment Property with Balloon Mortgage & Prepayments",
    bricks=[cash, seed, house, mortgage]
)

print("✅ Scenario created successfully!")
print(f"📋 Scenario: {scenario.name}")
print(f"🏠 Property: €{house.spec['price']:,.0f} with €{house.spec['down_payment']:,.0f} down payment")
print(f"🏦 Mortgage: {mortgage.spec['term_months']//12}-year amortization, {mortgage.spec['rate_pa']*100:.1f}% APR")
print(f"🎯 Balloon: 5-year window with payoff policy")
print(f"💰 Prepayments: One-shot + percentage + annual schedule")

# =============================================================================
# RUN SIMULATION
# =============================================================================

print("\n🚀 Running simulation...")
print("-" * 50)

try:
    results = scenario.run(start=date(2026, 1, 1), months=72)  # 6 years
    validate_run(results, scenario.bricks, mode="raise")
    print("✅ Simulation completed successfully!")
    
except AssertionError as e:
    print("❌ Simulation failed validation:")
    print(f"   {str(e)}")
    print("\n💡 This is expected for large balloon payments - the liquidity validator is working correctly!")
    print("   In a real scenario, you would need sufficient cash reserves for the balloon payment.")
    exit(1)

# =============================================================================
# RESULTS ANALYSIS
# =============================================================================

print("\n📊 RESULTS ANALYSIS")
print("=" * 70)

# Extract key outputs
mortgage_out = results['outputs']['mortgage']
house_out = results['outputs']['house']
totals = results['totals']

# Show debt progression
print("\n🏦 MORTGAGE DEBT PROGRESSION:")
print("-" * 40)
for i in range(0, 72, 6):  # Every 6 months
    month = i
    year = month // 12 + 1
    debt = mortgage_out['debt_balance'][i]
    payment = mortgage_out['cash_out'][i]
    print(f"  Year {year}, Month {month:2d}: Debt €{debt:8,.0f}, Payment €{payment:6,.0f}")

# Show property value progression
print("\n🏠 PROPERTY VALUE PROGRESSION:")
print("-" * 40)
for i in range(0, 72, 12):  # Every year
    year = i // 12 + 1
    value = house_out['asset_value'][i]
    print(f"  Year {year}: €{value:,.0f}")

# Show prepayment events
print("\n💰 PREPAYMENT EVENTS:")
print("-" * 40)
prepay_events = [e for e in mortgage_out['events'] if 'prepay' in e.message.lower()]
for event in prepay_events:
    print(f"  {event.t}: {event.message}")

# Show balloon event
print("\n🎯 BALLOON PAYMENT:")
print("-" * 40)
balloon_events = [e for e in mortgage_out['events'] if 'balloon' in e.message.lower()]
for event in balloon_events:
    print(f"  {event.t}: {event.message}")

# Show final financial position
print("\n💼 FINAL FINANCIAL POSITION:")
print("-" * 40)
final_cash = totals['cash'].iloc[-1]
final_assets = totals['assets'].iloc[-1]
final_debt = totals['debt'].iloc[-1]
final_equity = totals['equity'].iloc[-1]

print(f"  Cash Balance:     €{final_cash:,.0f}")
print(f"  Total Assets:     €{final_assets:,.0f}")
print(f"  Total Debt:       €{final_debt:,.0f}")
print(f"  Net Worth:        €{final_equity:,.0f}")

# Show key metrics
print("\n📈 KEY METRICS:")
print("-" * 40)
initial_investment = house.spec['down_payment'] + house.spec['price'] * house.spec['fees_pct'] * (1 - house.spec.get('fees_financed_pct', 1.0))
total_prepayments = sum(event.meta.get('amount', 0) for event in prepay_events if 'amount' in event.meta)
total_interest = sum(mortgage_out['cash_out']) - mortgage.spec['principal'] - total_prepayments

print(f"  Initial Investment: €{initial_investment:,.0f}")
print(f"  Total Prepayments:  €{total_prepayments:,.0f}")
print(f"  Total Interest:     €{total_interest:,.0f}")
print(f"  Property Appreciation: €{final_assets - house.spec['price']:,.0f}")

# =============================================================================
# LESSONS LEARNED
# =============================================================================

print("\n🎓 LESSONS LEARNED:")
print("=" * 70)
print("1. 🎯 Balloon mortgages require careful cash flow planning")
print("2. 💰 Prepayments can significantly reduce total interest paid")
print("3. 📅 Annual prepayment schedules provide systematic debt reduction")
print("4. 🏠 Property appreciation can offset mortgage costs")
print("5. ⚖️ Liquidity validation ensures realistic scenarios")
print("6. 📊 Activation windows enable complex timing scenarios")

print("\n✅ Example 02 completed successfully!")
print("\nThis example demonstrates realistic German mortgage scenarios with:")
print("- Balloon payments for investment properties")
print("- Systematic prepayments (Sondertilgung)")
print("- Prepayment fees and policies")
print("- Integration with property appreciation")
print("- Comprehensive validation and error handling")
