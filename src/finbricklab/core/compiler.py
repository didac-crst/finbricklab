"""
Compilation system for converting bricks to journal entries.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from .accounts import Account, AccountRegistry, AccountScope, AccountType
from .bricks import ABrick, FBrick, TBrick
from .context import ScenarioContext
from .currency import create_amount
from .journal import JournalEntry, Posting, generate_transaction_id


class BrickCompiler:
    """
    Compiler for converting bricks to journal entries.

    This class handles the compilation of different brick types into
    double-entry journal entries that maintain accounting invariants.
    """

    def __init__(self, account_registry: AccountRegistry | None = None):
        self.account_registry = account_registry or AccountRegistry()

    def compile_tbrick(
        self, brick: TBrick, ctx: ScenarioContext, sequence: int = 0
    ) -> list[JournalEntry]:
        """
        Compile a TBrick to journal entries.

        TBricks generate internal transfers between internal accounts.
        These must be zero-sum and not affect net worth.

        Args:
            brick: The transfer brick
            ctx: The simulation context
            sequence: Sequence number for tie-breaking

        Returns:
            List of journal entries for this transfer

        Raises:
            ValueError: If accounts are not internal or validation fails
        """
        entries = []

        # Validate accounts are internal
        from_account = brick.links["from"]
        to_account = brick.links["to"]
        self.account_registry.validate_transfer_accounts(from_account, to_account)

        # Get transfer amount and currency
        amount = Decimal(str(brick.spec["amount"]))
        currency = brick.spec.get("currency", "EUR")
        amount_obj = create_amount(amount, currency)

        # Create postings for the transfer
        postings = [
            Posting(from_account, -amount_obj, {"type": "transfer_out"}),
            Posting(to_account, +amount_obj, {"type": "transfer_in"}),
        ]

        # Normalize timestamp to datetime
        timestamp = brick.start_date if brick.start_date else ctx.t_index[0]
        if isinstance(timestamp, str):
            timestamp_dt = datetime.fromisoformat(timestamp)
        elif isinstance(timestamp, date) and not isinstance(timestamp, datetime):
            timestamp_dt = datetime.combine(timestamp, datetime.min.time())
        else:
            timestamp_dt = timestamp

        # Create transfer entry (must be 2 postings)
        txn_id = generate_transaction_id(
            brick.id, timestamp_dt, brick.spec, brick.links, sequence
        )
        entry = JournalEntry(
            id=txn_id,
            timestamp=timestamp_dt,
            postings=postings,
            metadata={
                "brick_id": brick.id,
                "brick_type": "transfer",
                "kind": brick.kind,
                "transaction_type": "transfer",
            },
        )
        entries.append(entry)

        # Handle fees if specified (create separate fee entry - V2 pattern)
        if "fees" in brick.spec:
            fees = brick.spec["fees"]
            fee_amount = Decimal(str(fees["amount"]))
            fee_currency = fees.get("currency", currency)
            fee_amount_obj = create_amount(fee_amount, fee_currency)
            fee_account = fees["account"]

            # V2: Fee entry is separate with 2 postings: DR expense (BOUNDARY), CR destination (INTERNAL)
            # Fee entry: destination account pays fee, boundary account receives it
            fee_postings = [
                Posting(to_account, -fee_amount_obj, {"type": "fee_payment"}),
                Posting(fee_account, +fee_amount_obj, {"type": "fee_income"}),
            ]

            # Generate fee entry ID (use sequence + 1 for fee entry)
            fee_txn_id = generate_transaction_id(
                brick.id, timestamp_dt, brick.spec, brick.links, sequence + 1
            )
            fee_entry = JournalEntry(
                id=fee_txn_id,
                timestamp=timestamp_dt,
                postings=fee_postings,
                metadata={
                    "brick_id": brick.id,
                    "brick_type": "transfer",
                    "kind": brick.kind,
                    "transaction_type": "transfer",
                    "fee": True,
                },
            )
            entries.append(fee_entry)

        # Handle FX if specified (FX entries are handled by transfer strategies)
        # V2: Compiler delegates to strategy layer for FX handling
        # Strategies will create FX entries during simulate() phase
        if "fx" in brick.spec:
            # FX handling is done in transfer strategies, not compiler
            # This is a no-op here - strategies will create FX entries
            pass

        return entries

    def compile_fbrick(
        self, brick: FBrick, ctx: ScenarioContext, sequence: int = 0
    ) -> list[JournalEntry]:
        """
        Compile an FBrick to journal entries.

        FBricks generate external flows that must touch boundary accounts.
        These affect net worth and represent money entering/leaving the system.

        Args:
            brick: The flow brick
            ctx: The simulation context
            sequence: Sequence number for tie-breaking

        Returns:
            List of journal entries for this flow

        Raises:
            ValueError: If accounts are not properly scoped or validation fails
        """
        entries = []

        # Get flow amount and currency
        amount = self._extract_flow_amount(brick)
        currency = brick.spec.get("currency", "EUR")
        amount_obj = create_amount(amount, currency)

        # Determine if this is income or expense
        is_income = "income" in brick.kind.lower()
        is_expense = "expense" in brick.kind.lower()

        if not (is_income or is_expense):
            raise ValueError(f"FBrick {brick.id} must be income or expense type")

        # Create boundary account posting
        if is_income:
            boundary_account = f"Income:{brick.name.replace(' ', '_')}"
            boundary_posting = Posting(
                boundary_account, -amount_obj, {"type": "income"}
            )
        else:
            boundary_account = f"Expenses:{brick.name.replace(' ', '_')}"
            boundary_posting = Posting(
                boundary_account, +amount_obj, {"type": "expense"}
            )

        # Register boundary account if not already registered
        if not self.account_registry.has_account(boundary_account):
            account_type = AccountType.INCOME if is_income else AccountType.EXPENSE
            self.account_registry.register_account(
                Account(
                    boundary_account,
                    boundary_account,
                    AccountScope.BOUNDARY,
                    account_type,
                )
            )

        # Get internal account allocations
        internal_accounts = self._get_internal_accounts(brick, ctx)

        # Create internal account postings
        internal_postings = []
        for account_id, allocation in internal_accounts.items():
            allocated_amount = amount * Decimal(str(allocation))
            allocated_amount_obj = create_amount(allocated_amount, currency)

            if is_income:
                internal_postings.append(
                    Posting(
                        account_id, +allocated_amount_obj, {"type": "income_allocation"}
                    )
                )
            else:
                internal_postings.append(
                    Posting(
                        account_id, -allocated_amount_obj, {"type": "expense_payment"}
                    )
                )

        # Create journal entry
        timestamp = brick.start_date if brick.start_date else ctx.t_index[0]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif isinstance(timestamp, date) and not isinstance(timestamp, datetime):
            # Convert date to datetime for the transaction ID generation
            timestamp_dt = datetime.combine(timestamp, datetime.min.time())
            txn_id = generate_transaction_id(
                brick.id, timestamp_dt, brick.spec, brick.links, sequence
            )
            postings = [boundary_posting] + internal_postings
            entry = JournalEntry(
                id=txn_id,
                timestamp=timestamp_dt,
                postings=postings,
                metadata={
                    "brick_id": brick.id,
                    "brick_type": "flow",
                    "kind": brick.kind,
                },
            )
            entries.append(entry)
            return entries
        else:
            txn_id = generate_transaction_id(
                brick.id, timestamp, brick.spec, brick.links, sequence
            )

        postings = [boundary_posting] + internal_postings
        entry = JournalEntry(
            id=txn_id,
            timestamp=timestamp,
            postings=postings,
            metadata={"brick_id": brick.id, "brick_type": "flow", "kind": brick.kind},
        )

        entries.append(entry)
        return entries

    def compile_abrick_valuation(
        self,
        brick: ABrick,
        ctx: ScenarioContext,
        old_value: Decimal,
        new_value: Decimal,
        sequence: int = 0,
    ) -> list[JournalEntry]:
        """
        Compile asset valuation changes to journal entries.

        Asset revaluations must be recorded to maintain net worth consistency.

        Args:
            brick: The asset brick
            ctx: The simulation context
            old_value: Previous asset value
            new_value: New asset value
            sequence: Sequence number for tie-breaking

        Returns:
            List of journal entries for valuation changes
        """
        entries: list[JournalEntry] = []

        if old_value == new_value:
            return entries  # No change

        # Calculate valuation change
        valuation_change = new_value - old_value
        currency = brick.spec.get("currency", "EUR")
        change_amount_obj = create_amount(valuation_change, currency)

        # Create postings for valuation change
        asset_account = f"Assets:{brick.name.replace(' ', '_')}"
        pnl_account = "P&L:Unrealized"

        if valuation_change > 0:
            # Asset increased in value
            postings = [
                Posting(
                    asset_account, +change_amount_obj, {"type": "valuation_increase"}
                ),
                Posting(pnl_account, -change_amount_obj, {"type": "unrealized_gain"}),
            ]
        else:
            # Asset decreased in value
            postings = [
                Posting(
                    asset_account, change_amount_obj, {"type": "valuation_decrease"}
                ),
                Posting(pnl_account, -change_amount_obj, {"type": "unrealized_loss"}),
            ]

        # Create journal entry
        # Valuation at end of period; normalize to datetime
        ts = ctx.t_index[-1]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif isinstance(ts, date) and not isinstance(ts, datetime):
            ts = datetime.combine(ts, datetime.min.time())

        txn_id = generate_transaction_id(
            f"{brick.id}_valuation", ts, brick.spec, brick.links, sequence
        )

        entry = JournalEntry(
            id=txn_id,
            timestamp=ts,
            postings=postings,
            metadata={
                "brick_id": brick.id,
                "brick_type": "valuation",
                "kind": brick.kind,
                "old_value": float(old_value),
                "new_value": float(new_value),
            },
        )

        entries.append(entry)
        return entries

    def _extract_flow_amount(self, brick: FBrick) -> Decimal:
        """Extract flow amount from brick specification."""
        if "amount_monthly" in brick.spec:
            return Decimal(str(brick.spec["amount_monthly"]))
        elif "amount" in brick.spec:
            return Decimal(str(brick.spec["amount"]))
        else:
            raise ValueError(f"FBrick {brick.id} must specify amount or amount_monthly")

    def _get_internal_accounts(
        self, brick: FBrick, ctx: ScenarioContext
    ) -> dict[str, Decimal]:
        """Get internal account allocations from brick links."""
        # Handle both old and new link formats for backward compatibility
        if not brick.links:
            # Default to first cash account
            cash_accounts = [
                b
                for b in ctx.registry.values()
                if isinstance(b, ABrick) and b.kind == "a.cash"
            ]
            if not cash_accounts:
                raise ValueError("No cash accounts available for flow routing")
            return {cash_accounts[0].id: Decimal("1.0")}

        # Check for new format first (route.to)
        if "route" in brick.links and "to" in brick.links["route"]:
            to_accounts = brick.links["route"]["to"]
        # Check for old format (direct to/from links)
        elif "to" in brick.links:
            to_accounts = brick.links["to"]
        else:
            # Default to first cash account
            cash_accounts = [
                b
                for b in ctx.registry.values()
                if isinstance(b, ABrick) and b.kind == "a.cash"
            ]
            if not cash_accounts:
                raise ValueError("No cash accounts available for flow routing")
            return {cash_accounts[0].id: Decimal("1.0")}

        if isinstance(to_accounts, str):
            return {to_accounts: Decimal("1.0")}
        elif isinstance(to_accounts, dict):
            # Validate allocations sum to 1.0
            total_allocation = sum(Decimal(str(v)) for v in to_accounts.values())
            if abs(total_allocation - Decimal("1.0")) > Decimal("0.001"):
                raise ValueError(
                    f"Flow allocations must sum to 1.0, got {total_allocation}"
                )

            return {k: Decimal(str(v)) for k, v in to_accounts.items()}
        else:
            raise ValueError("Invalid flow routing format")
