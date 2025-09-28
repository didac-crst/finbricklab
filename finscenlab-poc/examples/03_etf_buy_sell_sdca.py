#!/usr/bin/env python3
"""
FinScenLab Example 03: ETF Buy/Sell/SDCA

This example demonstrates the enhanced ETF strategy with:
- One-shot buys and sells
- Dollar-cost averaging (DCA) in and out
- Systematic DCA-out (SDCA) for regular withdrawals
- Dividend reinvestment
- Complete buy/sell lifecycle management

This shows how to model realistic investment strategies with systematic
accumulation and decumulation phases.
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

print("📈 FinScenLab Example 03: ETF Buy/Sell/SDCA")
print("=" * 70)

# =============================================================================
# SCENARIO SETUP
# =============================================================================

# Cash account
cash = ABrick(
    id="cash:EUR", 
    name="Investment Cash", 
    kind=K.A_CASH,
    spec={
        "initial_balance": 0.0, 
        "overdraft_limit": 0.0, 
        "min_buffer": 0.0
    }
)

# Initial capital
seed = FBrick(
    id="seed", 
    name="Initial Investment Capital", 
    kind=K.F_TRANSFER, 
    spec={"amount": 100000}  # €100k initial capital
)

# S&P 500 ETF with comprehensive buy/sell strategy
etf = ABrick(
    id="etf", 
    name="S&P 500 ETF Portfolio", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 3, 1),  # Start investing in March 2026
    end_date=date(2036, 2, 1),    # 10-year investment window
    spec={
        "price0": 100,  # €100 per unit
        "drift_pa": 0.07,  # 7% annual growth
        "div_yield_pa": 0.015,  # 1.5% dividend yield
        "initial_units": 0,
        
        # Initial investment
        "buy_at_start": {"amount": 20000},  # €20k initial investment
        
        # DCA accumulation phase (5 years)
        "dca": {
            "mode": "amount",
            "amount": 2000,  # €2k/month
            "start_offset_m": 1,  # Start after initial buy
            "months": 60,  # 5 years of accumulation
            "annual_step_pct": 0.03  # +3% per year
        },
        
        # One-shot sells for major expenses
        "sell": [
            {"t": "2029-06", "amount": 15000},  # €15k for major expense
            {"t": "2032-12", "amount": 25000}   # €25k for another expense
        ],
        
        # SDCA decumulation phase (5 years)
        "sdca": {
            "mode": "amount",
            "amount": 3000,  # €3k/month withdrawal
            "start_offset_m": 60,  # Start after accumulation phase
            "months": 60  # 5 years of decumulation
        },
        
        "reinvest_dividends": True,  # Reinvest dividends for compound growth
        "events_level": "major"  # Show major events
    }
)

# Create the scenario
scenario = Scenario(
    id="etf_buy_sell_sdca", 
    name="S&P 500 ETF: Accumulation + Decumulation Strategy",
    bricks=[cash, seed, etf]
)

print("✅ Scenario created successfully!")
print(f"📋 Scenario: {scenario.name}")
print(f"💰 Initial Capital: €{seed.spec['amount']:,.0f}")
print(f"📈 ETF: S&P 500 with {etf.spec['drift_pa']*100:.1f}% growth, {etf.spec['div_yield_pa']*100:.1f}% dividends")
print(f"🔄 Strategy: 5-year accumulation + 5-year decumulation")
print(f"💸 DCA: €{etf.spec['dca']['amount']:,.0f}/month with {etf.spec['dca']['annual_step_pct']*100:.1f}% annual step-up")
print(f"📉 SDCA: €{etf.spec['sdca']['amount']:,.0f}/month systematic withdrawal")

# =============================================================================
# RUN SIMULATION
# =============================================================================

print("\n🚀 Running simulation...")
print("-" * 50)

try:
    results = scenario.run(start=date(2026, 1, 1), months=120)  # 10 years
    validate_run(results, scenario.bricks, mode="raise")
    print("✅ Simulation completed successfully!")
    
except AssertionError as e:
    print("❌ Simulation failed validation:")
    print(f"   {str(e)}")
    exit(1)

# =============================================================================
# RESULTS ANALYSIS
# =============================================================================

print("\n📊 RESULTS ANALYSIS")
print("=" * 70)

# Extract key outputs
etf_out = results['outputs']['etf']
totals = results['totals']

# Show ETF value progression
print("\n📈 ETF VALUE PROGRESSION:")
print("-" * 40)
for i in range(0, 120, 12):  # Every year
    year = i // 12 + 1
    etf_value = etf_out['asset_value'][i]
    cash_flow = etf_out['cash_in'][i] - etf_out['cash_out'][i]
    phase = "Accumulation" if i < 60 else "Decumulation"
    print(f"  Year {year:2d} ({phase:12s}): ETF €{etf_value:8,.0f}, Net CF €{cash_flow:6,.0f}")

# Show DCA events (sample)
print("\n💰 DCA EVENTS (Sample):")
print("-" * 40)
dca_events = [e for e in etf_out['events'] if 'dca' in e.message.lower()]
for event in dca_events[:6]:  # Show first 6 DCA events
    print(f"  {event.t}: {event.message}")

# Show sell events
print("\n💸 SELL EVENTS:")
print("-" * 40)
sell_events = [e for e in etf_out['events'] if 'sell' in e.message.lower()]
for event in sell_events:
    print(f"  {event.t}: {event.message}")

# Show SDCA events (sample)
print("\n📉 SDCA EVENTS (Sample):")
print("-" * 40)
sdca_events = [e for e in etf_out['events'] if 'sdca' in e.message.lower()]
for event in sdca_events[:6]:  # Show first 6 SDCA events
    print(f"  {event.t}: {event.message}")

# Show dividend events (sample)
print("\n💎 DIVIDEND EVENTS (Sample):")
print("-" * 40)
div_events = [e for e in etf_out['events'] if 'div' in e.message.lower()]
for event in div_events[:6]:  # Show first 6 dividend events
    print(f"  {event.t}: {event.message}")

# Show final financial position
print("\n💼 FINAL FINANCIAL POSITION:")
print("-" * 40)
final_cash = totals['cash'].iloc[-1]
final_assets = totals['assets'].iloc[-1]
final_equity = totals['equity'].iloc[-1]

print(f"  Cash Balance:     €{final_cash:,.0f}")
print(f"  Total Assets:     €{final_assets:,.0f}")
print(f"  Net Worth:        €{final_equity:,.0f}")

# Calculate key metrics
print("\n📈 INVESTMENT METRICS:")
print("-" * 40)
total_invested = sum(etf_out['cash_out'])
total_withdrawn = sum(etf_out['cash_in'])
net_investment = total_invested - total_withdrawn
final_value = etf_out['asset_value'][-1]
total_return = final_value - net_investment
return_pct = (total_return / net_investment) * 100 if net_investment > 0 else 0

print(f"  Total Invested:   €{total_invested:,.0f}")
print(f"  Total Withdrawn:  €{total_withdrawn:,.0f}")
print(f"  Net Investment:   €{net_investment:,.0f}")
print(f"  Final Value:      €{final_value:,.0f}")
print(f"  Total Return:     €{total_return:,.0f}")
print(f"  Return %:         {return_pct:.1f}%")

# Show phase analysis
print("\n🔄 PHASE ANALYSIS:")
print("-" * 40)
accumulation_phase = etf_out['cash_out'][:60].sum()
decumulation_phase = etf_out['cash_in'][60:].sum()
peak_value = etf_out['asset_value'].max()
peak_month = etf_out['asset_value'].argmax()

print(f"  Accumulation Phase: €{accumulation_phase:,.0f} invested")
print(f"  Decumulation Phase: €{decumulation_phase:,.0f} withdrawn")
print(f"  Peak Value: €{peak_value:,.0f} at month {peak_month}")

# =============================================================================
# LESSONS LEARNED
# =============================================================================

print("\n🎓 LESSONS LEARNED:")
print("=" * 70)
print("1. 📈 DCA reduces timing risk and smooths market volatility")
print("2. 💰 Annual step-ups in DCA can match salary growth")
print("3. 📉 SDCA provides systematic income in retirement")
print("4. 💎 Dividend reinvestment accelerates compound growth")
print("5. 🎯 One-shot sells can fund major expenses without disrupting strategy")
print("6. ⏰ Activation windows enable precise timing of investment phases")
print("7. 📊 Systematic approaches outperform emotional trading")

print("\n✅ Example 03 completed successfully!")
print("\nThis example demonstrates a complete investment lifecycle:")
print("- Systematic accumulation with DCA and step-ups")
print("- Strategic one-shot sells for major expenses")
print("- Systematic decumulation with SDCA")
print("- Dividend reinvestment for compound growth")
print("- Integration with activation windows")
print("- Comprehensive event tracking and analysis")
