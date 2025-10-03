"""Generate API reference pages for MkDocs."""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files

SRC = Path("src")
PKG = "finbricklab"

# Generate a single comprehensive reference page instead of individual pages
with mkdocs_gen_files.open("reference/index.md", "w") as fd:
    print("# API Reference", file=fd)
    print("", file=fd)
    print(
        "Complete API documentation for FinBrickLab. Use the search for quick jumps.",
        file=fd,
    )
    print("", file=fd)

    # Generate sections for each module
    modules = []
    for path in sorted((SRC / PKG).rglob("*.py")):
        if path.name == "__init__.py":
            continue
        mod = ".".join(path.relative_to(SRC).with_suffix("").parts)
        modules.append(mod)

    # Group modules by category
    core_modules = [m for m in modules if m.startswith("finbricklab.core")]
    strategy_modules = [m for m in modules if m.startswith("finbricklab.strategies")]
    util_modules = [
        m
        for m in modules
        if not m.startswith(("finbricklab.core", "finbricklab.strategies"))
    ]

    if core_modules:
        print("## Core Modules", file=fd)
        print("", file=fd)
        for mod in core_modules:
            print(f"### {mod}", file=fd)
            print("", file=fd)
            print(f"::: {mod}", file=fd)
            print("", file=fd)

    if strategy_modules:
        print("## Strategies", file=fd)
        print("", file=fd)
        for mod in strategy_modules:
            print(f"### {mod}", file=fd)
            print("", file=fd)
            print(f"::: {mod}", file=fd)
            print("", file=fd)

    if util_modules:
        print("## Utilities", file=fd)
        print("", file=fd)
        for mod in util_modules:
            print(f"### {mod}", file=fd)
            print("", file=fd)
            print(f"::: {mod}", file=fd)
            print("", file=fd)
