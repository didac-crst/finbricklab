"""Generate API reference pages for MkDocs."""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files

SRC = Path("src")
PKG = "finbricklab"

# Generate reference pages for each Python module
for path in sorted((SRC / PKG).rglob("*.py")):
    if path.name == "__init__.py":
        continue

    mod = ".".join(path.relative_to(SRC).with_suffix("").parts)
    doc_path = Path("reference", *path.relative_to(SRC).with_suffix(".md").parts)

    with mkdocs_gen_files.open(doc_path, "w") as fd:
        print(f"::: {mod}", file=fd)

# Generate the reference index page
with mkdocs_gen_files.open("reference/index.md", "w") as fd:
    print("# API Reference", file=fd)
    print("", file=fd)
    print("Browse the API by module. Use the search for quick jumps.", file=fd)
    print("", file=fd)
    print("## Core Modules", file=fd)
    print("- [finbricklab.core.scenario](finbricklab/core/scenario.md)", file=fd)
    print("- [finbricklab.core.bricks](finbricklab/core/bricks.md)", file=fd)
    print("- [finbricklab.core.entity](finbricklab/core/entity.md)", file=fd)
    print("- [finbricklab.core.context](finbricklab/core/context.md)", file=fd)
    print("- [finbricklab.core.results](finbricklab/core/results.md)", file=fd)
    print("", file=fd)
    print("## Strategies", file=fd)
    print(
        "- [finbricklab.strategies.valuation.cash](finbricklab/strategies/valuation/cash.md)",
        file=fd,
    )
    print(
        "- [finbricklab.strategies.valuation.etf_unitized](finbricklab/strategies/valuation/etf_unitized.md)",
        file=fd,
    )
    print(
        "- [finbricklab.strategies.valuation.property_discrete](finbricklab/strategies/valuation/property_discrete.md)",
        file=fd,
    )
    print(
        "- [finbricklab.strategies.flow.income](finbricklab/strategies/flow/income.md)",
        file=fd,
    )
    print(
        "- [finbricklab.strategies.flow.expense](finbricklab/strategies/flow/expense.md)",
        file=fd,
    )
    print(
        "- [finbricklab.strategies.flow.transfer](finbricklab/strategies/flow/transfer.md)",
        file=fd,
    )
    print(
        "- [finbricklab.strategies.schedule.mortgage_annuity](finbricklab/strategies/schedule/mortgage_annuity.md)",
        file=fd,
    )
    print("", file=fd)
    print("## Utilities", file=fd)
    print("- [finbricklab.charts](finbricklab/charts.md)", file=fd)
    print("- [finbricklab.cli](finbricklab/cli.md)", file=fd)
    print("- [finbricklab.fx](finbricklab/fx.md)", file=fd)
    print("- [finbricklab.kpi](finbricklab/kpi.md)", file=fd)
