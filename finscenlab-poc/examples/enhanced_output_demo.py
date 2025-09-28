#!/usr/bin/env python3
"""
Enhanced Scenario Output Demo

This demo showcases the enhanced scenario output features:
1. Changed "debt" to "liabilities" for better clarity
2. Added "non_cash" column to show non-cash assets (properties, ETFs, etc.)
3. Added quarterly and yearly aggregation options for better time analysis

Key Features Demonstrated:
- Monthly, quarterly, and yearly views of scenario results
- Clear separation of cash vs non-cash assets
- Better terminology with "liabilities" instead of "debt"
- Flexible time aggregation for different analysis needs
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
import pandas as pd

print("🎯 Enhanced Scenario Output Demo")
print("=" * 60)
print("\nThis demo showcases the enhanced scenario output features:")
print("1. Changed 'debt' to 'liabilities' for better clarity")
print("2. Added 'non_cash' column to show non-cash assets")
print("3. Added quarterly and yearly aggregation options")
print("\nKey Benefits:")
print("- Better terminology and clarity")
print("- Clear separation of cash vs non-cash assets")
print("- Flexible time aggregation for analysis")
print("- Professional financial reporting format")

# =============================================================================
# CREATE A COMPREHENSIVE SCENARIO
# =============================================================================

print("\n🏗️  Creating Comprehensive Scenario")
print("-" * 50)

# Cash account
cash = ABrick(
    id="cash:EUR", 
    name="Main Cash", 
    kind=K.A_CASH,
    spec={"initial_balance": 0.0, "overdraft_limit": 0.0, "min_buffer": 0.0}
)

# Initial capital
seed = FBrick(
    id="seed", 
    name="Initial Capital", 
    kind=K.F_TRANSFER, 
    spec={"amount": 500000}
)

# Investment property
house = ABrick(
    id="house", 
    name="Investment Property", 
    kind=K.A_PROPERTY,
    start_date=date(2026, 2, 1),
    end_date=date(2028, 6, 1),  # 2.5-year window
    spec={
        "price": 400000,
        "fees_pct": 0.08,
        "appreciation_pa": 0.025,
        "down_payment": 80000,
        "finance_fees": True,
        "sell_on_window_end": True,
        "sell_fees_pct": 0.05
    }
)

# ETF investment
etf = ABrick(
    id="etf", 
    name="Growth ETF", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 3, 1),
    end_date=date(2027, 12, 1),  # 22-month window
    spec={
        "price0": 100,
        "drift_pa": 0.06,
        "initial_units": 0,
        "buy_at_start": {"amount": 100000},
        "liquidate_on_window_end": True,
        "sell_fees_pct": 0.01
    }
)

# Mortgage
mortgage = LBrick(
    id="mortgage", 
    name="Investment Mortgage", 
    kind=K.L_MORT_ANN,
    start_date=date(2026, 2, 1),
    end_date=date(2028, 6, 1),  # 2.5-year window
    spec={
        "principal": 320000,
        "rate_pa": 0.035,
        "term_months": 300,  # 25-year amortization
        "first_payment_offset": 1,
        "balloon_policy": "payoff"
    }
)

# Salary income
salary = FBrick(
    id="salary", 
    name="Monthly Salary", 
    kind=K.F_INCOME,
    start_date=date(2026, 2, 1),
    spec={
        "amount_monthly": 8000,
        "annual_step_pct": 0.03,  # 3% annual increase
        "step_month": 1  # January increases
    }
)

# Living expenses
living = FBrick(
    id="living", 
    name="Living Expenses", 
    kind=K.F_EXP_LIVING,
    start_date=date(2026, 2, 1),
    spec={"amount_monthly": 3000}
)

# Create scenario
scenario = Scenario(
    id="enhanced_demo", 
    name="Enhanced Output Demo",
    bricks=[cash, seed, house, etf, mortgage, salary, living]
)

# Run simulation
print("Running 3-year simulation...")
results = scenario.run(start=date(2026, 1, 1), months=36, include_cash=True)
validate_run(results, scenario.bricks, mode="raise")

print("✅ Simulation completed successfully!")

# =============================================================================
# MONTHLY VIEW
# =============================================================================

print("\n📅 MONTHLY VIEW")
print("-" * 50)

monthly = results["totals"]
print(f"Monthly data shape: {monthly.shape}")
print(f"Columns: {list(monthly.columns)}")
print(f"Date range: {monthly.index[0]} to {monthly.index[-1]}")

print("\nFirst 6 months:")
print(monthly.head(6).round(2))

print("\nLast 6 months:")
print(monthly.tail(6).round(2))

# =============================================================================
# QUARTERLY VIEW
# =============================================================================

print("\n📊 QUARTERLY VIEW")
print("-" * 50)

quarterly = scenario.aggregate_totals(results["totals"], "quarterly")
print(f"Quarterly data shape: {quarterly.shape}")
print(f"Date range: {quarterly.index[0]} to {quarterly.index[-1]}")

print("\nQuarterly Summary:")
print(quarterly.round(2))

# Show key metrics
print(f"\n📈 Key Quarterly Metrics:")
print(f"  Total Cash In:  €{quarterly['cash_in'].sum():,.2f}")
print(f"  Total Cash Out: €{quarterly['cash_out'].sum():,.2f}")
print(f"  Net Cash Flow:  €{quarterly['net_cf'].sum():,.2f}")
print(f"  Final Assets:   €{quarterly['assets'].iloc[-1]:,.2f}")
print(f"  Final Liabilities: €{quarterly['liabilities'].iloc[-1]:,.2f}")
print(f"  Final Equity:   €{quarterly['equity'].iloc[-1]:,.2f}")

# =============================================================================
# YEARLY VIEW
# =============================================================================

print("\n📈 YEARLY VIEW")
print("-" * 50)

yearly = scenario.aggregate_totals(results["totals"], "yearly")
print(f"Yearly data shape: {yearly.shape}")
print(f"Date range: {yearly.index[0]} to {yearly.index[-1]}")

print("\nYearly Summary:")
print(yearly.round(2))

# Show key metrics
print(f"\n📈 Key Yearly Metrics:")
print(f"  Total Cash In:  €{yearly['cash_in'].sum():,.2f}")
print(f"  Total Cash Out: €{yearly['cash_out'].sum():,.2f}")
print(f"  Net Cash Flow:  €{yearly['net_cf'].sum():,.2f}")
print(f"  Final Assets:   €{yearly['assets'].iloc[-1]:,.2f}")
print(f"  Final Liabilities: €{yearly['liabilities'].iloc[-1]:,.2f}")
print(f"  Final Equity:   €{yearly['equity'].iloc[-1]:,.2f}")

# =============================================================================
# ASSET BREAKDOWN ANALYSIS
# =============================================================================

print("\n💰 ASSET BREAKDOWN ANALYSIS")
print("-" * 50)

# Analyze the final month
final_month = monthly.iloc[-1]
print(f"Final Month Analysis ({monthly.index[-1]}):")
print(f"  Total Assets:     €{final_month['assets']:,.2f}")
print(f"  Cash Assets:      €{final_month['cash']:,.2f}")
print(f"  Non-Cash Assets:  €{final_month['non_cash']:,.2f}")
print(f"  Liabilities:      €{final_month['liabilities']:,.2f}")
print(f"  Equity:           €{final_month['equity']:,.2f}")

# Calculate percentages
cash_pct = (final_month['cash'] / final_month['assets']) * 100
non_cash_pct = (final_month['non_cash'] / final_month['assets']) * 100
leverage_ratio = final_month['liabilities'] / final_month['assets']

print(f"\n📊 Asset Composition:")
print(f"  Cash:             {cash_pct:.1f}%")
print(f"  Non-Cash:         {non_cash_pct:.1f}%")
print(f"  Leverage Ratio:   {leverage_ratio:.2f}")

# =============================================================================
# CASH FLOW ANALYSIS
# =============================================================================

print("\n💸 CASH FLOW ANALYSIS")
print("-" * 50)

# Monthly cash flow analysis
monthly_cf = monthly[['cash_in', 'cash_out', 'net_cf']].copy()
monthly_cf['cumulative_cf'] = monthly_cf['net_cf'].cumsum()

print("Monthly Cash Flow Summary:")
print(monthly_cf.describe().round(2))

# Quarterly cash flow analysis
quarterly_cf = quarterly[['cash_in', 'cash_out', 'net_cf']].copy()
quarterly_cf['cumulative_cf'] = quarterly_cf['net_cf'].cumsum()

print(f"\nQuarterly Cash Flow Summary:")
print(quarterly_cf.round(2))

# =============================================================================
# EQUITY GROWTH ANALYSIS
# =============================================================================

print("\n📈 EQUITY GROWTH ANALYSIS")
print("-" * 50)

# Calculate equity growth rates
monthly['equity_growth'] = monthly['equity'].pct_change() * 100
quarterly['equity_growth'] = quarterly['equity'].pct_change() * 100
yearly['equity_growth'] = yearly['equity'].pct_change() * 100

print("Equity Growth Rates:")
print(f"  Monthly Average:  {monthly['equity_growth'].mean():.2f}%")
print(f"  Quarterly Average: {quarterly['equity_growth'].mean():.2f}%")
print(f"  Yearly Average:   {yearly['equity_growth'].mean():.2f}%")

# Total return
initial_equity = monthly['equity'].iloc[0]
final_equity = monthly['equity'].iloc[-1]
total_return = ((final_equity - initial_equity) / initial_equity) * 100

print(f"\nTotal Return Analysis:")
print(f"  Initial Equity:   €{initial_equity:,.2f}")
print(f"  Final Equity:     €{final_equity:,.2f}")
print(f"  Total Return:     {total_return:.2f}%")

# =============================================================================
# COMPARISON: MONTHLY vs QUARTERLY vs YEARLY
# =============================================================================

print("\n🔄 COMPARISON: MONTHLY vs QUARTERLY vs YEARLY")
print("-" * 50)

print("Data Points Comparison:")
print(f"  Monthly:   {len(monthly)} data points")
print(f"  Quarterly: {len(quarterly)} data points")
print(f"  Yearly:    {len(yearly)} data points")

print(f"\nFinal Equity Comparison:")
print(f"  Monthly:   €{monthly['equity'].iloc[-1]:,.2f}")
print(f"  Quarterly: €{quarterly['equity'].iloc[-1]:,.2f}")
print(f"  Yearly:    €{yearly['equity'].iloc[-1]:,.2f}")

print(f"\nTotal Cash Flow Comparison:")
print(f"  Monthly:   €{monthly['net_cf'].sum():,.2f}")
print(f"  Quarterly: €{quarterly['net_cf'].sum():,.2f}")
print(f"  Yearly:    €{yearly['net_cf'].sum():,.2f}")

# =============================================================================
# SUMMARY
# =============================================================================

print("\n🎉 ENHANCED OUTPUT FEATURES SUMMARY")
print("=" * 60)
print("\n✅ All enhanced output features working perfectly!")
print("\nKey Achievements:")
print("1. 🏷️  Changed 'debt' to 'liabilities' for better clarity")
print("2. 💰 Added 'non_cash' column to separate cash from other assets")
print("3. 📅 Added quarterly and yearly aggregation options")
print("4. 📊 Flexible time analysis for different reporting needs")
print("5. 🔍 Enhanced asset breakdown and composition analysis")
print("6. 💸 Comprehensive cash flow analysis across time periods")
print("7. 📈 Equity growth analysis with multiple time horizons")
print("\nTechnical Benefits:")
print("- Better terminology aligns with financial standards")
print("- Clear separation of cash vs non-cash assets")
print("- Flexible time aggregation for different analysis needs")
print("- Professional financial reporting format")
print("- Enhanced data analysis capabilities")
print("- Better visualization and reporting options")
print("\nThe enhanced output provides a much more professional and")
print("flexible way to analyze financial scenarios across different")
print("time horizons and asset categories.")
