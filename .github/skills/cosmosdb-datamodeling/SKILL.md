---
name: cosmosdb-datamodeling
description: |
  Comprehensive Azure Cosmos DB NoSQL data modeling expert. Use when:
  - Designing or reviewing Cosmos DB container schemas and partition strategies
  - Analyzing access patterns and aggregate boundaries
  - Optimizing RU costs, indexing policies, or query performance
  - Evaluating multi-document vs single-document aggregates
  - Working on the project's Cosmos DB containers (agent-sessions, conversations, etc.)
---

# Azure Cosmos DB NoSQL Data Modeling

Step-by-step guide for capturing application requirements and producing optimized Cosmos DB NoSQL data models.

## Role

Help design Cosmos DB NoSQL models by:
1. Gathering application details, access patterns, and volumetrics → document in `cosmosdb_requirements.md`
2. Designing the data model using core philosophy and design patterns → deliver in `cosmosdb_data_model.md`

**Limit questions** — ask at most 3 related questions at a time.

---

## Core Design Philosophy

### Strategic Co-Location

Use multi-document containers to group data frequently accessed together, as long as it can be operationally coupled.

**Multi-Document Container Benefits:**
- Single query efficiency — retrieve related data in one SQL query
- Cost optimization — one query instead of multiple point reads
- Latency reduction — eliminate multiple database round trips
- Transactional consistency — ACID within the same partition

**When to Use:**
- User and their Orders: partition key = user_id
- Product and its Reviews: partition key = product_id
- Course and its Lessons: partition key = course_id

**When NOT to Use (separate containers):**
- Different operational characteristics (independent throughput, scaling, indexing)
- Unrelated entities forced into one container = anti-pattern

### Aggregate Boundaries Based on Access Patterns

| Access Correlation | Recommendation |
|-------------------|----------------|
| >90% accessed together | Strong single document aggregate candidate |
| 50-90% accessed together | Multi-document container aggregate candidate |
| <50% accessed together | Separate aggregates/containers |

**Check constraints:** Size (>1MB → force multi-document), update frequency mismatch (→ consider multi-document), atomicity needs (→ favor same partition).

### Natural Keys Over Generic Identifiers

- ✅ `user_id`, `order_id`, `product_sku` — clear, purposeful
- ❌ `PK`, `SK`, `GSI1PK` — obscure, requires documentation

### Optimize Indexing for Your Queries

Index only properties your access patterns actually query. Use selective indexing by excluding unused paths to reduce RU consumption and storage costs.

### Design For Scale

- Use high cardinality partition keys (user_id, order_id) — aim for 100+ distinct values
- Avoid hot partitions: low cardinality keys (e.g., subscription_tier) create bottlenecks
- Physical partition math: total data size ÷ 50GB = number of physical partitions
- Each logical partition: up to 10,000 RU/s

---

## Key Design Patterns

### Multi-Entity Document Containers

Group related entity types in the same container with different `type` discriminators:

```json
[
  {"id": "user_123", "partitionKey": "user_123", "type": "user", "name": "John"},
  {"id": "order_456", "partitionKey": "user_123", "type": "order", "amount": 99.99}
]
```

Use when: 40-80% access correlation, natural parent-child, acceptable operational coupling.

### Identifying Relationships

Use parent_id as partition key to eliminate cross-partition queries:

```
// Instead of: Reviews container with partition key = review_id (cross-partition to find by product)
// Use: Reviews container with partition key = product_id, id = review_id
```

### Short-Circuit Denormalization

Duplicate small, mostly-immutable properties to avoid extra lookups. Trade storage for read performance.

### Hierarchical Partition Keys (HPK)

For natural hierarchies (tenant → user → document), use HPK to enable prefix queries without synthetic key complexity. **Requires dedicated tier** (not available on serverless).

### TTL for Transient Data

Use TTL for automatic cleanup of session tokens, cache entries, temporary data:

```json
{"id": "sess_abc", "partitionKey": "user_456", "ttl": 86400}
```

### Massive Scale Data Binning

For >10k writes/sec of small records, group into chunks (100 records per document) to reduce write RUs by 90%+.

---

## Constants for Reference

| Metric | Value |
|--------|-------|
| Document size limit | 2MB (hard) |
| Point read (1KB) | 1 RU |
| Query (1KB) | ~2-5 RUs |
| Write (1KB) | ~5 RUs |
| Update (1KB) | ~7 RUs |
| Cross-partition overhead | ~2.5 RU per physical partition |
| Storage | $0.25/GB-month |
| Throughput (manual) | $0.008/RU per hour |
| Throughput (autoscale) | $0.012/RU per hour |
| Monthly seconds | 2,592,000 |

---

## Documentation Workflow

### Working File: `cosmosdb_requirements.md`

Update after **every** user message with new information. Captures:
- Application overview (domain, entities, scale, distribution)
- Access patterns table (pattern #, description, RPS peak/avg, type, attributes, requirements)
- Entity relationships deep dive
- Aggregate analysis and consolidation decisions
- Design considerations (hot partitions, indexing, denormalization)

### Final Deliverable: `cosmosdb_data_model.md`

Create only after user confirms all access patterns are captured. Contains:
- Design philosophy and approach
- Container designs with JSON examples (5-10 representative documents per container)
- Partition key justifications
- Indexing strategies (included/excluded paths, composite indexes)
- Access pattern mapping (every pattern → container + operation)
- Hot partition analysis
- Trade-offs and optimizations
- Cost estimates

---

## Project Context

This project uses Cosmos DB (serverless) with these containers:

| Container | Partition Key | Purpose |
|-----------|--------------|---------|
| `agent-sessions` | `/id` | Agent conversation persistence (AgentSession) |
| `conversations` | `/userId` | Web app conversation metadata |
| `messages` | `/conversationId` | Chat message history |
| `references` | `/conversationId` | Chunk references for citation display |

When reviewing or extending these containers, apply the design patterns above. The serverless tier means HPK is not available — use synthetic keys if needed.

## Critical Rules

- **Never fabricate RPS numbers** — work with user to estimate
- **Always calculate costs** using realistic document sizes, not theoretical 1KB
- **Include cross-partition overhead** in all cross-partition query costs
- **Discuss major design decisions** before implementing
- **Update requirements file** after each user response
