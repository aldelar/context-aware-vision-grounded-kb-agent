# Context Aware & Vision Grounded KB Agent — Makefile
# ==============================================================================
# Local targets use kb/staging/ (source) and kb/serving/ (processed output).
# Azure targets operate against deployed Azure resources via AZD.
# Run 'make help' for all available targets.
# ==============================================================================

analyzer ?= mistral-doc-ai

.DEFAULT_GOAL := help

# ==============================================================================
# Help
# ==============================================================================
.PHONY: help
help: ## Show available targets
	@echo ""
	@echo "  \033[1mLocal\033[0m"
	@echo "  ─────"
	@grep -E '^## LOCAL' $(MAKEFILE_LIST) | head -1 > /dev/null
	@awk '/^## LOCAL-START/,/^## LOCAL-END/' $(MAKEFILE_LIST) | \
		grep -E '^[a-zA-Z_-]+:.*?## ' | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[36m%-38s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  \033[1mAzure\033[0m"
	@echo "  ─────"
	@awk '/^## AZURE-START/,/^## AZURE-END/' $(MAKEFILE_LIST) | \
		grep -E '^[a-zA-Z_-]+:.*?## ' | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[36m%-38s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  \033[1mUtilities — Local\033[0m"
	@echo "  ─────────────────"
	@awk '/^## UTIL-LOCAL-START/,/^## UTIL-LOCAL-END/' $(MAKEFILE_LIST) | \
		grep -E '^[a-zA-Z_-]+:.*?## ' | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[36m%-38s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  \033[1mUtilities — Azure\033[0m"
	@echo "  ─────────────────"
	@awk '/^## UTIL-AZURE-START/,/^## UTIL-AZURE-END/' $(MAKEFILE_LIST) | \
		grep -E '^[a-zA-Z_-]+:.*?## ' | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[36m%-38s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ==============================================================================
# Local
# ==============================================================================
## LOCAL-START
.PHONY: setup setup-azure kb test agent app

setup: dev-doctor dev-setup ## Install tools + Python dependencies
	@echo ""
	@echo "\033[32m✅ Local tools and dependencies installed.\033[0m"
	@echo ""
	@echo "  Azure resources are required for local dev (AI Services, Search, Storage)."
	@echo "  If not yet provisioned:"
	@echo "    1. az login && azd init"
	@echo "    2. make setup-azure"
	@echo ""

setup-azure: azure-provision dev-setup-env grant-dev-roles validate-infra ## Provision Azure + configure local env (some Azure services required for dev)

kb: convert index ## Run full local KB pipeline (convert + index)

test: test-agent test-app test-functions ## Run all fast tests (unit + endpoint, no Azure needed)

agent: ## Run KB Agent locally (http://localhost:8088)
	@cd src/agent && uv run python main.py

app: ## Run web app locally (http://localhost:8080)
	@cd src/web-app && uv run chainlit run app/main.py -w --port 8080
## LOCAL-END

# ==============================================================================
# Azure
# ==============================================================================
## AZURE-START
.PHONY: azure-up azure-kb azure-test azure-app-url

azure-up: azure-provision azure-deploy azure-setup-auth ## Full Azure deploy (provision + deploy + auth)

azure-kb: azure-upload-staging azure-convert azure-index ## Full Azure KB pipeline (upload + convert + index)

azure-test: azure-test-agent azure-test-app ## Run all Azure integration tests

azure-app-url: ## Print the deployed web app URL
	@azd env get-value WEBAPP_URL
## AZURE-END

# ==============================================================================
# Utilities — Local
# ==============================================================================
## UTIL-LOCAL-START

# --- Setup ---
.PHONY: dev-doctor dev-setup dev-setup-env validate-infra dev-enable-storage dev-enable-cosmos grant-dev-roles

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
	@echo "Installing Python dependencies (agent)..."
	@cd src/agent && uv sync --extra dev
	@echo "Python dependencies installed."

dev-setup-env: ## Populate .env files from AZD environment
	@echo "Writing AZD environment values to src/functions/.env..."
	@azd env get-values > src/functions/.env
	@echo "Done. $(shell wc -l < src/functions/.env 2>/dev/null || echo 0) variables written."
	@echo "Writing AZD environment values to src/web-app/.env..."
	@azd env get-values > src/web-app/.env
	@echo "Done. $(shell wc -l < src/web-app/.env 2>/dev/null || echo 0) variables written."
	@echo "Writing AZD environment values to src/agent/.env..."
	@azd env get-values > src/agent/.env
	@echo "Done. $(shell wc -l < src/agent/.env 2>/dev/null || echo 0) variables written."

validate-infra: ## Validate Azure infra is ready for local dev
	@bash scripts/functions/validate-infra.sh

dev-enable-storage: ## Re-enable public access on storage accounts (disabled nightly)
	@bash scripts/enable-storage-public-access.sh

dev-enable-cosmos: ## Enable public access on Cosmos DB + add developer IP to firewall
	@bash scripts/enable-cosmos-public-access.sh

grant-dev-roles: ## Grant Cosmos DB native RBAC to current developer
	@echo "Granting developer RBAC roles..."
	@echo ""
	@set -a && . src/functions/.env && set +a && \
	USER_OID=$$(az ad signed-in-user show --query id -o tsv) && \
	echo "  User: $$USER_OID" && \
	echo "" && \
	ENV=$$(azd env get-value AZURE_ENV_NAME 2>/dev/null || echo "dev") && \
	COSMOS_ACCOUNT="cosmos-kbidx-$$ENV" && \
	RG="rg-kbidx-$$ENV" && \
	SUB=$$(az account show --query id -o tsv) && \
	SCOPE="/subscriptions/$$SUB/resourceGroups/$$RG/providers/Microsoft.DocumentDB/databaseAccounts/$$COSMOS_ACCOUNT" && \
	echo "  Cosmos DB: $$COSMOS_ACCOUNT ($$RG)" && \
	echo "  Assigning Cosmos DB Built-in Data Contributor (native RBAC)..." && \
	az cosmosdb sql role assignment create \
		--account-name "$$COSMOS_ACCOUNT" \
		--resource-group "$$RG" \
		--role-definition-id "00000000-0000-0000-0000-000000000002" \
		--principal-id "$$USER_OID" \
		--scope "$$SCOPE" \
		-o none 2>/dev/null && \
	echo "  ✓ Cosmos DB data-plane role assigned." || \
	echo "  ✓ Cosmos DB data-plane role already assigned (or assignment skipped)."
	@echo ""
	@echo "  ARM-level roles are managed via Bicep (infra/)."
	@echo "  If missing, run: make azure-up"

# --- KB ---
.PHONY: convert index

convert: ## Run fn-convert locally (analyzer=$(analyzer))
	@bash scripts/functions/convert.sh $(analyzer)

index: ## Run fn-index locally (kb/serving → Azure AI Search)
	@bash scripts/functions/index.sh

# --- Test ---
.PHONY: test-agent test-app test-functions test-agent-integration

test-agent: ## Run agent unit + endpoint tests
	@cd src/agent && uv run pytest tests/ -v -m "not integration" || test $$? -eq 5

test-app: ## Run web app unit tests
	@cd src/web-app && uv run pytest tests/ -v -m "not integration" || test $$? -eq 5

test-functions: ## Run functions unit tests
	@cd src/functions && uv run pytest tests/ -v || test $$? -eq 5

test-agent-integration: ## Run agent integration tests (needs running local agent)
	@cd src/agent && AGENT_ENDPOINT=http://localhost:8088 uv run pytest tests/ -v -m integration || test $$? -eq 5

## UTIL-LOCAL-END

# ==============================================================================
# Utilities — Azure
# ==============================================================================
## UTIL-AZURE-START

# --- Provision ---
.PHONY: azure-provision

azure-provision: ## Provision all Azure resources (azd provision)
	azd provision

# --- Deploy ---
.PHONY: azure-deploy azure-deploy-app azure-setup-auth

azure-deploy: ## Deploy all services + CU analyzer + publish agent
	AZD_EXT_TIMEOUT=180 azd deploy
	@echo "Configuring CU defaults and deploying kb-image-analyzer..."
	@(cd src/functions && uv run python -m manage_analyzers deploy)
	@echo "Publishing agent..."
	@bash scripts/publish-agent.sh

azure-deploy-app: ## Deploy web app only
	azd deploy --service web-app

azure-setup-auth: ## Configure Entra redirect URIs (idempotent)
	@bash scripts/setup-redirect-uris.sh

# --- KB ---
.PHONY: azure-upload-staging azure-convert azure-index azure-index-summarize

azure-upload-staging: ## Upload kb/staging → Azure staging blob
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

azure-convert: ## Trigger fn-convert in Azure (analyzer=$(analyzer))
	@echo "Triggering fn-convert Azure Function (analyzer=$(analyzer))..."
	@FUNC_URL=$$(azd env get-value FUNCTION_APP_URL) && \
	ROUTE=$$(if [ "$(analyzer)" = "content-understanding" ]; then echo "convert"; else echo "convert-mistral"; fi) && \
	ENDPOINT="$$FUNC_URL/api/$$ROUTE" && \
	echo "  POST $$ENDPOINT" && \
	curl -sf --max-time 600 -X POST "$$ENDPOINT" -H "Content-Type: application/json" -d '{}' | python3 -m json.tool
	@echo ""

azure-index: ## Trigger fn-index in Azure (serving → AI Search)
	@echo "Triggering fn-index Azure Function..."
	@FUNC_URL=$$(azd env get-value FUNCTION_APP_URL) && \
	ENDPOINT="$$FUNC_URL/api/index" && \
	echo "  POST $$ENDPOINT" && \
	curl -sf --max-time 600 -X POST "$$ENDPOINT" -H "Content-Type: application/json" -d '{}' | python3 -m json.tool
	@echo ""

azure-index-summarize: ## Show AI Search index contents summary
	@cd src/functions && uv run python ../../scripts/functions/display-index-summary.py

# --- Test ---
.PHONY: azure-test-agent-dev azure-test-agent azure-test-app

azure-test-agent-dev: ## Integration tests vs dev (unpublished) endpoint
	@cd src/agent && AGENT_ENDPOINT=$$(azd env get-value AGENT_AGENT_ENDPOINT) uv run pytest tests/ -v -m integration || test $$? -eq 5

azure-test-agent: ## Integration tests vs published Foundry endpoint
	@cd src/agent && AGENT_ENDPOINT=$$(azd env get-value AGENT_ENDPOINT) uv run pytest tests/ -v -m integration || test $$? -eq 5

azure-test-app: ## Web app integration tests (Cosmos + Blob + Agent)
	@cd src/web-app && \
	  SERVING_BLOB_ENDPOINT=$$(azd env get-value SERVING_BLOB_ENDPOINT) \
	  COSMOS_ENDPOINT=$$(azd env get-value COSMOS_ENDPOINT) \
	  COSMOS_DATABASE_NAME=$$(azd env get-value COSMOS_DATABASE_NAME) \
	  AGENT_ENDPOINT=$$(azd env get-value AGENT_ENDPOINT) \
	  uv run pytest tests/ -v -m integration || test $$? -eq 5

# --- App / Agent ---
.PHONY: azure-app-logs azure-agent-logs

azure-app-logs: ## Stream live logs from deployed web app
	@APP=$$(azd env get-value WEBAPP_NAME) && \
	RG=$$(azd env get-value RESOURCE_GROUP) && \
	az containerapp logs show --name $$APP --resource-group $$RG --type console --follow

azure-agent-logs: ## Stream agent logs from Foundry
	@AI_NAME=$$(azd env get-value AI_SERVICES_NAME) && \
	RG=$$(azd env get-value RESOURCE_GROUP) && \
	echo "Agent logs — use the Foundry portal for full tracing:" && \
	echo "  https://ai.azure.com" && \
	echo "" && \
	echo "Or query via CLI:" && \
	az monitor app-insights events show \
		--app $$(azd env get-value APPINSIGHTS_NAME) \
		--resource-group $$RG \
		--type traces \
		--order-by timestamp \
		--top 50

# --- Cleanup ---
.PHONY: azure-clean-orphan-roles azure-clean-storage azure-clean-index azure-clean

azure-clean-orphan-roles: ## Delete orphaned role assignments
	@echo "Scanning for orphaned role assignments in resource group..."
	@RG=$$(azd env get-value RESOURCE_GROUP 2>/dev/null || echo "rg-kbidx-dev") && \
	ORPHANS=$$(az role assignment list --resource-group "$$RG" --query "[?principalName==''].[id]" -o tsv) && \
	if [ -z "$$ORPHANS" ]; then \
		echo "  No orphaned role assignments found."; \
	else \
		COUNT=$$(echo "$$ORPHANS" | wc -l) && \
		echo "  Found $$COUNT orphaned role assignment(s). Deleting..." && \
		echo "$$ORPHANS" | while read -r ID; do \
			echo "  ✕ $$ID" && \
			az role assignment delete --ids "$$ID" -o none; \
		done && \
		echo "  Done. Run 'make azure-provision' to recreate them."; \
	fi

azure-clean-storage: ## Empty staging + serving blob containers
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

## UTIL-AZURE-END
