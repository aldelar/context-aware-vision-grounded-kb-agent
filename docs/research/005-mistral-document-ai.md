# Research: Mistral Document AI as Alternative to Azure Content Understanding

> **Date:** 2026-02-20
> **Status:** Complete (validated via [Spike 002](../spikes/002-mistral-document-ai.md))
> **Model reviewed:** `mistral-document-ai-2512` (Mistral OCR 3, released December 18, 2025)

---

## Context

Our current pipeline uses **Azure Content Understanding (CU)** for two tasks:

1. **HTML → markdown** — `prebuilt-documentSearch` extracts text, tables, headings, and a summary from the HTML article
2. **Image → description** — a custom `kb-image-analyzer` (based on `prebuilt-image`) extracts `Description`, `UIElements`, and `NavigationPath` from each article image individually

This research evaluates whether **Mistral Document AI** (`mistral-document-ai-2512`), now available in the Microsoft Foundry model catalog, could serve as an alternative or second option for the document processing stage.

### Key Requirements to Preserve

- **Image references in output markdown** — each chunk in AI Search carries `image_urls[]` pointing to source images in blob storage
- **Source images served to agent LLM** — the web app's vision middleware fetches actual images and injects them into the LLM conversation as base64; the agent reasons over the real images, not just text descriptions
- **Image descriptions for search** — AI-generated text descriptions are embedded alongside paragraphs to boost vector similarity for visual concepts during search
- **Hyperlink preservation** — original `<a href>` URLs from the HTML must survive in the output

> **Note on summary:** CU's `prebuilt-documentSearch` auto-generates a summary field that `fn-convert` writes to `summary.txt`. However, `fn-index` never reads or indexes this file — it only consumes `article.md`. Summary is therefore **not a pipeline requirement** and would simply be dropped with Mistral.

---

## 1. Model Overview

### What Is It

**Mistral Document AI** is Mistral AI's enterprise-grade document processing model, branded as "OCR 3" in Mistral's own documentation. On Azure, it's deployed as `mistral-document-ai-2512` (the `2512` suffix = December 2025 release). It is classified as an **Image-to-Text** model in the Foundry catalog.

Mistral OCR 3 replaces the now-retired `Mistral-OCR-2503` model (retirement date: January 30, 2026).

### Capabilities

| Capability | Details |
|---|---|
| **Input formats** | PDF, images (PNG, JPEG/JPG, AVIF, etc.), PPTX, DOCX |
| **Output format** | Markdown (with optional HTML tables), JSON |
| **HTML input** | **Not supported natively** — HTML files cannot be sent directly |
| **Max pages (Azure)** | 30 pages, max 30MB PDF |
| **Max pages (Mistral direct)** | Higher limits via direct API |
| **Languages** | English (primary), multilingual support |
| **Tool calling** | No |
| **Image extraction** | Yes — detects embedded images, returns bounding boxes and optional base64 |
| **Table extraction** | Yes — configurable as `null` (inline), `markdown`, or `html` (with colspan/rowspan) |
| **Hyperlink extraction** | Returned in response `hyperlinks` field, but **not injected into markdown**. PDFs don't carry `href` URLs from the original HTML — hyperlinks must be recovered separately from the source HTML. |
| **Header/footer extraction** | Yes (new in 2512) — via `extract_header` / `extract_footer` parameters |
| **Structured output** | Via "Annotations" feature — extract typed fields with JSON schema |
| **Batch processing** | Supported via Mistral Batch Inference service |
| **Pricing** | $2 / 1,000 pages ($1 / 1,000 pages with batch discount) |

### Key Strengths (from benchmarks)

- **74% overall win rate** over Mistral OCR 2 on forms, scanned documents, complex tables, and handwriting
- State-of-the-art accuracy against both enterprise and AI-native OCR solutions
- Robust handling of compression artifacts, skew, distortion, low DPI, background noise
- Reconstructs complex table structures with headers, merged cells, multi-row blocks, column hierarchies
- Outputs HTML table tags with `colspan`/`rowspan` to fully preserve layout

### API Endpoint

On Mistral's platform: `POST /v1/ocr` with the `mistralai` Python SDK.
On Azure Foundry: the endpoint path is **`/providers/mistral/azure/ocr`** on the `services.ai.azure.com` host (not the `/v1/ocr` path from the Mistral SDK). The host must be derived from the Cognitive Services endpoint by replacing `cognitiveservices.azure.com` with `services.ai.azure.com`.

