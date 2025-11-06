"""
Tests for the user-friendly ETF API improvements.
"""

from datetime import date

import numpy as np
from finbricklab.core.entity import Entity
from finbricklab.core.kinds import K


def test_initial_amount_conversion():
    """Test that initial_amount is converted to initial_units correctly."""
    entity = Entity(id="test", name="Test Entity")

    # Create cash account
    entity.new_ABrick(
        id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
    )

    # Create ETF with initial_amount (should be converted to units)
    entity.new_ABrick(
        id="etf",
        name="ETF",
        kind=K.A_SECURITY_UNITIZED,
        spec={
            "initial_amount": 1000.0,  # €1000
            "price0": 100.0,  # €100 per unit
            "volatility_pa": 0.0,  # No volatility for testing
            "drift_pa": 0.0,  # No drift for testing
            "sell": [],
        },
    )

    # Create scenario
    entity.create_scenario(
        id="test_scenario",
        name="Test Scenario",
        brick_ids=["cash", "etf"],
        settlement_default_cash_id="cash",
    )

    # Run scenario
    results = entity.run_scenario("test_scenario", start=date(2026, 1, 1), months=1)

    # Check that ETF has 10 units (€1000 / €100 = 10 units)
    etf_output = results["outputs"]["etf"]
    assert etf_output["assets"][0] == 1000.0  # 10 units * €100 = €1000


def test_user_friendly_sell_date():
    """Test that Python date objects work in sell directives."""
    entity = Entity(id="test", name="Test Entity")

    # Create cash account
    entity.new_ABrick(
        id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
    )

    # Create ETF with user-friendly sell date
    entity.new_ABrick(
        id="etf",
        name="ETF",
        kind=K.A_SECURITY_UNITIZED,
        spec={
            "initial_amount": 1000.0,
            "price0": 100.0,
            "volatility_pa": 0.0,
            "drift_pa": 0.0,
            "sell": [
                {
                    "date": date(2026, 2, 1),  # User-friendly date
                    "amount": 500.0,  # Sell €500 worth
                }
            ],
        },
    )

    # Create scenario
    entity.create_scenario(
        id="test_scenario",
        name="Test Scenario",
        brick_ids=["cash", "etf"],
        settlement_default_cash_id="cash",
    )

    # Run scenario for 3 months
    results = entity.run_scenario("test_scenario", start=date(2026, 1, 1), months=3)

    # V2: Check journal entries instead of deprecated cash_in arrays
    journal = results["journal"]
    monthly = results["views"].monthly()
    entry_ids = [entry.id for entry in journal.entries]
    assert len(entry_ids) == len(
        set(entry_ids)
    ), "Journal entry IDs should be unique for user-friendly sell date scenario"

    # Check that ETF was sold in February (month index 1)
    # V2: ETF sales create internal transfer entries (ETF -> cash)
    # Note: Transfer entries may not have brick_id set, check by parent_id or account IDs
    from finbricklab.core.accounts import get_node_id

    etf_node_id = get_node_id("etf", "a")
    cash_node_id = get_node_id("cash", "a")

    transfer_entries = [
        e
        for e in journal.entries
        if e.metadata.get("transaction_type") == "transfer"
        and any(p.account_id == etf_node_id for p in e.postings)
    ]
    assert (
        len(transfer_entries) == 1
    ), "Should create exactly one transfer entry for sale"

    # V2: Check monthly aggregation for cash inflows from ETF sale
    # Note: Internal transfers (ETF -> cash) are cancelled in aggregation when both nodes are selected
    # For now, verify that the transfer entry exists and check ETF asset value changed
    etf_output = results["outputs"]["etf"]
    # ETF should have less assets after sale (initial €1000, sold €500, so remaining should be ~€500)
    assert (
        etf_output["assets"][1] < etf_output["assets"][0]
    ), "ETF assets should decrease after sale"


def test_user_friendly_sell_percentage():
    """Test that percentage-based selling works."""
    entity = Entity(id="test", name="Test Entity")

    # Create cash account
    entity.new_ABrick(
        id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
    )

    # Create ETF with percentage-based sell
    entity.new_ABrick(
        id="etf",
        name="ETF",
        kind=K.A_SECURITY_UNITIZED,
        spec={
            "initial_amount": 1000.0,
            "price0": 100.0,
            "volatility_pa": 0.0,
            "drift_pa": 0.0,
            "sell": [
                {"date": date(2026, 2, 1), "percentage": 0.5}  # Sell 50% of holdings
            ],
        },
    )

    # Create scenario
    entity.create_scenario(
        id="test_scenario",
        name="Test Scenario",
        brick_ids=["cash", "etf"],
        settlement_default_cash_id="cash",
    )

    # Run scenario for 3 months
    results = entity.run_scenario("test_scenario", start=date(2026, 1, 1), months=3)

    # V2: Check journal entries and monthly aggregation instead of deprecated cash_in arrays
    journal = results["journal"]
    monthly = results["views"].monthly()
    etf_output = results["outputs"]["etf"]
    entry_ids = [entry.id for entry in journal.entries]
    assert len(entry_ids) == len(
        set(entry_ids)
    ), "Journal entry IDs should be unique for percentage sale scenario"

    # Check that 50% was sold (5 units out of 10, worth €500)
    # V2: ETF sales create internal transfer entries (ETF -> cash)
    from finbricklab.core.accounts import get_node_id

    etf_node_id = get_node_id("etf", "a")
    transfer_entries = [
        e
        for e in journal.entries
        if e.metadata.get("transaction_type") == "transfer"
        and any(p.account_id == etf_node_id for p in e.postings)
    ]
    assert (
        len(transfer_entries) == 1
    ), "Should create exactly one transfer entry for percentage sale"

    # V2: Check monthly aggregation and asset values
    # Note: Internal transfers (ETF -> cash) are cancelled in aggregation when both nodes are selected
    # So monthly["cash_in"] won't show the transfer, but asset values will reflect the sale
    assert etf_output["assets"][1] == 500.0, "Remaining ETF value should be €500"


