# Setup & Makefile Guide

## Overview

The repo now has two explicit workflows:

- `dev-*` targets run a zero-Azure local environment backed by Docker emulators and Ollama.
- `prod-*` targets provision and deploy the retained Azure topology with AZD.

`PROJECT_NAME` and `CONVERTER` remain AZD-backed settings for production workflows. Local development does not require Azure credentials.

## Prerequisites

### Dev

- Docker Engine with Compose support
- Python 3.11+
- `uv`
- Optional: an NVIDIA GPU for faster Ollama inference

### Prod

- Azure CLI (`az`)
- Azure Developer CLI (`azd`)
- An Azure subscription with access to the services defined in [docs/specs/infrastructure.md](./specs/infrastructure.md)

## Dev Quick Start

```bash
# 1. Install local dependencies and create/update .env.dev
make dev-setup

# 2. Start local emulators and initialize databases, containers, and Ollama models
make dev-infra-up

# 3. Build and start all application services
make dev-services-up

# 4. Run the local KB pipeline
make dev-pipeline

# 5. Run tests
make dev-test

# 6. Open the UI
make dev-ui
```

The local UI is served at `http://localhost:8080`.

### What `dev-setup` now does

- Installs Azure CLI, Azure Developer CLI, `uv`, Azure Functions Core Tools, and the Playwright Chromium browser.
- Creates `.env.dev` from `.env.dev.template` if it does not exist.
- Detects the first NVIDIA GPU UUID from `nvidia-smi -L` and writes `OLLAMA_GPU_DEVICE=<uuid>` into `.env.dev`.
- If no NVIDIA GPU is detected, removes `OLLAMA_GPU_DEVICE` from `.env.dev` so Ollama is not pinned to a specific device.
- Detects whether it is running on native Linux, WSL with a local Docker Engine, or WSL with Docker Desktop integration.
- If an NVIDIA GPU is visible and Docker is local to Linux, installs and configures `nvidia-container-toolkit`, generates the CDI spec, restarts Docker, and validates `docker run --gpus all`.
- If it detects WSL backed by Docker Desktop, it skips Linux-side toolkit installation and only validates whether Docker Desktop GPU passthrough is already working.

### GPU Setup Notes

- Native Linux and WSL with a local `dockerd` use the same Linux-side NVIDIA container toolkit flow.
- WSL with Docker Desktop is different: GPU support is managed on the Windows side by Docker Desktop plus the Windows NVIDIA driver.
- GPU acceleration is optional. If no NVIDIA GPU is visible, Ollama still runs on CPU.
- To skip GPU setup explicitly, run `DEV_SETUP_SKIP_GPU=1 make dev-setup`.
- `dev-setup` pins Ollama to the first detected NVIDIA GPU UUID. If no GPU is detected, it leaves `OLLAMA_GPU_DEVICE` unset.

### What `dev-infra-up` starts

- Cosmos DB Linux emulator
- Azurite
# Setup & Makefile Guide

## Overview

The repo now has two explicit workflows:

- `dev-*` targets run a zero-Azure local environment backed by Docker emulators and Ollama.
- `prod-*` targets provision and deploy the retained Azure topology with AZD.

`PROJECT_NAME` and `CONVERTER` remain AZD-backed settings for production workflows. Local development does not require Azure credentials.

## Prerequisites

### Dev

- Docker Engine with Compose support
- Python 3.11+
- `uv`
- Optional: an NVIDIA GPU for faster Ollama inference

### Prod

- Azure CLI (`az`)
- Azure Developer CLI (`azd`)
- An Azure subscription with access to the services defined in [docs/specs/infrastructure.md](./specs/infrastructure.md)

## Dev Quick Start

```bash
# 1. Install local dependencies as your normal user and create/update .env.dev
make dev-setup

# 2. If dev-setup tells you Docker GPU support is missing and you use
#    a local Linux/WSL Docker engine with an NVIDIA GPU, configure it once
sudo make dev-setup-gpu

# 3. Start local emulators and initialize databases, containers, and Ollama models
make dev-infra-up

# 4. Build and start all application services
make dev-services-up

# 5. Run the local KB pipeline
make dev-pipeline

# 6. Run tests
make dev-test

# 7. Open the UI
make dev-ui
```

The local UI is served at `http://localhost:8080`.

### What `dev-setup` does