> **Spike finding:** Neither the Azure docs nor the Mistral SDK document this path. It was discovered empirically after systematic testing of 50+ URL combinations.

---

## 2. API & SDK Details

### Python SDK Usage (Mistral Platform)

```python
from mistralai import Mistral

client = Mistral(api_key="...")

# OCR a PDF from URL
ocr_response = client.ocr.process(
    model="mistral-ocr-latest",  # or "mistral-ocr-2512"
    document={
        "type": "document_url",
        "document_url": "https://example.com/document.pdf"
    },
    table_format="html",          # "html" | "markdown" | None
    extract_header=True,          # new in 2512
    extract_footer=True,          # new in 2512
    include_image_base64=True     # return base64-encoded extracted images
)
```

### Azure Foundry Usage

On Azure, the model is deployed via Bicep (model format `Mistral AI`, SKU `GlobalStandard`) and called via REST. Auth uses **Entra ID bearer tokens** (not API keys) via `DefaultAzureCredential` with scope `https://cognitiveservices.azure.com/.default`:

```bash
# Derive the Foundry endpoint from the Cognitive Services endpoint
# e.g. https://ai-{project}-dev.cognitiveservices.azure.com/
#    → https://ai-{project}-dev.services.ai.azure.com/

TOKEN=$(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)

curl --request POST \
  --url https://<account>.services.ai.azure.com/providers/mistral/azure/ocr \
  --header "Authorization: Bearer $TOKEN" \
  --header 'Content-Type: application/json' \
  --data '{
    "model": "mistral-document-ai-2512",
    "document": {
      "type": "document_url",
      "document_url": "data:application/pdf;base64,<base64-encoded-pdf>"
    },
    "include_image_base64": true
  }'
```

> **Azure limitation:** The Azure deployment requires **base64-encoded data** for the `document_url` parameter. Direct HTTP URLs to PDFs are not supported on Azure — only the Mistral platform supports fetching from URLs.
>
> **Deployment note:** CLI deployment via `az cognitiveservices account deployment create` fails for Mistral models. Use **Bicep** with `format: 'Mistral AI'` (API version `2024-04-01-preview`) instead.

### Response Structure

```json
{
  "pages": [
    {
      "index": 0,
      "markdown": "# Document Title\n\nParagraph text...\n\n![img-0.jpeg](img-0.jpeg)\n\n...",
      "images": [
        {
          "id": "img-0.jpeg",
          "top_left_x": 100, "top_left_y": 200,
          "bottom_right_x": 500, "bottom_right_y": 600,
          "image_base64": "data:image/jpeg;base64,..."
        }
      ],
      "tables": [
        {
          "id": "tbl-0.html",
          "content": "<table>...</table>"
        }
      ],
      "hyperlinks": [...],
      "header": "Page Header Text",
      "footer": "Page 1 of 10",
      "dimensions": { "width": 612, "height": 792 }
    }
  ],
  "model": "mistral-ocr-2512",
  "usage_info": { ... }
}
```

**Critical observation for our use case:** When Mistral OCR detects images in a PDF, it:
1. Replaces them with **markdown placeholders** in the page text: `![img-0.jpeg](img-0.jpeg)`
2. Returns the **bounding box** coordinates for each image
3. Optionally returns the **base64-encoded image data** (via `include_image_base64=True`)

This means the output markdown has clear, positioned image references — exactly what we need for our chunking + indexing pipeline.

---

## 3. Document AI Services Stack

Mistral offers three services under the Document AI umbrella, all accessible via `client.ocr.process` / `/v1/ocr`:

| Service | Purpose | Relevance to Our Pipeline |
|---|---|---|
| **OCR Processor** | Extract text, tables, images, hyperlinks → markdown | Core replacement for CU's HTML text extraction |
| **Annotations** | Structured data extraction with JSON schema (fields, types) | Could replace CU's `fieldSchema` for custom field extraction |
| **Document QnA** | Combine OCR with LLM for question-answering over documents | Not directly relevant — our agent does this downstream |

---

## 4. Comparison: Azure Content Understanding vs Mistral Document AI

### Feature-by-Feature

