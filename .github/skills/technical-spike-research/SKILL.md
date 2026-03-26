---
name: technical-spike-research
description: 'Systematically research and validate technical spike documents through exhaustive investigation and controlled experimentation. Use when conducting spikes documented in docs/spikes/ or docs/research/.'
---

# Technical Spike Research

Systematically validate technical spike documents through exhaustive investigation and controlled experimentation.

## Requirements

**CRITICAL**: User must specify spike document path before proceeding. Stop if no spike document provided.

Spike documents live in:
- `docs/spikes/` — Hands-on spike investigations
- `docs/research/` — Research notes and findings

## Research Methodology

### Tool Usage Philosophy

- Use tools **obsessively** and **recursively** — exhaust all available research avenues
- Follow every lead: if one search reveals new terms, search those terms immediately
- Cross-reference between multiple tool outputs to validate findings
- Never stop at first result — use search, fetch, and code exploration in combination
- Layer research: docs → code examples → real implementations → edge cases

### Todo Management Protocol

- Create comprehensive todo list at research start
- Break spike into granular, trackable investigation tasks
- Mark todos in-progress before starting each investigation thread
- Update todo status immediately upon completion
- Add new todos as research reveals additional investigation paths

### Spike Document Update Protocol

- **CONTINUOUSLY update spike document during research** — never wait until end
- Update relevant sections immediately after each tool use and discovery
- Add findings to "Investigation Results" section in real-time
- Document sources and evidence as you find them
- Note preliminary conclusions and evolving understanding throughout process

## Research Process

### 0. Investigation Planning

- Create comprehensive todo list with all known research areas
- Parse spike document completely
- Extract all research questions and success criteria
- Prioritize investigation tasks by dependency and criticality

### 1. Spike Analysis

- Extract all research questions and success criteria
- **UPDATE SPIKE**: Document initial understanding and research plan
- Identify technical unknowns requiring deep investigation
- Plan investigation strategy with recursive research points

### 2. Documentation Research

**Obsessive Documentation Mining**: Research every angle exhaustively

- Search official docs and Microsoft Learn (use MCP tools when available)
- **UPDATE SPIKE**: Add each significant finding immediately
- For each result, fetch complete documentation pages
- Cross-reference with discovered terminology
- Document findings with source citations and recursive follow-up searches

### 3. Code Analysis

**Recursive Code Investigation**: Follow every implementation trail

- Examine relevant repositories for similar functionality
- **UPDATE SPIKE**: Document implementation patterns and architectural approaches
- Study integration approaches, error handling, and auth methods
- Recursively investigate dependencies and related libraries
- Document specific code references and add follow-up investigation todos

### 4. Experimental Validation

**ASK USER PERMISSION before any code creation or command execution**

- Design minimal proof-of-concept tests based on documentation research
- **UPDATE SPIKE**: Document experimental design and expected outcomes
- Execute validation and record results immediately, including failures
- Document technical blockers and workarounds

### 5. Documentation Update

- Update spike document sections:
  - Investigation Results: detailed findings with evidence
  - Prototype/Testing Notes: experimental results
  - External Resources: all sources found
  - Decision/Recommendation: clear conclusion based on exhaustive research
  - Status History: mark complete
- Ensure all todos are marked complete or have clear next steps

## Evidence Standards

- **REAL-TIME DOCUMENTATION**: Update spike document continuously, not at end
- Cite specific sources with URLs and versions immediately upon discovery
- Include quantitative data where possible
- Note limitations and constraints as you encounter them
- Provide clear validation or invalidation statements
- Document recursive research trails showing investigation depth

## User Collaboration

Always ask permission for: creating files, running commands, modifying system, experimental operations.

Transform uncertainty into actionable knowledge through systematic, obsessive, recursive research.
