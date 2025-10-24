"""
Transfer visibility controls for FinBrickLab analysis.

This module defines how transfer bricks (TBricks) are displayed in analysis views,
allowing users to hide internal transfers while preserving boundary-crossing transfers.
"""

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .journal import JournalEntry


class TransferVisibility(Enum):
    """
    Controls which transfers are visible in analysis views.

    Attributes:
        OFF: Hide internal transfers (INTERNAL→INTERNAL), show boundary transfers
        ONLY: Show only transfers (for debugging)
        ALL: Show all transfers
        BOUNDARY_ONLY: Show only transfers that touch the boundary
    """

    OFF = "off"  # Hide INTERNAL→INTERNAL transfers
    ONLY = "only"  # Show only transfers (debugging)
    ALL = "all"  # Show all transfers
    BOUNDARY_ONLY = "boundary_only"  # Show only boundary-crossing transfers


def is_internal_transfer(entry: "JournalEntry", account_registry) -> bool:
    """
    Determine if a journal entry represents an internal transfer.

    An internal transfer is one where all postings are within the INTERNAL scope
    and the entry type is a transfer.

    Args:
        entry: The journal entry to check
        account_registry: Registry to determine account scopes

    Returns:
        True if this is an internal transfer that should be hidden by default
    """
    from .accounts import AccountScope

    # Check if this is a transfer-type entry
    if entry.metadata.get("transaction_type") not in {"transfer", "tbrick"}:
        return False

    # Get scopes of all accounts involved
    scopes = set()
    for posting in entry.postings:
        account_scope = account_registry.get_scope(posting.account_id)
        scopes.add(account_scope)

    # Internal transfer: all accounts are INTERNAL scope
    return scopes == {AccountScope.INTERNAL}


def touches_boundary(entry: "JournalEntry", account_registry) -> bool:
    """
    Determine if a journal entry touches the boundary (external world).

    Args:
        entry: The journal entry to check
        account_registry: Registry to determine account scopes

    Returns:
        True if any posting involves a BOUNDARY account
    """
    from .accounts import AccountScope

    for posting in entry.postings:
        account_scope = account_registry.get_scope(posting.account_id)
        if account_scope == AccountScope.BOUNDARY:
            return True
    return False


def filter_entries_by_visibility(
    entries: list["JournalEntry"], visibility: TransferVisibility, account_registry
) -> list["JournalEntry"]:
    """
    Filter journal entries based on transfer visibility settings.

    Args:
        entries: List of journal entries to filter
        visibility: The visibility setting to apply
        account_registry: Registry to determine account scopes

    Returns:
        Filtered list of journal entries
    """
    if visibility == TransferVisibility.ALL:
        return entries

    filtered = []
    for entry in entries:
        is_internal = is_internal_transfer(entry, account_registry)
        touches_bound = touches_boundary(entry, account_registry)

        if visibility == TransferVisibility.OFF:
            # Hide internal transfers, show boundary-crossing transfers
            if not is_internal:
                filtered.append(entry)
        elif visibility == TransferVisibility.ONLY:
            # Show only transfers
            if is_internal or touches_bound:
                filtered.append(entry)
        elif visibility == TransferVisibility.BOUNDARY_ONLY:
            # Show only boundary-crossing transfers
            if touches_bound and not is_internal:
                filtered.append(entry)

    return filtered