| Feature | Azure Content Understanding | Mistral Document AI (OCR 3) |
|---|---|---|
| **HTML input (direct)** | ✅ Binary upload or URL | ❌ Not supported |
| **PDF input** | ✅ | ✅ (up to 30 pages / 30MB on Azure) |
| **Image input** | ✅ | ✅ (PNG, JPEG, AVIF, etc.) |
| **DOCX / PPTX input** | ❌ | ✅ |
| **Markdown output** | ✅ | ✅ |
| **Image detection in PDF** | ✅ (with figure description/analysis) | ✅ (with bounding boxes + base64 extraction) |
| **Image description generation** | ✅ Built-in (`enableFigureDescription`) | ❌ OCR only — no AI descriptions of images |
| **Hyperlink extraction** | ✅ (PDF only, not from HTML) | ✅ (when available in source) |
| **Table extraction** | ✅ (HTML/markdown format) | ✅ (null/markdown/HTML with colspan/rowspan) |
| **Summary generation** | ✅ (`prebuilt-documentSearch`) | ❌ Not built-in |
| **Custom field extraction** | ✅ (`fieldSchema`) | ✅ (Annotations with JSON schema) |
| **Confidence scores** | ✅ | ❌ |
| **Header/footer separation** | ❌ | ✅ (new in 2512) |
| **Batch processing** | Via async API | ✅ Native batch support (50% discount) |
| **Pricing (text extraction)** | Per-page pricing (varies by analyzer) | $2 / 1,000 pages ($1 batch) |
| **Azure managed identity** | ✅ Native | ✅ Microsoft Entra ID / managed identity via `DefaultAzureCredential` (`Cognitive Services User` role) |
| **Self-hosting** | ❌ | ✅ Available for enterprise |

### Key Differences for Our Pipeline

1. **No native HTML input** — Mistral cannot process HTML directly. We'd need to render HTML → PDF first (bringing back the Playwright dependency we dropped in ARD-001).

2. **No AI image descriptions** — Mistral OCR extracts images from PDFs and returns them as base64 blobs with bounding boxes, but it does NOT generate natural-language descriptions. For our pipeline, we still need GPT-4.1 (vision) to describe each image.

3. **Image extraction is better scoped** — Mistral explicitly returns each detected image as a separate entry with coordinates and base64, making it easy to map images back to their position in the markdown. CU requires parsing `D(page,x1,y1,...,x8,y8)` bounding polygon format and cropping via PyMuPDF.

4. **No summary field** — CU's `prebuilt-documentSearch` generates a summary automatically. With Mistral, there is no built-in equivalent. However, this is **not a gap in practice** — our `fn-index` pipeline never reads or indexes the summary; it only consumes `article.md`. The `summary.txt` file is a dead artifact. No replacement needed.

5. **Hyperlinks NOT embedded in markdown** — Mistral returns a `hyperlinks` field in the response, but hyperlinks from the original HTML are **not preserved through PDF rendering** — PDFs don't carry `href` URLs. In practice, hyperlinks must be recovered by scanning the source HTML for `<a>` tags and re-injecting them into the OCR markdown via text matching. This is the same approach used by the CU pipeline.

---

## 5. Proposed Alternative Architecture: HTML → PDF → Mistral OCR

### Pipeline Flow

Since Mistral Document AI does not accept HTML, the pipeline would be:

```
kb/staging/<article>/
  index.html + images/*.image
  │
  ▼  Step 1: Render HTML → PDF (Playwright headless Chromium)
  │  → article.pdf (images rendered inline)
  │
  ▼  Step 2: PDF → Mistral OCR (mistral-document-ai-2512)
  │  → Structured markdown with image placeholders
  │  → Extracted images as base64 (from PDF rendering)
  │  → Hyperlinks, tables, headers/footers
  │
  ▼  Step 3: Map Mistral-extracted images to original source images
  │  • Use HTML marker injection strategy (see §5a below)
  │  • Markers in OCR output identify each source filename
  │  • Goal: reference ORIGINAL source images (higher quality than PDF-rendered)
  │
  ▼  Step 4: Generate image descriptions (GPT-4.1)
  │  • Send each original source image to GPT-4.1 (vision)
  │  • Prompt for Description, UIElements, NavigationPath
  │  • This replaces CU's custom kb-image-analyzer
  │
  ▼  Step 5: Merge & Reconstruct
  │  • Replace image placeholders with description blocks + image links
  │  • Inject hyperlinks if not already in markdown
  │  • Output: article.md + images/*.png
  │
kb/serving/<article>/
  article.md + images/*.png
  │
  ▼  Existing fn-index pipeline (unchanged)
  │  Chunk by headings → embed → push to AI Search
```

