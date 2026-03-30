---
name: agent-governance
description: |
  Patterns for adding governance, safety, and trust controls to AI agent systems
  using Microsoft Foundry and Azure API Management (APIM) AI Gateway. Use when:
  - Adding rate limiting, content safety, or jailbreak detection to agent traffic
  - Configuring APIM policies for token limits, throttling, or semantic caching
  - Leveraging Foundry tracing, evaluations, and agent monitoring
  - Implementing department-scoped access via JWT claims
  - Deciding what to handle at the platform layer vs. thin application code
---

# Agent Governance — Foundry + APIM AI Gateway

Governance for AI agents should be implemented at the **platform layer** wherever possible. Microsoft Foundry and Azure API Management provide most governance controls out of the box — avoid building custom equivalents in application code.

## Core Principle

> **Don't build what the platform provides.** Rate limiting, content safety, request logging, tracing, and token tracking are infrastructure concerns — handle them in APIM policies and Foundry configuration, not in Python decorators or custom middleware.

```
User Request → APIM AI Gateway → Agent Container App → Foundry (tracing + eval)
                    ↓                      ↓
            Policy Pipeline          JWT → department scoping
            (rate limit,             (SecurityFilterMiddleware)
             content safety,
             token tracking,
             audit logging)
```

## When to Use

- **Adding governance to an agent behind APIM** — use APIM policies first
- **Evaluating agent quality** — use Foundry evaluations, not custom scoring
- **Tracing agent behavior** — use Foundry Control Plane traces, not custom audit tables
- **Scoping access by department/role** — use JWT claims + OData filters (already implemented in this project)

---

## What the Platform Provides (Use These First)

### Foundry — Agent Lifecycle & Observability

| Capability | How | Status in This Project |
|------------|-----|----------------------|
| **Tracing** | Platform-native traces in Foundry Control Plane (Operate → Traces). Agent Framework auto-emits spans for tool calls, model invocations, and middleware. | ✅ Configured via `appinsights-connection` in `foundry-project.bicep` |
| **Agent Registration** | Register agents in Foundry portal (Operate → Assets) for lifecycle management. | ✅ Via `scripts/register-agent.sh` + APIM connection |
| **Evaluations** | Batch eval runs to measure quality, groundedness, relevance. Golden datasets + custom evaluators. | ✅ See Epic 006 |
| **Model Deployments** | Centralized model endpoint management (GPT-4.1, gpt-5-mini, text-embedding-3-small). | ✅ In `ai-services.bicep` |
| **App Insights Integration** | OTel spans + structured logs exported to App Insights automatically. | ✅ Account-level setting in `ai-services.bicep` |

### APIM AI Gateway — Traffic Governance

| Capability | APIM Policy | Status in This Project |
|------------|-------------|----------------------|
| **Pass-through proxy** | `<set-backend-service>` | ✅ Configured in `apim-agent-api.bicep` |
| **Request/response logging** | Built-in App Insights diagnostic logging | ✅ Automatic with APIM |
| **Rate limiting** | `<rate-limit>` or `<rate-limit-by-key>` | ⬜ Not yet configured — add as APIM policy |
| **Token tracking** | `<azure-openai-token-limit>` or `<llm-token-limit>` | ⬜ Not yet configured |
| **Content safety** | `<azure-openai-content-safety>` callout to Azure Content Safety | ⬜ Not yet configured |
| **Jailbreak detection** | Content Safety API with `jailbreak` category | ⬜ Not yet configured |
| **Semantic caching** | `<azure-openai-semantic-cache-store>` / `<azure-openai-semantic-cache-lookup>` | ⬜ Low priority for dev |
| **JWT validation** | `<validate-azure-ad-token>` | Agent-side (`jwt_auth.py`) — could be moved to APIM |
| **Subscription keys** | Built-in subscription management | ⬜ Currently `subscriptionRequired: false` |

---

## Implementation Patterns

### Pattern 1: Rate Limiting via APIM Policy

Add per-user throttling as an APIM inbound policy — no application code needed:

```xml
<!-- APIM inbound policy: rate limit by authenticated user -->
<inbound>
    <base />
    <set-backend-service backend-id="kb-agent-backend" />
    <rate-limit-by-key
        calls="20"
        renewal-period="60"
        counter-key="@(context.Request.Headers.GetValueOrDefault("Authorization","").Split(' ').Last())"
        increment-condition="@(context.Response.StatusCode >= 200)" />
</inbound>
```

For subscription-based limiting (if subscriptions are enabled later):

```xml
<rate-limit calls="100" renewal-period="3600" />
```

### Pattern 2: Content Safety via APIM Policy

Route user prompts through Azure Content Safety before they reach the agent:

```xml
<!-- APIM inbound policy: content safety check on request body -->
<inbound>
    <base />
    <set-backend-service backend-id="kb-agent-backend" />
    <!-- Block jailbreak attempts and harmful content -->
    <azure-openai-content-safety
        backend-id="content-safety-backend"
        jailbreak-detection="true"
        sexual="medium"
        violence="medium"
        self-harm="medium"
        hate="medium">
        <on-violation>
            <return-response>
                <set-status code="400" reason="Content policy violation" />
                <set-body>{"error": "Request blocked by content safety policy"}</set-body>
            </return-response>
        </on-violation>
    </azure-openai-content-safety>
</inbound>
```

This requires provisioning an Azure Content Safety resource and adding it as an APIM backend. Define in Bicep alongside `apim-agent-api.bicep`.

### Pattern 3: Token Limit Enforcement via APIM Policy

