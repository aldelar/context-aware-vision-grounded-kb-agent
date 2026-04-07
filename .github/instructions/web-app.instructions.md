---
name: 'Web App Standards'
description: 'Next.js + CopilotKit web app conventions, dependency rules, and testing patterns'
applyTo: "src/web-app/**"
---

# Web App Standards

## Stack

- **Next.js 16** (App Router) with React 19 and TypeScript 5
- **CopilotKit** for chat UI (`@copilotkit/react-core`, `@copilotkit/react-ui`, `@copilotkit/runtime`)
- **AG-UI protocol** connects the CopilotKit frontend to the agent via `@ag-ui/client` `HttpAgent`
- **Node.js 20** runtime (Dockerfile base image)
- Port **3000** — configured in `next dev`, `next start`, and Dockerfile `EXPOSE`
- `output: "standalone"` in `next.config.ts` for Docker-optimized builds

## Project Layout

```
src/web-app/
├── app/              # Next.js App Router pages and API routes
│   ├── api/          # Backend-for-frontend API routes
│   │   ├── copilotkit/  # CopilotKit ↔ AG-UI proxy endpoint
│   │   └── images/      # Azure Blob Storage image proxy
│   ├── layout.tsx
│   └── page.tsx
├── components/       # React components (CopilotChat, sidebar, tool renderers)
├── lib/              # Server-side utilities (auth, config, blob, conversations)
├── __tests__/        # Vitest tests mirroring the source directory structure
├── public/           # Static assets
├── Dockerfile        # Multi-stage build (deps → builder → runner)
└── package.json
```

## Dependency Rules

### CopilotKit + AG-UI Version Coupling

`@ag-ui/client` and `@copilotkit/*` packages are **tightly coupled** — CopilotKit pins a specific `@ag-ui/client` version internally. Bumping `@ag-ui/client` independently of CopilotKit will cause TypeScript type mismatches (e.g., new AG-UI content types like `image`/`audio` that CopilotKit's type definitions don't recognize). Always upgrade them **together**.

To check compatibility before bumping:
```bash
npm ls @ag-ui/client   # shows CopilotKit's internal pin
```

### Adding Dependencies

- Production deps in `dependencies`, dev/test deps in `devDependencies`
- After modifying: `npm install` to regenerate `package-lock.json`
- Verify the Docker build: `docker build -t web-app-test src/web-app/`

## Configuration

- All runtime config via environment variables — see `.env.sample` for the full list
- `lib/config.ts` exports a typed `config` object with defaults for local dev
- **Environment-driven**: `ENVIRONMENT=dev` enables local emulator paths (Azurite, Cosmos emulator)
- `AGENT_ENDPOINT` points to the agent container (default: `http://localhost:8088`)
- AG-UI endpoint derived from `AGENT_ENDPOINT` + `/ag-ui/` path

## Authentication

- **Production**: Entra ID Easy Auth on the Container App; `x-ms-client-principal*` headers forwarded to the agent
- **Local dev**: auth disabled (`REQUIRE_AUTH=false` on the agent); `X-User-Id` and `X-User-Name` headers populated from config defaults
- `lib/auth.ts` resolves user context from request headers and builds group headers for the agent

## Image Proxy

- `/api/images/[...path]` serves images from Azure Blob Storage (prod) or Azurite (dev)
- Images referenced in agent responses use `/api/images/...` URLs
- Never expose raw blob storage URLs to the browser

## Testing

- **Vitest** with `jsdom` environment — tests in `__tests__/` directory
- Run: `npm test` (equivalent to `vitest run`)
- Test structure mirrors source: `__tests__/components/`, `__tests__/lib/`, `__tests__/api/`
- Use `@testing-library/react` for component tests
- Mock server-side modules (Azure SDKs, fetch) — tests run in jsdom, not Node

## Docker

- Multi-stage build: `deps` → `builder` → `runner`
- `npm ci` in deps stage for reproducible installs
- Standalone output copied to runner (no `node_modules` in final image)
- Final image runs `node server.js` — no npm in the runner stage

## Code Style

- TypeScript strict mode (`"strict": true` in tsconfig)
- No `allowJs` — all source must be TypeScript
- Use `interface` for component props, `type` for unions and utility types
- Server Components by default; add `"use client"` only when needed
- `lib/` modules are server-only — don't import them from client components
