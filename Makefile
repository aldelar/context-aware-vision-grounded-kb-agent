.DEFAULT_GOAL := help

DEV_ENV_FILE ?= .env.dev
PROD_ENV_FILE ?= .env.prod
AZD := azd -C infra/azure
PROD_PIPELINE_TRIGGER := bash scripts/prod-pipeline-request.sh
PROD_DOWN_CLEANUP := bash scripts/prod-post-down-cleanup.sh
DEV_INFRA_PROJECT := kb-agent-infra
DEV_SERVICES_PROJECT := kb-agent-services
DEV_INFRA_COMPOSE := docker compose -p $(DEV_INFRA_PROJECT) --project-directory . --env-file $(DEV_ENV_FILE) -f infra/docker/docker-compose.dev-infra.yml
DEV_SERVICES_COMPOSE := docker compose -p $(DEV_SERVICES_PROJECT) --project-directory . --env-file $(DEV_ENV_FILE) -f infra/docker/docker-compose.dev-services.yml
CONVERTER ?= $(shell $(AZD) env get-value CONVERTER 2>/dev/null || echo markitdown)
PROD_PIPELINE_RETRY_ATTEMPTS ?= 60
PROD_PIPELINE_RETRY_DELAY ?= 6

.PHONY: help
help:
	@echo ""
	@echo "━━━ Shared ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "  make set-converter name=<name>      Set CONVERTER to cu, markitdown, or mistral"
	@echo ""
	@echo "━━━ Dev ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "  sudo make dev-setup-gpu             Configure Docker GPU for local LLM support (Linux only)"
	@echo ""
	@echo "  make dev-up                         Full local bring-up (calls targets below)"
	@echo "    make dev-setup                      Install local tools and Python dependencies"
	@echo "    make dev-infra-up                   Start local emulators and initialize resources"
	@echo "    make dev-services-up                Build and start the full local stack"
	@echo "      make dev-services-pipeline-up       fn-convert + fn-index only"
	@echo "      make dev-services-app-up            web app only"
	@echo "      make dev-services-agents-up         agent only"
	@echo "    make dev-pipeline                   Run local convert + index pipeline"
	@echo "      make dev-pipeline-convert           Trigger local MarkItDown convert"
	@echo "        make dev-seed-kb                   Sync kb/staging into local Azurite"
	@echo "      make dev-pipeline-index             Trigger local indexing"
	@echo "    make dev-ui                         Print the local UI URL"
	@echo ""
	@echo "  make dev-test                       Run unit + integration tests"
	@echo "  make dev-test-ui                    Run browser UI tests"
	@echo "  make dev-otel-dashboard             Print the local Aspire dashboard URL"
	@echo ""
	@echo "  ── Clean up / Reset ──"
	@echo "  make dev-clean                      Clean all local data (calls targets below)"
	@echo "    make dev-clean-storage              Clean staging + serving blob containers"
	@echo "    make dev-clean-cosmos               Clean Cosmos DB conversation data"
	@echo "    make dev-clean-index                Clean all documents from the AI Search index"
	@echo ""
	@echo "  ── Tear Down ──"
	@echo "  make dev-down                       Tear down everything local and remove Docker state"
	@echo "    make dev-services-destroy           Remove local application services and compose state"
	@echo "    make dev-infra-destroy              Remove local emulators and named volumes"
	@echo "  make dev-services-down              Stop local application services without removing volumes"
	@echo "  make dev-infra-down                 Stop local emulators without removing volumes"
	@echo ""
	@echo "━━━ Prod ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "  make set-project name=<id>          Set PROJECT_NAME in the active AZD environment"
	@echo ""
	@echo "  make prod-up                        Full Azure bring-up (calls targets below)"
	@echo "    make prod-setup                     Install Azure CLI and AZD if missing"
	@echo "    make prod-infra-up                  Provision Azure infrastructure with AZD"
	@echo "    make prod-services-up               Deploy all services"
	@echo "      make prod-services-pipeline-up      Pipeline services (fn-index + selected converter)"
	@echo "      make prod-services-app-up           Web app only"
	@echo "      make prod-services-agents-up        Agent only"
	@echo "    make prod-pipeline                  Run Azure convert + index pipeline"
	@echo "      make prod-seed-kb                   Upload kb/staging to Azure blob"
	@echo "      make prod-pipeline-convert           Trigger the selected Azure converter"
	@echo "      make prod-pipeline-index             Trigger Azure indexing"
	@echo "    make prod-ui-url                    Print the production web app URL"
	@echo ""
	@echo "  ── Clean up / Reset ──"
	@echo "  make prod-clean                     Clean all Azure data (calls targets below)"
	@echo "    make prod-clean-storage             Clean staging + serving blob containers"
	@echo "    make prod-clean-cosmos              Clean Cosmos DB conversation data"
	@echo "    make prod-clean-index               Clean all documents from the AI Search index"
	@echo ""
	@echo "  ── Tear Down ──"
	@echo "  make prod-down                      Tear down Azure environment (calls targets below)"
	@echo "    make prod-services-down             Print scale-down guidance for deployed services"
	@echo "    make prod-infra-down                Delete Azure infrastructure with confirmation"

