# Setup & Makefile Guide

The repo exposes two workflows — `dev-*` for a fully local Docker-based environment and `prod-*` for the Azure environment managed by AZD. Run `make help` for the quick reference; this document provides additional detail.

The layout is split by runtime concern:
- `infra/docker/` holds the local Docker Compose topology.
- `infra/azure/` holds the AZD project, Azure hooks, and Bicep IaC.
- The Makefile wraps both from the repo root.

---

## Shared

```
make set-converter name=<name>      Set CONVERTER to cu, markitdown, or mistral
```

`CONVERTER` selects which converter backend the pipeline uses: `cu`, `markitdown`, or `mistral`. It applies to both local and Azure workflows.

---

## Dev

The local workflow is Docker-first and does not require Azure cloud resources, Azure credentials, Azure CLI, AZD, or Entra auth. Local auth is bypassed with `REQUIRE_AUTH=false`. It uses smaller local Ollama-hosted models, so it is cheap and self-contained, but answer quality is below the Azure-hosted production path.

### Dev targets

```
sudo make dev-setup-gpu             Configure Docker GPU for local LLM support (Linux only)

make dev-up                         Full local bring-up (calls targets below)
  make dev-setup                      Install local tools and Python dependencies
  make dev-infra-up                   Start local emulators and initialize resources
  make dev-services-up                Build and start the full local stack
    make dev-services-pipeline-up       fn-convert + fn-index only
    make dev-services-app-up            web app only
    make dev-services-agents-up         agent only
  make dev-pipeline                   Run local convert + index pipeline
    make dev-pipeline-convert           Trigger local MarkItDown convert
      make dev-seed-kb                   Sync kb/staging into local Azurite
    make dev-pipeline-index             Trigger local indexing
  make dev-ui                         Print the local UI URL

make dev-test                       Run unit + integration tests
make dev-test-ui                    Run browser UI tests
make dev-otel-dashboard             Print the local Aspire dashboard URL

── Clean up / Reset ──
make dev-clean                      Clean all local data (calls targets below)
  make dev-clean-storage              Clean staging + serving blob containers
  make dev-clean-cosmos               Clean Cosmos DB conversation data
  make dev-clean-index                Clean all documents from the AI Search index

── Tear Down ──
make dev-down                       Tear down everything local and remove Docker state
  make dev-services-destroy           Remove local application services and compose state
  make dev-infra-destroy              Remove local emulators and named volumes
make dev-services-down              Stop local application services without removing volumes
make dev-infra-down                 Stop local emulators without removing volumes
```

### Dev notes

- `dev-setup-gpu` is only needed if you use an NVIDIA GPU with a native Linux Docker engine or local-WSL Docker engine (not Docker Desktop). It installs and configures the NVIDIA container toolkit. Run it once with `sudo`.
- `dev-setup` must be run as your normal user, not with `sudo`. It installs `uv`, Azure Functions Core Tools, Playwright Chromium, creates `.env.dev` from the template if it does not exist, and backfills any newly added template keys into an existing `.env.dev` without overwriting your current values.
- `.env.dev.template` uses Docker Compose service hostnames (`ollama`, `agent`, `azurite`, `cosmos-emulator`). If you call services from the host instead of inside Compose, use `localhost` equivalents.
- `dev-test` runs all non-UI tests across agent, functions, and web-app. Integration tests expect local infra to be running.
- `dev-test-ui` runs browser-based UI tests separately.
- `dev-otel-dashboard` prints the URL for the local [Aspire Dashboard](https://learn.microsoft.com/dotnet/aspire/fundamentals/dashboard/overview) (OpenTelemetry traces, logs, metrics) at `http://localhost:18888`.
- `dev-down` is destructive: it removes the local Compose containers, networks, and named volumes for a clean-slate rebuild. Use `dev-services-down` or `dev-infra-down` when you only want to stop containers.

---

## Prod

The prod workflow provisions and deploys the Azure topology with AZD. It requires an Azure subscription and authentication via `az login` / `azd auth login`.

If you run raw AZD commands instead of the Makefile, use `azd -C infra/azure ...` from the repo root.

### Prod targets

```
make set-project name=<id>          Set PROJECT_NAME in the active AZD environment

make prod-up                        Full Azure bring-up (calls targets below)
  make prod-setup                     Install Azure CLI and AZD if missing
  make prod-infra-up                  Provision Azure infrastructure with AZD
  make prod-services-up               Deploy all services
    make prod-services-pipeline-up      Pipeline services (fn-index + selected converter)
    make prod-services-app-up           Web app only
    make prod-services-agents-up        Agent only
  make prod-pipeline                  Run Azure convert + index pipeline
    make prod-seed-kb                   Upload kb/staging to Azure blob
    make prod-pipeline-convert          Trigger the selected Azure converter
    make prod-pipeline-index            Trigger Azure indexing
  make prod-ui-url                    Print the production web app URL

── Clean up / Reset ──
make prod-clean                     Clean all Azure data (calls targets below)
  make prod-clean-storage             Clean staging + serving blob containers
  make prod-clean-cosmos              Clean Cosmos DB conversation data
  make prod-clean-index               Clean all documents from the AI Search index

── Tear Down ──
make prod-down                      Tear down Azure environment (calls targets below)
  make prod-services-down             Print scale-down guidance for deployed services
  make prod-infra-down                Delete Azure infrastructure with confirmation
```

### Prod notes

- `set-project` must be run once before the first `prod-up`. It stores `PROJECT_NAME` in the active AZD environment, which drives Azure resource naming.
- `prod-infra-up` requires `AZURE_LOCATION` to be set either in the active AZD environment or in `.env.prod`. If the AZD environment is missing that value and `.env.prod` contains `AZURE_LOCATION=<location>`, the Makefile copies it into the active AZD environment before provisioning.
- If neither the AZD environment nor `.env.prod` defines `AZURE_LOCATION`, `prod-infra-up` fails with a clear error instead of choosing a region implicitly.
- `prod-infra-down` preserves the user-managed AZD inputs needed for the next redeploy (`PROJECT_NAME`, `AZURE_LOCATION`, and `CONVERTER`) before running `azd down --purge`, then restores them into the local AZD environment afterward.
- After `azd down --purge`, `prod-infra-down` explicitly verifies that the resource group is gone, purges soft-deleted Cognitive Services and APIM resources with the same environment name, force-deletes the Log Analytics workspace if it is still live when teardown returns, and warns if a deleted Log Analytics workspace still appears in the subscription.
- The AZD preprovision hook ensures the subscription-level `Microsoft.Insights/AIWorkspacePreview` feature is registered before provisioning, because workspace-based Application Insights creation depends on it in this environment.
- `prod-setup` installs Azure CLI and AZD if they are missing. It is called automatically by `prod-up`, but can be run standalone.
- `prod-services-up` reattaches provisioned Container Apps to the active Azure Container Registry with system-assigned identity before deploying, and corrects ingress target ports after deploy.
- `prod-pipeline` retries the converter and index trigger calls for a short window after deploy. It now checks the JSON response body as well, so a logical pipeline failure such as “no articles found” or per-article conversion errors is surfaced directly instead of being misreported as “endpoint not ready.”
- `prod-services-down` is intentionally non-destructive; it prints scale-down guidance rather than tearing down resources.
- `prod-down` calls `prod-services-down` then `prod-infra-down`, which deletes the Azure environment after confirmation.