### What This Preserves

- ✅ **Source images in blob storage** — original images are copied to serving layer, referenced by markdown
- ✅ **Image URLs in search chunks** — `image_urls[]` field populated per chunk
- ✅ **Vision middleware works** — agent LLM receives actual source images for visual reasoning
- ✅ **Image descriptions for search** — generated by GPT-4.1 in Step 4, embedded in chunk text for vector similarity
- ✅ **Hyperlinks** — extracted by Mistral from the PDF rendering
- ~~Summary~~ — not needed; `fn-index` never uses it

### 5a. Image-to-Source Mapping Strategy: HTML Marker Injection

**The problem:** Mistral OCR extracts images from the rendered PDF and returns them as `img-0.jpeg`, `img-1.jpeg`, etc. We need to map each extracted image back to the original source file (e.g., `images/architecture-diagram.png`) so we can:
- Reference original high-quality images in the article markdown
- Serve them from blob storage URLs via `image_urls[]` in search chunks
- Feed them to the agent LLM for visual reasoning (vision middleware)

We want a strategy that is **simple and deterministic** — no complex image comparison or LLM processing.

#### Implemented: Replace `<img>` Tags with Visible Text Markers

Before rendering HTML → PDF with Playwright, pre-process the HTML to **replace** each `<img>` tag (and any wrapping `<a>` lightbox link) with a visible text marker `[[IMG:<filename>]]`. The actual image is removed from the PDF entirely — we don't need Mistral to detect it since we have the source files in the staging directory.

The marker is rendered in normal-sized text (14px) so OCR reliably preserves it.

**Before injection:**
```html
<p>The architecture is shown below:</p>
<a href="images/architecture-diagram.png"><img src="images/architecture-diagram.png" alt="Architecture"></a>
<p>As you can see, the pipeline has three stages.</p>
```

**After injection:**
```html
<p>The architecture is shown below:</p>
<p style="margin:0.4em 0;font-size:14px;">[[IMG:architecture-diagram.png]]</p>
<p>As you can see, the pipeline has three stages.</p>
```

When Playwright renders this to PDF and Mistral OCR processes it, the output markdown will contain:
```markdown
The architecture is shown below:

[[IMG:architecture-diagram.png]]

As you can see, the pipeline has three stages.
```

**Mapping is now trivial:** scan the markdown for `[[IMG:<filename>]]` markers. Each marker self-identifies its source file. No positional correlation with Mistral's `img-N.jpeg` references is needed — the markers **are** the image placeholders.

> **Spike finding:** The original research proposed 6px gray `⟦IMG:⟧` markers (using Unicode mathematical angle brackets) placed *before* the `<img>` tag, relying on OCR to read the tiny text and then correlating with the next `img-N.jpeg` placeholder. This failed — 6px text was too small for OCR to reliably preserve. Increasing to 14px and **replacing** the image entirely proved far more robust: the markers always survive OCR, and the approach handles edge cases like the same image appearing multiple times in a document (each occurrence gets its own marker).

#### Implementation

```python
import re
from pathlib import Path


def _replace_images_with_markers(html: str) -> str:
    """Replace each <img> (and its wrapping <a> if present) with a
    visible [[IMG:<filename>]] text marker."""

    def _img_to_marker(match: re.Match) -> str:
        tag = match.group(0)
        src_match = re.search(r'src=["\']([^"\']+)["\']', tag)
        if not src_match:
            return tag
        filename = Path(src_match.group(1)).name
        return (
            f'<p style="margin:0.4em 0;font-size:14px;">'
            f'[[IMG:{filename}]]</p>'
        )

    # First, unwrap <a> tags that wrap <img> tags (lightbox links)
    html = re.sub(
        r'<a\b[^>]*>\s*(<img\b[^>]*>)\s*</a>',
        r'\1',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Then replace each <img> with a marker
    return re.sub(r'<img\b[^>]*>', _img_to_marker, html, flags=re.IGNORECASE)


def find_image_markers(pages_markdown: list[str]) -> tuple[str, list[str]]:
    """Scan OCR markdown for [[IMG:...]] markers and return source filenames."""
    import re
    MARKER_RE = re.compile(r"\[\[IMG:([^\]]+?)\]\]")
    full_markdown = "\n\n".join(pages_markdown)
    source_filenames = [m.group(1).strip() for m in MARKER_RE.finditer(full_markdown)]
    return full_markdown, source_filenames
```

