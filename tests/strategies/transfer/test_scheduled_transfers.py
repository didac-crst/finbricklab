"""Regression tests for scheduled transfer strategy."""

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
from finbricklab.strategies.transfer.scheduled import TransferScheduled


def test_scheduled_transfers_use_unique_sequences_within_month() -> None:
    """Scheduled transfers should not reuse journal IDs within the same month."""

    account_registry = AccountRegistry()
    account_registry.register_account(
        Account("a:source", "Source Account", AccountScope.INTERNAL, AccountType.ASSET)
    )
    account_registry.register_account(
        Account(
            "a:dest", "Destination Account", AccountScope.INTERNAL, AccountType.ASSET
        )
    )

    journal = Journal(account_registry)
    t_index = np.arange("2026-01", "2026-04", dtype="datetime64[M]")
    ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={}, journal=journal)

    strategy = TransferScheduled()
    brick = TBrick(
        id="sched",
        name="Scheduled Transfer",
        kind="t.transfer.scheduled",
        spec={
            "currency": "EUR",
            "schedule": [
                {"date": "2026-01-05", "amount": 100},
                {"date": "2026-01-20", "amount": 150},
            ],
            "fees": {"amount": 5, "account": BOUNDARY_NODE_ID},
        },
        links={"from": "source", "to": "dest"},
        transfer=strategy,
    )

    strategy.prepare(brick, ctx)
    strategy.simulate(brick, ctx)

    entry_ids = [entry.id for entry in journal.entries]
    assert len(entry_ids) == 4
    assert len(entry_ids) == len(set(entry_ids))

    transfer_sequences = sorted(
        entry.metadata["sequence"]
        for entry in journal.entries
        if entry.metadata.get("tags", {}).get("type") == "transfer"
    )
    assert transfer_sequences == [1, 11]

    fee_sequences = sorted(
        entry.metadata["sequence"]
        for entry in journal.entries
        if entry.metadata.get("tags", {}).get("type") == "transfer_fee"
    )
    assert fee_sequences == [2, 12]
