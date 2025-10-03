"""
Demonstration of the new user-friendly ETF API.

This example shows how the improved API makes ETF configuration much more intuitive:
- initial_amount instead of initial_units + price0 calculation
- Python date objects instead of numpy datetime64
- amount and percentage-based selling instead of just units
"""

from datetime import date
import finbricklab.strategies
from finbricklab import Entity
from finbricklab.core.kinds import K

def main():
    print("=== User-Friendly ETF API Demo ===\n")
    
    entity = Entity(id="person", name="John Doe")
    
    # Cash account
    entity.new_ABrick(id="checking", name="Checking", kind=K.A_CASH, 
                      spec={"initial_balance": 10000.0, "interest_pa": 0.01})
    
    # Salary income
    entity.new_FBrick(id="salary", name="Salary", kind=K.F_INCOME_FIXED, 
                      start_date=date(2026, 2, 1),
                      spec={"amount_monthly": 5000.0},
                      links={"route": {"to": "checking"}})
    
    # ETF with user-friendly configuration
    print("Creating ETF with user-friendly parameters:")
    print("- initial_amount: €2000 (much clearer than units × price)")
    print("- date: date(2026, 10, 1) (standard Python date)")
    print("- amount: €1000 (sell by monetary value)")
    print("- percentage: 0.5 (sell 50% of holdings)")
    print()
    
    entity.new_ABrick(id="etf", name="ETF", kind=K.A_ETF_UNITIZED, 
                      start_date=date(2026, 6, 1),
                      spec={
                            "initial_amount": 2000.0,  # ✅ Clear: €2000 invested
                            "price0": 100.0,
                            "volatility_pa": 0.25,
                            "drift_pa": 0.05,  # 5% annual growth
                            "dca": {
                                "mode": "amount",
                                "amount": 500.0,  # €500/month
                                "source": "checking",
                            },
                            "sell": [
                                {
                                    "date": date(2026, 10, 1),  # ✅ Standard Python date
                                    "amount": 1000.0  # ✅ Sell €1000 worth
                                },
                                {
                                    "date": date(2026, 12, 1),
                                    "percentage": 0.5  # ✅ Sell 50% of remaining holdings
                                }
                            ],
                            "liquidate_on_window_end": False  # Keep remaining holdings
                        })
    
    # Create scenario
    entity.create_scenario(
        id="demo", name="User-Friendly ETF Demo",
        brick_ids=["salary", "checking", "etf"],
        settlement_default_cash_id="checking"
    )
    
    print("Running scenario for 12 months...")
    results = entity.run_scenario("demo", start=date(2026, 1, 1), months=12)
    
    # Analyze results
    etf_output = results["outputs"]["etf"]
    checking_output = results["outputs"]["checking"]
    
    print("\n=== Results ===")
    print(f"Initial ETF value: €{etf_output['asset_value'][0]:,.2f}")
    print(f"Final ETF value: €{etf_output['asset_value'][-1]:,.2f}")
    print(f"Final cash balance: €{checking_output['asset_value'][-1]:,.2f}")
    
    # Show ETF events
    print("\n=== ETF Events ===")
    for event in etf_output['events']:
        print(f"{event.t}: {event.message}")
    
    # Show monthly ETF values
    print("\n=== Monthly ETF Values ===")
    totals = results["totals"]
    for i, (date_idx, row) in enumerate(totals.iterrows()):
        if i % 2 == 0:  # Show every other month
            print(f"{date_idx.strftime('%Y-%m')}: €{row['non_cash']:,.2f}")

if __name__ == "__main__":
    main()