#### Why This Works

| Property | Assessment |
|---|---|
| **OCR readability** | 14px text in a normal `<p>` — OCR reads it perfectly every time |
| **Deterministic** | Each marker carries its own filename — no positional correlation needed |
| **Handles duplicates** | Same image used twice in a document → two markers, both found |
| **No image processing** | No perceptual hashing, pixel comparison, or embedding similarity needed |
| **Robust to quality loss** | Images aren't even in the PDF — no quality concerns |
| **Low complexity** | ~30 lines of Python for injection + scanning |
| **Marker format** | `[[IMG:...]]` uses ASCII brackets — simple, unlikely to appear in source HTML |

#### Alternative Strategies Considered (and Tested)

| Strategy | Pros | Cons | Verdict |
|---|---|---|---|
| **6px gray markers before `<img>`** (original proposal) | Minimal visual impact | OCR failed to read 6px text — markers silently dropped | **Rejected (tested)** |
| **Positional matching** (img-0 = first `<img>`, etc.) | Works when marker OCR fails | Fails when same image appears twice; breaks if OCR merges/drops images | **Rejected (tested)** — worked for 2 of 3 articles but failed for duplicate-image edge case |
| **14px markers replacing `<img>`** (final approach) | OCR reads perfectly; handles duplicates; simple | Images not in PDF (not needed — we use source files) | **Implemented ✅** |
| **Perceptual hashing** (pHash/dHash comparing extracted vs source) | Handles reordering | PDF rendering degrades quality; needs `imagehash` + Pillow deps; may have false positives | Over-engineered |
| **Visual embedding similarity** (encode both images with a vision model) | Robust matching | Expensive (LLM call per image pair); overkill | Rejected |
| **Alt-text enrichment** (inject filename into `alt` attribute) | No visual impact | OCR may or may not include alt text in output; unreliable | Rejected |
| **Hidden text** (`font-size: 0` or `display: none`) | No visual impact | OCR does not detect invisible text; CSS hidden text ignored by renderers | Rejected |

#### Validation Plan for Spike

1. Inject markers into a sample HTML article
2. Render to PDF with Playwright, visually confirm markers appear near images
3. Process PDF with Mistral OCR, confirm markers appear in output markdown
4. Run `map_images_from_markdown()` and verify correct source file mapping
5. Edge cases to test: adjacent images (no text between them), images inside tables, images in list items

### Trade-offs vs Current CU Pipeline

| Aspect | Current (CU) | Proposed (Mistral + LLM) |
|---|---|---|
| **HTML → PDF rendering** | ❌ Dropped (ARD-001) | ✅ Required again |
| **Image extraction quality** | CU returns bounding polygons, requires PyMuPDF cropping | Mistral returns clean base64 images directly |
| **Image descriptions** | Custom CU analyzer (`kb-image-analyzer`) | GPT-4.1 vision call |
| **Summary** | Built-in to `prebuilt-documentSearch` | Not needed (`fn-index` never indexes it) |
| **Azure managed identity** | ✅ Native RBAC | ✅ Microsoft Entra ID / managed identity via `DefaultAzureCredential` |
| **Dependencies** | `azure-ai-contentunderstanding` SDK | `mistralai` SDK (or REST) + Playwright |
| **API calls per article** | 1 (HTML) + N (images) = N+1 CU calls | 1 (PDF→Mistral) + N (image→GPT-4.1) |
| **Cost** | ~$0.033/article (see §6) | ~$0.026/article (see §6) |
| **Vendor lock-in** | Azure-only | Mistral available on Azure, self-hosted, or direct API |
| **Image mapping** | Parse HTML DOM for `<img>` positions | Mistral provides image positions in markdown via placeholders |

---

## 6. Cost Comparison (Estimated)