.PHONY: dev-setup
dev-setup:
	@if [ $$(id -u) -eq 0 ] || [ -n "$${SUDO_USER:-}" ]; then \
		echo "Run make dev-setup as your normal user." >&2; \
		echo "Use sudo make dev-setup-gpu only for Docker GPU runtime setup." >&2; \
		exit 1; \
	fi
	@bash scripts/dev-setup.sh
	@cd src/functions && uv sync --extra dev
	@cd src/agent && uv sync --extra dev
	@cd src/web-app && uv sync --extra dev
	@test -f $(DEV_ENV_FILE) || (echo "Missing $(DEV_ENV_FILE) after dev-setup." >&2; exit 1)

.PHONY: dev-setup-gpu
dev-setup-gpu:
	@if [ $$(id -u) -ne 0 ] && [ -z "$${SUDO_USER:-}" ]; then \
		echo "Run sudo make dev-setup-gpu." >&2; \
		exit 1; \
	fi
	@bash scripts/dev-setup-gpu.sh

.PHONY: prod-setup
prod-setup:
	@bash scripts/prod-setup.sh

.PHONY: dev-up
dev-up: dev-setup dev-infra-up dev-services-up dev-pipeline
	@$(MAKE) dev-ui

.PHONY: dev-down
dev-down: dev-services-destroy dev-infra-destroy

.PHONY: dev-infra-up
dev-infra-up:
	@test -f $(DEV_ENV_FILE) || (echo "Missing $(DEV_ENV_FILE). Copy .env.dev.template first." >&2; exit 1)
	@$(DEV_INFRA_COMPOSE) up -d
	@bash scripts/dev-init-emulators.sh

.PHONY: dev-infra-down
dev-infra-down:
	@$(DEV_INFRA_COMPOSE) down

.PHONY: dev-infra-destroy
dev-infra-destroy:
	@$(DEV_INFRA_COMPOSE) down -v --remove-orphans

.PHONY: dev-services-up
dev-services-up:
	@test -f $(DEV_ENV_FILE) || (echo "Missing $(DEV_ENV_FILE). Copy .env.dev.template first." >&2; exit 1)
	@$(DEV_SERVICES_COMPOSE) up -d --build

.PHONY: dev-services-down
dev-services-down:
	@$(DEV_SERVICES_COMPOSE) down

.PHONY: dev-services-destroy
dev-services-destroy:
	@$(DEV_SERVICES_COMPOSE) down -v --remove-orphans

.PHONY: dev-services-pipeline-up
dev-services-pipeline-up:
	@test -f $(DEV_ENV_FILE) || (echo "Missing $(DEV_ENV_FILE). Copy .env.dev.template first." >&2; exit 1)
	@$(DEV_SERVICES_COMPOSE) up -d --build fn-convert fn-index

.PHONY: dev-services-app-up
dev-services-app-up:
	@test -f $(DEV_ENV_FILE) || (echo "Missing $(DEV_ENV_FILE). Copy .env.dev.template first." >&2; exit 1)
	@$(DEV_SERVICES_COMPOSE) up -d --build web-app

