# Azure Content Understanding — Analyzer Options for HTML/Image Processing

> Research notes for the Content Understanding spike.
> Based on the [GA API (2025-11-01)](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/) documentation reviewed 2026-02-12.

---

## Current State

We're using `prebuilt-layout` with `begin_analyze_binary(content_type="text/html")` to convert HTML KB articles to markdown. It works for text, headings, paragraphs, and tables — but **images are completely dropped** (no URLs, no alt text, no descriptions in the output).

---

## 1. Figure Detection & Description

Content Understanding has two config flags that control image/figure handling. Both are **off by default**:

| Config Option              | Default | Effect                                                                                     |
| -------------------------- | ------- | ------------------------------------------------------------------------------------------ |
| `enableFigureDescription`  | `false` | Uses the completion model (e.g. gpt-4.1) to generate natural-language descriptions for figures, diagrams, images, and illustrations |
| `enableFigureAnalysis`     | `false` | Deeper analysis — extracts chart data as Chart.js JSON, converts diagrams to Mermaid.js syntax, classifies figure types |

### Impact on Markdown Output

| Configuration                                         | Markdown                                                                                      |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Neither flag                                          | `![detected text](figures/1.1)`                                                               |
| `enableFigureDescription: true`                       | `![detected text](figures/1.1 "This is a generated image description.")`                      |
| Both flags                                            | Same as above **plus** a Chart.js or Mermaid code block appended after the image               |
| `enableFigureAnalysis` only                           | `![detected text](figures/1.1)` followed by chart/diagram code block                          |

### Impact on JSON Response

When enabled, the `figures` array in the response gets richer:

```json
{
  "figures": [{
    "description": "This figure illustrates the sales revenue over 2023.",
    "kind": "chart",
    "content": {
      "type": "line",
      "data": {
        "labels": ["January", "February", "March"],
        "datasets": [{ "label": "A", "data": [93, -29, -17] }]
      }
    }
  }]
}
```

### Supported Figure Types (enableFigureAnalysis)

| Type             | Output Format |
| ---------------- | ------------- |
| Bar chart        | Chart.js      |
| Line chart       | Chart.js      |
| Pie chart        | Chart.js      |
| Radar chart      | Chart.js      |
| Scatter chart    | Chart.js      |
| Bubble chart     | Chart.js      |
| Quadrant chart   | Chart.js      |
| Mixed chart      | Mermaid.js    |
| Flow chart       | Mermaid.js    |
| Sequence diagram | Mermaid.js    |
| Gantt chart      | Mermaid.js    |

### Important Limitation

The `prebuilt-documentSearch` docs state: **"Figure analysis is only supported for PDF and image file formats."** This means HTML input may not benefit from figure detection/description even with these flags enabled. This is a key hypothesis to test.

---

## 2. Prebuilt Analyzer Comparison

All content extraction analyzers are built on top of `prebuilt-document`.

| Capability                 | `prebuilt-read` | `prebuilt-layout` | `prebuilt-document` (base) | `prebuilt-documentSearch` (RAG) |
| -------------------------- | :-------------: | :---------------: | :-----------------------: | :----------------------------: |
| OCR / text extraction      | ✅              | ✅                | ✅                        | ✅                             |
| Layout (paragraphs, etc.)  | —               | ✅                | ✅                        | ✅                             |
| Tables                     | —               | ✅                | ✅                        | ✅                             |
| Figure detection           | —               | ✅ (PDF only)     | ✅                        | ✅                             |
| Figure description         | —               | —                 | Config flag               | **On by default**              |
| Figure analysis (→ data)   | —               | —                 | Config flag               | **On by default**              |
| Hyperlinks                 | —               | ✅                | ✅                        | ✅                             |
| Annotations                | —               | ✅ (digital PDF)  | Config flag               | ✅                             |
| Auto-generated summary     | —               | —                 | —                         | ✅                             |
| Custom field extraction    | —               | —                 | Via `fieldSchema`         | Via `fieldSchema`              |
| Requires generative model  | No              | No                | When figure flags on      | **Always**                     |

### Key Takeaway

