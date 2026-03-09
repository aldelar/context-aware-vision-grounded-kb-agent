# ARD-006: MarkItDown as Third Conversion Backend

> **Status:** Accepted
> **Date:** 2026-03-09
> **Decision Makers:** Engineering Team

## Context

The ingestion pipeline already supports two conversion backends for transforming HTML KB articles into Markdown:

1. **Content Understanding** (`fn_convert_cu`) — Azure AI service that processes HTML directly for text extraction, with a custom CU analyzer for image descriptions
2. **Mistral Document AI** (`fn_convert_mistral`) — HTML → PDF rendering via Playwright, then Mistral OCR for text extraction, plus GPT-4.1 vision for image descriptions

Both backends involve cloud API calls for text extraction, incur per-call costs, and require backend-specific Azure infrastructure (CU analyzers, Mistral model deployments, Playwright/Chromium).

The question is whether to add a third, lighter-weight option that can extract text locally without cloud API calls.

## Decision

**Add MarkItDown as a third conversion backend** (`fn_convert_markitdown`) using the [microsoft/markitdown](https://github.com/microsoft/markitdown) open-source Python library for HTML → Markdown conversion, with GPT-4.1 vision for image descriptions.

### What This Means

- Text extraction runs entirely in local Python — no cloud API calls, no network latency, no per-call cost
- Image descriptions still use GPT-4.1 vision (same prompt schema as CU and Mistral backends)
- Hyperlinks are preserved natively by MarkItDown (no post-processing recovery step needed)
- No new Azure infrastructure required — only the existing `gpt-4.1` deployment is used
- Selected at runtime via `analyzer=markitdown` (same pattern as existing backends)

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **Stay with two backends** | No new code to maintain | Missing the simplest/cheapest option for basic HTML articles |
| **Replace CU or Mistral** | Fewer backends to maintain | Lose CU's deep analysis or Mistral's OCR capabilities; each has strengths for different content types |
| **MarkItDown as third option** (chosen) | Fastest, cheapest, simplest; zero infra cost for text extraction; best link handling | One more backend to maintain; less sophisticated than CU for complex documents |

## Trade-offs

| Aspect | MarkItDown | Content Understanding | Mistral Document AI |
|--------|-----------|----------------------|---------------------|
| **Text extraction** | Local Python (ms) | Cloud API (seconds) | Cloud API (seconds) |
| **Text extraction cost** | Free | CU charges | Mistral OCR charges |
| **Image descriptions** | GPT-4.1 vision | Custom CU analyzer (GPT-4.1) | GPT-4.1 vision |
| **Link handling** | Native preservation | Post-processing recovery | Post-processing recovery |
| **Dependencies** | `markitdown` (pure Python) | `azure-ai-contentunderstanding` | `playwright`, `httpx` |
| **Azure infra required** | GPT-4.1 only | AI Services (CU + GPT models) | AI Services (Mistral + GPT-4.1) |
| **Offline text extraction** | Yes | No | No |
| **Complex document analysis** | Basic (HTML structure only) | Advanced (CU field extraction) | Good (Mistral OCR) |

## Validation

A spike evaluation ([Spike 003](../spikes/003-markitdown.md)) tested MarkItDown against all three sample KB articles and compared output quality with the existing backends:

- **Heading structure**: Preserved faithfully across all articles
- **Table rendering**: Comparable quality to CU and Mistral output
- **Hyperlinks**: Preserved natively (CU and Mistral require post-processing recovery)
- **Image extraction**: All images detected via HTML DOM parsing
- **Recommendation**: Go — quality is sufficient for KB article use cases

## Consequences

- **Positive**: Developers can run the text extraction step without any Azure connectivity; fastest iteration cycle for testing pipeline changes
- **Positive**: Zero additional infrastructure cost for text extraction; only GPT-4.1 vision calls are billed
- **Positive**: Simplest dependency footprint — single `markitdown` pip package, no binary dependencies (unlike Playwright/Chromium for Mistral)
- **Negative**: One more backend to maintain (mitigated by shared contract and test patterns)
- **Neutral**: Image descriptions still require GPT-4.1 — same cost as Mistral backend for that step

## References

- [Spike 003 — MarkItDown](../spikes/003-markitdown.md)
- [Epic 007 — MarkItDown for Convert](../epics/007-markitdown-for-convert.md)
- [Architecture spec — MarkItDown Backend](../specs/architecture.md#markitdown-backend-fn_convert_markitdown)
