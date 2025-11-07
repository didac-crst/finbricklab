#!/usr/bin/env python3
"""
Journal Analysis Example

This example demonstrates the enhanced journal functionality in FinBrickLab:
- Complete transaction-level detail for all financial activities
- Double-entry bookkeeping with proper account tracking
- Time-series analysis of financial flows
- Account-level reconciliation and debugging
- Filtered journal analysis for specific bricks/MacroBricks

The journal provides a comprehensive audit trail of all financial transactions
throughout the simulation period, enabling detailed analysis and compliance.
"""

from datetime import date

from finbricklab.core.entity import Entity
from finbricklab.core.kinds import K


def main():
    """Demonstrate comprehensive journal analysis functionality."""
    print("=== FinBrickLab Journal Analysis Example ===\n")

    # Create entity with complex financial scenario
    entity = Entity(id="journal_demo", name="Journal Analysis Demo")

    # === CASH ACCOUNTS ===
    entity.new_ABrick(
        id="checking",
        name="Checking Account",
        kind=K.A_CASH,
        spec={"initial_balance": 25000.0, "interest_pa": 0.01},
    )

    entity.new_ABrick(
        id="savings",
        name="High-Yield Savings",
        kind=K.A_CASH,
        spec={"initial_balance": 50000.0, "interest_pa": 0.025},
    )

    # === INCOME SOURCES ===
    entity.new_FBrick(
        id="salary",
        name="Monthly Salary",
        kind=K.F_INCOME_RECURRING,
        start_date=date(2025, 1, 1),
        spec={
            "amount_monthly": 5000.0,
            "step_pct": 0.03,  # 3% annual raise
            "step_every_m": 12,
        },
        links={"route": {"to": "checking"}},
    )

    entity.new_FBrick(
        id="freelance",
        name="Freelance Income",
        kind=K.F_INCOME_RECURRING,
        start_date=date(2025, 1, 1),
        spec={"amount_monthly": 1500.0, "step_pct": 0.0, "step_every_m": 12},
        links={"route": {"to": "savings"}},
    )

    # === EXPENSES ===
    entity.new_FBrick(
        id="rent",
        name="Monthly Rent",
        kind=K.F_EXPENSE_RECURRING,
        start_date=date(2025, 1, 1),
        spec={
            "amount_monthly": 1200.0,
            "step_pct": 0.02,  # 2% annual increase
            "step_every_m": 12,
        },
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

    # === INVESTMENTS ===
    entity.new_ABrick(
        id="etf_portfolio",
        name="ETF Portfolio",
        kind=K.A_SECURITY_UNITIZED,
        start_date=date(2025, 1, 1),
        spec={
            "buy_at_start": {"amount": 10000.0},
            "volatility_pa": 0.15,
            "drift_pa": 0.08,
            "dca": {"mode": "amount", "amount": 1000.0, "source": "savings"},
        },
    )

    # === TRANSFERS ===
    entity.new_TBrick(
        id="savings_transfer",
        name="Monthly Savings Transfer",
        kind=K.T_TRANSFER_RECURRING,
        spec={"amount": 2000.0, "frequency": "MONTHLY"},
        links={"from": "checking", "to": "savings"},
    )

    # Note: ETF investments are handled via DCA in the ETF spec, not via transfers
    # The ETF will automatically invest from savings based on the DCA configuration

    # === LOAN ===
    entity.new_LBrick(
        id="car_loan",
        name="Car Loan",
        kind=K.L_LOAN_ANNUITY,
        start_date=date(2025, 1, 1),
        spec={"principal": 25000.0, "rate_pa": 0.045, "term_months": 60},
    )

    # === MACROBRICKS ===
    # V2: MacroBricks can only contain A/L bricks (not F/T bricks)
    # Income sources are F/T bricks, so we can't create a MacroBrick for them
    # Instead, we'll create a MacroBrick for investment strategy only

    entity.new_MacroBrick(
        id="investment_strategy",
        name="Investment Strategy",
        member_ids=["etf_portfolio"],
    )

    # === SCENARIO ===
    entity.create_scenario(
        id="journal_demo",
        name="Journal Analysis Demo",
        brick_ids=[
            "checking",
            "savings",
            "salary",
            "freelance",
            "rent",
            "groceries",
            "etf_portfolio",
            "savings_transfer",
            "car_loan",
            "investment_strategy",
        ],
        settlement_default_cash_id="checking",
    )

    # Run scenario for 12 months
    print("Running 12-month simulation...")
    results = entity.run_scenario("journal_demo", start=date(2025, 1, 1), months=12)

    # === JOURNAL OVERVIEW ===
    print("\n=== JOURNAL OVERVIEW ===")
    journal_df = results["views"].journal()
    print(f"📊 Total journal entries: {len(journal_df)}")
    print(
        f"📅 Date range: {journal_df['timestamp'].min()} to {journal_df['timestamp'].max()}"
    )
    print(f"💰 Total transaction volume: €{journal_df['amount'].abs().sum():,.2f}")
    print()

    # === MONTHLY TRANSACTION ANALYSIS ===
    print("=== MONTHLY TRANSACTION ANALYSIS ===")
    monthly_stats = (
        journal_df.groupby("timestamp")
        .agg({"record_id": "nunique", "amount": "sum"})
        .rename(columns={"record_id": "transactions", "amount": "net_amount"})
    )

    print("Monthly breakdown:")
    for month, row in monthly_stats.iterrows():
        print(
            f"  {month.strftime('%Y-%m')}: {row['transactions']} transactions, net: €{row['net_amount']:+,.2f}"
        )
    print()

    # === ACCOUNT ANALYSIS ===
    print("=== ACCOUNT ANALYSIS ===")
    account_stats = (
        journal_df.groupby("account_id").agg({"amount": ["count", "sum"]}).round(2)
    )
    account_stats.columns = ["transactions", "net_amount"]
    account_stats = account_stats.sort_values("net_amount", ascending=False)

    print("Account breakdown:")
    for account, row in account_stats.iterrows():
        print(
            f"  {account}: {row['transactions']} transactions, net: €{row['net_amount']:+,.2f}"
        )
    print()

    # === TRANSACTION TYPE ANALYSIS ===
    print("=== TRANSACTION TYPE ANALYSIS ===")
    transaction_types = (
        journal_df["metadata"].apply(lambda x: x.get("type", "unknown")).value_counts()
    )
    print("Transaction types:")
    for txn_type, count in transaction_types.items():
        print(f"  {txn_type}: {count} transactions")
    print()

    # === DOUBLE-ENTRY VALIDATION ===
    print("=== DOUBLE-ENTRY VALIDATION ===")
    entry_balances = journal_df.groupby("record_id")["amount"].sum()
    unbalanced_entries = entry_balances[entry_balances.abs() > 1e-6]
    if len(unbalanced_entries) == 0:
        print("✅ All journal entries are properly balanced (zero-sum)")
    else:
        print(f"❌ {len(unbalanced_entries)} unbalanced entries found")
    print()

    # === FILTERED JOURNAL ANALYSIS (by category) ===
    print("=== FILTERED JOURNAL ANALYSIS ===")
    income_journal = journal_df[
        journal_df["metadata"].apply(
            lambda m: m.get("category", "").startswith("income.")
        )
    ]
    print(f"📊 Income journal: {len(income_journal)} entries")
    if not income_journal.empty:
        print("Sample income transactions:")
        print(income_journal[["timestamp", "account_id", "amount", "metadata"]].head())
    print()

    # Filter by ETF portfolio brick_id and transaction types
    investment_journal = journal_df[
        journal_df["brick_id"].isin(["etf_portfolio"])
        | journal_df["metadata"].apply(
            lambda m: m.get("transaction_type", "") in {"transfer", "dividend"}
        )
    ]
    print(f"📊 Investment strategy journal: {len(investment_journal)} entries")
    if not investment_journal.empty:
        print("Sample investment transactions:")
        print(
            investment_journal[["timestamp", "account_id", "amount", "metadata"]].head()
        )
    print()

    # === SPECIFIC ACCOUNT TRANSACTIONS ===
    print("=== SPECIFIC ACCOUNT TRANSACTIONS ===")

    # Checking account transactions (filter journal by node_id)
    checking_txns = journal_df[journal_df["account_id"] == "a:checking"]
    print(f"📊 Checking account transactions: {len(checking_txns)}")
    if not checking_txns.empty:
        print("Checking account sample:")
        print(checking_txns[["timestamp", "amount", "metadata"]].head())
    print()

    # Savings account transactions (filter journal by node_id)
    savings_txns = journal_df[journal_df["account_id"] == "a:savings"]
    print(f"📊 Savings account transactions: {len(savings_txns)}")
    if not savings_txns.empty:
        print("Savings account sample:")
        print(savings_txns[["timestamp", "amount", "metadata"]].head())
    print()

    # === ADVANCED JOURNAL ANALYSIS ===
    print("=== ADVANCED JOURNAL ANALYSIS ===")

    # Cash flow analysis by month
    monthly_cash_flows = journal_df.groupby("timestamp")["amount"].sum()
    print("Monthly net cash flows:")
    for month, net_flow in monthly_cash_flows.items():
        print(f"  {month.strftime('%Y-%m')}: €{net_flow:+,.2f}")
    print()

    # Account balance changes
    print("Account balance changes (first 3 months):")
    for month in journal_df["timestamp"].unique()[:3]:
        month_txns = journal_df[journal_df["timestamp"] == month]
        print(f"  {month.strftime('%Y-%m')}:")
        for account in month_txns["account_id"].unique():
            account_txns = month_txns[month_txns["account_id"] == account]
            net_change = account_txns["amount"].sum()
            print(f"    {account}: €{net_change:+,.2f}")
    print()

    # === SUMMARY ===
    print("=== SUMMARY ===")
    print("✅ Journal provides complete transaction-level detail")
    print("✅ Double-entry bookkeeping ensures proper accounting")
    print("✅ Time-series analysis of all financial flows")
    print("✅ Account-level reconciliation and debugging")
    print("✅ Filtered journal analysis for specific components")
    print("✅ Transaction type classification and analysis")
    print("✅ Comprehensive audit trail for compliance")
    print()
    print("🎉 Journal analysis demonstrates full financial transparency!")


if __name__ == "__main__":
    main()
