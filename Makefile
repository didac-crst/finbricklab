.PHONY: docs-serve docs-build docs-build-strict docs-check help pr-report pr-report-open pr-report-clean
docs-serve:
	poetry run mkdocs serve
docs-build:
	poetry run mkdocs build
docs-build-strict:
	poetry run mkdocs build --strict
docs-check:
	poetry run interrogate -c pyproject.toml src/finbricklab

# ----------------------------------------
# PR report helpers (requires GitHub CLI `gh`)
# Usage:
#   make pr-report PR=18 [REPO=didac-crst/finbricklab]
# ----------------------------------------

REPO ?= didac-crst/finbricklab
PR_REPORT_DIR ?= var/pr-reports

help: ## Show available make targets
	@awk 'BEGIN {FS=":.*## "}; /^[a-zA-Z0-9_-]+:.*## /{printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

pr-report: ## Fetch PR details and review comments into var/pr-reports/pr-<PR>.md (set PR=<number>)
	@if ! command -v gh >/dev/null 2>&1; then \
		echo "Error: GitHub CLI 'gh' not found. Install from https://cli.github.com/"; \
		exit 1; \
	fi
	@if [ -z "$(PR)" ]; then \
		echo "Usage: make pr-report PR=<number> [REPO=$(REPO)]"; \
		exit 1; \
	fi
	@mkdir -p "$(PR_REPORT_DIR)"
	@out="$(PR_REPORT_DIR)/pr-$(PR).md"; \
	echo "# PR $(PR) report for $(REPO)" > "$$out"; \
	echo "" >> "$$out"; \
	echo "Generated: $$(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> "$$out"; \
	echo "" >> "$$out"; \
	echo "## gh pr view $(PR) -c" >> "$$out"; \
	echo '```' >> "$$out"; \
	gh pr view "$(PR)" -c >> "$$out"; \
	echo '```' >> "$$out"; \
	echo "" >> "$$out"; \
	echo "## Review comments (pulls/$(PR)/comments)" >> "$$out"; \
	echo '```' >> "$$out"; \
	gh api "repos/$(REPO)/pulls/$(PR)/comments" --paginate --jq '.[].body' >> "$$out"; \
	echo '```' >> "$$out"; \
	echo "Saved $$out"

pr-report-open: ## Generate and open the report for PR=<number>
	@if [ -z "$(PR)" ]; then \
		echo "Usage: make pr-report-open PR=<number>"; \
		exit 1; \
	fi
	@$(MAKE) --no-print-directory pr-report PR=$(PR) REPO=$(REPO)
	@open "$(PR_REPORT_DIR)/pr-$(PR).md" 2>/dev/null || true

pr-report-clean: ## Remove all generated PR reports
	@rm -rf "$(PR_REPORT_DIR)"
