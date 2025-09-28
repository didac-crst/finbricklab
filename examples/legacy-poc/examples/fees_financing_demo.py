#!/usr/bin/env python3
"""
FinScenLab Fees Financing Demo

This script demonstrates the new fees financing feature with time-stamped events,
validation, and kind constants.
"""

# Fix the import path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the core components
from datetime import date
from finscenlab.core import Scenario, ABrick, LBrick, FBrick, validate_run, export_run_json, export_ledger_csv
from finscenlab.kinds import K
import finscenlab.strategies  # This registers the default strategies
import pandas as pd
import json

print("✅ All imports successful!")

# Create a scenario demonstrating fees financing
print("\n🏗️  Creating financial bricks with fees financing...")

# Cash account
cash = ABrick(
    id="cash:EUR", 
    name="Main Cash Account", 
    kind=K.A_CASH,  # Using kind constants!
    spec={
        "initial_balance": 100_000,  # Start with some money
        "interest_pa": 0.02
    }
)

# Seed money
seed = FBrick(
    id="seed", 
    name="Initial Capital", 
    kind=K.F_TRANSFER,
    spec={"amount": 200_000}
)

# Salary
salary = FBrick(
    id="salary", 
    name="Monthly Salary", 
    kind=K.F_INCOME,
    spec={"amount_monthly": 5_000}
)

# Living expenses
living = FBrick(
    id="living", 
    name="Living Expenses", 
    kind=K.F_EXP_LIVING,
    spec={"amount_monthly": 2_000}
)

# House with PARTIAL fees financing (50% financed, 50% cash)
house = ABrick(
    id="house_tls", 
    name="Toulouse Flat", 
    kind=K.A_PROPERTY,
    start_date=date(2027, 1, 1),  # Buy in 2027
    spec={
        "price": 500_000,
        "fees_pct": 0.10,  # 10% fees
        "appreciation_pa": 0.025,  # 2.5% appreciation
        "down_payment": 100_000,
        "finance_fees": True,  # Enable fees financing
        "fees_financed_pct": 0.5  # 50% of fees financed, 50% cash
    }
)

# Mortgage with auto-calculated principal including financed fees
mortgage = LBrick(
    id="mort_10y", 
    name="25-Year Fixed Mortgage", 
    kind=K.L_MORT_ANN,
    start_date=date(2027, 1, 1),  # Same as house
    links={"auto_principal_from": "house_tls"},
    spec={
        "rate_pa": 0.035,  # 3.5% rate
        "term_months": 300  # 25 years
    }
)

print("✅ Created all bricks:")
print(f"  - Cash account: starts immediately")
print(f"  - Seed money: €{seed.spec['amount']:,} - starts immediately")
print(f"  - Salary: €{salary.spec['amount_monthly']:,}/month - starts immediately")
print(f"  - Living expenses: €{living.spec['amount_monthly']:,}/month - starts immediately")
print(f"  - House: €{house.spec['price']:,} - starts {house.start_date}")
print(f"    Fees: {house.spec['fees_pct']*100:.1f}% = €{house.spec['price'] * house.spec['fees_pct']:,.2f}")
print(f"    Fees financing: {house.spec['fees_financed_pct']*100:.1f}% financed, {(1-house.spec['fees_financed_pct'])*100:.1f}% cash")
print(f"  - Mortgage: linked to house - starts {mortgage.start_date}")

# Create the scenario
print("\n🎯 Creating scenario...")
scenario = Scenario(
    id="fees_demo", 
    name="Fees Financing Demo", 
    bricks=[cash, seed, salary, living, house, mortgage]
)

print(f"✅ Scenario created: {scenario.name}")

# Run the simulation for 3 years (36 months)
print("\n🚀 Running 3-year simulation...")
results = scenario.run(start=date(2026, 1, 1), months=36)

print("✅ Simulation completed!")

# Validate the results
print("\n🔍 Validating results...")
try:
    validate_run(results, mode="raise")
    print("✅ All validation checks passed!")
except AssertionError as e:
    print(f"❌ Validation failed: {e}")

# Show key milestones
print("\n📊 Key Milestones:")
print("=" * 70)

# Month 1 (2026-01)
month_1 = results["totals"].iloc[0]
print(f"2026-01: Initial setup")
print(f"  Cash In:  €{month_1['cash_in']:,.2f}")
print(f"  Net Worth: €{month_1['equity']:,.2f}")

# Month 13 (2027-01) - House purchase
month_13 = results["totals"].iloc[12]
print(f"\n2027-01: House purchase")
print(f"  Cash Out: €{month_13['cash_out']:,.2f}")
print(f"  Net Worth: €{month_13['equity']:,.2f}")

# Month 36 (2028-12) - End of simulation
month_36 = results["totals"].iloc[-1]
print(f"\n2028-12: End of simulation")
print(f"  Cash In:  €{month_36['cash_in']:,.2f}")
print(f"  Cash Out: €{month_36['cash_out']:,.2f}")
print(f"  Net Worth: €{month_36['equity']:,.2f}")

# Show all events with timestamps
print(f"\n📝 Time-Stamped Events:")
print("=" * 70)
all_events = []
for brick_id, output in results['outputs'].items():
    for event in output['events']:
        all_events.append((event.t, brick_id, event.kind, event.message))