Prevent excessive token consumption at the gateway layer:

```xml
<!-- APIM policy: enforce token limits per user per hour -->
<azure-openai-token-limit
    tokens-per-minute="10000"
    counter-key="@(context.Request.Headers.GetValueOrDefault("Authorization","").Split(' ').Last())"
    estimate-prompt-tokens="true"
    remaining-tokens-header-name="x-remaining-tokens" />
```

### Pattern 4: Department-Scoped Access (Application Layer)

This is the one area where thin application code is appropriate — APIM cannot interpret business-level authorization. This project already implements this correctly:

1. **JWT validation** at HTTP boundary (`middleware/jwt_auth.py`)
2. **Claim extraction** into `ContextVar` (`middleware/request_context.py`)
3. **Group → department resolution** (`agent/group_resolver.py`)
4. **OData filter injection** via `SecurityFilterMiddleware` → tool `**kwargs`
5. **Search scoping** — `search.in(department, 'eng,sales', ',')`

The LLM never sees the filter context. This is correct — it's business logic that belongs in application code, not APIM policy.

### Pattern 5: Structured Audit via App Insights + Foundry Traces

Prefer platform telemetry over custom audit tables:

```python
# In agent tool functions — emit structured OTel spans
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

# The Agent Framework already emits spans for tool calls.
# Add business-level attributes to existing spans:
span = trace.get_current_span()
span.set_attribute("governance.department", departments)
span.set_attribute("governance.user_id", user_id)
span.set_attribute("governance.tool_result_count", len(results))
```

These attributes flow to App Insights and are queryable via KQL:

```kql
// Query: audit all tool calls by department in last 24h
dependencies
| where timestamp > ago(24h)
| where name startswith "tool_"
| extend department = tostring(customDimensions["governance.department"])
| summarize calls=count(), avg_duration=avg(duration) by name, department
| order by calls desc
```

**Do NOT** build a custom `AuditTrail` class or Cosmos DB audit container. The OTel traces + App Insights + Foundry Control Plane already provide this.

---

## Governance Tiers

| Tier | Platform Controls | Application Code | Use Case |
|------|-------------------|-------------------|----------|
| **Dev** | APIM pass-through + Foundry tracing | JWT auth (optional) | Local dev, testing |
| **Standard** | APIM rate limiting + request logging + Foundry tracing + evals | JWT auth + department scoping | General production |
| **Hardened** | All Standard + content safety + jailbreak detection + token limits | JWT auth + department scoping | Sensitive data, compliance |

## Decision Framework: Platform vs. Custom Code

| Governance Need | Use Platform | Use Application Code |
|----------------|--------------|---------------------|
| Rate limiting | ✅ APIM `<rate-limit-by-key>` | ❌ |
| Content safety | ✅ APIM + Azure Content Safety | ❌ |
| Jailbreak detection | ✅ APIM + Content Safety API | ❌ |
| Token tracking | ✅ APIM `<azure-openai-token-limit>` | ❌ |
| Request logging | ✅ APIM + App Insights (automatic) | ❌ |
| Agent tracing | ✅ Foundry Control Plane (automatic) | ❌ |
| Agent evaluation | ✅ Foundry batch evals | ❌ |
| Semantic caching | ✅ APIM (when warranted by volume) | ❌ |
| JWT validation | Either (currently agent-side) | ✅ Current impl is fine |
| Department scoping | ❌ (business logic) | ✅ JWT claims → OData filters |
| Tool-level authorization | ❌ (business logic) | ✅ If needed, thin middleware |
| Custom business audit attrs | ❌ | ✅ OTel span attributes (not custom tables) |

## Best Practices

| Practice | Rationale |
|----------|-----------|
| **APIM policy over Python decorator** | Rate limiting, content filtering, and token limits are infrastructure — handle at the gateway, not in app code |
| **Foundry traces over custom audit tables** | OTel spans + App Insights KQL replaces custom `AuditTrail` classes and Cosmos containers |
| **Foundry evals over trust scoring** | Batch evaluations with golden datasets measure agent quality better than runtime trust scores |
| **Bicep-defined policies** | APIM policies should be defined in Bicep modules (IaC) alongside `apim-agent-api.bicep`, not configured manually |
| **Thin application layer** | Only implement in code what the platform cannot: business-level authorization (department scoping), domain-specific tool logic |
| **Layered defense** | APIM handles coarse-grained governance (rate limits, content safety); application handles fine-grained authorization (department filters) |

## Project-Specific Context

| Component | Location | Purpose |
|-----------|----------|---------|
| APIM gateway | `infra/azure/infra/modules/apim.bicep` | BasicV2, system-assigned identity |
| APIM agent API | `infra/azure/infra/modules/apim-agent-api.bicep` | Pass-through proxy (add policies here) |
| Foundry project | `infra/azure/infra/modules/foundry-project.bicep` | Tracing + APIM connection + App Insights |
| JWT middleware | `src/agent/middleware/jwt_auth.py` | Entra ID token validation |
| Security middleware | `src/agent/agent/security_middleware.py` | Department scoping via `**kwargs` |
| Agent registration | `scripts/register-agent.sh` | Registers agent in Foundry via APIM gateway |
| Architecture decision | `docs/ards/ARD-010-agent-external-auth-gateway.md` | APIM AI Gateway rationale |
| **Fail closed** | If governance check errors, deny the action rather than allowing it |
| **Separate policy from logic** | Governance enforcement should be independent of agent business logic |

## Related Resources

- [Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
- [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