### What Is a "Page" — Normalization

CU and Mistral count **pages** differently, which matters for cost comparison:

| | Azure Content Understanding | Mistral Document AI |
|---|---|---|
| **HTML input** | Entire document = **1 page** (no native page concept) | N/A — doesn't accept HTML |
| **PDF input** | Each PDF page = 1 page | Each PDF page = 1 page |
| **Image input** | 1 image = 1 image (separate pricing tier) | 1 image = 1 page |

> **Key insight:** CU bills a long HTML article as **1 page** regardless of content length ([source](https://learn.microsoft.com/azure/ai-services/content-understanding/document/elements#document-elements): *"For file formats like HTML or Word documents, which lack a native page concept without rendering, the entire main content is treated as a single page."*). Mistral, which processes the **PDF-rendered** version, bills per rendered page — a typical KB article renders to roughly **3–5 PDF pages** via Playwright.
>
> This means CU's content extraction has a structural advantage for long HTML documents: 1 page flat-rate vs N pages in the Mistral pipeline. But Mistral's per-page rate ($0.002) is much lower than CU's ($0.005), so the difference is modest.

### Pricing Inputs (GPT-4.1 Global Deployment, East US)

| Rate Card | Price |
|---|---|
| CU content extraction (documents) | $5.00 / 1,000 pages |
| CU content extraction (images) | $0.00 (no charge) |
| CU contextualization | $1.00 / 1M tokens (~1,000 tokens/page or image) |
| CU figure analysis | ~1,000 input + 200 output tokens per figure |
| CU image analyzer fields | ~1,000 input + 300 output tokens per image (est.) |
| GPT-4.1 input tokens | $2.00 / 1M tokens |
| GPT-4.1 output tokens | $8.00 / 1M tokens |
| Mistral OCR (standard) | $2.00 / 1,000 pages ($0.002/page) |
| Mistral OCR (batch) | $1.00 / 1,000 pages ($0.001/page) |

> Sources: [CU pricing explainer](https://learn.microsoft.com/azure/ai-services/content-understanding/pricing-explainer), [Azure OpenAI pricing](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/). All prices are illustrative and subject to change.

### Per Article Breakdown (1 article, 3 images, ~5 rendered PDF pages)

#### CU Pipeline

Our pipeline makes **1 + N** CU calls: `prebuilt-documentSearch` for text (which includes built-in figure analysis), plus `kb-image-analyzer` for each image.

| Component | Calculation | Cost |
|---|---|---|
| **documentSearch — content extraction** | 1 page × $5.00/1,000 | $0.0050 |
| **documentSearch — contextualization** | 1,000 tokens × $1.00/1M | $0.0010 |
| **documentSearch — figure analysis (input)** | 3 figs × 1,000 tokens × $2.00/1M | $0.0060 |
| **documentSearch — figure analysis (output)** | 3 figs × 200 tokens × $8.00/1M | $0.0048 |
| **kb-image-analyzer — content extraction** | 3 images, no charge | $0.0000 |
| **kb-image-analyzer — contextualization** | 3 × 1,000 tokens × $1.00/1M | $0.0030 |
| **kb-image-analyzer — field extraction (input)** | 3 × 1,000 tokens × $2.00/1M | $0.0060 |
| **kb-image-analyzer — field extraction (output)** | 3 × 300 tokens × $8.00/1M | $0.0072 |
| **CU Total** | | **~$0.033** |

#### Mistral + GPT-4.1 Pipeline

| Component | Calculation | Cost |
|---|---|---|
| **PDF rendering (Playwright)** | Compute only | $0.0000 |
| **Mistral OCR** | 5 PDF pages × $2.00/1,000 | $0.0100 |
| **GPT-4.1 image descriptions (input)** | 3 images × ~1,500 tokens × $2.00/1M | $0.0090 |
| **GPT-4.1 image descriptions (output)** | 3 images × ~300 tokens × $8.00/1M | $0.0072 |
| **Mistral + GPT-4.1 Total** | | **~$0.026** |

### At Scale

| Scale | CU Pipeline | Mistral + GPT-4.1 | Mistral + GPT-4.1 (batch OCR) |
|---|---|---|---|
| 1 article | ~$0.033 | ~$0.026 | ~$0.021 |
| 100 articles | ~$3.30 | ~$2.60 | ~$2.10 |
| 1,000 articles | ~$33 | ~$26 | ~$21 |

### Cost Analysis Notes

1. **Costs are comparable** — In the per-article range, both pipelines cost ~$0.02–0.04. Neither has a dramatic advantage.
2. **CU's main cost drivers** are figure analysis tokens and image analyzer tokens (GPT-4.1 charges via Foundry deployment), not the CU content extraction per-page fee itself.
3. **Mistral's main cost driver** is also the GPT-4.1 image description calls. Mistral OCR's own fee is negligible at $0.002/page.
4. **Both pipelines pay GPT-4.1 for image understanding** — CU uses it internally for figure analysis and custom field extraction; Mistral pipeline calls it directly. The token costs are similar.
5. **Page-count sensitivity** — If an article renders to >5 PDF pages, Mistral's OCR cost rises proportionally, while CU stays flat. For articles rendering to 10+ pages, CU's extraction cost advantage grows, but the GPT-4.1 image costs (which are page-count independent) still dominate.
6. **Batch discount** — Mistral offers 50% off for batch processing ($1/1,000 pages), which could matter for bulk KB ingestion.

---

## 7. Can Mistral Process HTML with Embedded Images Directly?

**Short answer: No.**

Mistral Document AI / OCR 3 does **not** accept HTML as input. Supported input formats are:
- **PDF** (primary document format)
- **Images** (PNG, JPEG, AVIF, etc.)
- **DOCX, PPTX** (office documents)

### Implications

We cannot feed our raw HTML files (even with base64-embedded images) to Mistral. The two viable approaches are:

1. **HTML → PDF → Mistral OCR** (recommended — preserves images inline in the rendered PDF)
2. **Python HTML parser for text + Mistral/LLM for images** (alternative — avoids PDF step but loses Mistral's OCR advantage for text)

Option 1 is preferred because:
- Mistral OCR excels at PDF processing and will extract the rendered images automatically
- Hyperlinks survive in the PDF rendering and are extracted by Mistral
- Tables rendered by the browser are captured faithfully
- We get a single API call for the entire document's text + image positions

The **two-step approach** (text separately, images separately) would only make sense if we wanted to avoid the Playwright/PDF dependency entirely — but that was our architecture before (Option 1 in `004-architecture-proposal.md`), and CU handles HTML text extraction better than a Python library in that scenario.

---

## 8. Open Questions — Answered by Spike

All questions below were answered empirically by [Spike 002](../spikes/002-mistral-document-ai.md).

1. **PDF image extraction quality** — **Not applicable.** Our final implementation removes images from the PDF entirely and replaces them with text markers. Source images are used directly from the staging directory, so there is zero quality loss.

2. **Image-to-source mapping** — **Works reliably.** The initial 6px gray `⟦IMG:⟧` marker approach failed (OCR dropped the tiny text). The final solution — replacing `<img>` tags with 14px `[[IMG:filename]]` markers — works perfectly. Markers survive OCR 100% of the time across all test articles, including edge cases where the same image appears multiple times.

3. **Hyperlink fidelity** — **Hyperlinks do NOT survive PDF rendering.** PDFs don't carry `href` URLs from the original HTML. Mistral's `hyperlinks` field returns limited data. Solution: extract `<a>` tags from the source HTML and re-inject links into the OCR markdown via word-boundary text matching. This matches CU's behavior — both pipelines recover links the same way.

4. **Azure endpoint limitations** — **30 pages / 30MB is not a concern.** Our KB articles render to 4–9 PDF pages. Well within limits.

5. **Markdown quality comparison** — **Comparable.** Mistral OCR produces clean markdown with good heading hierarchy and table formatting. Character counts are within ~3% of CU output. Minor differences in whitespace and line breaks, but semantically equivalent.

6. **LLM image description quality** — **Comparable.** GPT-4.1 vision produces descriptions following the same `Description`, `UIElements`, `NavigationPath` schema as CU's `kb-image-analyzer`. Quality is at least as good since both use GPT-4.1 under the hood.

7. **Azure API compatibility** — **Partially.** The `include_image_base64` parameter works. `table_format`, `extract_header`, and `extract_footer` were not tested (not needed for our pipeline). The key discovery was the non-obvious endpoint path: `/providers/mistral/azure/ocr` on the `services.ai.azure.com` host.

8. **End-to-end latency** — **Comparable.** Processing 3 articles takes ~45 seconds total (Playwright render + OCR + GPT-4.1 descriptions). The OCR step itself is fast (~4s per article). GPT-4.1 image description calls dominate latency in both pipelines.

---

## 9. Conclusion

### Verdict: Spike Successful — Viable LLM-Centric Alternative to CU

Mistral Document AI is a **proven alternative** to Azure Content Understanding for our KB article conversion pipeline. [Spike 002](../spikes/002-mistral-document-ai.md) demonstrated a fully working 5-step pipeline that produces output matching CU's quality:

| Metric | CU Pipeline | Mistral Pipeline |
|---|---|---|
| **Images detected** | 2, 2, 2 | 2, 2, 2 |
| **Hyperlinks recovered** | 30, 8, 82 | 30, 8, 82 |
| **Markdown quality** | Baseline | Comparable (~3% character count variance) |
| **Image descriptions** | GPT-4.1 via CU analyzer | GPT-4.1 direct — same model |
| **Output format** | `article.md` + `images/` | Identical structure |

### Key Learnings

1. **Marker-based image mapping works** — Replacing `<img>` tags with visible `[[IMG:filename]]` text markers is simple, deterministic, and handles all edge cases including duplicate images.

2. **Hyperlinks must be recovered from HTML** — Neither CU nor Mistral reliably extracts hyperlinks from HTML→PDF rendering. Both pipelines need a post-processing step that scans the source HTML for `<a>` tags and re-injects links via text matching.

3. **Azure deployment is non-trivial** — CLI deployment fails for Mistral models; Bicep with `format: 'Mistral AI'` is required. The OCR endpoint path (`/providers/mistral/azure/ocr` on `services.ai.azure.com`) is undocumented and was discovered empirically.

4. **No SDK needed** — Raw REST calls via `httpx` with Entra ID bearer tokens work well. The `mistralai` Python SDK is unnecessary on Azure.

5. **Playwright dependency returns** — The pipeline requires HTML→PDF rendering, reintroducing the Playwright/Chromium dependency that ARD-001 eliminated. This is acceptable for a spike but should be weighed for production adoption.

### When to Choose This Pipeline

- **LLM-centric architecture** — When you want the document processing pipeline to be fully LLM-driven rather than dependent on a single Azure service
- **Multi-cloud flexibility** — Mistral is available on Azure, Mistral's own platform, and self-hosted
- **DOCX/PPTX support** — If KB sources expand beyond HTML to include Office formats that CU doesn't support
- **Cost optimization at scale** — Mistral batch pricing ($1/1,000 pages) may be advantageous for large-scale ingestion

### When to Stay with CU

- **Native HTML support** — CU processes HTML directly without the PDF rendering step, which is simpler
- **Integrated image analysis** — CU's `kb-image-analyzer` is a single service call vs. separate GPT-4.1 calls
- **No Playwright dependency** — CU avoids the headless browser requirement in production

---

## References

- [Mistral OCR 3 announcement](https://mistral.ai/news/mistral-ocr-3)
- [Mistral Document AI docs](https://docs.mistral.ai/capabilities/document_ai/basic_ocr)
- [Mistral OCR 3 model card](https://docs.mistral.ai/models/ocr-3-25-12)
- [Azure Foundry — Mistral models sold directly by Azure](https://learn.microsoft.com/azure/ai-foundry/foundry-models/concepts/models-sold-directly-by-azure?view=foundry-classic&pivots=azure-direct-others)
- [Azure — How to use image-to-text models](https://learn.microsoft.com/azure/ai-foundry/how-to/use-image-models?view=foundry-classic)
- [Azure — Choosing the right tool for document processing](https://learn.microsoft.com/azure/ai-services/content-understanding/choosing-right-ai-tool)
- [Mistral model deprecation — OCR 2503 → Document AI 2505/2512](https://learn.microsoft.com/azure/ai-foundry/concepts/model-lifecycle-retirement?view=foundry-classic)
- [Our CU research — architecture-proposal.md](004-architecture-proposal.md)
- [Our CU research — architecture-research.md](002-architecture-research.md)
- [Our CU research — analyzer-options.md](001-analyzer-options.md)
