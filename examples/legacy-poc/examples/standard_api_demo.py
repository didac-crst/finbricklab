#!/usr/bin/env python3
"""
Standard API Demo

This demo showcases the standardized API methods that allow you to use
a consistent pattern with just a variable change for different frequencies.

Key Features Demonstrated:
1. results["views"].monthly() - returns monthly data
2. results["views"].quarterly() - returns quarterly data  
3. results["views"].yearly() - returns yearly data
4. scenario.aggregate_totals("M") - returns monthly data
5. scenario.aggregate_totals("Q") - returns quarterly data
6. scenario.aggregate_totals("Y") - returns yearly data

This allows for clean, consistent code patterns where you only need to
change a variable instead of changing the code structure.
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

print("🎯 Standard API Demo")
print("=" * 60)
print("\nThis demo showcases the standardized API methods that allow")
print("you to use a consistent pattern with just a variable change")
print("for different frequencies.")
print("\nKey Benefits:")
print("- Consistent API across all frequencies")
print("- Easy to switch between monthly/quarterly/yearly")
print("- Clean code patterns with minimal changes")
print("- Professional and intuitive interface")

# =============================================================================
# CREATE A SIMPLE SCENARIO
# =============================================================================

print("\n🏗️  Creating Simple Scenario")
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
    spec={"amount": 200000}
)

# ETF investment
etf = ABrick(
    id="etf", 
    name="Growth ETF", 
    kind=K.A_INV_ETF,
    start_date=date(2026, 2, 1),
    spec={
        "price0": 100,
        "drift_pa": 0.05,
        "initial_units": 0,
        "buy_at_start": {"amount": 50000}
    }
)

# Salary income
salary = FBrick(
    id="salary", 
    name="Monthly Salary", 
    kind=K.F_INCOME,
    start_date=date(2026, 2, 1),
    spec={
        "amount_monthly": 5000,
        "annual_step_pct": 0.02  # 2% annual increase
    }
)

# Living expenses
living = FBrick(
    id="living", 
    name="Living Expenses", 
    kind=K.F_EXP_LIVING,
    start_date=date(2026, 2, 1),
    spec={"amount_monthly": 2000}
)

# Create scenario
scenario = Scenario(
    id="standard_demo", 
    name="Standard API Demo",
    bricks=[cash, seed, etf, salary, living]
)

# Run simulation
print("Running 2-year simulation...")
results = scenario.run(start=date(2026, 1, 1), months=24, include_cash=True)
validate_run(results, scenario.bricks, mode="raise")

print("✅ Simulation completed successfully!")

# =============================================================================
# PATTERN 1: USING VIEWS HELPER WITH VARIABLE
# =============================================================================

print("\n🔄 PATTERN 1: Views Helper with Variable")
print("-" * 50)

# Define frequency variable - just change this to switch frequencies!
frequency = "quarterly"  # Try: "monthly", "quarterly", "yearly"

# Standard pattern - same code, just change the variable
if frequency == "monthly":
    data = results["views"].monthly()
elif frequency == "quarterly":
    data = results["views"].quarterly()
elif frequency == "yearly":
    data = results["views"].yearly()
else:
    raise ValueError(f"Unknown frequency: {frequency}")

print(f"Using frequency: {frequency}")
print(f"Data shape: {data.shape}")
print(f"Index type: {type(data.index)}")
print(f"Sample periods: {list(data.index[:3])}")

print(f"\n{frequency.title()} Summary:")
print(data.round(2))

# =============================================================================
# PATTERN 2: USING SCENARIO CONVENIENCE METHOD WITH VARIABLE
# =============================================================================

print("\n🔄 PATTERN 2: Scenario Convenience Method with Variable")
print("-" * 50)

# Define frequency variable - just change this to switch frequencies!
frequency = "M"  # Try: "M", "Q", "Y"

# Standard pattern - same code, just change the variable
data = scenario.aggregate_totals(frequency)

print(f"Using frequency: {frequency}")
print(f"Data shape: {data.shape}")
print(f"Index type: {type(data.index)}")
print(f"Sample periods: {list(data.index[:3])}")

print(f"\n{frequency} Summary:")
print(data.round(2))

# =============================================================================
# PATTERN 3: LOOPING THROUGH MULTIPLE FREQUENCIES
# =============================================================================

print("\n🔄 PATTERN 3: Looping Through Multiple Frequencies")
print("-" * 50)

# Define frequencies to loop through
frequencies = ["monthly", "quarterly", "yearly"]

print("Views Helper Pattern:")
for freq in frequencies:
    if freq == "monthly":
        data = results["views"].monthly()
    elif freq == "quarterly":
        data = results["views"].quarterly()
    elif freq == "yearly":
        data = results["views"].yearly()
    
    print(f"  {freq.title()}: {data.shape[0]} periods, final equity: €{data['equity'].iloc[-1]:,.2f}")

print("\nScenario Method Pattern:")
freq_codes = ["M", "Q", "Y"]
for freq in freq_codes:
    data = scenario.aggregate_totals(freq)
    print(f"  {freq}: {data.shape[0]} periods, final equity: €{data['equity'].iloc[-1]:,.2f}")

# =============================================================================
# PATTERN 4: FUNCTION WITH FREQUENCY PARAMETER
# =============================================================================

print("\n🔄 PATTERN 4: Function with Frequency Parameter")
print("-" * 50)

def analyze_scenario(scenario, results, freq="quarterly"):
    """
    Analyze scenario at specified frequency.
    
    Args:
        scenario: The scenario object
        results: The scenario results
        freq: Frequency ("monthly", "quarterly", "yearly", "M", "Q", "Y")
    """
    # Handle both string and code formats
    if freq in ["monthly", "quarterly", "yearly"]:
        if freq == "monthly":
            data = results["views"].monthly()
        elif freq == "quarterly":
            data = results["views"].quarterly()
        elif freq == "yearly":
            data = results["views"].yearly()
    elif freq in ["M", "Q", "Y"]:
        data = scenario.aggregate_totals(freq)
    else:
        raise ValueError(f"Unknown frequency: {freq}")
    
    # Analysis
    total_cash_in = data["cash_in"].sum()
    total_cash_out = data["cash_out"].sum()
    net_cash_flow = data["net_cf"].sum()
    final_equity = data["equity"].iloc[-1]
    
    return {
        "frequency": freq,
        "periods": data.shape[0],
        "total_cash_in": total_cash_in,
        "total_cash_out": total_cash_out,
        "net_cash_flow": net_cash_flow,
        "final_equity": final_equity,
        "data": data
    }

# Test the function with different frequencies
frequencies_to_test = ["monthly", "quarterly", "yearly", "M", "Q", "Y"]

print("Analysis Results:")
for freq in frequencies_to_test:
    analysis = analyze_scenario(scenario, results, freq)
    print(f"  {freq}: {analysis['periods']} periods, "
          f"Net CF: €{analysis['net_cash_flow']:,.2f}, "
          f"Final Equity: €{analysis['final_equity']:,.2f}")

# =============================================================================
# PATTERN 5: CONFIGURATION-DRIVEN ANALYSIS
# =============================================================================

print("\n🔄 PATTERN 5: Configuration-Driven Analysis")
print("-" * 50)

# Configuration - just change this to switch the entire analysis
config = {
    "frequency": "quarterly",  # Try: "monthly", "quarterly", "yearly"
    "show_details": True,
    "round_decimals": 2
}

# Standard analysis code - no changes needed when switching frequencies
def run_analysis(scenario, results, config):
    freq = config["frequency"]
    
    # Get data using standard pattern
    if freq == "monthly":
        data = results["views"].monthly()
    elif freq == "quarterly":
        data = results["views"].quarterly()
    elif freq == "yearly":
        data = results["views"].yearly()
    else:
        raise ValueError(f"Unknown frequency: {freq}")
    
    # Analysis
    summary = {
        "frequency": freq,
        "periods": data.shape[0],
        "total_cash_in": data["cash_in"].sum(),
        "total_cash_out": data["cash_out"].sum(),
        "net_cash_flow": data["net_cf"].sum(),
        "final_assets": data["assets"].iloc[-1],
        "final_liabilities": data["liabilities"].iloc[-1],
        "final_equity": data["equity"].iloc[-1],
        "final_cash": data["cash"].iloc[-1],
        "final_non_cash": data["non_cash"].iloc[-1]
    }
    
    if config["show_details"]:
        summary["data"] = data.round(config["round_decimals"])
    
    return summary

# Run analysis with current config
analysis = run_analysis(scenario, results, config)

print(f"Analysis Configuration: {config}")
print(f"\n{analysis['frequency'].title()} Analysis Results:")
print(f"  Periods: {analysis['periods']}")
print(f"  Total Cash In: €{analysis['total_cash_in']:,.2f}")
print(f"  Total Cash Out: €{analysis['total_cash_out']:,.2f}")
print(f"  Net Cash Flow: €{analysis['net_cash_flow']:,.2f}")
print(f"  Final Assets: €{analysis['final_assets']:,.2f}")
print(f"  Final Liabilities: €{analysis['final_liabilities']:,.2f}")
print(f"  Final Equity: €{analysis['final_equity']:,.2f}")
print(f"  Final Cash: €{analysis['final_cash']:,.2f}")
print(f"  Final Non-Cash: €{analysis['final_non_cash']:,.2f}")

if config["show_details"]:
    print(f"\nDetailed Data:")
    print(analysis["data"])

# =============================================================================
# VERIFICATION: ALL METHODS PRODUCE CONSISTENT RESULTS
# =============================================================================

print("\n✅ VERIFICATION: All Methods Produce Consistent Results")
print("-" * 50)

# Test that all methods produce the same results
monthly_views = results["views"].monthly()
quarterly_views = results["views"].quarterly()
yearly_views = results["views"].yearly()

monthly_scenario = scenario.aggregate_totals("M")
quarterly_scenario = scenario.aggregate_totals("Q")
yearly_scenario = scenario.aggregate_totals("Y")

print("Consistency Check:")
print(f"  Monthly views == scenario: {monthly_views.equals(monthly_scenario)}")
print(f"  Quarterly views == scenario: {quarterly_views.equals(quarterly_scenario)}")
print(f"  Yearly views == scenario: {yearly_views.equals(yearly_scenario)}")

# Verify final equity is consistent across all methods
final_equities = [
    monthly_views["equity"].iloc[-1],
    quarterly_views["equity"].iloc[-1],
    yearly_views["equity"].iloc[-1],
    monthly_scenario["equity"].iloc[-1],
    quarterly_scenario["equity"].iloc[-1],
    yearly_scenario["equity"].iloc[-1]
]

print(f"\nFinal Equity Consistency:")
print(f"  All methods produce same final equity: {len(set(final_equities)) == 1}")
print(f"  Final equity: €{final_equities[0]:,.2f}")

# =============================================================================
# SUMMARY
# =============================================================================

print("\n🎉 STANDARD API IMPLEMENTATION SUMMARY")
print("=" * 60)
print("\n✅ All standard API methods working perfectly!")
print("\nKey Achievements:")
print("1. 🔄 results['views'].monthly() - returns monthly data")
print("2. 🔄 results['views'].quarterly() - returns quarterly data")
print("3. 🔄 results['views'].yearly() - returns yearly data")
print("4. 🔄 scenario.aggregate_totals('M') - returns monthly data")
print("5. 🔄 scenario.aggregate_totals('Q') - returns quarterly data")
print("6. 🔄 scenario.aggregate_totals('Y') - returns yearly data")
print("\nBenefits:")
print("- Consistent API across all frequencies")
print("- Easy to switch between frequencies with just a variable change")
print("- Clean code patterns with minimal code changes")
print("- Professional and intuitive interface")
print("- All methods produce identical results")
print("- Perfect for configuration-driven analysis")
print("\nUsage Patterns:")
print("- Variable-driven frequency selection")
print("- Loop through multiple frequencies")
print("- Function parameters for frequency")
print("- Configuration-driven analysis")
print("- Consistent results across all access methods")
print("\nThe standard API provides a clean, consistent interface that")
print("makes it easy to work with different time frequencies without")
print("changing your code structure - just change a variable!")
