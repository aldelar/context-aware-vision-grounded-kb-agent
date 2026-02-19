# Context Aware & Vision Grounded KB Agent — Makefile
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
	@grep -E '^(dev-|convert|index|test|validate|grant|app)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | \
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
.PHONY: dev-doctor dev-setup dev-setup-env

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

dev-setup: ## Install required dev tools and Python dependencies
	@bash scripts/dev-setup.sh
	@echo ""
	@echo "Installing Python dependencies (functions)..."
	@cd src/functions && uv sync --extra dev
	@echo "Installing Python dependencies (web app)..."
	@cd src/web-app && uv sync --extra dev
	@echo "Python dependencies installed."

dev-setup-env: ## Populate .env files from AZD environment (functions + web app)
	@echo "Writing AZD environment values to src/functions/.env..."
	@azd env get-values > src/functions/.env
	@echo "Done. $(shell wc -l < src/functions/.env 2>/dev/null || echo 0) variables written."
	@echo "Writing AZD environment values to src/web-app/.env..."
	@azd env get-values > src/web-app/.env
	@echo "Done. $(shell wc -l < src/web-app/.env 2>/dev/null || echo 0) variables written."

# ------------------------------------------------------------------------------
# Local Development — Pipeline
# ------------------------------------------------------------------------------
.PHONY: convert index test validate-infra

test: ## Run unit tests (pytest)
	@cd src/functions && uv run pytest tests/ -v || test $$? -eq 5

validate-infra: ## Validate Azure infra is ready for local dev
	@bash scripts/functions/validate-infra.sh

convert: ## Run fn-convert locally (kb/staging → kb/serving)
	@bash scripts/functions/convert.sh

index: ## Run fn-index locally (kb/serving → Azure AI Search)
	@bash scripts/functions/index.sh

# ------------------------------------------------------------------------------
# Local Development — Web App
# ------------------------------------------------------------------------------
.PHONY: app app-test

app: ## Run Context Aware & Vision Grounded KB Agent locally (http://localhost:8080)
	@cd src/web-app && uv run chainlit run app/main.py -w --port 8080

app-test: ## Run web app unit tests
	@cd src/web-app && uv run pytest tests/ -v || test $$? -eq 5

# ------------------------------------------------------------------------------
# Local Development — RBAC
# ------------------------------------------------------------------------------
.PHONY: grant-dev-roles

grant-dev-roles: ## Verify developer RBAC roles (provisioned via Bicep)
	@echo "Developer RBAC roles are now managed declaratively via Bicep (infra/)."
	@echo "Run 'make azure-provision' to apply. Checking current assignments..."
	@echo ""
	@set -a && . src/functions/.env && set +a && \
	USER_OID=$$(az ad signed-in-user show --query id -o tsv) && \
	echo "  User: $$USER_OID" && \
	echo "" && \
	echo "  Roles are assigned during 'azd provision' via the principalId parameter." && \
	echo "  If missing, run: make azure-provision"

# ------------------------------------------------------------------------------
# Azure — Provision & Deploy
# ------------------------------------------------------------------------------
.PHONY: azure-provision azure-deploy

azure-provision: ## Provision all Azure resources (azd provision)
	azd provision

azure-deploy: ## Deploy functions, search index, and CU analyzer (azd deploy)
	azd deploy
	@echo "Configuring CU defaults and deploying kb-image-analyzer..."
	@(cd src/functions && uv run python -m manage_analyzers deploy)

# ------------------------------------------------------------------------------
# Azure — Run Pipeline
# ------------------------------------------------------------------------------
.PHONY: azure-upload-staging azure-convert azure-index

azure-upload-staging: ## Upload local kb/staging articles to Azure staging blob
	@echo "Uploading kb/staging/ to Azure staging blob container..."
	@ACCOUNT=$$(azd env get-value STAGING_STORAGE_ACCOUNT) && \
	for dir in kb/staging/*/; do \
		ARTICLE=$$(basename "$$dir") && \
		echo "  ↑ $$ARTICLE" && \
		az storage blob upload-batch \
			--destination staging \
			--source "$$dir" \
			--destination-path "$$ARTICLE" \
			--account-name "$$ACCOUNT" \
			--auth-mode login \
			--overwrite \
			--only-show-errors; \
	done
	@echo "Done."

azure-convert: ## Trigger fn-convert in Azure (processes staging → serving)
	@echo "Triggering fn-convert Azure Function..."
	@APP_NAME=$$(azd env get-value FUNCTION_APP_NAME) && \
	RG=$$(azd env get-value RESOURCE_GROUP) && \
	KEY=$$(az functionapp keys list --name $$APP_NAME --resource-group $$RG --query "functionKeys.default" -o tsv) && \
	ENDPOINT="https://$$APP_NAME.azurewebsites.net/api/convert?code=$$KEY" && \
	echo "  POST $$ENDPOINT" && \
	curl -sf --max-time 600 -X POST "$$ENDPOINT" -H "Content-Type: application/json" -d '{}' | python3 -m json.tool
	@echo ""

azure-index: ## Trigger fn-index in Azure (processes serving → AI Search)
	@echo "Triggering fn-index Azure Function..."
	@APP_NAME=$$(azd env get-value FUNCTION_APP_NAME) && \
	RG=$$(azd env get-value RESOURCE_GROUP) && \
	KEY=$$(az functionapp keys list --name $$APP_NAME --resource-group $$RG --query "functionKeys.default" -o tsv) && \
	ENDPOINT="https://$$APP_NAME.azurewebsites.net/api/index?code=$$KEY" && \
	echo "  POST $$ENDPOINT" && \
	curl -sf --max-time 600 -X POST "$$ENDPOINT" -H "Content-Type: application/json" -d '{}' | python3 -m json.tool
	@echo ""

azure-index-summarize: ## Show AI Search index contents summary
	@cd src/functions && uv run python ../../scripts/functions/display-index-summary.py

# ------------------------------------------------------------------------------
# Azure — Web App
# ------------------------------------------------------------------------------
.PHONY: azure-deploy-app azure-app-url azure-app-logs

azure-deploy-app: ## Build & deploy the web app to Azure Container Apps
	azd deploy --service web-app

azure-app-url: ## Print the deployed web app URL
	@azd env get-value WEBAPP_URL

azure-app-logs: ## Stream live logs from the deployed web app
	@APP=$$(azd env get-value WEBAPP_NAME) && \
	RG=$$(azd env get-value RESOURCE_GROUP) && \
	az containerapp logs show --name $$APP --resource-group $$RG --type console --follow

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
	@cd src/functions && uv run python -c "\
	from shared.config import config; \
	from azure.search.documents.indexes import SearchIndexClient; \
	from azure.identity import DefaultAzureCredential; \
	c = SearchIndexClient(config.search_endpoint, DefaultAzureCredential()); \
	c.delete_index('kb-articles'); \
	print('  Index deleted.')" 2>/dev/null || echo "  Index did not exist."

azure-clean: azure-clean-storage azure-clean-index ## Clean all Azure data (storage + index + analyzer)
	@echo "Deleting kb-image-analyzer..."
	@(cd src/functions && uv run python -m manage_analyzers delete) 2>/dev/null || true
	@echo "All Azure data cleaned."
