---
name: cloud-design-patterns
description: 'Cloud design patterns for distributed systems architecture covering 42 industry-standard patterns across reliability, performance, messaging, security, and deployment categories. Use when designing, reviewing, or implementing distributed system architectures.'
---

# Cloud Design Patterns

Architects design workloads by integrating platform services, functionality, and code to meet both functional and nonfunctional requirements. Cloud design patterns provide solutions to many common challenges in distributed systems.

## How Cloud Design Patterns Enhance the Design Process

Cloud workloads are vulnerable to the fallacies of distributed computing:

- The network is reliable.
- Latency is zero.
- Bandwidth is infinite.
- The network is secure.
- Topology doesn't change.
- There's one administrator.
- Component versioning is simple.
- Observability implementation can be delayed.

These misconceptions can result in flawed workload designs. Design patterns don't eliminate these misconceptions but help raise awareness, provide compensation strategies, and provide mitigations. Each cloud design pattern has trade-offs. Focus on why you should choose a specific pattern instead of how to implement it.

---

## Pattern Categories at a Glance

| Category | Patterns | Focus |
|---|---|---|
| Reliability & Resilience | 9 patterns | Fault tolerance, self-healing, graceful degradation |
| Performance | 10 patterns | Caching, scaling, load management, data optimization |
| Messaging & Integration | 7 patterns | Decoupling, event-driven communication, workflow coordination |
| Architecture & Design | 7 patterns | System boundaries, API gateways, migration strategies |
| Deployment & Operational | 5 patterns | Infrastructure management, geo-distribution, configuration |
| Security | 3 patterns | Identity, access control, content validation |
| Event-Driven Architecture | 1 pattern | Event sourcing and audit trails |

## Key Patterns for This Project

### Relevant to the KB Agent Pipeline

| Pattern | Relevance |
|---------|-----------|
| **Pipes and Filters** | fn-convert → fn-index two-stage pipeline |
| **Queue-Based Load Leveling** | Storage queue between convert and index functions |
| **Retry** | Azure Function triggers with retry policies |
| **Circuit Breaker** | External API calls (AI Services, Cosmos DB) |
| **Cache-Aside** | AI Search index as a read cache over KB content |
| **External Configuration Store** | Environment-driven config via `.env` and `azd` |
| **Gateway Routing** | APIM as API gateway for agent endpoint |
| **Sidecar** | Container Apps with shared infrastructure |
| **Federated Identity** | Azure Managed Identity + Entra ID auth |
| **Backends for Frontends** | Same-origin image proxy avoids SAS token complexity |

### Pattern Selection Guide

When designing or reviewing architecture:

1. **Identify the challenge** — reliability, performance, security, integration?
2. **Match to category** — use the table above
3. **Evaluate trade-offs** — every pattern has costs
4. **Validate against requirements** — align with Well-Architected Framework pillars
5. **Document decisions** — record pattern choices in ARDs (`docs/ards/`)

## External Links

- [Cloud Design Patterns - Azure Architecture Center](https://learn.microsoft.com/azure/architecture/patterns/)
- [Azure Well-Architected Framework](https://learn.microsoft.com/azure/architecture/framework/)
