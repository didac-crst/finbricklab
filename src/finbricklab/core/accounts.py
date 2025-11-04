"""
Account classification and scope management for FinBrickLab.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

# BoundaryInterface constant
BOUNDARY_NODE_ID = "b:boundary"


class AccountScope(Enum):
    """Account scope classification."""

    INTERNAL = "internal"  # Assets, Liabilities within the system
    BOUNDARY = "boundary"  # Income, Expenses, Equity - external world interface


class AccountType(Enum):
    """Account type classification."""

    ASSET = "asset"
    LIABILITY = "liability"
    INCOME = "income"
    EXPENSE = "expense"
    EQUITY = "equity"
    PNL = "pnl"  # Profit & Loss


class Account:
    """
    Account definition with scope and type classification.

    Attributes:
        id: Unique account identifier
        name: Human-readable account name
        scope: Account scope (internal or boundary)
        account_type: Account type classification
        currency: Account currency (default: EUR)
    """

    def __init__(
        self,
        id: str,
        name: str,
        scope: AccountScope,
        account_type: AccountType,
        currency: str = "EUR",
    ):
        self.id = id
        self.name = name
        self.scope = scope
        self.account_type = account_type
        self.currency = currency

    def is_internal(self) -> bool:
        """Check if account is internal scope."""
        return self.scope == AccountScope.INTERNAL

    def is_boundary(self) -> bool:
        """Check if account is boundary scope."""
        return self.scope == AccountScope.BOUNDARY

    def is_asset(self) -> bool:
        """Check if account is an asset."""
        return self.account_type == AccountType.ASSET

    def is_liability(self) -> bool:
        """Check if account is a liability."""
        return self.account_type == AccountType.LIABILITY

    def is_income(self) -> bool:
        """Check if account is income."""
        return self.account_type == AccountType.INCOME

    def is_expense(self) -> bool:
        """Check if account is expense."""
        return self.account_type == AccountType.EXPENSE

    def is_equity(self) -> bool:
        """Check if account is equity."""
        return self.account_type == AccountType.EQUITY

    def is_pnl(self) -> bool:
        """Check if account is P&L."""
        return self.account_type == AccountType.PNL

    def __str__(self) -> str:
        return f"{self.id} ({self.name})"

    def __repr__(self) -> str:
        return f"Account(id='{self.id}', scope={self.scope.value}, type={self.account_type.value})"


class AccountRegistry:
    """
    Registry for managing account definitions and scope validation.
    """

    def __init__(self):
        self._accounts: dict[str, Account] = {}
        self._scope_rules: dict[str, set[AccountScope]] = {}
        # Auto-register boundary account
        boundary_account = Account(
            id=BOUNDARY_NODE_ID,
            name="Boundary Interface",
            scope=AccountScope.BOUNDARY,
            account_type=AccountType.PNL,
        )
        self.register_account(boundary_account)

    def register_account(self, account: Account) -> None:
        """Register an account."""
        self._accounts[account.id] = account

    def get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        return self._accounts.get(account_id)

    def has_account(self, account_id: str) -> bool:
        """Check if account exists."""
        return account_id in self._accounts

    def get_accounts_by_scope(self, scope: AccountScope) -> set[Account]:
        """Get all accounts with specified scope."""
        return {acc for acc in self._accounts.values() if acc.scope == scope}

    def get_internal_accounts(self) -> set[Account]:
        """Get all internal accounts."""
        return self.get_accounts_by_scope(AccountScope.INTERNAL)

    def get_boundary_accounts(self) -> set[Account]:
        """Get all boundary accounts."""
        return self.get_accounts_by_scope(AccountScope.BOUNDARY)

    def validate_transfer_accounts(
        self, from_account_id: str, to_account_id: str
    ) -> None:
        """
        Validate that transfer accounts are both internal.

        Args:
            from_account_id: Source account ID
            to_account_id: Destination account ID

        Raises:
            ValueError: If either account is not internal
        """
        from_account = self.get_account(from_account_id)
        to_account = self.get_account(to_account_id)

        if not from_account:
            raise ValueError(f"Source account '{from_account_id}' not found")
        if not to_account:
            raise ValueError(f"Destination account '{to_account_id}' not found")

        if not from_account.is_internal():
            raise ValueError(
                f"Source account '{from_account_id}' must be internal (scope: {from_account.scope.value})"
            )
        if not to_account.is_internal():
            raise ValueError(
                f"Destination account '{to_account_id}' must be internal (scope: {to_account.scope.value})"
            )

    def validate_flow_accounts(
        self, boundary_account_id: str, internal_account_ids: list[str]
    ) -> None:
        """
        Validate that flow accounts have exactly one boundary and one/many internal.

        Args:
            boundary_account_id: Boundary account ID
            internal_account_ids: List of internal account IDs

        Raises:
            ValueError: If account scope validation fails
        """
        boundary_account = self.get_account(boundary_account_id)
        if not boundary_account:
            raise ValueError(f"Boundary account '{boundary_account_id}' not found")
        if not boundary_account.is_boundary():
            raise ValueError(
                f"Account '{boundary_account_id}' must be boundary (scope: {boundary_account.scope.value})"
            )

        for internal_account_id in internal_account_ids:
            internal_account = self.get_account(internal_account_id)
            if not internal_account:
                raise ValueError(f"Internal account '{internal_account_id}' not found")
            if not internal_account.is_internal():
                raise ValueError(
                    f"Account '{internal_account_id}' must be internal (scope: {internal_account.scope.value})"
                )

    def get_account_by_node_id(self, node_id: str) -> Optional[Account]:
        """
        Get account by node ID (a:/l:/b:boundary).

        Args:
            node_id: Node ID to look up

        Returns:
            Account if found, None otherwise
        """
        return self.get_account(node_id)

    def register_brick_account(self, brick_id: str, family: str, name: str) -> Account:
        """
        Register an account for a brick with automatic node ID mapping.

        Args:
            brick_id: Brick identifier
            family: Brick family ('a', 'l', 'f', 't')
            name: Human-readable account name

        Returns:
            Registered Account instance
        """
        # Map family to account type and scope
        if family == "a":
            account_type = AccountType.ASSET
            scope = AccountScope.INTERNAL
            node_id = f"a:{brick_id}"
        elif family == "l":
            account_type = AccountType.LIABILITY
            scope = AccountScope.INTERNAL
            node_id = f"l:{brick_id}"
        elif family == "f":
            # FlowShell - parent only, not posted to
            account_type = AccountType.PNL
            scope = AccountScope.BOUNDARY
            node_id = f"fs:{brick_id}"
        elif family == "t":
            # TransferShell - parent only, not posted to
            account_type = AccountType.PNL
            scope = AccountScope.INTERNAL
            node_id = f"ts:{brick_id}"
        else:
            raise ValueError(f"Unknown brick family: {family}")

        account = Account(
            id=node_id,
            name=name,
            scope=scope,
            account_type=account_type,
        )
        self.register_account(account)
        return account


def infer_account_scope(account_id: str, account_name: str = "") -> AccountScope:
    """
    Infer account scope from account ID and name.

    Args:
        account_id: Account identifier
        account_name: Account name (optional)

    Returns:
        Inferred account scope
    """
    # Check for boundary account patterns
    boundary_patterns = [
        "income:",
        "expense:",
        "equity:",
        "pnl:",
        "profit:",
        "loss:",
        "salary",
        "wage",
        "dividend",
        "interest_income",
        "rent",
        "groceries",
        "utilities",
        "insurance",
        "tax",
        "opening_balance",
        "retained_earnings",
    ]

    account_lower = (account_id + " " + account_name).lower()

    for pattern in boundary_patterns:
        if pattern in account_lower:
            return AccountScope.BOUNDARY

    # Default to internal for assets and liabilities
    return AccountScope.INTERNAL


def infer_account_type(account_id: str, account_name: str = "") -> AccountType:
    """
    Infer account type from account ID and name.

    Args:
        account_id: Account identifier
        account_name: Account name (optional)

    Returns:
        Inferred account type
    """
    account_lower = (account_id + " " + account_name).lower()

    # Income patterns
    if any(
        pattern in account_lower
        for pattern in ["income:", "salary", "wage", "dividend", "interest_income"]
    ):
        return AccountType.INCOME

    # Expense patterns
    if any(
        pattern in account_lower
        for pattern in [
            "expense:",
            "rent",
            "groceries",
            "utilities",
            "insurance",
            "tax",
        ]
    ):
        return AccountType.EXPENSE

    # Equity patterns
    if any(
        pattern in account_lower
        for pattern in ["equity:", "opening_balance", "retained_earnings"]
    ):
        return AccountType.EQUITY

    # P&L patterns
    if any(
        pattern in account_lower
        for pattern in ["pnl:", "profit:", "loss:", "unrealized", "revaluation", "fx"]
    ):
        return AccountType.PNL

    # Liability patterns
    if any(
        pattern in account_lower
        for pattern in ["liability:", "mortgage", "loan", "debt", "credit"]
    ):
        return AccountType.LIABILITY

    # Default to asset
    return AccountType.ASSET


def get_node_id(brick_id: str, family: str) -> str:
    """
    Get node ID from brick ID and family.

    Args:
        brick_id: Brick identifier
        family: Brick family ('a', 'l', 'f', 't')

    Returns:
        Node ID string (a:<brick_id>, l:<brick_id>, fs:<brick_id>, ts:<brick_id>)
    """
    if family == "a":
        return f"a:{brick_id}"
    elif family == "l":
        return f"l:{brick_id}"
    elif family == "f":
        return f"fs:{brick_id}"
    elif family == "t":
        return f"ts:{brick_id}"
    else:
        raise ValueError(f"Unknown brick family: {family}")


def get_brick_id_from_node(node_id: str) -> str | None:
    """
    Extract brick ID from node ID.

    Args:
        node_id: Node ID (a:<brick_id>, l:<brick_id>, fs:<brick_id>, ts:<brick_id>, b:boundary)

    Returns:
        Brick ID if node ID is a brick node, None for boundary
    """
    if node_id == BOUNDARY_NODE_ID:
        return None

    if node_id.startswith("a:") or node_id.startswith("l:"):
        return node_id[2:]
    elif node_id.startswith("fs:") or node_id.startswith("ts:"):
        return node_id[3:]
    else:
        # Unknown format, return as-is
        return node_id


def is_boundary_node(node_id: str) -> bool:
    """
    Check if node ID is the boundary node.

    Args:
        node_id: Node ID to check

    Returns:
        True if node ID is boundary
    """
    return node_id == BOUNDARY_NODE_ID


def get_node_scope(node_id: str, registry: AccountRegistry) -> AccountScope:
    """
    Get account scope for a node ID.

    Args:
        node_id: Node ID
        registry: Account registry

    Returns:
        Account scope
    """
    account = registry.get_account_by_node_id(node_id)
    if account:
        return account.scope

    # Default based on node ID prefix
    if node_id == BOUNDARY_NODE_ID or node_id.startswith("fs:"):
        return AccountScope.BOUNDARY
    return AccountScope.INTERNAL


def get_node_type(node_id: str | None, registry: AccountRegistry) -> AccountType:
    """
    Get account type for a node ID.

    Args:
        node_id: Node ID (may be None for legacy entries)
        registry: Account registry

    Returns:
        Account type

    Raises:
        ValueError: If node_id is None (legacy entries not supported)
    """
    if node_id is None:
        raise ValueError("node_id is None - legacy entry format not supported in V2")

    account = registry.get_account_by_node_id(node_id)
    if account:
        return account.account_type

    # Default based on node ID prefix
    if node_id.startswith("a:"):
        return AccountType.ASSET
    elif node_id.startswith("l:"):
        return AccountType.LIABILITY
    elif node_id == BOUNDARY_NODE_ID or node_id.startswith("fs:"):
        return AccountType.PNL
    else:
        return AccountType.ASSET
