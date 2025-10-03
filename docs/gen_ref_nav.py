"""Generate API reference pages for MkDocs."""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files

SRC = Path("src")
PKG = "finbricklab"

# Collect all modules
modules = []
for path in sorted((SRC / PKG).rglob("*.py")):
    if path.name == "__init__.py":
        continue
    mod = ".".join(path.relative_to(SRC).with_suffix("").parts)
    modules.append(mod)


# Build a hierarchical tree structure
def build_tree(modules):
    """Build a nested tree structure from module names."""
    tree = {}
    for mod in modules:
        parts = mod.split(".")
        current = tree

        # Build nested structure
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Mark as leaf (has actual module)
        current["_module"] = mod

    return tree


def render_tree(tree, level=0, fd=None):
    """Render the tree structure as markdown with proper nesting."""
    # Get all items except the _module marker
    items = [(name, subtree) for name, subtree in tree.items() if name != "_module"]
    # Sort items alphabetically
    items = sorted(items, key=lambda x: x[0])

    for name, subtree in items:
        # Check if this node has a module (is a leaf) or just subdirectories
        has_module = "_module" in subtree
        has_children = any(key != "_module" for key in subtree.keys())

        if has_module and not has_children:
            # This is a leaf node - just show the link
            module_name = subtree["_module"]
            doc_path = f"{module_name.replace('.', '/')}.md"
            indent = "  " * level
            print(f"{indent}- [{name}]({doc_path})", file=fd)
        elif has_children:
            # This is a directory node with children
            if has_module:
                # Directory with both module and children - show as bold with link
                module_name = subtree["_module"]
                doc_path = f"{module_name.replace('.', '/')}.md"
                indent = "  " * level
                print(f"{indent}- **[{name}]({doc_path})**", file=fd)
            else:
                # Just a directory - show as bold
                indent = "  " * level
                print(f"{indent}- **{name}**", file=fd)
            # Recursively render children with proper indentation
            render_tree(subtree, level + 1, fd)


# Generate the main reference index with hierarchical navigation
with mkdocs_gen_files.open("reference/index.md", "w") as fd:
    print("# Reference", file=fd)
    print("", file=fd)
    print("Browse the API by module. Use the search for quick jumps.", file=fd)
    print("", file=fd)

    # Group modules by category for a cleaner display
    util_modules = [
        m
        for m in modules
        if not m.startswith(("finbricklab.core", "finbricklab.strategies"))
    ]
    core_modules = [m for m in modules if m.startswith("finbricklab.core")]
    strategy_modules = [m for m in modules if m.startswith("finbricklab.strategies")]

    # Display utilities first
    if util_modules:
        print("## Utilities", file=fd)
        print("", file=fd)
        for mod in util_modules:
            name = mod.split(".")[-1]
            doc_path = f"{mod.replace('.', '/')}.md"
            print(f"- [{name}]({doc_path})", file=fd)
        print("", file=fd)

    # Display core modules
    if core_modules:
        print("## Core Modules", file=fd)
        print("", file=fd)
        for mod in core_modules:
            name = mod.split(".")[-1]
            doc_path = f"{mod.replace('.', '/')}.md"
            print(f"- [{name}]({doc_path})", file=fd)
        print("", file=fd)

    # Display strategy modules grouped by subcategory
    if strategy_modules:
        print("## Strategy Modules", file=fd)
        print("", file=fd)

        # Group strategies by subcategory
        flow_strategies = [m for m in strategy_modules if "flow" in m]
        schedule_strategies = [m for m in strategy_modules if "schedule" in m]
        valuation_strategies = [m for m in strategy_modules if "valuation" in m]
        other_strategies = [
            m
            for m in strategy_modules
            if not any(x in m for x in ["flow", "schedule", "valuation"])
        ]

        if flow_strategies:
            print("### Flow Strategies", file=fd)
            print("", file=fd)
            for mod in flow_strategies:
                name = mod.split(".")[-1]
                doc_path = f"{mod.replace('.', '/')}.md"
                print(f"- [{name}]({doc_path})", file=fd)
            print("", file=fd)

        if other_strategies:
            print("### Other Strategies", file=fd)
            print("", file=fd)
            for mod in other_strategies:
                name = mod.split(".")[-1]
                doc_path = f"{mod.replace('.', '/')}.md"
                print(f"- [{name}]({doc_path})", file=fd)
            print("", file=fd)

        if schedule_strategies:
            print("### Schedule Strategies", file=fd)
            print("", file=fd)
            for mod in schedule_strategies:
                name = mod.split(".")[-1]
                doc_path = f"{mod.replace('.', '/')}.md"
                print(f"- [{name}]({doc_path})", file=fd)
            print("", file=fd)

        if valuation_strategies:
            print("### Valuation Strategies", file=fd)
            print("", file=fd)
            for mod in valuation_strategies:
                name = mod.split(".")[-1]
                doc_path = f"{mod.replace('.', '/')}.md"
                print(f"- [{name}]({doc_path})", file=fd)
            print("", file=fd)

# Generate individual module pages
for mod in modules:
    doc_path = f"reference/{mod.replace('.', '/')}.md"

    with mkdocs_gen_files.open(doc_path, "w") as fd:
        print(f"# {mod}", file=fd)
        print("", file=fd)
        print(f"::: {mod}", file=fd)