- `prebuilt-layout` (our current choice) detects figures in PDFs but **does not** describe or analyze them, and has no generative model requirement.
- `prebuilt-document` is the **base analyzer** for creating custom analyzers with `enableFigureDescription` / `enableFigureAnalysis`.
- `prebuilt-documentSearch` is the RAG-optimized analyzer with figure analysis on by default — but it returned 0 contents for our HTML binary upload in earlier tests.

---

## 3. URL-Based Input

Instead of reading an HTML file into bytes and calling `begin_analyze_binary()`, the API supports passing a URL:

### REST API

```http
POST /analyzers/{analyzerId}:analyze
Content-Type: application/json

{
  "inputs": [{ "url": "https://example.com/article.html" }]
}
```

### Python SDK

The `AnalyzeInput` model has both `data` and `url` properties:

```python
from azure.ai.contentunderstanding.models import AnalyzeInput

result = client.begin_analyze(
    "my-analyzer",
    input=AnalyzeInput(url="https://learn.microsoft.com/en-us/.../overview")
)
```

### Constraints

| Constraint          | Value                                |
| ------------------- | ------------------------------------ |
| Max URL length      | 8,192 characters                     |
| HTML file size      | ≤ 1 MB                              |
| Accessibility       | URL must be publicly accessible or use Azure Blob Storage with SAS token |
| Video (URL vs binary) | URL: 4 GB / 2 hrs — binary: 200 MB / 30 min |

### Why This Matters

When CU fetches the document from a URL, it **may** resolve `<img src="...">` references by following the image URLs — potentially solving the "images dropped" problem we see with binary upload of local HTML. This is a hypothesis worth testing.

---

## 4. Custom Analyzer Creation

You can create a custom analyzer by extending the `prebuilt-document` base with your own config and optional field schema. This is the mechanism to enable figure flags.

### Definition (JSON)

```json
{
  "description": "KB article analyzer with figure descriptions",
  "baseAnalyzerId": "prebuilt-document",
  "models": {
    "completion": "gpt-4.1",
    "embedding": "text-embedding-3-small"
  },
  "config": {
    "enableFigureDescription": true,
    "enableFigureAnalysis": true,
    "enableLayout": true,
    "enableOcr": true,
    "returnDetails": true
  },
  "fieldSchema": { "fields": {} }
}
```

### Lifecycle

1. **Create**: `PUT /analyzers/{analyzerId}` with the JSON definition → returns `201 Created` with an `Operation-Location` header
2. **Poll**: `GET` the operation URL until `status: "succeeded"`
3. **Use**: `POST /analyzers/{analyzerId}:analyze` with input (URL or binary)
4. **Poll result**: `GET /analyzerResults/{resultId}` until `status: "Succeeded"`

### Python SDK Equivalent

```python
# Create
client.create_analyzer("my-kb-analyzer", body=analyzer_definition)

# Analyze
result = client.begin_analyze("my-kb-analyzer", input=AnalyzeInput(url="..."))
analyze_result = result.result()
```

### All Document Analyzer Config Options

For reference, document analyzers (`baseAnalyzerId: "prebuilt-document"`) support:

| Option                               | Default     | Purpose                                          |
| ------------------------------------ | ----------- | ------------------------------------------------ |
| `returnDetails`                      | `false`     | Include confidence scores, bounding boxes, spans  |
| `enableOcr`                          | `true`      | OCR for scanned/image-based content               |
| `enableLayout`                       | `true`      | Paragraphs, lines, sections, reading order        |
| `enableFormula`                      | `true`      | LaTeX formula detection                           |
| `enableBarcode`                      | `true`      | Barcode/QR code detection                         |
| `tableFormat`                        | `"html"`    | Table output format: `"html"` or `"markdown"`     |
| `chartFormat`                        | `"chartjs"` | Chart data format (Chart.js)                      |
| `enableFigureDescription`            | `false`     | Generate NL descriptions for figures              |
| `enableFigureAnalysis`               | `false`     | Deep figure analysis (chart data, diagrams)       |
| `enableAnnotations`                  | —           | Extract highlights, underlines, etc. (PDF only)   |
| `annotationFormat`                   | `"markdown"`| Annotation output format                          |
| `enableSegment`                      | `false`     | Split content by category                         |
| `segmentPerPage`                     | `false`     | Force one segment per page                        |
| `estimateFieldSourceAndConfidence`   | `false`     | Source location + confidence for extracted fields  |
| `contentCategories`                  | —           | Classification categories + routing               |
| `omitContent`                        | `false`     | Exclude original content from response            |

