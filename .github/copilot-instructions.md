# Copilot Instructions

## Project Overview

This is an Azure-hosted application. Follow these instructions when generating code, reviewing PRs, or answering questions about this codebase.

## Architecture

See /docs/specs/architecture.md for a high-level overview of the system architecture.
See /docs/specs/infrastructure.md for details on the Azure services used to implement this architecture.

### Solution Structure

docs/ - Documentation, specs, and design docs
- ards/ - Architecture Decision Records
- epics/ - Epic and story tracking markdown files
- research/ - Research notes, spike results
- specs/ - Architecture and design specifications
infra/ - Bicep modules and infrastructure code
kb/ - Knowledge base articles samples
scripts/ - Ad-hoc scripts for data processing, testing, etc.
src/ - Application source code
- spikes/ - Spike implementations and prototypes (not part of the solution, code for research and experimentation only)

## Environment & Setup

- Every environment change must be captured in scripts or IaC — never make one-off manual changes to the dev environment
- AZD is used for deployment automation; follow the patterns in `infra/` for new services or resources
- Infrastructure changes (new Azure services, connection strings, app settings) go in `infra/` (Bicep modules) and are deployed via `azd provision` or CI/CD
- Database schema changes require an EF Core migration (`dotnet ef migrations add <Name>`), never raw DDL or manual portal edits
- If you add a new tool, service, or environment variable, update the relevant docs and infra templates
- Configuration is environment-driven: use `appsettings.{Environment}.json`, environment variables, or Azure App Configuration — never hardcode environment-specific values
- A fresh `git clone` + the documented setup steps must produce a fully working environment — verify this mentally before finishing any infra or setup work
- Refer to the Makefile for common commands and scripts to automate setup, testing, and deployment tasks

## Azure & Deployment

- Infrastructure as Code using Bicep. Leverage AZD for deployment automation.
- Use managed identities over keys/secrets wherever possible
- Follow Azure Well-Architected Framework principles
- Environment config via Azure App Configuration or environment variables
- CI/CD via GitHub Actions

## Security

- Never commit secrets, connection strings, or keys
- Use Key Vault references or managed identity
- Enable HTTPS everywhere
- Use Azure Entra ID for authentication/authorization
- Follow OWASP guidelines for input validation

## Error Handling & Observability

- Use structured logging with `ILogger<T>`
- Correlate logs with Application Insights
- Use global exception handling middleware
- Return `ProblemDetails` (RFC 9457) for API errors

## Epic & Story Tracking

- Epic docs live in `/epics/` — each epic file is the source of truth for story status
- After completing a story, update the epic file immediately:
  - Check off all acceptance criteria (`- [x]`)
  - Add ✅ to the story title
  - Mark implementation-scope table rows with ✅ for completed files
  - Check off all Definition of Done items
- Update the epic's top-level `Status:` field when all stories are done (→ `Done`)
- Before starting a new story, verify the epic file reflects reality, validate that the tests pass, and ensure the next story is ready to be picked up without needing to audit the code or doc
- Never leave an epic partially updated — if code is done, the doc must match so the next session can pick up confidently without re-auditing

## Pull Request Guidelines

- Keep PRs focused and small
- Include unit tests for new logic
- Update relevant documentation
- Ensure CI passes before requesting review