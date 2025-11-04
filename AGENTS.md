# Repository Guidelines

## Project Structure & Module Organization
- `src/finbricklab/`: library code
  - `core/`: engine (entities, journal, scenarios, validation)
  - `strategies/`: flow, schedule, transfer, valuation
  - `cli.py`: CLI entry (`poetry run finbrick`)
- `tests/`: pytest suite (`test_*.py`; markers: `slow`, `integration`)
- `docs/` + `mkdocs.yml`: docs site (Material theme)
- `examples/`, `notebooks/`: usage and demos
- `scripts/`: utilities (e.g., `scripts/check_forbidden_tokens.py`)
- `dist/`: build artifacts

## Build, Test, and Development Commands
- Setup: `poetry install --with dev,docs` then `pre-commit install`
- CLI help: `poetry run finbrick --help`
- Tests: `poetry run pytest -q` (exclude slow: `-m "not slow"`)
- Lint/format: `poetry run ruff check . --fix` and `poetry run black .`
- Types: `poetry run mypy src/finbricklab`
- Docs: `make docs-serve`, `make docs-build`, `make docs-check` (docstring coverage)

## Current Architecture Direction (v2)
- Authoritative specs:
  - Logic: `docs/POSTINGS_MODEL_AND_BRICK_TYPES.md`
  - Technical: `docs/TECHNICAL_SPEC_POSTINGS_MODEL.md`
- Key concepts:
  - A/L bricks produce balances only; cash movements come from two-posting journal entries (DR/CR) emitted by strategies.
  - FlowShellBrick/TransferShellBrick generate postings; MacroGroups contain only A/L (and/or nested MacroGroups; DAG).
  - MacroGroup inspection uses journal-first aggregation with internal-transfer cancellation.
- Implementation branch: `feat/postings-model-v2` (no dual path).

## Branching & Release
- Mainline: `main` (stable). Feature work: short-lived branches (e.g., `feat/...`, `fix/...`).
- Small fixes: prefer minimal, forward-compatible PRs to `main`.
- v2 work: open PRs against `feat/postings-model-v2` and link the specs.
- Tagging: match `src/finbricklab/__init__.py::__version__`; create annotated tags (e.g., `v0.1.0`).
- GitHub CLI is available; you may create PRs/releases with `gh pr create` / `gh release create`.

## Validation & Guardrails
- Journal entries must be two-posting and zero-sum per currency; include required metadata (see technical spec).
- MacroGroups must be DAGs; members are A/L or other MacroGroups only (no Shell, no Boundary).
- Transfer visibility defaults to boundary-only for end-user views; expose toggles in CLI.

## Docs Pointers
- Guides live under `docs/` and are surfaced via `mkdocs.yml`:
  - Postings Model & Brick Types: `docs/POSTINGS_MODEL_AND_BRICK_TYPES.md`
  - Technical Spec: `docs/TECHNICAL_SPEC_POSTINGS_MODEL.md`
  - Strategy guides and examples: see `docs/STRATEGIES.md`, `docs/EXAMPLES.md`

## Coding Style & Naming Conventions
- Python 3.11+, Black (88 cols), Ruff (pycodestyle/pyflakes/isort/bugbear/pyupgrade)
- Keep imports sorted; avoid unused code; prefer pure functions where reasonable
- Type hints throughout; Google-style docstrings; docstring coverage ≥ 80% (interrogate)
- Naming: packages/modules `snake_case`; classes `CamelCase`; functions/vars `snake_case`; constants `UPPER_SNAKE_CASE`

## Testing Guidelines
- Place tests under `tests/` mirroring `src/` paths
- Files `test_*.py`, classes `Test*`, functions `test_*`
- Use markers: `slow`, `integration`; default runs exclude `slow`
- Aim for deterministic assertions; property tests with Hypothesis are welcome
- Coverage example: `poetry run pytest --cov -q`

## Commit & Pull Request Guidelines
- Conventional Commits: `type(scope): summary` (e.g., `fix(core): normalize journal timestamps`)
- Keep PRs focused; describe intent, breaking changes, and verification steps; link issues
- Run `pre-commit run -a` before pushing; update tests/docs and `CHANGELOG.md` for user‑facing changes

## Security & Configuration Tips
- Target Python `^3.11`; do not commit secrets or data outputs
- Use `pre-commit` (Black, Ruff, mypy, pytest, interrogate) to enforce quality
