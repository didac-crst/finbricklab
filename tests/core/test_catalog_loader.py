from __future__ import annotations

from datetime import date
from pathlib import Path

import finbricklab.strategies  # noqa: F401 - ensure registries are wired
import pytest
from finbricklab.core.catalog_loader import CatalogError, load_catalog
from finbricklab.core.entity import Entity

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "catalogs" / "base.yaml"
STARTER_CATALOG = (
    Path(__file__).resolve().parents[2] / "examples" / "catalogs" / "starter.yaml"
)


def _write_catalog(tmp_path: Path) -> Path:
    path = tmp_path / "catalog.yaml"
    path.write_text(CATALOG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def test_load_catalog_merges_defaults(tmp_path: Path) -> None:
    catalog = load_catalog(_write_catalog(tmp_path))

    assert len(catalog.bricks) == 4
    salary = catalog.bricks[1]
    assert salary.family == "f"
    assert salary.currency == "EUR"
    assert salary.start_date == date(2026, 1, 1)

    brokerage = catalog.bricks[2]
    assert brokerage.start_date == date(2026, 3, 1)
    assert brokerage.duration_m == 12

    transfer = catalog.bricks[3]
    assert transfer.family == "t"
    assert transfer.transparent is False

    assert len(catalog.macrobricks) == 2
    assert catalog.macrobricks[1].members == ["liquid"]


def test_entity_ingest_catalog(tmp_path: Path) -> None:
    entity = Entity(name="Catalog Demo")
    summary = entity.ingest_catalog(_write_catalog(tmp_path))

    assert set(summary["bricks"]) >= {
        "cash",
        "brokerage",
        "salary",
        "transfer_brokerage",
    }
    assert set(summary["macrobricks"]) == {"liquid", "portfolio_total"}

    salary = entity.get_brick("salary")
    assert salary is not None
    assert salary.start_date == date(2026, 1, 1)

    transfer = entity.get_brick("transfer_brokerage")
    assert transfer is not None
    assert getattr(transfer, "transparent", True) is False

    macro = entity.get_macrobrick("portfolio_total")
    assert macro is not None
    assert "liquid" in macro.members


def test_invalid_catalog_raises(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("bricks: [{}]", encoding="utf-8")
    with pytest.raises(CatalogError):
        load_catalog(bad_yaml)


def test_starter_catalog_ingest(tmp_path: Path) -> None:
    entity = Entity(name="Starter Demo")
    summary = entity.ingest_catalog(STARTER_CATALOG)

    assert "cash" in summary["bricks"]
    assert {"liquid_assets", "housing_stack"} <= set(summary["macrobricks"])

    scenario = entity.create_scenario(
        id="starter",
        name="Starter Scenario",
        brick_ids=["cash", "salary", "rent", "transfer_savings"],
    )
    assert scenario is not None