def test_backward_compatibility():
    """Test that legacy parameters still work."""
    entity = Entity(id="test", name="Test Entity")

    # Create cash account
    entity.new_ABrick(
        id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
    )

    # Create ETF with legacy parameters
    entity.new_ABrick(
        id="etf",
        name="ETF",
        kind=K.A_SECURITY_UNITIZED,
        spec={
            "initial_units": 10.0,  # Legacy parameter
            "price0": 100.0,
            "volatility_pa": 0.0,
            "drift_pa": 0.0,
            "sell": [
                {
                    "t": np.datetime64("2026-02"),  # Legacy date format
                    "units": 5.0,  # Legacy units parameter
                }
            ],
        },
    )

    # Create scenario
    entity.create_scenario(
        id="test_scenario",
        name="Test Scenario",
        brick_ids=["cash", "etf"],
        settlement_default_cash_id="cash",
    )

    # Run scenario for 3 months
    results = entity.run_scenario("test_scenario", start=date(2026, 1, 1), months=3)

    # V2: Check journal entries and monthly aggregation instead of deprecated cash_in arrays
    journal = results["journal"]
    monthly = results["views"].monthly()
    etf_output = results["outputs"]["etf"]
    entry_ids = [entry.id for entry in journal.entries]
    assert len(entry_ids) == len(
        set(entry_ids)
    ), "Journal entry IDs should be unique for legacy parameters scenario"

    # Check that legacy format still works
    assert etf_output["assets"][0] == 1000.0, "Initial ETF value should be €1000"

    # V2: Check transfer entries and asset values
    # Note: Internal transfers (ETF -> cash) are cancelled in aggregation when both nodes are selected
    from finbricklab.core.accounts import get_node_id

    etf_node_id = get_node_id("etf", "a")
    transfer_entries = [
        e
        for e in journal.entries
        if e.metadata.get("transaction_type") == "transfer"
        and any(p.account_id == etf_node_id for p in e.postings)
    ]
    assert (
        len(transfer_entries) == 1
    ), "Should create exactly one transfer entry for legacy sale"
    assert (
        etf_output["assets"][1] == 500.0
    ), "Remaining ETF value after sale should be €500"


def test_combined_user_friendly_features():
    """Test combining multiple user-friendly features."""
    entity = Entity(id="test", name="Test Entity")

    # Create cash account
    entity.new_ABrick(
        id="cash", name="Cash", kind=K.A_CASH, spec={"initial_balance": 10000.0}
    )

    # Create ETF with multiple user-friendly features
    entity.new_ABrick(
        id="etf",
        name="ETF",
        kind=K.A_SECURITY_UNITIZED,
        spec={
            "initial_amount": 2000.0,  # User-friendly initial investment
            "price0": 100.0,
            "volatility_pa": 0.0,
            "drift_pa": 0.0,
            "sell": [
                {"date": date(2026, 3, 1), "percentage": 0.25},  # Sell 25% of holdings
                {"date": date(2026, 4, 1), "amount": 500.0},  # Sell €500 worth
            ],
        },
    )

    # Create scenario
    entity.create_scenario(
        id="test_scenario",
        name="Test Scenario",
        brick_ids=["cash", "etf"],
        settlement_default_cash_id="cash",
    )

    # Run scenario for 5 months
    results = entity.run_scenario("test_scenario", start=date(2026, 1, 1), months=5)

    # V2: Check journal entries and monthly aggregation instead of deprecated cash_in arrays
    journal = results["journal"]
    monthly = results["views"].monthly()
    etf_output = results["outputs"]["etf"]
    entry_ids = [entry.id for entry in journal.entries]
    assert len(entry_ids) == len(
        set(entry_ids)
    ), "Journal entry IDs should be unique when combining user-friendly features"

    # V2: ETF sales create internal transfer entries (ETF -> cash)
    from finbricklab.core.accounts import get_node_id

    etf_node_id = get_node_id("etf", "a")
    transfer_entries = [
        e
        for e in journal.entries
        if e.metadata.get("transaction_type") == "transfer"
        and any(p.account_id == etf_node_id for p in e.postings)
    ]
    assert (
        len(transfer_entries) == 2
    ), "Journal should have exactly 2 transfer entries matching the configured sales"

    # March: 25% of €2000 = €500
    # V2: Check asset values (internal transfers are cancelled in aggregation when both nodes are selected)
    assert (
        etf_output["assets"][2] == 1500.0
    ), "Remaining ETF value after 25% sale should be €1500"

    # April: €500 sale
    assert (
        etf_output["assets"][3] == 1000.0
    ), "Remaining ETF value after €500 sale should be €1000"
