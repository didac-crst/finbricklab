#!/usr/bin/env python3
"""
FinScenLab House + ETF Integration Demo

This script demonstrates a realistic scenario combining:
- House purchase with mortgage
- ETF investing with DCA
- Salary income to fund investments
- Living expenses
- Liquidity management across multiple cash flows
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

# Create a realistic financial scenario
print("\n🏠 Realistic House + ETF Investment Scenario")
print("=" * 70)

# Cash account with buffer
cash = ABrick(
    id="cash:EUR", 
    name="Main Cash", 
    kind=K.A_CASH,
    spec={
        "initial_balance": 0.0, 
        "overdraft_limit": 0.0, 
        "min_buffer": 5000.0  # Keep €5k buffer
    }
)

# Initial seed money
seed = FBrick(
    id="seed", 
    name="Initial Capital", 
    kind=K.F_TRANSFER, 
    spec={"amount": 120000}  # €120k seed money
)

# House purchase
house = ABrick(
    id="house", 
    name="Family Home", 
    kind=K.A_PROPERTY,
    start_date=date(2026, 2, 1),  # Buy house in February 2026
    spec={
        "price": 500000,
        "fees_pct": 0.08,  # 8% fees (€40k)
        "appreciation_pa": 0.02,  # 2% annual appreciation
        "down_payment": 100000,
        "finance_fees": True  # Finance the fees
    }
)

# Mortgage
mortgage = LBrick(
    id="mortgage", 
    name="25y Mortgage", 
    kind=K.L_MORT_ANN,
    start_date=date(2026, 2, 1),
    links={"auto_principal_from": "house"},
    spec={
        "rate_pa": 0.034,  # 3.4% APR
        "term_months": 300,  # 25 years
        "first_payment_offset": 1
    }
)

# ETF investment with DCA
etf = ABrick(
    id="etf", 
    name="S&P 500 ETF", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 4, 1),  # Start investing 2 months after house
    spec={
        "price0": 100,
        "drift_pa": 0.07,  # 7% annual growth
        "div_yield_pa": 0.015,  # 1.5% dividend yield
        "initial_units": 0,
        "buy_at_start": {"amount": 5000},  # Initial €5k investment
        "dca": {
            "mode": "amount",
            "amount": 1000,  # €1k/month DCA
            "start_offset_m": 1,  # Start next month
            "months": 36,  # 3 years of DCA
            "annual_step_pct": 0.03  # +3% per year
        },
        "reinvest_dividends": True,  # Reinvest dividends
        "events_level": "major"
    }
)

# Salary income
salary = FBrick(
    id="salary", 
    name="Monthly Salary", 
    kind=K.F_INCOME,
    spec={
        "amount_monthly": 8000,  # €8k/month
        "start_month": 0,
        "end_month": None
    }
)

# Living expenses
living = FBrick(
    id="living", 
    name="Living Expenses", 
    kind=K.F_EXP_LIVING,
    spec={
        "amount_monthly": 3500,  # €3.5k/month
        "start_month": 0,
        "end_month": None
    }
)

# Create the scenario
scenario = Scenario(
    id="house_etf", 
    name="House Purchase + ETF Investment",
    bricks=[cash, seed, house, mortgage, etf, salary, living]
)

print("Scenario setup:")
print(f"  Initial capital: €{seed.spec['amount']:,}")
print(f"  House price: €{house.spec['price']:,}")
print(f"  Down payment: €{house.spec['down_payment']:,}")
print(f"  Fees: €{house.spec['price'] * house.spec['fees_pct']:,} (financed)")
print(f"  Monthly salary: €{salary.spec['amount_monthly']:,}")
print(f"  Monthly expenses: €{living.spec['amount_monthly']:,}")
print(f"  ETF initial: €5,000")
print(f"  ETF DCA: €1,000/month (3 years, +3%/year)")
print(f"  Cash buffer: €5,000")

try:
    results = scenario.run(start=date(2026, 1, 1), months=48)  # 4 years
    validate_run(results, scenario.bricks, mode="raise")
    print("\n✅ SUCCESS: House + ETF scenario passed validation!")
    
    # Show key financial metrics
    totals = results['totals']
    print(f"\n📊 Key Financial Metrics:")
    print(f"  Starting cash: €{totals['cash'].iloc[0]:,.2f}")
    print(f"  Month 2 (after house): €{totals['cash'].iloc[1]:,.2f}")
    print(f"  Month 12: €{totals['cash'].iloc[11]:,.2f}")
    print(f"  Month 24: €{totals['cash'].iloc[23]:,.2f}")
    print(f"  Month 36: €{totals['cash'].iloc[35]:,.2f}")
    print(f"  Month 48 (end): €{totals['cash'].iloc[47]:,.2f}")
    
    print(f"\n🏠 House Value:")
    house_out = results['outputs']['house']
    print(f"  Month 2 (purchase): €{house_out['asset_value'][1]:,.2f}")
    print(f"  Month 48 (4 years later): €{house_out['asset_value'][47]:,.2f}")
    
    print(f"\n📈 ETF Investment:")
    etf_out = results['outputs']['etf']
    print(f"  Month 4 (start): €{etf_out['asset_value'][3]:,.2f}")
    print(f"  Month 48 (4 years later): €{etf_out['asset_value'][47]:,.2f}")
    
    print(f"\n💰 Net Worth Progression:")
    print(f"  Month 2: €{totals['equity'].iloc[1]:,.2f}")
    print(f"  Month 12: €{totals['equity'].iloc[11]:,.2f}")
    print(f"  Month 24: €{totals['equity'].iloc[23]:,.2f}")
    print(f"  Month 36: €{totals['equity'].iloc[35]:,.2f}")
    print(f"  Month 48: €{totals['equity'].iloc[47]:,.2f}")
    
    print(f"\n📝 Key Events:")
    for brick_id, output in results['outputs'].items():
        if output['events']:
            print(f"  {brick_id}:")
            for event in output['events'][:3]:  # Show first 3 events
                print(f"    {event.t}: {event.message}")
            if len(output['events']) > 3:
                print(f"    ... and {len(output['events']) - 3} more events")
    
    # Show cash flow breakdown
    print(f"\n💸 Monthly Cash Flows (Sample):")
    print(f"  Month 12:")
    print(f"    Cash in: €{totals['cash_in'].iloc[11]:,.2f}")
    print(f"    Cash out: €{totals['cash_out'].iloc[11]:,.2f}")
    print(f"    Net: €{totals['net_cf'].iloc[11]:,.2f}")
    
    print(f"  Month 24:")
    print(f"    Cash in: €{totals['cash_in'].iloc[23]:,.2f}")
    print(f"    Cash out: €{totals['cash_out'].iloc[23]:,.2f}")
    print(f"    Net: €{totals['net_cf'].iloc[23]:,.2f}")
    
except AssertionError as e:
    print("❌ FAILURE:")
    print(f"   {str(e)}")

print("\n✅ House + ETF integration demo completed!")
print("\nThis demonstrates:")
print("- Realistic multi-brick financial planning")
print("- House purchase with mortgage financing")
print("- ETF investing with DCA alongside major purchases")
print("- Salary income funding investments and expenses")
print("- Liquidity management across multiple cash flows")
print("- Proper integration of all FinScenLab features")