.PHONY: dev-services-agents-up
dev-services-agents-up:
	@test -f $(DEV_ENV_FILE) || (echo "Missing $(DEV_ENV_FILE). Copy .env.dev.template first." >&2; exit 1)
	@$(DEV_SERVICES_COMPOSE) up -d --build agent

.PHONY: dev-test
dev-test:
	@cd src/functions && uv run pytest tests -o addopts= -m "not uitest"
	@cd src/agent && uv run pytest tests -o addopts= -m "not uitest"
	@cd src/web-app && uv run pytest tests -o addopts= -m "not uitest"

.PHONY: dev-seed-kb
dev-seed-kb:
	@bash scripts/dev-seed-kb.sh

.PHONY: dev-test-ui
dev-test-ui:
	@cd src/web-app && uv run pytest tests -o addopts= -m uitest

.PHONY: dev-ui
dev-ui:
	@echo http://localhost:8080

.PHONY: dev-otel-dashboard
dev-otel-dashboard:
	@echo http://localhost:18888

.PHONY: dev-pipeline
dev-pipeline: dev-pipeline-convert dev-pipeline-index

.PHONY: dev-pipeline-convert
dev-pipeline-convert:
	@$(MAKE) dev-seed-kb
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		curl -fsS -X POST http://localhost:7071/api/convert-markitdown -H 'Content-Type: application/json' -d '{}' && break; \
		echo "  Waiting for fn-convert to be ready... ($$i/10)"; sleep 3; \
	done

.PHONY: dev-pipeline-index
dev-pipeline-index:
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		curl -fsS -X POST http://localhost:7072/api/index -H 'Content-Type: application/json' -d '{}' && break; \
		echo "  Waiting for fn-index to be ready... ($$i/10)"; sleep 3; \
	done

.PHONY: dev-clean
dev-clean: dev-clean-storage dev-clean-cosmos dev-clean-index

.PHONY: dev-clean-storage
dev-clean-storage:
	@bash scripts/dev-clean-data.sh storage

.PHONY: dev-clean-cosmos
dev-clean-cosmos:
	@bash scripts/dev-clean-data.sh cosmos

.PHONY: dev-clean-index
dev-clean-index:
	@bash scripts/dev-clean-data.sh index

.PHONY: prod-down
prod-down: prod-services-down prod-infra-down

.PHONY: prod-infra-up

.PHONY: prod-env-prepare
prod-env-prepare:
	@location="$$($(AZD) env get-values --no-prompt 2>/dev/null | sed -n 's/^AZURE_LOCATION="\(.*\)"$$/\1/p' | head -n 1)"; \
	if [ -z "$$location" ] && [ -f "$(PROD_ENV_FILE)" ]; then \
		location="$(sed -n 's/^AZURE_LOCATION=//p' $(PROD_ENV_FILE) | head -n 1 | tr -d '"')"; \
	fi; \
	if [ -z "$$location" ]; then \
		echo "ERROR: AZURE_LOCATION is not set for the active AZD environment." >&2; \
		echo "Set it with: azd -C infra/azure env set AZURE_LOCATION <location> --environment $$($(AZD) env get-value AZURE_ENV_NAME 2>/dev/null || echo prod)" >&2; \
		echo "Or define AZURE_LOCATION=<location> in $(PROD_ENV_FILE)." >&2; \
		exit 1; \
	fi; \
	if ! $(AZD) env get-value AZURE_LOCATION >/dev/null 2>&1; then \
		echo "Setting AZURE_LOCATION to $$location in the active AZD environment..."; \
		$(AZD) env set AZURE_LOCATION "$$location"; \
	fi

prod-infra-up: prod-env-prepare
	@$(AZD) provision

