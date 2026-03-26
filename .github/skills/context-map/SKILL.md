---
name: context-map
description: 'Generate a map of all files relevant to a task before making changes. Use when planning multi-file modifications, cross-service changes, or any work that touches multiple modules.'
---

# Context Map

Before implementing any changes, analyze the codebase and create a context map.

## Task

{{task_description}}

## Instructions

1. Search the codebase for files related to this task
2. Identify direct dependencies (imports/exports)
3. Find related tests
4. Look for similar patterns in existing code
5. Check for cross-service boundaries (agent/functions/web-app/infra)

## Output Format

```markdown
## Context Map

### Files to Modify
| File | Service | Purpose | Changes Needed |
|------|---------|---------|----------------|
| path/to/file | agent/functions/web-app/infra | description | what changes |

### Dependencies (may need updates)
| File | Relationship |
|------|--------------|
| path/to/dep | imports X from modified file |

### Test Files
| Test | Coverage |
|------|----------|
| path/to/test | tests affected functionality |

### Reference Patterns
| File | Pattern |
|------|---------|
| path/to/similar | example to follow |

### Cross-Service Impact
| Service | Impact | Action Needed |
|---------|--------|---------------|
| agent/functions/web-app/infra | description | yes/no |

### Risk Assessment
- [ ] Breaking changes to public API
- [ ] Database migrations needed
- [ ] Configuration changes required
- [ ] Infrastructure (Bicep) changes needed
- [ ] Environment variable changes
- [ ] Service boundary violations
```

Do not proceed with implementation until this map is reviewed.
