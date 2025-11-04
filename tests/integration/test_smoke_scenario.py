"""
Comprehensive smoke scenario test.

This test exercises all major features of the system:
- Salary inflow (boundary)
- Internal transfers
- Quarterly FX transfers
- Maturity transfers
- Transfer visibility modes
- Accounting identities

This ensures the entire system works together correctly.
"""

from datetime import date

from finbricklab import Entity
from finbricklab.core.kinds import K
from finbricklab.core.transfer_visibility import TransferVisibility


class TestSmokeScenario:
    """Comprehensive smoke scenario testing multiple features together."""

    def test_full_scenario_with_all_features(self):
        """Test a complete scenario with salary, transfers, FX, and maturities."""
        entity = Entity(id="smoke_test", name="Smoke Test Entity")

        # Create cash accounts
        entity.new_ABrick(
            "checking_usd",
            "Checking USD",
            K.A_CASH,
            {"initial_balance": 10000.0, "interest_pa": 0.0},
        )
        entity.new_ABrick(
            "savings_eur",
            "Savings EUR",
            K.A_CASH,
            {"initial_balance": 5000.0, "interest_pa": 0.001},
        )
        entity.new_ABrick(
            "investment_eur",
            "Investment EUR",
            K.A_CASH,
            {"initial_balance": 0.0, "interest_pa": 0.0},
        )

        # Create a maturing savings account
        entity.new_ABrick(
            "savings_maturing",
            "Maturing Savings",
            K.A_CASH,
            {
                "initial_balance": 2000.0,
                "interest_pa": 0.002,
                "currency": "EUR",
            },
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 1),
            links={"route": {"to": "investment_eur"}},
        )

        # Boundary income (salary)
        entity.new_FBrick(
            "salary",
            "Monthly Salary",
            K.F_INCOME_RECURRING,
            {"amount_monthly": 5000.0},
            links={"route": {"to": "checking_usd"}},
        )

        # Internal transfer (monthly savings)
        entity.new_TBrick(
            "monthly_savings",
            "Monthly Savings Transfer",
            K.T_TRANSFER_RECURRING,
            {"amount": 500.0, "frequency": "MONTHLY"},
            links={"from": "checking_usd", "to": "savings_eur"},
        )

        # Quarterly FX transfer (USD to EUR)
        entity.new_TBrick(
            "quarterly_fx",
            "Quarterly USD->EUR Transfer",
            K.T_TRANSFER_RECURRING,
            {
                "amount": 1000.0,
                "frequency": "QUARTERLY",
                "currency": "USD",
                "fx": {
                    "rate": 0.92,  # 1 USD = 0.92 EUR
                    "pair": "USD/EUR",
                    "pnl_account": "P&L:FX",
                },
            },
            start_date=date(2024, 1, 1),
            links={"from": "checking_usd", "to": "investment_eur"},
        )

        # Create scenario
        scenario = entity.create_scenario(
            id="smoke",
            name="Smoke Test",
            brick_ids=[
                "checking_usd",
                "savings_eur",
                "investment_eur",
                "savings_maturing",
                "salary",
                "monthly_savings",
                "quarterly_fx",
            ],
            settlement_default_cash_id="checking_usd",
        )

        # Run scenario for 12 months
        results = scenario.run(start=date(2024, 1, 1), months=12)

        # Verify scenario ran successfully
        assert results is not None
        assert "totals" in results
        assert "views" in results
        assert "journal" in results

        # Verify totals DataFrame
        totals = results["totals"]
        assert len(totals) == 12  # 12 months
        assert all(
            col in totals.columns
            for col in ["cash_in", "cash_out", "assets", "liabilities"]
        )

        # Verify journal has entries
        journal = results["journal"]
        assert len(journal.entries) > 0

        # Test all transfer visibility modes
        for visibility in [
            TransferVisibility.OFF,
            TransferVisibility.ONLY,
            TransferVisibility.ALL,
            TransferVisibility.BOUNDARY_ONLY,
        ]:
            monthly_data = results["views"].monthly(transfer_visibility=visibility)

            # Verify accounting identities for each month
            for idx in range(len(monthly_data)):
                # Identity: assets == cash + non_cash
                assets = monthly_data.iloc[idx]["assets"]
                cash = monthly_data.iloc[idx]["cash"]
                non_cash = monthly_data.iloc[idx]["non_cash"]
                assert abs(assets - cash - non_cash) < 0.01, (
                    f"Identity violation: assets != cash + non_cash at {idx} "
                    f"in {visibility.value} mode"
                )

                # Identity: equity == assets - liabilities
                equity = monthly_data.iloc[idx]["equity"]
                assets = monthly_data.iloc[idx]["assets"]
                liabilities = monthly_data.iloc[idx]["liabilities"]
                assert abs(equity - (assets - liabilities)) < 0.01, (
                    f"Identity violation: equity != assets - liabilities at {idx} "
                    f"in {visibility.value} mode"
                )

                # Identity: net_cf == cash_in - cash_out
                net_cf = monthly_data.iloc[idx]["net_cf"]
                cash_in = monthly_data.iloc[idx]["cash_in"]
                cash_out = monthly_data.iloc[idx]["cash_out"]
                assert abs(net_cf - (cash_in - cash_out)) < 0.01, (
                    f"Identity violation: net_cf != cash_in - cash_out at {idx} "
                    f"in {visibility.value} mode"
                )

        # Verify journal zero-sum per currency
        for entry in journal.entries:
            currency_totals = entry.get_currency_totals()
            for currency, total in currency_totals.items():
                assert (
                    abs(total) < 0.01
                ), f"Journal entry {entry.id} is not zero-sum for currency {currency}: {total}"

        # Verify maturity transfer occurred in month 6 (June 2024)
        maturity_month = 5  # June 2024 is index 5 (0-indexed)
        maturity_transfer_entries = [
            e
            for e in journal.entries
            if e.metadata.get("transaction_type") == "maturity_transfer"
        ]
        assert len(maturity_transfer_entries) > 0, "Expected maturity transfer entries"

        # Verify at least one maturity transfer happened in June
        maturity_in_june = any(
            e.metadata.get("month") == maturity_month for e in maturity_transfer_entries
        )
        assert maturity_in_june, f"Expected maturity transfer in month {maturity_month}"
