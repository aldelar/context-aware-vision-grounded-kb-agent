# ARD-016: Migrate the Thin Client from Chainlit to CopilotKit + Next.js

> **Status:** Accepted (2026-03-28)
> **Date:** 2026-03-27
> **Decision Makers:** Engineering Team

## Context

The original thin client was a Python Chainlit app that talked to the KB Agent through the Responses API. It worked, but it had three structural drawbacks:

- Tool activity was mostly hidden until after the answer completed.
- The web app owned too much chat-display state, including message/reference storage that duplicated agent-owned history.
- The UI/runtime stack diverged from the event model used by the Microsoft Agent Framework and made richer streaming behavior harder to expose.

Epic 016 needed a frontend that could show live tool execution, preserve the existing Easy Auth and image-proxy behaviors, and keep the agent as the system of record for multi-turn memory.

## Decision

**Replace the Chainlit thin client with a Next.js web app that uses CopilotKit for chat UI/runtime and the AG-UI protocol for agent streaming.**

### What This Means

- The agent exposes an AG-UI endpoint at `/ag-ui` alongside the existing Responses API.
- The web app runs as a Node.js/Next.js container on port `3000`.
- CopilotKit's runtime proxies requests from the browser to the agent's AG-UI endpoint.
- The agent remains the sole owner of turn history in the `agent-sessions` Cosmos container.
- The web app stores only lightweight sidebar metadata in the `conversations` Cosmos container.
- Conversation resume is read-only from `agent-sessions` via a Next.js API route.
- Search citations are rendered directly from structured tool output using React components, with `Ref #N` markers linked back to rendered citation cards.

## Alternatives Considered

### Alternative 1: Keep Chainlit and add more custom rendering (Rejected)

- **Pros:** Lower migration cost, minimal rewrite.
- **Cons:** Retains the existing Python UI surface, weak tool-event UX, and duplicated web-app-owned chat persistence. Does not align with AG-UI/CopilotKit patterns already available in the stack.

### Alternative 2: Build a custom React client without CopilotKit (Rejected)

- **Pros:** Maximum control over rendering and protocol plumbing.
- **Cons:** Reimplements chat/runtime concerns already handled by CopilotKit, increases maintenance burden, and slows delivery of tool-aware UX.

### Alternative 3: Move all conversation display state into the web app (Rejected)

- **Pros:** Simpler client-side resume logic.
- **Cons:** Conflicts with the existing architecture where the agent owns memory and compaction. Introduces dual ownership of message history and increases risk of drift between displayed and actual model context.

## Consequences

1. The agent now supports both Responses API consumers and AG-UI consumers.
2. The web app is a TypeScript/Next.js project, not a Python app.
3. Conversation metadata and conversation history have separate ownership boundaries:
   - `conversations` for sidebar metadata
   - `agent-sessions` for full turn history
4. Citation rendering moves from Chainlit side panels to CopilotKit-native tool and message rendering.
5. The `messages` and `references` Cosmos containers remain provisioned only for backward compatibility and are no longer written by the web app.

## References

- [Epic 016](../epics/016-copilotkit-migration.md)
- [Architecture Spec](../specs/architecture.md)
- [Infrastructure Spec](../specs/infrastructure.md)
- [Agent Sessions Spec](../specs/agent-sessions.md)
- [Conversation State Model](../specs/conversations-state-model.md)