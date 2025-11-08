"""
Shared utilities for loan schedule strategies.
"""

from __future__ import annotations

from typing import Any

from finbricklab.core.accounts import get_node_id
from finbricklab.core.bricks import LBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.errors import ConfigError


def _fallback_cash_node(ctx: ScenarioContext) -> str:
    """
    Determine a reasonable cash node fallback when explicit routing is absent.
    """

    if ctx.settlement_default_cash_id:
        return get_node_id(ctx.settlement_default_cash_id, "a")

    for other_brick in ctx.registry.values():
        if getattr(other_brick, "kind", None) == "a.cash":
            return get_node_id(other_brick.id, "a")

    return "a:cash"


def _resolve_route_leg(
    leg_value: Any,
    *,
    leg_name: str,
    brick: LBrick,
    ctx: ScenarioContext,
) -> str | None:
    """
    Resolve a single routing leg to a cash node.
    """

    if not leg_value:
        return None

    if not isinstance(leg_value, str):
        raise ConfigError(
            f"{brick.id}: links.route.{leg_name} must be a brick id string, "
            f"got {leg_value!r}"
        )

    target_brick = ctx.registry.get(leg_value)
    if target_brick is None:
        raise ConfigError(
            f"{brick.id}: links.route.{leg_name} references unknown brick '{leg_value}'"
        )

    if getattr(target_brick, "kind", None) != "a.cash":
        raise ConfigError(
            f"{brick.id}: links.route.{leg_name} must reference a cash brick "
            f"(kind='a.cash'), got kind '{getattr(target_brick, 'kind', None)}'"
        )

    return get_node_id(leg_value, "a")


def resolve_loan_cash_nodes(brick: LBrick, ctx: ScenarioContext) -> tuple[str, str]:
    """
    Resolve cash nodes for loan drawdowns (route['to']) and payments (route['from']).
    """

    route: dict[str, Any] = {}
    if isinstance(brick.links, dict):
        route = brick.links.get("route") or {}

    draw_node = _resolve_route_leg(route.get("to"), leg_name="to", brick=brick, ctx=ctx)
    pay_node = _resolve_route_leg(
        route.get("from"), leg_name="from", brick=brick, ctx=ctx
    )

    fallback_node = _fallback_cash_node(ctx)
    return draw_node or fallback_node, pay_node or fallback_node