.PHONY: prod-infra-down
prod-infra-down:
	@env_name="$$($(AZD) env get-value AZURE_ENV_NAME 2>/dev/null || echo prod)"; \
	project_name="$$($(AZD) env get-value PROJECT_NAME 2>/dev/null || true)"; \
	resource_group="$$($(AZD) env get-value AZURE_RESOURCE_GROUP 2>/dev/null || true)"; \
	location="$$($(AZD) env get-value AZURE_LOCATION 2>/dev/null || true)"; \
	converter="$$($(AZD) env get-value CONVERTER 2>/dev/null || true)"; \
	printf "Delete the active Azure environment? [y/N] " && read answer && case "$$answer" in [yY]|[yY][eE][sS]) true ;; *) false ;; esac && \
	$(AZD) down --force --purge; \
	$(PROD_DOWN_CLEANUP) --project-name "$$project_name" --environment "$$env_name" --location "$$location" --resource-group "$$resource_group"; \
	if [ -n "$$project_name" ]; then $(AZD) env set PROJECT_NAME "$$project_name" --environment "$$env_name"; fi; \
	if [ -n "$$location" ]; then $(AZD) env set AZURE_LOCATION "$$location" --environment "$$env_name"; fi; \
	if [ -n "$$converter" ]; then $(AZD) env set CONVERTER "$$converter" --environment "$$env_name"; fi

.PHONY: prod-up
prod-up: prod-setup prod-infra-up prod-services-up prod-pipeline
	@$(MAKE) prod-ui-url

.PHONY: prod-services-up
prod-services-up: prod-services-app-up prod-services-agents-up prod-services-pipeline-up
	@$(MAKE) prod-configure-target-ports

.PHONY: prod-configure-registries
prod-configure-registries:
	@bash scripts/configure-containerapp-registries.sh

.PHONY: prod-configure-target-ports
prod-configure-target-ports:
	@bash scripts/configure-containerapp-target-ports.sh

.PHONY: prod-services-down
prod-services-down:
	@echo "Scale-down remains environment-specific. Use Azure CLI or the portal to reduce replicas to zero for deployed Container Apps."

.PHONY: prod-services-pipeline-up
prod-services-pipeline-up: prod-configure-registries
	@$(AZD) deploy --service func-index
	@case "$(CONVERTER)" in \
		cu) $(AZD) deploy --service func-convert-cu ;; \
		mistral) $(AZD) deploy --service func-convert-mistral ;; \
		markitdown) $(AZD) deploy --service func-convert-markitdown ;; \
		*) echo "Unsupported CONVERTER=$(CONVERTER). Use cu, markitdown, or mistral." >&2; exit 1 ;; \
	 esac

.PHONY: prod-services-app-up
prod-services-app-up: prod-configure-registries
	@$(AZD) deploy --service web-app
	@$(MAKE) prod-configure-target-ports

.PHONY: prod-services-agents-up
prod-services-agents-up: prod-configure-registries
	@$(AZD) deploy --service agent
	@$(MAKE) prod-configure-target-ports

.PHONY: prod-ui-url
prod-ui-url:
	@$(AZD) env get-value WEBAPP_URL

.PHONY: prod-seed-kb
prod-seed-kb:
	@test -d kb/staging || (echo "Missing kb/staging." >&2; exit 1)
	@az storage blob upload-batch \
		--account-name $$($(AZD) env get-value STAGING_STORAGE_ACCOUNT) \
		--destination staging \
		--source kb/staging \
		--auth-mode login \
		--overwrite

.PHONY: prod-pipeline
prod-pipeline: prod-seed-kb prod-pipeline-convert prod-pipeline-index

.PHONY: prod-pipeline-convert
prod-pipeline-convert:
	@case "$(CONVERTER)" in \
		cu) endpoint="$$($(AZD) env get-value FUNC_CONVERT_CU_URL)/api/convert" ;; \
		mistral) endpoint="$$($(AZD) env get-value FUNC_CONVERT_MISTRAL_URL)/api/convert-mistral" ;; \
		markitdown) endpoint="$$($(AZD) env get-value FUNC_CONVERT_MARKITDOWN_URL)/api/convert-markitdown" ;; \
		*) echo "Unsupported CONVERTER=$(CONVERTER). Use cu, markitdown, or mistral." >&2; exit 1 ;; \
	 esac; \
	for i in $$(seq 1 $(PROD_PIPELINE_RETRY_ATTEMPTS)); do \
		$(PROD_PIPELINE_TRIGGER) convert "$$endpoint"; \
		rc=$$?; \
		if [ $$rc -eq 0 ]; then \
			exit 0; \
		fi; \
		if [ $$rc -eq 20 ]; then \
			exit $$rc; \
		fi; \
		echo "  Waiting for Azure converter endpoint to be ready... ($$i/$(PROD_PIPELINE_RETRY_ATTEMPTS))"; \
		sleep $(PROD_PIPELINE_RETRY_DELAY); \
	done; \
	echo "Azure converter pipeline did not complete successfully in time." >&2; \
	exit 1

