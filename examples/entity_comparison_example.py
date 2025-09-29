#!/usr/bin/env python3
"""
Entity Comparison Example

This example demonstrates how to use the Entity system to compare multiple
financial scenarios with rich visualizations.
"""

import sys
from datetime import date
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finbricklab import ABrick, Entity, LBrick, Scenario  # noqa: E402
from finbricklab.charts import (  # noqa: E402
    asset_composition_small_multiples,
    net_worth_vs_time,
)
from finbricklab.core.kinds import K  # noqa: E402


def create_conservative_scenario():
    """Create a conservative investment scenario."""
    cash = ABrick(
        id="cash_conservative",
        name="Cash Account",
        kind=K.A_CASH,
        spec={"initial_balance": 75000.0, "interest_pa": 0.025},
    )

    etf = ABrick(
        id="etf_conservative",
        name="Conservative ETF",
        kind=K.A_ETF_UNITIZED,
        spec={
            "price0": 100.0,
            "drift_pa": 0.04,  # 4% annual growth
            "volatility_pa": 0.08,  # 8% volatility
            "initial_value": 25000.0,
        },
    )

    return Scenario(
        id="conservative",
        name="Conservative Portfolio",
        bricks=[cash, etf],
        currency="EUR",
    )


def create_aggressive_scenario():
    """Create an aggressive investment scenario with real estate."""
    cash = ABrick(
        id="cash_aggressive",
        name="Cash Account",
        kind=K.A_CASH,
        spec={"initial_balance": 15000.0, "interest_pa": 0.025},
    )

    house = ABrick(
        id="house",
        name="Investment Property",
        kind=K.A_PROPERTY_DISCRETE,
        spec={
            "initial_value": 350000.0,
            "appreciation_pa": 0.035,  # 3.5% annual appreciation
            "fees_pct": 0.08,  # 8% acquisition costs
        },
    )

    mortgage = LBrick(
        id="mortgage",
        name="Investment Mortgage",
        kind=K.L_MORT_ANN,
        spec={
            "principal": 280000.0,  # 80% LTV
            "rate_pa": 0.045,  # 4.5% interest rate
            "term_months": 300,  # 25 years
            "start_date": "2026-01-01",
        },
    )

    return Scenario(
        id="aggressive",
        name="Real Estate Portfolio",
        bricks=[cash, house, mortgage],
        currency="EUR",
    )


def create_balanced_scenario():
    """Create a balanced scenario with mixed investments."""
    cash = ABrick(
        id="cash_balanced",
        name="Cash Account",
        kind=K.A_CASH,
        spec={"initial_balance": 30000.0, "interest_pa": 0.025},
    )

    etf = ABrick(
        id="etf_balanced",
        name="Balanced ETF",
        kind=K.A_ETF_UNITIZED,
        spec={
            "price0": 100.0,
            "drift_pa": 0.06,  # 6% annual growth
            "volatility_pa": 0.12,  # 12% volatility
            "initial_value": 40000.0,
        },
    )

    house = ABrick(
        id="house_balanced",
        name="Primary Residence",
        kind=K.A_PROPERTY_DISCRETE,
        spec={
            "initial_value": 250000.0,
            "appreciation_pa": 0.03,  # 3% annual appreciation
            "fees_pct": 0.06,  # 6% acquisition costs
        },
    )

    mortgage = LBrick(
        id="mortgage_balanced",
        name="Home Mortgage",
        kind=K.L_MORT_ANN,
        spec={
            "principal": 200000.0,  # 80% LTV
            "rate_pa": 0.04,  # 4% interest rate
            "term_months": 360,  # 30 years
            "start_date": "2026-01-01",
        },
    )

    return Scenario(
        id="balanced",
        name="Balanced Portfolio",
        bricks=[cash, etf, house, mortgage],
        currency="EUR",
    )


def main():
    """Run the Entity comparison example."""
    print("🏗️  Creating scenarios...")

    # Create scenarios
    scenarios = [
        create_conservative_scenario(),
        create_aggressive_scenario(),
        create_balanced_scenario(),
    ]

    # Run scenarios for 10 years
    start_date = date(2026, 1, 1)
    months = 120  # 10 years

    print(f"📊 Running scenarios for {months} months starting {start_date}...")

    for scenario in scenarios:
        scenario.run(start=start_date, months=months)
        print(f"   ✅ {scenario.name} completed")

    # Create entity for comparison
    print("🏢 Creating Entity for comparison...")

    entity = Entity(
        id="investment_comparison",
        name="Investment Strategy Comparison",
        base_currency="EUR",
        scenarios=scenarios,
        benchmarks={"baseline": "conservative"},
        assumptions={
            "inflation_rate": 0.02,
            "tax_rate": 0.25,
            "risk_tolerance": "medium",
        },
    )

    # Compare scenarios
    print("📈 Comparing scenarios...")

    comparison_df = entity.compare()
    print(f"   📊 Comparison data shape: {comparison_df.shape}")
    print(
        f"   📅 Time period: {comparison_df['date'].min()} to {comparison_df['date'].max()}"
    )
    print(f"   🎯 Scenarios compared: {comparison_df['scenario_name'].nunique()}")

    # Analyze breakeven
    print("\n🎯 Breakeven Analysis:")
    breakeven_df = entity.breakeven_table("conservative")
    print(breakeven_df.to_string(index=False))

    # Check liquidity runway
    print("\n💧 Liquidity Runway Analysis:")
    runway_df = entity.liquidity_runway(lookback_months=6, essential_share=0.6)

    # Show final liquidity runway for each scenario
    final_runway = runway_df.groupby("scenario_name")["liquidity_runway_months"].last()
    for scenario_name, runway in final_runway.items():
        if runway == float("inf"):
            print(f"   {scenario_name}: ∞ months (no essential outflows)")
        else:
            print(f"   {scenario_name}: {runway:.1f} months")

    # Fees and taxes summary
    print("\n💰 Fees & Taxes Summary (10-year horizon):")
    summary_df = entity.fees_taxes_summary(horizons=[120])
    for _, row in summary_df.iterrows():
        print(
            f"   {row['scenario_name']}: Fees €{row['cumulative_fees']:,.0f}, Taxes €{row['cumulative_taxes']:,.0f}"
        )

    # Create visualizations
    print("\n📊 Creating visualizations...")

    try:
        # Net worth comparison
        fig1, _ = net_worth_vs_time(comparison_df)
        fig1.update_layout(
            title="Net Worth Comparison - Investment Strategies", height=500
        )
        fig1.write_html("net_worth_comparison.html")
        print("   ✅ Net worth chart saved to net_worth_comparison.html")

        # Asset composition
        fig2, _ = asset_composition_small_multiples(comparison_df)
        fig2.update_layout(title="Asset Composition Over Time", height=800)
        fig2.write_html("asset_composition.html")
        print("   ✅ Asset composition chart saved to asset_composition.html")

        print("\n🎉 Example completed successfully!")
        print("📁 Check the generated HTML files for interactive visualizations.")

    except ImportError:
        print("   ⚠️  Plotly not available - install with: pip install plotly kaleido")
        print("   📊 Visualization data is available in the DataFrames above.")

    # Show final results
    print("\n📊 Final Results (10-year horizon):")
    final_results = (
        comparison_df.groupby("scenario_name")
        .agg({"net_worth": "last", "total_assets": "last", "liabilities": "last"})
        .round(0)
    )

    print(final_results.to_string())

    print(f"\n🏆 Best performing strategy: {final_results['net_worth'].idxmax()}")
    print(f"   Final net worth: €{final_results['net_worth'].max():,.0f}")


if __name__ == "__main__":
    main()
