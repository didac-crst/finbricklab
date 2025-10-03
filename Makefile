.PHONY: docs-serve docs-build docs-build-strict docs-check
docs-serve:
	poetry run mkdocs serve
docs-build:
	poetry run mkdocs build
docs-build-strict:
	poetry run mkdocs build --strict
docs-check:
	poetry run interrogate -c pyproject.toml src/finbricklab
