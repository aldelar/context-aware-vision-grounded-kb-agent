# ARD-004: Custom CU Image Analyzer for Knowledge Base Screenshots

> **Status:** Accepted
> **Date:** 2026-02-13
> **Decision Makers:** Engineering Team

## Context

The pipeline analyzes each article image individually through Azure Content Understanding to produce text descriptions that are embedded inline in the Markdown output. These descriptions serve dual purposes:

1. **Searchability** — image descriptions become part of chunk text and are vectorized alongside surrounding content, making image content discoverable via semantic search
2. **Agent grounding** — agents can reason over the descriptions to determine when an image is relevant and surface the actual image URL to users

The source images are UI screenshots and technical diagrams from knowledge base articles (13–40 KB PNGs) showing software interfaces, navigation menus, configuration screens, and workflow diagrams.

## Decision

**Create a custom Content Understanding analyzer (`kb-image-analyzer`) based on `prebuilt-image` with a domain-tuned field schema** optimized for UI screenshots and technical documentation images.

### Analyzer Definition

```json
{
  "analyzerId": "kb_image_analyzer",
  "baseAnalyzerId": "prebuilt-image",
  "models": { "completion": "gpt-4.1" },
  "fieldSchema": {
    "fields": {
      "Description": {
        "type": "string",
        "method": "generate",
        "description": "A detailed description focusing on: what screen/page is shown, key UI elements visible, highlighted or annotated areas, navigation steps illustrated, and any text visible in the image."
      },
      "UIElements": {
        "type": "array",
        "method": "generate",
        "description": "List of key UI elements visible (buttons, menus, fields, labels)",
        "items": { "type": "string" }
      },
      "NavigationPath": {
        "type": "string",
        "method": "generate",
        "description": "The navigation path shown, e.g. 'Settings > Security > Manage user security'"
      }
    }
  }
}
```

The analyzer definition is stored in [src/analyzers/definitions/kb-image-analyzer.json](../../src/analyzers/definitions/kb-image-analyzer.json) and managed via `manage_analyzers.py`. It is created/updated during `make azure-deploy` and deleted during `make azure-clean`.

## Alternatives Considered

### Alternative 1: `prebuilt-documentSearch` on Individual Images (Rejected)

Send each image to the generic `prebuilt-documentSearch` analyzer.

- **Tested empirically:** Works — generates descriptions, detects sub-figures, produces a summary
- **Cons:** Generic descriptions not tuned for UI screenshots; no structured fields for UI elements or navigation paths; produces excess metadata (paragraphs, spans, bounding boxes) irrelevant for individual image analysis. Uses the heavier `text-embedding-3-large` model unnecessarily.

### Alternative 2: `prebuilt-image` Standalone (Not Viable)

Use the `prebuilt-image` base analyzer without customization.

- **Result:** `prebuilt-image` cannot be run standalone — it requires a custom analyzer with a `fieldSchema` to define the output structure. Calling it directly fails.

### Alternative 3: Direct GPT-4.1 Vision Calls (Rejected)

Skip CU entirely and call the GPT-4.1 completion model directly with the image as a vision input.

- **Pros:** Full control over the prompt; no analyzer lifecycle management
- **Cons:** No structured output schema enforcement; requires manual prompt engineering for each field; no CU pre-processing (OCR, layout detection) that improves image understanding quality; loses the CU SDK's retry and polling infrastructure

### Alternative 4: PDF Figure Cropping (Rejected)

Convert HTML → PDF, let CU detect figures via bounding polygons, crop them from the PDF, then re-analyze.

- **Cons:** Image quality loss from rasterization + re-cropping; complex bounding polygon math; three additional dependencies (`playwright`, `PyMuPDF`, `Pillow`). See [ARD-001](ARD-001-html-direct-processing.md).

## Consequences

### Positive

- **Domain-tuned descriptions** — the `Description` prompt focuses on UI-specific details (screens, navigation, annotations) rather than generic image captioning, producing richer text for vectorization
- **Structured metadata** — `UIElements` and `NavigationPath` fields are extracted as structured data, improving search relevance for queries about specific UI components or navigation steps
- **Original image quality** — source PNGs are sent directly to CU without any intermediate conversion or cropping. The analyzer receives the full-resolution image
- **Reusable analyzer** — the analyzer is defined once in the CU resource and reused for all images across all articles. The field schema can be updated without code changes
- **Consistent lifecycle** — managed alongside other Azure resources via `make azure-deploy` / `make azure-clean`, versioned in the repository

### Negative

- **Analyzer lifecycle dependency** — the analyzer must exist in the CU resource before the pipeline can process images. Managed by `make azure-deploy` but requires awareness during initial setup
- **CU ID restrictions** — Content Understanding forbids hyphens in analyzer IDs, so the ID is `kb_image_analyzer` (underscores) despite the JSON filename using hyphens
- **Single model dependency** — uses `gpt-4.1` as the completion model. Model changes require updating the analyzer definition and re-creating it in CU
- **Per-image API call** — each image requires a separate CU analysis call (create result → poll until complete). For articles with many images, this adds latency. Mitigated by the small image sizes (13–40 KB, fast processing)

## Evidence

From the [analyzer options research](../research/001-analyzer-options.md):

- `prebuilt-image` requires a custom analyzer with `fieldSchema` — not runnable standalone
- `prebuilt-documentSearch` on a single PNG works but produces generic captions
- Custom analyzers based on `prebuilt-image` support `method: "generate"` fields with domain-specific prompts
- The `gpt-4.1` completion model produces high-quality UI descriptions when guided by the field schema

From production output, a typical image description block:

```markdown
> **[Image: zzy1770827101433](images/zzy1770827101433.png)**
> Screenshot of the RUN dashboard showing the left navigation menu with
> Dashboard, Companies, Reports & tax forms, and Settings options.
```

## References

- [Analyzer Options Research](../research/001-analyzer-options.md)
- [Architecture Spec — Image Analysis Custom Analyzer](../specs/architecture.md)
- [Analyzer Definition](../../src/analyzers/definitions/kb-image-analyzer.json)
- [Spike: Content Understanding](../research/003-content-understanding.md)
