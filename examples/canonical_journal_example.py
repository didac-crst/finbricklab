#!/usr/bin/env python3
"""
Canonical Journal Structure Example

This example demonstrates the new canonical journal structure in FinBrickLab,
showing how the enhanced journal system provides self-documenting record IDs
and primary columns for easy analysis.
"""

from datetime import date

import pandas as pd
from finbricklab import Entity
from finbricklab.core.kinds import K

pd.options.display.float_format = "{:,.2f} €".format


def main():
    """Demonstrate canonical journal structure functionality."""
    print("=== FinBrickLab Canonical Journal Structure Example ===\n")

    # Create entity
    entity = Entity(id="canonical_demo", name="Canonical Journal Demo")

    # === SETUP COMPREHENSIVE SCENARIO ===
    print("Setting up comprehensive financial scenario...")

    # Cash accounts
    entity.new_ABrick(
        id="checking",
        name="Primary Checking",
        kind=K.A_CASH,
        spec={"initial_balance": 15000.0, "interest_pa": 0.01},
    )
    entity.new_ABrick(
        id="savings",
        name="High-Yield Savings",
        kind=K.A_CASH,
        spec={"initial_balance": 5000.0, "interest_pa": 0.03},
    )

    # Income sources
    entity.new_FBrick(
        id="salary",
        name="Monthly Salary",
        kind=K.F_INCOME_RECURRING,
        start_date=date(2025, 1, 1),
        spec={"amount_monthly": 4500.0, "step_pct": 0.03, "step_every_m": 12},
        links={"route": {"to": "checking"}},
    )
    entity.new_FBrick(
        id="freelance",
        name="Freelance Income",
        kind=K.F_INCOME_RECURRING,
        start_date=date(2025, 1, 1),
        spec={"amount_monthly": 800.0, "step_pct": 0.0, "step_every_m": 12},
        links={"route": {"to": "checking"}},
    )

    # Expenses
    entity.new_FBrick(
        id="rent",
        name="Monthly Rent",
        kind=K.F_EXPENSE_RECURRING,
        start_date=date(2025, 1, 1),
        spec={"amount_monthly": 1800.0, "step_pct": 0.02, "step_every_m": 12},
        links={"route": {"to": "checking"}},
    )
    entity.new_FBrick(
        id="groceries",
        name="Groceries",
        kind=K.F_EXPENSE_RECURRING,
        start_date=date(2025, 1, 1),
        spec={"amount_monthly": 400.0, "step_pct": 0.0, "step_every_m": 12},
        links={"route": {"to": "checking"}},
    )

    # Transfers
    entity.new_TBrick(
        id="savings_transfer",
        name="Monthly Savings",
        kind=K.T_TRANSFER_RECURRING,
        spec={"amount": 1000.0, "frequency": "MONTHLY"},
        links={"from": "checking", "to": "savings"},
    )
    entity.new_TBrick(
        id="emergency_fund",
        name="Emergency Fund Transfer",
        kind=K.T_TRANSFER_LUMP_SUM,
        spec={"amount": 2000.0},
        links={"from": "checking", "to": "savings"},
    )

    # Loan
    entity.new_LBrick(
        id="car_loan",
        name="Car Loan",
        kind=K.L_LOAN_ANNUITY,
        start_date=date(2025, 1, 1),
        spec={"principal": 25000.0, "rate_pa": 0.045, "term_months": 60},
    )

    # Investment
    entity.new_ABrick(
        id="investment",
        name="Investment Account",
        kind=K.A_SECURITY_UNITIZED,
        start_date=date(2025, 1, 1),
        spec={
            "buy_at_start": {"amount": 5000.0},
            "volatility_pa": 0.15,
            "drift_pa": 0.08,
            "dca": {"mode": "amount", "amount": 500.0, "source": "checking"},
        },
    )

    # Create scenario
    entity.create_scenario(
        id="canonical_demo",
        name="Canonical Demo",
        brick_ids=[
            "checking",
            "savings",
            "salary",
            "freelance",
            "rent",
            "groceries",
            "savings_transfer",
            "emergency_fund",
            "car_loan",
            "investment",
        ],
        settlement_default_cash_id="checking",
    )

    # Run scenario
    print("Running 6-month simulation...")
    results = entity.run_scenario("canonical_demo", start=date(2025, 1, 1), months=6)
    print()

    # === CANONICAL JOURNAL ANALYSIS ===
    print("=== CANONICAL JOURNAL STRUCTURE ANALYSIS ===")

    # Get journal DataFrame
    journal_df = results["views"].journal()

    print(f"📊 Total journal entries: {len(journal_df)}")
    print(
        f"📅 Date range: {journal_df['timestamp'].min()} to {journal_df['timestamp'].max()}"
    )
    print(f"💰 Total transaction volume: €{journal_df['amount'].abs().sum():,.2f}")
    print()

    # === CANONICAL STRUCTURE ANALYSIS ===
    print("=== CANONICAL STRUCTURE ANALYSIS ===")

    print("1. CANONICAL COLUMNS:")
    print(f"   Columns: {list(journal_df.columns)}")
    print()

    print("2. CLEAN RECORD_ID FORMAT:")
    print("   Sample clean record IDs:")
    for record_id in journal_df["record_id"].unique()[:10]:
        print(f"     {record_id}")
    print()

    print("3. BRICK_ID ANALYSIS:")
    brick_counts = journal_df["brick_id"].value_counts()
    print("   Transactions by brick:")
    for brick_id, count in brick_counts.head(10).items():
        if pd.notna(brick_id):
            print(f"     {brick_id}: {count} transactions")
    print()

    print("4. BRICK_TYPE ANALYSIS:")
    type_counts = journal_df["brick_type"].value_counts()
    print("   Transactions by type:")
    for brick_type, count in type_counts.items():
        if pd.notna(brick_type):
            print(f"     {brick_type}: {count} transactions")
    print()

    print("5. ACCOUNT_ID ANALYSIS:")
    account_counts = journal_df["account_id"].value_counts()
    print("   Transactions by account:")
    for account_id, count in account_counts.head(10).items():
        print(f"     {account_id}: {count} transactions")
    print()

    print("6. POSTING_SIDE ANALYSIS:")
    posting_side_counts = journal_df["posting_side"].value_counts()
    print("   Transactions by posting side:")
    for side, count in posting_side_counts.items():
        print(f"     {side}: {count} transactions")
    print()

    # === QUERY DEMONSTRATIONS ===
    print("=== CANONICAL QUERY DEMONSTRATIONS ===")

    print("1. FILTER BY BRICK_ID:")
    print("   Salary transactions:")
    salary_txns = journal_df[journal_df["brick_id"] == "salary"]
    print(f"     Found {len(salary_txns)} salary transactions")
    for i, row in salary_txns.head(3).iterrows():
        print(
            f"       {row['record_id']} | {row['account_id']} | {row['amount']:+.2f} €"
        )
    print()

    print("2. FILTER BY BRICK_TYPE:")
    print("   Flow transactions:")
    flow_txns = journal_df[journal_df["brick_type"] == "flow"]
    print(f"     Found {len(flow_txns)} flow transactions")
    print("   Transfer transactions:")
    transfer_txns = journal_df[journal_df["brick_type"] == "transfer"]
    print(f"     Found {len(transfer_txns)} transfer transactions")
    print()

    print("3. FILTER BY ACCOUNT_ID (STANDARDIZED FORMAT):")
    print("   Asset transactions:")
    asset_txns = journal_df[journal_df["account_id"].str.startswith("Asset:")]
    print(f"     Found {len(asset_txns)} asset transactions")
    print("   Income transactions:")
    income_txns = journal_df[journal_df["account_id"].str.startswith("Income:")]
    print(f"     Found {len(income_txns)} income transactions")
    print("   Liability transactions:")
    liability_txns = journal_df[journal_df["account_id"].str.startswith("Liability:")]
    print(f"     Found {len(liability_txns)} liability transactions")
    print()

    print("4. FILTER BY POSTING_SIDE:")
    print("   Debit transactions:")
    debit_txns = journal_df[journal_df["posting_side"] == "debit"]
    print(f"     Found {len(debit_txns)} debit transactions")
    print("   Credit transactions:")
    credit_txns = journal_df[journal_df["posting_side"] == "credit"]
    print(f"     Found {len(credit_txns)} credit transactions")
    print()

    # === ADVANCED CANONICAL ANALYSIS ===
    print("=== ADVANCED CANONICAL ANALYSIS ===")

    print("1. CLEAN RECORD_ID PARSING:")
    print("   Parse clean record IDs for detailed analysis:")
    journal_df["parsed_record"] = journal_df["record_id"].str.split(":")

    # Extract components from clean record IDs
    canonical_records = journal_df[journal_df["record_id"].str.contains(":", na=False)]
    if not canonical_records.empty:
        print("   Sample parsed clean records:")
        for i, row in canonical_records.head(5).iterrows():
            parsed = row["parsed_record"]
            if len(parsed) >= 5:
                print(
                    f"     {parsed[0]}:{parsed[1]} -> {parsed[2]}:{parsed[3]} (month {parsed[4]})"
                )
    print()

    print("2. MONTHLY TRANSACTION ANALYSIS:")
    monthly_stats = (
        journal_df.groupby("timestamp")
        .agg({"record_id": "count", "amount": "sum"})
        .rename(columns={"record_id": "transactions", "amount": "net_amount"})
    )
    print("   Monthly transaction summary:")
    print(monthly_stats.head())
    print()

    print("3. ACCOUNT BALANCE ANALYSIS:")
    account_balance = (
        journal_df.groupby("account_id")["amount"].sum().sort_values(ascending=False)
    )
    print("   Net balance by account:")
    for account, balance in account_balance.head(10).items():
        print(f"     {account}: {balance:+.2f} €")
    print()

    print("4. DOUBLE-ENTRY VALIDATION:")
    entry_balances = journal_df.groupby("record_id")["amount"].sum()
    unbalanced_entries = entry_balances[entry_balances.abs() > 1e-6]
    print(f"   Unbalanced entries: {len(unbalanced_entries)}")
    if len(unbalanced_entries) == 0:
        print("   ✅ All entries are properly balanced!")
    print()

    # === CANONICAL BENEFITS SUMMARY ===
    print("=== CANONICAL JOURNAL BENEFITS ===")
    print("✅ Clean, self-documenting record IDs: flow:income:salary:checking:0")
    print("✅ Primary brick_id column for easy filtering")
    print("✅ Clear brick_type classification")
    print("✅ Account_id shows where money flows")
    print("✅ Rich metadata for transaction analysis")
    print("✅ Perfect for financial analysis and auditing")
    print("✅ Supports complex queries and reporting")
    print()

    print("=== SUMMARY ===")
    print("🎉 Canonical journal structure provides:")
    print("   • Complete transaction-level detail")
    print("   • Self-documenting record IDs")
    print("   • Primary columns for easy analysis")
    print("   • Perfect double-entry bookkeeping")
    print("   • Rich metadata for financial analysis")
    print("   • Support for complex queries and reporting")
    print()
    print("✅ Canonical journal structure fully implemented and working!")


if __name__ == "__main__":
    main()