---

## 5. Proposals (Testing Order)

### Proposal A — URL-based `prebuilt-documentSearch`

**Quickest test.** Pass the live article URL to the RAG analyzer:

```python
result = client.begin_analyze(
    "prebuilt-documentSearch",
    input=AnalyzeInput(url="https://learn.microsoft.com/.../overview")
)
```

- Figure description/analysis is on by default
- When CU fetches the URL itself, it may resolve `<img>` tags → images get processed
- Also auto-generates a summary
- **Risk**: `prebuilt-documentSearch` returned 0 contents with binary upload previously — URL input may behave differently

### Proposal B — Custom Analyzer with Figure Flags + URL Input

More control. Create a custom analyzer extending `prebuilt-document`:

```json
{
  "baseAnalyzerId": "prebuilt-document",
  "models": { "completion": "gpt-4.1", "embedding": "text-embedding-3-small" },
  "config": {
    "enableFigureDescription": true,
    "enableFigureAnalysis": true
  },
  "fieldSchema": { "fields": {} }
}
```

Then call it with a URL. If that works, optionally add custom `fieldSchema` fields to extract structured data (e.g. article title, category, key topics).

- **Risk**: Figure analysis may still only work for PDF/image inputs

### Proposal C — HTML → PDF Conversion First

Render the HTML article to PDF using a headless browser (Playwright), then process the PDF through CU with figure flags:

- PDFs have **first-class** figure detection support (explicitly confirmed in docs)
- The rendered PDF includes images inline → figures become detectable
- **Pro**: Sidesteps all HTML-specific limitations
- **Con**: Adds a rendering dependency, may lose HTML-specific semantics (links, code blocks)

### Proposal D — Hybrid Pipeline

If figure analysis definitively doesn't work for HTML:

1. Keep `prebuilt-layout` for text/structure extraction (reliable)
2. Parse HTML separately to extract `<img>` tags + URLs
3. Process each image individually through `prebuilt-image` or `prebuilt-imageSearch`
4. Stitch image descriptions back into the markdown at correct positions

- **Pro**: Most reliable, full control
- **Con**: Most complex, multiple API calls, position management

---

## 6. Supported Models

| Category        | Model                    |
| --------------- | ------------------------ |
| Chat Completion | gpt-4.1                 |
| Chat Completion | gpt-4.1-mini            |
| Chat Completion | gpt-4.1-nano            |
| Chat Completion | gpt-4o                  |
| Chat Completion | gpt-4o-mini             |
| Embeddings      | text-embedding-3-large   |
| Embeddings      | text-embedding-3-small   |
| Embeddings      | text-embedding-ada-002   |

Our current deployments: `gpt-4.1`, `gpt-4.1-mini`, `text-embedding-3-small` (all Standard SKU).

---

## 7. Input File Limits (HTML Context)

| Format          | Max Size | Max Content   |
| --------------- | -------- | ------------- |
| HTML, MD, RTF   | 1 MB     | 1M characters |
| PDF, TIFF, images | 200 MB | 300 pages     |
| DOCX, XLSX, PPTX | 200 MB | 1M characters |

---

## References

- [Prebuilt analyzers](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/prebuilt-analyzers)
- [Analyzer reference (config options)](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/analyzer-reference)
- [Document elements (figures, hyperlinks, etc.)](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/document/elements)
- [Markdown representation](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/document/markdown)
- [Create custom analyzer tutorial](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/tutorial/create-custom-analyzer)
- [REST API quickstart](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/quickstart/use-rest-api)
- [Service limits](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/service-limits)
- [Analyzer templates (sample code)](https://github.com/Azure-Samples/azure-ai-content-understanding-python/tree/main/analyzer_templates)
