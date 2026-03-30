---
name: microsoft-agent-framework
description: 'Create, update, refactor, explain, or review Microsoft Agent Framework solutions. Use when working with the KB Agent (src/agent/) or any Microsoft Agent Framework code.'
---

# Microsoft Agent Framework

Use this skill when working with applications, agents, workflows, or migrations built on Microsoft Agent Framework.

Microsoft Agent Framework is the unified successor to Semantic Kernel and AutoGen, combining their strengths with new capabilities. Because it is still in public preview and changes quickly, always ground implementation advice in the latest official documentation and samples rather than relying on stale knowledge.

## Target Language

This project uses **Python**. The agent service is in `src/agent/` and uses Starlette with the Agent Framework SDK (`from_agent_framework` creates a Starlette ASGI app).

## Always Consult Live Documentation

- Read the Microsoft Agent Framework overview first: <https://learn.microsoft.com/agent-framework/overview/agent-framework-overview>
- Prefer official docs and samples for the current API surface.
- Use the Microsoft Docs MCP tooling when available to fetch up-to-date framework guidance and examples.
- Treat older Semantic Kernel or AutoGen patterns as migration inputs, not as the default implementation model.

## Shared Guidance

When working with Microsoft Agent Framework:

- Use async patterns for agent and workflow operations.
- Implement explicit error handling and logging.
- Prefer strong typing, clear interfaces, and maintainable composition patterns.
- Use `DefaultAzureCredential` when Azure authentication is appropriate.
- Use agents for autonomous decision-making, ad hoc planning, conversation flows, tool usage, and MCP server interactions.
- Use workflows for multi-step orchestration, predefined execution graphs, long-running tasks, and human-in-the-loop scenarios.
- Support model providers such as Azure AI Foundry, Azure OpenAI, OpenAI, and others, but prefer Azure AI Foundry services for new projects.
- Use thread-based or equivalent state handling, context providers, middleware, checkpointing, routing, and orchestration patterns when they fit the problem.

## Project-Specific Context

- **Agent location**: `src/agent/` — Starlette ASGI service with Agent Framework
- **Deployment**: Azure Container Apps (see `infra/azure/infra/modules/agent-container-app.bicep`)
- **Auth**: JWT validation via APIM gateway (see `docs/ards/ARD-010-agent-external-auth-gateway.md`)
- **Memory**: Cosmos DB for conversation history (see `docs/specs/agent-memory.md`)
- **Tools**: Agent uses tools for KB search, image analysis, and other domain operations

## Migration Guidance

- If migrating from Semantic Kernel, use the official migration guide: <https://learn.microsoft.com/agent-framework/migration-guide/from-semantic-kernel/>
- If migrating from AutoGen, use the official migration guide: <https://learn.microsoft.com/agent-framework/migration-guide/from-autogen/>
- Preserve behavior first, then adopt native Agent Framework patterns incrementally.

## Workflow

1. Determine the target language (Python for this project) and read the matching reference.
2. Fetch the latest official docs and samples before making implementation choices.
3. Apply the shared agent and workflow guidance from this skill.
4. Follow this project's conventions: `DefaultAzureCredential`, managed identity, uv for dependencies.
5. When examples in the repo differ from current docs, explain the difference and follow the current supported pattern.

## Completion Criteria

- Recommendations match Python and this project's stack.
- Package names, repository paths, and sample locations match the Python ecosystem.
- Guidance reflects current Microsoft Agent Framework documentation rather than legacy assumptions.
- Migration advice calls out Semantic Kernel and AutoGen only when relevant.