- Installs Azure CLI, Azure Developer CLI, `uv`, Azure Functions Core Tools, and the Playwright Chromium browser.
- Must be run as your normal user, not via `sudo`.
- Creates `.env.dev` from `.env.dev.template` if needed.
- Detects the first NVIDIA GPU UUID from `nvidia-smi -L` and writes it to `OLLAMA_GPU_DEVICE` in `.env.dev`.
- If no NVIDIA GPU is detected, removes `OLLAMA_GPU_DEVICE` from `.env.dev` so Ollama is not pinned.
- Detects whether it is running on native Linux, WSL with a local Docker Engine, or WSL with Docker Desktop integration.
- Validates whether Docker GPU support is already working and, when it is missing on a local Linux engine, tells you to run `sudo make dev-setup-gpu`.

### What `dev-setup-gpu` does

- Runs only as `root` and is intended to be invoked with `sudo make dev-setup-gpu`.
- On native Linux and WSL with a local `dockerd`, installs and configures `nvidia-container-toolkit`, generates the CDI spec, restarts Docker, and validates `docker run --gpus all`.
- On WSL backed by Docker Desktop, it does not try to install Linux-side GPU tooling and instead reports whether Docker Desktop GPU passthrough is already working.

### GPU Setup Notes

- Native Linux and WSL with a local `dockerd` use the same Linux-side NVIDIA container toolkit flow.
- WSL with Docker Desktop is different: GPU support is managed on the Windows side by Docker Desktop plus the Windows NVIDIA driver.
- GPU acceleration is optional. If no NVIDIA GPU is visible, Ollama still runs on CPU.
- `dev-setup` pins Ollama to the first detected NVIDIA GPU UUID. If no GPU is detected, it leaves `OLLAMA_GPU_DEVICE` unset.

### What `dev-infra-up` starts

- Cosmos DB Linux emulator
- Azurite
- Azure AI Search Simulator
- Ollama
- Aspire Dashboard

### What `dev-services-up` starts

- `fn-convert` from `src/functions/fn_convert_markitdown/Dockerfile`
- `fn-index`
- `agent`
- `web-app`

### Dev Notes

- `.env.dev.template` uses Docker Compose service hostnames such as `ollama`, `agent`, `azurite`, and `cosmos-emulator`.
- If you run tools from the host machine instead of inside Compose, override those endpoints to `localhost` equivalents.
- `make dev-test` runs all non-UI tests. Integration tests still expect the local infra to be up.
- `make dev-test-ui` is intentionally separate and only runs the browser tier.

## Prod Workflow

```bash
# Set AZD-backed workflow parameters
make set-project name=myproj
make set-converter name=markitdown

# Provision Azure infrastructure
make prod-infra-up

# Deploy services
make prod-services-up

# Seed Azure staging storage and run the Azure pipeline
make prod-pipeline

# Print the deployed web app URL
make prod-ui-url
```

### Prod Notes

- `CONVERTER` selects which existing Azure converter service is deployed or triggered for the current workflow: `cu`, `markitdown`, or `mistral`.
- The Azure topology still retains all three converter services defined in `azure.yaml`.
- `make prod-services-up` now reattaches the provisioned Container Apps to the active Azure Container Registry with system-assigned identity before running `azd deploy`.
- `make prod-services-up` also corrects the web app and agent ingress target ports after deployment so they switch from the placeholder bootstrap port to their real container ports.
- `make prod-pipeline` now uploads repo content from `kb/staging/` into the Azure staging container before triggering convert and index.
- `make prod-services-down` currently prints scale-down guidance instead of performing an environment-wide shutdown automatically.

## Target Reference

### Dev Targets

| Target | Description |
|---|---|
| `make dev-setup` | Install local tooling and Python dependencies as your normal user |
| `sudo make dev-setup-gpu` | Configure Docker GPU support for a local Linux Docker engine |
| `make dev-infra-up` | Start local emulators and run `scripts/dev-init-emulators.sh` |
| `make dev-infra-down` | Stop local emulator containers |
| `make dev-services-up` | Build and start the full local application stack |
| `make dev-services-down` | Stop local application services |
| `make dev-services-pipeline-up` | Start `fn-convert` and `fn-index` only |
| `make dev-services-app-up` | Start the web app only |
| `make dev-services-agents-up` | Start the agent only |
| `make dev-test` | Run unit and integration tests except `uitest` |
| `make dev-test-ui` | Run browser-based UI tests |
| `make dev-ui` | Print the local UI URL |
| `make dev-pipeline` | Trigger local convert then local index |
| `make dev-pipeline-convert` | Trigger local MarkItDown convert |
| `make dev-pipeline-index` | Trigger local indexing |

### Prod Targets