.PHONY: prod-pipeline-index
prod-pipeline-index:
	@for i in $$(seq 1 $(PROD_PIPELINE_RETRY_ATTEMPTS)); do \
		$(PROD_PIPELINE_TRIGGER) index "$$($(AZD) env get-value FUNC_INDEX_URL)/api/index"; \
		rc=$$?; \
		if [ $$rc -eq 0 ]; then \
			exit 0; \
		fi; \
		if [ $$rc -eq 20 ]; then \
			exit $$rc; \
		fi; \
		echo "  Waiting for Azure index endpoint to be ready... ($$i/$(PROD_PIPELINE_RETRY_ATTEMPTS))"; \
		sleep $(PROD_PIPELINE_RETRY_DELAY); \
	done; \
	echo "Azure index pipeline did not complete successfully in time." >&2; \
	exit 1

.PHONY: prod-clean
prod-clean: prod-clean-storage prod-clean-cosmos prod-clean-index

.PHONY: prod-clean-storage
prod-clean-storage:
	@echo "Clearing staging container..."
	@az storage blob delete-batch \
		--account-name $$($(AZD) env get-value STAGING_STORAGE_ACCOUNT) \
		--source staging \
		--auth-mode login
	@echo "Clearing serving container..."
	@az storage blob delete-batch \
		--account-name $$($(AZD) env get-value SERVING_STORAGE_ACCOUNT) \
		--source serving \
		--auth-mode login
	@echo "Done."

.PHONY: prod-clean-cosmos
prod-clean-cosmos:
	@echo "Clearing Cosmos DB containers..."
	@cd src/web-app && uv run python -c "\
import os; from azure.cosmos import CosmosClient; from azure.identity import DefaultAzureCredential; \
client = CosmosClient(os.environ['COSMOS_ENDPOINT'], DefaultAzureCredential()); \
db = client.get_database_client(os.environ.get('COSMOS_DATABASE_NAME', 'kb-agent')); \
containers = { \
    os.environ.get('COSMOS_SESSIONS_CONTAINER', 'agent-sessions'): '/id', \
    os.environ.get('COSMOS_CONVERSATIONS_CONTAINER', 'conversations'): '/userId', \
    os.environ.get('COSMOS_MESSAGES_CONTAINER', 'messages'): '/conversationId', \
    os.environ.get('COSMOS_REFERENCES_CONTAINER', 'references'): '/conversationId', \
}; \
[( \
    c := db.get_container_client(name), \
    items := list(c.read_all_items()), \
    [c.delete_item(i['id'], partition_key=i[pk.lstrip('/')]) for i in items], \
    print(f'  Cleared {len(items)} item(s) from {name}'), \
) for name, pk in containers.items()]"
	@echo "Done."

.PHONY: prod-clean-index
prod-clean-index:
	@echo "Clearing AI Search index documents..."
	@cd src/web-app && uv run python -c "\
import os; \
from azure.search.documents import SearchClient; \
from azure.identity import DefaultAzureCredential; \
idx = os.environ.get('SEARCH_INDEX_NAME', 'kb-articles'); \
c = SearchClient(os.environ['SEARCH_ENDPOINT'], idx, DefaultAzureCredential()); \
docs = list(c.search('*', select=['id'])); \
if docs: \
    c.delete_documents(documents=[{'id': d['id']} for d in docs]); \
print(f'  Cleared {len(docs)} document(s) from {idx}.')"

.PHONY: set-project
set-project:
	@if [ -z "$(name)" ]; then echo "Usage: make set-project name=<id>" >&2; exit 1; fi
	@$(AZD) env set PROJECT_NAME "$(name)"

.PHONY: set-converter
set-converter:
	@if [ -z "$(name)" ]; then echo "Usage: make set-converter name=<cu|markitdown|mistral>" >&2; exit 1; fi
	@case "$(name)" in cu|markitdown|mistral) ;; *) echo "Use cu, markitdown, or mistral." >&2; exit 1 ;; esac
	@$(AZD) env set CONVERTER "$(name)"