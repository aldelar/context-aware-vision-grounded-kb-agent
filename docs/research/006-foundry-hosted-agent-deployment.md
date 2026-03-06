# Research 006: Foundry Hosted Agent Deployment via AZD

> **Date:** 2026-02-25
> **Status:** Complete

## Objective

Determine the correct approach for deploying our KB Agent as a **Foundry hosted agent** using Azure Developer CLI (AZD) and the `azure.ai.agents` extension.

## Background

Our KB Agent is a FastAPI service (port 8088) that exposes an OpenAI-compatible Responses API (`/v1/responses`, `/v1/entities`, `/health`). It uses Microsoft Agent Framework (`ChatAgent` with `agent-framework-core` + `agent-framework-azure-ai`) for reasoning and tool calling, with a custom `search_knowledge_base` tool and vision middleware for image-grounded answers.

We need to deploy this agent as a **Foundry hosted agent** — a containerized agent hosted within an Azure AI Foundry project, with its own managed identity and endpoint.

## Research Approach

### 1. Official Documentation Review

Fetched and studied:
- [AZD AI Agent Extension docs](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/extensions/azure-ai-foundry-extension) — deployment workflow, `azure.yaml` format, required config
- [Foundry Hosted Agents concept](https://learn.microsoft.com/en-us/azure/ai-services/agents/concepts/hosted-agents) — architecture, hosting adapter, capability host, agent identity, lifecycle

### 2. Official Samples Review

Fetched and studied from `microsoft/foundry-samples`:
- **echo-agent** — simplest possible hosted agent (custom `BaseAgent`, `from_agent_framework()` adapter)
- **agent-with-local-tools** — agent using `AzureAIAgentClient` with model resources and env var templates

### 3. Scaffolding Experiment

Ran `azd ai agent init` in a temporary directory pointing at our existing Foundry project to see exactly what the extension generates:

```bash
mkdir /tmp/azd-agent-test
cd /tmp/azd-agent-test
echo 'name: test-project' > azure.yaml

# Create agent manifest in official format
cat > /tmp/agent-manifest/agent.yaml <<'EOF'
name: test-agent
description: Test agent for scaffolding
metadata:
  authors: [test]
template:
  kind: hosted
  protocols:
    - protocol: responses
      version: v1
  environment_variables:
    - name: PROJECT_ENDPOINT
      value: ${AZURE_AI_PROJECT_ENDPOINT}
resources:
  - kind: model
    id: gpt-4.1
    name: chat
EOF

# Run init with our real Foundry project
azd ai agent init \
  -m /tmp/agent-manifest/agent.yaml \
  -e test-env \
  --project-id "/subscriptions/.../projects/proj-{project}-dev" \
  --no-prompt
```

## Findings

### Generated `azure.yaml` Service Entry

The extension produces this service definition:

```yaml
services:
    test-agent:
        project: src/test-agent
        host: azure.ai.agent        # NOT "ai.agent" — needs azure. prefix
        language: docker             # NOT "python" — always docker for hosted agents
        docker:
            remoteBuild: true        # Build happens in ACR, not locally
        config:
            container:
                resources:
                    cpu: "0.25"
                    memory: 0.5Gi
                scale:
                    maxReplicas: 1
            deployments:             # Model deployments needed by the agent
                - model:
                    format: OpenAI
                    name: gpt-4.1
                    version: "2025-04-14"
                  name: gpt-4.1
                  sku:
                    capacity: 30
                    name: GlobalStandard
```

Key insights:
- **`host: azure.ai.agent`** — the full prefix is required (not just `ai.agent`)
- **`language: docker`** — hosted agents are always Docker-based
- **`docker.remoteBuild: true`** — the image is built in ACR
- **`config.container`** — specifies CPU, memory, and scale settings for the hosted container
- **`config.deployments`** — declares model deployments the agent needs (the extension checks these exist in the Foundry project)

### Generated `agent.yaml` (Processed)

The extension transforms the input manifest into a **flattened** `ContainerAgent` format:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/microsoft/AgentSchema/refs/heads/main/schemas/v1.0/ContainerAgent.yaml
kind: hosted
name: test-agent
description: Test agent for scaffolding
metadata:
    authors: [test]
protocols:
    - protocol: responses
      version: v1
environment_variables:
    - name: PROJECT_ENDPOINT
      value: ${AZURE_AI_PROJECT_ENDPOINT}
```

Key observations:
- The `template:` wrapper from the input is **removed** — `kind`, `protocols`, `environment_variables` become top-level
- The `resources:` section is **consumed** and moved into `azure.yaml`'s `config.deployments`
- The schema reference points to `ContainerAgent.yaml` (hosted container agents)

### AZD Environment Variables Set

The init command automatically sets these env vars from the Foundry project:

| Variable | Value | Source |
|----------|-------|--------|
| `AZURE_AI_PROJECT_ID` | Full ARM resource ID | From `--project-id` |
| `AZURE_AI_PROJECT_ENDPOINT` | `https://ai-{project}-dev.services.ai.azure.com/api/projects/proj-{project}-dev` | Queried from project |
| `AZURE_AI_ACCOUNT_NAME` | `ai-{project}-dev` | Parsed from resource ID |
| `AZURE_AI_PROJECT_NAME` | `proj-{project}-dev` | Parsed from resource ID |
| `AZURE_OPENAI_ENDPOINT` | `https://ai-{project}-dev.openai.azure.com/` | Queried from account |
| `AZURE_RESOURCE_GROUP` | `rg-{project}-dev` | Parsed from resource ID |

### Prerequisites Warning

The extension checks for:
1. **Azure Container Registry (ACR)** — needed for remote image build. We already have `cr{project}dev`.
2. **Application Insights** — needed for telemetry. We already have `appi-{project}-dev`.

Both exist in our infrastructure but the temp project wasn't connected to them, hence the warnings.

### Hosting Adapter vs Custom FastAPI

Official samples use the `azure-ai-agentserver-agentframework` hosting adapter:

```python
from azure.ai.agentserver.agentframework import from_agent_framework
agent = create_agent()
from_agent_framework(agent).run()  # exposes /responses on port 8088
```

Our agent uses a **custom FastAPI server** that already exposes `/v1/responses` on port 8088 with:
- Full OpenAI Responses API SSE streaming protocol
- Custom citation metadata injection in `response.completed` events
- `/health` and `/v1/entities` endpoints

**Decision**: Keep our custom FastAPI server. The hosted agent runtime proxies HTTP to the container — it doesn't require the hosting adapter. Our server already implements the expected Responses API contract. The hosting adapter is a convenience for simple agents; our custom implementation provides features (citation metadata, streaming control) that the adapter doesn't support.

## What Needs to Change

### Config Changes Required

1. **`azure.yaml`**: Agent service must use `host: azure.ai.agent`, `language: docker`, `docker.remoteBuild: true`, and include `config` block
2. **`agent.yaml`**: Must use the flattened `ContainerAgent` schema with `kind: hosted`, `protocols`, and `environment_variables`
3. **AZD env vars**: Must set `AZURE_AI_PROJECT_ID`, `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_ACCOUNT_NAME`, `AZURE_AI_PROJECT_NAME`, `AZURE_OPENAI_ENDPOINT`

### No Code Changes Needed

- The FastAPI server (`main.py`) is kept as-is
- The Dockerfile is kept as-is
- The agent framework code (`kb_agent.py`) is kept as-is
- The web app client code is kept as-is (dual-mode auth already handles https endpoints)

## References

- [AZD AI Agent Extension](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/extensions/azure-ai-foundry-extension)
- [Hosted Agents Concept](https://learn.microsoft.com/en-us/azure/ai-services/agents/concepts/hosted-agents)
- [Agent Schema (ContainerAgent.yaml)](https://github.com/microsoft/AgentSchema/blob/main/schemas/v1.0/ContainerAgent.yaml)
- [foundry-samples/echo-agent](https://github.com/microsoft/foundry-samples/tree/main/samples/microsoft/hosted-agents/echo-agent)
- [foundry-samples/agent-with-local-tools](https://github.com/microsoft/foundry-samples/tree/main/samples/microsoft/hosted-agents/agent-with-local-tools)
