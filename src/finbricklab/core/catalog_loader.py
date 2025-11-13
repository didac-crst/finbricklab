"""Utilities for loading brick catalogs from YAML/JSON sources."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

try:  # PyYAML is declared as a runtime dependency but guard for safety
    import yaml
except ImportError:  # pragma: no cover - fallback for reduced installs
    yaml = None  # type: ignore[assignment]

__all__ = [
    "CatalogError",
    "CatalogDefinition",
    "BrickDirective",
    "MacroBrickDirective",
    "load_catalog",
]


class CatalogError(ValueError):
    """Raised when a catalog file cannot be parsed or validated."""


@dataclass(slots=True)
class BrickDirective:
    """Normalized brick payload ready for registration in an Entity."""

    family: str
    id: str | None
    name: str
    kind: str
    currency: str | None
    spec: dict[str, Any]
    links: dict[str, Any] | None
    start_date: date | None
    end_date: date | None
    duration_m: int | None
    transparent: bool | None = None
    notes: str | None = None


@dataclass(slots=True)
class MacroBrickDirective:
    """Normalized macrobrick payload ready for registration in an Entity."""

    id: str | None
    name: str
    members: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CatalogDefinition:
    """Structured representation of a brick catalog."""

    bricks: list[BrickDirective]
    macrobricks: list[MacroBrickDirective]
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "<memory>"


@dataclass(slots=True)
class _CatalogDefaults:
    """Helper container for default sections inside a catalog file."""

    currency: str | None = None
    spec: dict[str, Any] | None = None
    links: dict[str, Any] | None = None
    window: dict[str, Any] | None = None


def load_catalog(
    source: str | Path | dict[str, Any], *, format: str | None = None
) -> CatalogDefinition:
    """Parse a brick catalog from YAML/JSON/dict into normalized directives."""

    mapping, label = _read_source(source, format=format)
    defaults = _normalize_defaults(mapping.get("defaults"), label)
    bricks = _normalize_bricks(mapping.get("bricks"), defaults, label)
    macrobricks = _normalize_macrobricks(mapping.get("macrobricks"), label)
    metadata = {
        "version": mapping.get("version", 1),
        "entity": _ensure_dict(mapping.get("entity"), f"{label}::entity"),
    }
    return CatalogDefinition(
        bricks=bricks,
        macrobricks=macrobricks,
        metadata=metadata,
        source=label,
    )


def _read_source(
    source: str | Path | dict[str, Any], *, format: str | None
) -> tuple[dict[str, Any], str]:
    if isinstance(source, dict):
        return deepcopy(source), "<mapping>"

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(path)

    fmt = (format or path.suffix.lstrip(".")).lower()
    text = path.read_text(encoding="utf-8")
    if fmt in {"yaml", "yml", ""}:
        if yaml is None:
            raise CatalogError(
                "PyYAML is required to parse YAML catalogs. Install with 'pip install PyYAML'."
            )
        data = yaml.safe_load(text)
    elif fmt == "json":
        data = json.loads(text)
    else:
        raise CatalogError(f"Unsupported catalog format '{fmt}' for {path}")

    if not isinstance(data, dict):
        raise CatalogError(f"Catalog root must be a mapping (source={path})")
    return data, str(path)


def _normalize_defaults(raw: Any, label: str) -> _CatalogDefaults:
    if raw is None:
        return _CatalogDefaults()
    defaults = _ensure_dict(raw, f"{label}::defaults")
    return _CatalogDefaults(
        currency=_coerce_optional_str(
            defaults.get("currency"), f"{label}::defaults.currency"
        ),
        spec=_ensure_dict(defaults.get("spec"), f"{label}::defaults.spec") or None,
        links=_ensure_dict(defaults.get("links"), f"{label}::defaults.links") or None,
        window=_ensure_dict(defaults.get("window"), f"{label}::defaults.window")
        or None,
    )


def _normalize_bricks(
    raw: Any, defaults: _CatalogDefaults, label: str
) -> list[BrickDirective]:
    entries = _ensure_list(raw, f"{label}::bricks")
    if not entries:
        raise CatalogError(f"{label}: catalog must define at least one brick")

    bricks: list[BrickDirective] = []
    for idx, entry in enumerate(entries):
        ctx = f"{label}::bricks[{idx}]"
        data = _ensure_dict(entry, ctx)
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise CatalogError(f"{ctx}: 'name' is required")
        kind = data.get("kind")
        if not isinstance(kind, str) or not kind.strip():
            raise CatalogError(f"{ctx}: 'kind' is required")
        family = _infer_family(kind, ctx)
        spec = _deep_merge(defaults.spec, _ensure_dict(data.get("spec"), f"{ctx}.spec"))
        if spec is None:
            raise CatalogError(f"{ctx}: 'spec' is required (can be empty dict)")
        links = _deep_merge(
            defaults.links, _ensure_dict(data.get("links"), f"{ctx}.links")
        )
        window = _deep_merge(
            defaults.window, _ensure_dict(data.get("window"), f"{ctx}.window")
        )
        start_date = (
            _coerce_date(window.get("start"), f"{ctx}.window.start") if window else None
        )
        end_date = (
            _coerce_date(window.get("end"), f"{ctx}.window.end") if window else None
        )
        duration_m = (
            _coerce_duration(window.get("duration_m"), f"{ctx}.window.duration_m")
            if window
            else None
        )
        currency = data.get("currency") or defaults.currency
        if currency is not None:
            currency = _coerce_str(currency, f"{ctx}.currency")
        transparent = data.get("transparent")
        if transparent is not None and not isinstance(transparent, bool):
            raise CatalogError(f"{ctx}.transparent must be boolean when provided")
        notes = data.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise CatalogError(f"{ctx}.notes must be a string when provided")

        bricks.append(
            BrickDirective(
                family=family,
                id=data.get("id"),
                name=name,
                kind=kind,
                currency=currency,
                spec=spec,
                links=links,
                start_date=start_date,
                end_date=end_date,
                duration_m=duration_m,
                transparent=transparent,
                notes=notes,
            )
        )
    return bricks


def _normalize_macrobricks(raw: Any, label: str) -> list[MacroBrickDirective]:
    entries = _ensure_list(raw, f"{label}::macrobricks", allow_none=True)
    if entries is None:
        return []

    macros: list[MacroBrickDirective] = []
    for idx, entry in enumerate(entries):
        ctx = f"{label}::macrobricks[{idx}]"
        data = _ensure_dict(entry, ctx)
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise CatalogError(f"{ctx}: 'name' is required")
        members = _ensure_str_list(data.get("members"), f"{ctx}.members")
        if not members:
            raise CatalogError(f"{ctx}: 'members' must list at least one id")
        tags = _ensure_str_list(data.get("tags"), f"{ctx}.tags", allow_none=True) or []
        macros.append(
            MacroBrickDirective(
                id=data.get("id"),
                name=name,
                members=members,
                tags=tags,
            )
        )
    return macros


def _infer_family(kind: str, ctx: str) -> str:
    family = kind.split(".", 1)[0].lower() if kind else ""
    if family and family[0] in {"a", "l", "f", "t"}:
        return family[0]
    raise CatalogError(f"{ctx}: could not infer brick family from kind '{kind}'")


def _coerce_date(value: Any, ctx: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:  # pragma: no cover - defensive
            raise CatalogError(f"{ctx}: invalid ISO date '{value}'") from exc
    raise CatalogError(f"{ctx}: expected ISO date string")


def _coerce_duration(value: Any, ctx: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):  # Avoid bool being treated as int
        raise CatalogError(f"{ctx}: duration must be integer months")
    if isinstance(value, (int, float)):
        ivalue = int(value)
        if ivalue < 1:
            raise CatalogError(f"{ctx}: duration must be >= 1 month")
        return ivalue
    raise CatalogError(f"{ctx}: duration must be an integer")


def _coerce_str(value: Any, ctx: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{ctx}: expected non-empty string")
    return value


def _coerce_optional_str(value: Any, ctx: str) -> str | None:
    if value is None:
        return None
    return _coerce_str(value, ctx)


def _ensure_dict(value: Any, ctx: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise CatalogError(f"{ctx}: expected a mapping")
    return deepcopy(value)


def _ensure_list(value: Any, ctx: str, *, allow_none: bool = False) -> list[Any] | None:
    if value is None:
        if allow_none:
            return None
        raise CatalogError(f"{ctx}: expected a list")
    if not isinstance(value, list):
        raise CatalogError(f"{ctx}: expected a list")
    return list(value)


def _ensure_str_list(
    value: Any, ctx: str, *, allow_none: bool = False
) -> list[str] | None:
    entries = _ensure_list(value, ctx, allow_none=allow_none)
    if entries is None:
        return None
    out: list[str] = []
    for idx, item in enumerate(entries):
        if not isinstance(item, str) or not item.strip():
            raise CatalogError(f"{ctx}[{idx}]: expected non-empty string")
        out.append(item)
    return out


def _deep_merge(
    base: dict[str, Any] | None, override: dict[str, Any] | None
) -> dict[str, Any] | None:
    if base is None and override is None:
        return None
    result: dict[str, Any] = deepcopy(base) if base else {}
    if override:
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = _deep_merge(result[key], value) or {}
            else:
                result[key] = deepcopy(value)
    return result
