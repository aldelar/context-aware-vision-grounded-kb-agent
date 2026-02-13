# Azure KB Ingestion — Makefile
# ==============================================================================
# Targets for local development, Azure provisioning, and pipeline execution.
#
# Local targets use kb/staging/ (source articles) and kb/serving/ (processed output).
# Azure targets operate against deployed Azure resources via AZD.
# ==============================================================================

# Discover articles in local staging folder
STAGING_ARTICLES := $(notdir $(wildcard kb/staging/*))

.DEFAULT_GOAL := help

# ------------------------------------------------------------------------------
# Help
# ------------------------------------------------------------------------------
.PHONY: help
help: ## Show available targets
	@echo ""
	@echo "  Local Development"
	@echo "  ─────────────────"
	@grep -E '^(dev-|convert|index|test)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[36m%-24s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Azure Operations"
	@echo "  ─────────────────"
	@grep -E '^azure-[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[36m%-24s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ------------------------------------------------------------------------------
# Local Development — Prerequisites
# ------------------------------------------------------------------------------
.PHONY: dev-doctor dev-setup

dev-doctor: ## Check if required dev tools are installed
	@echo "Checking development prerequisites...\n"
	@status=0; \
	for cmd in az azd uv python3 func; do \
		printf "  %-12s" "$$cmd"; \
		if command -v $$cmd >/dev/null 2>&1; then \
			if [ "$$cmd" = "azd" ]; then \
				version=$$($$cmd version 2>&1 | head -1); \
			else \
				version=$$($$cmd --version 2>&1 | head -1); \
			fi; \
			printf "\033[32m✔\033[0m  $$version\n"; \
		else \
			printf "\033[31m✘  not found\033[0m\n"; \
			status=1; \
		fi; \
	done; \
	echo ""; \
	if [ $$status -eq 0 ]; then \
		echo "\033[32mAll prerequisites met.\033[0m"; \
	else \
		echo "\033[31mSome tools are missing. Run 'make dev-setup' to install.\033[0m"; \
	fi

dev-setup: ## Install required dev tools (az, azd, uv, func)
	@bash scripts/dev-setup.sh

# ------------------------------------------------------------------------------
# Local Development — Pipeline
# ------------------------------------------------------------------------------
.PHONY: convert index test

test: ## Run unit tests (pytest)
	@cd src/functions && uv run pytest tests/ -v

convert: ## Run fn-convert locally (kb/staging → kb/serving)
	@if [ -z "$(STAGING_ARTICLES)" ]; then \
		echo "No articles found in kb/staging/. Add article folders first."; \
		exit 1; \
	fi
	@for article in $(STAGING_ARTICLES); do \
		echo "\n=== fn-convert: $$article ==="; \
		(cd src && uv run python fn_convert.py --article $$article); \
	done

index: ## Run fn-index locally (kb/serving → Azure AI Search)
	@SERVING_ARTICLES=$$(ls -d kb/serving/*/ 2>/dev/null | xargs -I{} basename {}); \
	if [ -z "$$SERVING_ARTICLES" ]; then \
		echo "No articles found in kb/serving/. Run 'make convert' first."; \
		exit 1; \
	fi; \
	for article in $$SERVING_ARTICLES; do \
		echo "\n=== fn-index: $$article ==="; \
		(cd src && uv run python fn_index.py --article $$article); \
	done

# ------------------------------------------------------------------------------
# Azure — Provision & Deploy
# ------------------------------------------------------------------------------
.PHONY: azure-provision azure-deploy

azure-provision: ## Provision all Azure resources (azd provision)
	azd provision

azure-deploy: ## Deploy functions, search index, and CU analyzer (azd deploy)
	azd deploy
	@echo "Deploying kb-image-analyzer..."
	@(cd src && uv run python manage_analyzers.py deploy)

# ------------------------------------------------------------------------------
# Azure — Run Pipeline
# ------------------------------------------------------------------------------
.PHONY: azure-convert azure-index

azure-convert: ## Trigger fn-convert in Azure (processes staging → serving)
	@echo "Triggering fn-convert Azure Function..."
	func azure functionapp publish $$(azd env get-value FUNCTION_APP_NAME) 2>/dev/null || true
	@echo "TODO: invoke fn-convert HTTP trigger endpoint"

azure-index: ## Trigger fn-index in Azure (processes serving → AI Search)
	@echo "Triggering fn-index Azure Function..."
	@echo "TODO: invoke fn-index HTTP trigger endpoint"

# ------------------------------------------------------------------------------
# Azure — Cleanup
# ------------------------------------------------------------------------------
.PHONY: azure-clean-storage azure-clean-index azure-clean

azure-clean-storage: ## Empty staging and serving blob containers in Azure
	@echo "Cleaning staging container..."
	az storage blob delete-batch \
		--account-name $$(azd env get-value STAGING_STORAGE_ACCOUNT) \
		--source staging \
		--auth-mode login
	@echo "Cleaning serving container..."
	az storage blob delete-batch \
		--account-name $$(azd env get-value SERVING_STORAGE_ACCOUNT) \
		--source serving \
		--auth-mode login
	@echo "Done."

azure-clean-index: ## Delete the AI Search index
	@echo "Deleting kb-articles index..."
	az search index delete \
		--name kb-articles \
		--service-name $$(azd env get-value SEARCH_SERVICE_NAME) \
		--resource-group $$(azd env get-value RESOURCE_GROUP) \
		--yes
	@echo "Done."

azure-clean: azure-clean-storage azure-clean-index ## Clean all Azure data (storage + index + analyzer)
	@echo "Deleting kb-image-analyzer..."
	@(cd src && uv run python manage_analyzers.py delete) 2>/dev/null || true
	@echo "All Azure data cleaned."