# Sort events by time
all_events.sort(key=lambda x: x[0])

for t, brick_id, kind, message in all_events:
    print(f"{t}: {brick_id} [{kind}] - {message}")

# Show mortgage details
print(f"\n🏠 Mortgage Details:")
print("=" * 70)
if "_derived" in mortgage.spec:
    derived = mortgage.spec["_derived"]
    print(f"Property price: €{derived['price']:,.2f}")
    print(f"Down payment: €{derived['down_payment']:,.2f}")
    print(f"Total fees: €{derived['fees']:,.2f}")
    print(f"Fees financed: €{derived['fees_financed']:,.2f}")
    print(f"Fees paid cash: €{derived['fees'] - derived['fees_financed']:,.2f}")
    print(f"Mortgage principal: €{mortgage.spec['principal']:,.2f}")
    print(f"  = Price - Down + Fees Financed")
    print(f"  = €{derived['price']:,.2f} - €{derived['down_payment']:,.2f} + €{derived['fees_financed']:,.2f}")

# Export results to Excel
print("\n📊 Exporting results to Excel...")

# Create a DataFrame with each brick as a column
excel_data = {}

# Add time index
excel_data['Month'] = results['totals'].index

# Add each brick's cash flows and values
for brick_id, output in results['outputs'].items():
    brick_name = next(brick.name for brick in scenario.bricks if brick.id == brick_id)
    
    # Cash flows
    excel_data[f'{brick_name}_CashIn'] = output['cash_in']
    excel_data[f'{brick_name}_CashOut'] = output['cash_out']
    
    # Asset values (for assets)
    if output['asset_value'].any():
        excel_data[f'{brick_name}_AssetValue'] = output['asset_value']
    
    # Debt balances (for liabilities)
    if output['debt_balance'].any():
        excel_data[f'{brick_name}_DebtBalance'] = output['debt_balance']

# Add aggregated totals
excel_data['Total_CashIn'] = results['totals']['cash_in']
excel_data['Total_CashOut'] = results['totals']['cash_out']
excel_data['Total_Assets'] = results['totals']['assets']
excel_data['Total_Debt'] = results['totals']['debt']
excel_data['Equity'] = results['totals']['equity']

# Create DataFrame and export to Excel
df = pd.DataFrame(excel_data)
excel_filename = 'fees_financing_results.xlsx'

# Export with formatting
with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
    # Main results sheet
    df.to_excel(writer, sheet_name='Results', index=False)
    
    # Get the workbook and worksheet for formatting
    workbook = writer.book
    worksheet = writer.sheets['Results']
    
    # Format currency columns (all columns except Month)
    from openpyxl.styles import NamedStyle
    currency_style = NamedStyle(name="currency")
    currency_style.number_format = '€#,##0.00'
    
    # Apply currency formatting to all numeric columns
    for col in range(2, len(df.columns) + 1):  # Skip Month column (col 1)
        for row in range(2, len(df) + 2):  # Skip header row
            worksheet.cell(row=row, column=col).number_format = '€#,##0.00'
    
    # Auto-adjust column widths
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 20)  # Cap at 20 characters
        worksheet.column_dimensions[column_letter].width = adjusted_width

print(f"✅ Results exported to: {excel_filename}")
print(f"   Rows: {len(df)} months")
print(f"   Columns: {len(df.columns)} (including {len(scenario.bricks)} bricks + totals)")
print(f"   Format: Excel with currency formatting and auto-sized columns")

# Export to enhanced JSON format
print("\n📊 Exporting results to enhanced JSON...")
json_filename = 'fees_financing_results_enhanced.json'
export_run_json(json_filename, scenario, results, include_specs=True, precision=2)

print(f"✅ Enhanced JSON exported to: {json_filename}")
print(f"   Includes: Series data, events, validation results, and brick specs")

# Export to ledger CSV format
print("\n📊 Exporting results to ledger CSV...")
ledger_filename = 'fees_financing_ledger.csv'
export_ledger_csv(ledger_filename, results)

print(f"✅ Ledger CSV exported to: {ledger_filename}")
print(f"   Format: One row per cash flow/event for easy analysis")

# Show a preview of the data
print(f"\n📋 Excel Preview (first 5 rows):")
print("=" * 80)
print(df.head().to_string(index=False))

# Show JSON structure preview
print(f"\n📋 Enhanced Export Files Created:")
print("=" * 80)
print(f"✅ Excel: fees_financing_results.xlsx (professional formatting)")
print(f"✅ Enhanced JSON: fees_financing_results_enhanced.json (structured data + events + validation)")
print(f"✅ Ledger CSV: fees_financing_ledger.csv (transaction-level detail)")

print("\n✅ Fees financing demo completed!")
print("\nThis demonstrates:")
print("- Fees financing with partial financing (50% financed, 50% cash)")
print("- Time-stamped events for audit trail")
print("- Automatic validation of financial invariants")
print("- Kind constants preventing typos")
print("- Proper cash flow routing and timing")
print(f"- Excel export with detailed brick-by-brick breakdown and currency formatting")
print(f"- Enhanced JSON export with events, validation results, and brick specifications")
print(f"- Ledger CSV export for easy transaction analysis")
