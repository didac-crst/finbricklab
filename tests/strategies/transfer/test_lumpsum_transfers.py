"""Regression tests for lump sum transfer strategy."""

from __future__ import annotations

import numpy as np
from finbricklab.core.accounts import (
    BOUNDARY_NODE_ID,
    Account,
    AccountRegistry,
    AccountScope,
    AccountType,
)
from finbricklab.core.bricks import TBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.journal import Journal
from finbricklab.strategies.transfer.lumpsum import TransferLumpSum


def test_lumpsum_posts_fees_when_fx_enabled() -> None:
    """Lump sum transfers should emit fee entries even when FX legs are used."""

    account_registry = AccountRegistry()
    account_registry.register_account(
        Account("a:source", "Source", AccountScope.INTERNAL, AccountType.ASSET)
    )
    account_registry.register_account(
        Account("a:dest", "Destination", AccountScope.INTERNAL, AccountType.ASSET)
    )

    journal = Journal(account_registry)
    t_index = np.arange("2026-01", "2026-04", dtype="datetime64[M]")
    ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={}, journal=journal)

    strategy = TransferLumpSum()
    brick = TBrick(
        id="lump-fx-fee",
        name="Lump Sum FX with Fee",
        kind="t.transfer.lumpsum",
        spec={
            "amount": 100,
            "currency": "EUR",
            "fees": {"amount": 2, "currency": "EUR", "account": BOUNDARY_NODE_ID},
            "fx": {"pair": "EUR/USD", "rate": "1.1"},
        },
        links={"from": "source", "to": "dest"},
        transfer=strategy,
    )

    strategy.prepare(brick, ctx)
    strategy.simulate(brick, ctx)

    fee_entries = [
        entry
        for entry in journal.entries
        if entry.metadata.get("tags", {}).get("type") == "transfer_fee"
    ]

    assert fee_entries, "Expected transfer_fee entry even when FX is configured"

    fee_entry = fee_entries[0]
    fee_accounts = {posting.account_id for posting in fee_entry.postings}
    assert BOUNDARY_NODE_ID in fee_accounts
    assert "a:dest" in fee_accounts
