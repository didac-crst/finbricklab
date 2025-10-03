"""Generate navigation structure for API reference documentation."""
from pathlib import Path

import mkdocs_gen_files

SRC = Path("src")
PKG = "finbricklab"

for path in sorted((SRC / PKG).rglob("*.py")):
    if path.name == "__init__.py":
        continue
    mod = ".".join(path.relative_to(SRC).with_suffix("").parts)
    doc_path = Path("reference", *path.relative_to(SRC).with_suffix(".md").parts)

    with mkdocs_gen_files.open(doc_path, "w") as fd:
        print(f"::: {mod}", file=fd)
