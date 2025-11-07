"""Shared validation helpers for transfer strategies."""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from decimal import Decimal, InvalidOperation
from typing import Any

from finbricklab.core.accounts import BOUNDARY_NODE_ID, FX_CLEAR_NODE_ID, get_node_id
from finbricklab.core.errors import ConfigError

_BOUNDARY_ACCOUNT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*:[^:\s]+$")
_ALLOWED_INTERNAL_PREFIXES = {"a", "l"}
_ALLOWED_BOUNDARY_IDS = {BOUNDARY_NODE_ID, FX_CLEAR_NODE_ID}


def validate_fee_account(brick_id: str, account: Any) -> str:
    """Validate and normalize a fee account identifier.

    Args:
        brick_id: The identifier of the brick being prepared/simulated.
        account: Raw account value provided via the brick specification.

    Returns:
        Normalized node ID for the fee account.

    Raises:
        ConfigError: If the account value is missing or malformed.
    """

    if not isinstance(account, str) or not account.strip():
        raise ConfigError(f"{brick_id}: Fee 'account' must be a non-empty string")

    account_str = account.strip()

    if account_str in _ALLOWED_BOUNDARY_IDS:
        return account_str

    if ":" not in account_str:
        raise ConfigError(
            f"{brick_id}: Fee account '{account_str}' must include a scope prefix"
        )

    prefix, identifier = account_str.split(":", 1)
    prefix_normalized = prefix.strip().lower()
    identifier = identifier.strip()

    if not identifier:
        raise ConfigError(f"{brick_id}: Fee account identifier cannot be empty")

    if prefix_normalized in _ALLOWED_INTERNAL_PREFIXES:
        return get_node_id(identifier, prefix_normalized)

    if not _BOUNDARY_ACCOUNT_PATTERN.match(account_str):
        raise ConfigError(
            f"{brick_id}: Fee account '{account_str}' is not a recognized internal or boundary"
            " identifier"
        )

    return account_str


_ISO_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")


def validate_fx_spec(
    brick_id: str, fx_spec: MutableMapping[str, Any], source_currency: str
) -> tuple[str, str, Decimal, Decimal | None]:
    """Validate FX configuration for a transfer.

    Args:
        brick_id: Identifier of the brick using the FX spec.
        fx_spec: Mutable FX configuration mapping.
        source_currency: Currency code of the source leg (usually the transfer currency).

    Returns:
        Tuple of (source_currency_code, dest_currency_code, rate, amount_dest_override).

    Raises:
        ConfigError: If the FX configuration is malformed.
    """

    if not isinstance(fx_spec, MutableMapping):
        raise ConfigError(f"{brick_id}: FX configuration must be a mapping")

    raw_pair = fx_spec.get("pair")
    if not isinstance(raw_pair, str) or not raw_pair.strip():
        raise ConfigError(f"{brick_id}: FX 'pair' must be a non-empty string")

    pair_parts = [part.strip().upper() for part in raw_pair.split("/")]
    if len(pair_parts) != 2 or any(not part for part in pair_parts):
        raise ConfigError(
            f"{brick_id}: FX 'pair' must contain exactly two ISO codes separated by '/'"
        )

    pair_source, pair_dest = pair_parts
    if not _ISO_CODE_PATTERN.match(pair_source) or not _ISO_CODE_PATTERN.match(
        pair_dest
    ):
        raise ConfigError(
            f"{brick_id}: FX currencies must be 3-letter ISO codes; got '{raw_pair}'"
        )

    transfer_currency = (source_currency or "").strip().upper()
    if transfer_currency and pair_source != transfer_currency:
        raise ConfigError(
            f"{brick_id}: FX pair source currency '{pair_source}' must match transfer"
            f" currency '{transfer_currency}'"
        )

    raw_rate = fx_spec.get("rate")
    try:
        rate = Decimal(str(raw_rate))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ConfigError(f"{brick_id}: FX 'rate' must be a positive decimal") from exc

    if rate <= 0:
        raise ConfigError(f"{brick_id}: FX 'rate' must be greater than zero")

    raw_amount_dest = fx_spec.get("amount_dest")
    amount_dest: Decimal | None = None
    if raw_amount_dest is not None:
        try:
            amount_dest = Decimal(str(raw_amount_dest))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ConfigError(
                f"{brick_id}: FX 'amount_dest' must be a positive decimal when provided"
            ) from exc

        if amount_dest <= 0:
            raise ConfigError(
                f"{brick_id}: FX 'amount_dest' must be greater than zero when provided"
            )

    fx_spec["pair"] = f"{pair_source}/{pair_dest}"
    fx_spec["rate"] = rate
    if amount_dest is not None:
        fx_spec["amount_dest"] = amount_dest
    elif "amount_dest" in fx_spec:
        del fx_spec["amount_dest"]

    fx_spec["_pair_codes"] = (pair_source, pair_dest)
    fx_spec["_rate_decimal"] = rate
    if amount_dest is not None:
        fx_spec["_amount_dest_decimal"] = amount_dest
    else:
        fx_spec.pop("_amount_dest_decimal", None)

    return pair_source, pair_dest, rate, amount_dest
