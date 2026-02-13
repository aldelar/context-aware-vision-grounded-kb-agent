# Architecture Proposal: HTML Articles → Searchable Markdown + Images via Azure Content Understanding

> **Date:** 2026-02-13
> **Status:** Draft v3 — revised to explore dropping the PDF conversion step

---

## Goal

Transform HTML KB articles (with embedded images) into:
1. **`article.md`** — a markdown file with hyperlinks preserved, images replaced by AI-generated text descriptions inline, and each image description linking to the actual image file in the article folder.
2. **`images/`** — the original image files from the article folder, referenced by the markdown (no PDF cropping needed).

End-state: vectorize into Azure AI Search so that each chunk has a text embedding (from the description) **and** stored links to 0–N related images (in Azure Blob Storage), enabling an agent to return both the answer text and the source images.

---

## Empirical Findings (2026-02-13)

### Experiment 1: HTML with Base64-Embedded Images → CU

**Hypothesis:** If we encode the article images as base64 data URIs (`data:image/png;base64,...`) directly in the HTML `<img>` tags, CU might detect and describe them.

**Result: FAILED.** The base64-embedded HTML (173 KB, well under the 1 MB limit) returned identical output to the plain HTML — 0 figures, 0 hyperlinks, same 2,919-char markdown. CU strips data URIs from HTML during processing.

### Experiment 2: HTML vs PDF → CU Output Comparison

| Feature | HTML → CU | HTML+Base64 → CU | PDF → CU |
|---|---|---|---|
| Markdown length | 2,919 chars | 2,919 chars | 7,305 chars |
| Figures detected | 0 | 0 | 4 |
| Hyperlinks in JSON | 0 | 0 | 1 |
| Structured tables in JSON | 0 | 0 | 2 |
| Paragraphs in JSON | 0 | 0 | 112 |
| Image refs in markdown | 0 | 0 | 4 |
| kmsearch hyperlink in MD | ❌ Missing | ❌ Missing | ✅ Preserved |
| Tables in markdown text | ✅ Present | ✅ Present | ✅ Present |
| Summary field | ✅ Good quality | ✅ Good quality | ✅ Good quality |

**Key findings:**
- HTML→CU gives **good text/table extraction** but **no figures, no hyperlinks, no structured elements** in the JSON response
- The markdown itself has tables rendered correctly and text is high quality
- Hyperlinks are present as plain text (the link label survives) but the URL is stripped
- PDF→CU gives a much richer result — but requires the HTML→PDF conversion step

### Experiment 3: Individual Image Analysis via CU

**`prebuilt-documentSearch` on a single PNG image:** ✅ Works — generated descriptions for the 371×142 px screenshot, identified 3 sub-figures, generated a Summary field.

**`prebuilt-image` on a single PNG image:** ❌ Requires a custom analyzer with a `fieldSchema` — `prebuilt-image` is not runnable standalone.

**Conclusion:** We can process each article image individually through CU. Either:
- Use `prebuilt-documentSearch` (works out of the box, generates descriptions + summary)
- Create a custom analyzer based on `prebuilt-image` with a domain-tuned field schema (better control, UI-focused descriptions)

### Experiment 4: HTML Source Image Mapping

The original HTML uses absolute server paths for images:
```html
<img src="/sites/KMSearch/Articles/ymr1770823224196_en-us/zzy1770827101433.image">
```

The filename portion (`zzy1770827101433.image`) maps directly to the local `.image` files in the article folder. All 4 images are PNG format (confirmed via `file` command), 13–40 KB each. The position of each `<img>` tag in the HTML DOM tells us exactly where in the document the image belongs.

---

## Pipeline Options (No-PDF vs PDF)

### Option 1: HTML-Direct Pipeline ★ RECOMMENDED

**Drop the PDF conversion entirely.** Process HTML for text, process images separately, merge results.

```
kb/1_html/<article>/
  │
  ▼  Step 1a: HTML → CU (prebuilt-documentSearch, text/html)
  │  → Raw markdown (text, tables, headings) + Summary
  │
  ▼  Step 1b: Parse HTML DOM to extract <img> positions + <a> hyperlinks
  │  → Image map: { position_in_doc → local_image_file }
  │  → Link map: { link_text → URL }
  │
  ▼  Step 2: Analyze each image individually via CU
  │  → Per-image: Description, UIElements, NavigationPath (custom image analyzer)
  │
  ▼  Step 3: Merge & Reconstruct (post-processing script)
  │  • Start with CU markdown from Step 1a
  │  • Re-inject hyperlinks from Step 1b link map
  │  • Insert image descriptions + links at correct positions from Step 1b image map
  │  • Each image block links to the actual file in the article folder
  │
kb/3_output/<article>/
  ├── article.md              (clean markdown with image descriptions + links)
  └── images/                 (symlinks or copies of original .image files, renamed to .png)
      ├── zzy1770827101433.png
      ├── mnz1770827151034.png
      └── ...
  │
  ▼  Step 4: Chunk + Index into AI Search
  │  • Split markdown by headers (plain Python, no LangChain)
  │  • Each chunk has 0-N image URLs (from Blob Storage)
  │  • Embed text via Azure Foundry embedding endpoint
  │
Azure AI Search Index
```

**How image position merging works:**

The CU markdown from HTML preserves the document structure (headings, paragraphs, steps) faithfully. The original HTML's `<img>` tags appear inside specific steps (e.g., step 1 under "Identifying Firm Users" has 3 images, step 2 under "Identifying Client Users" has 1 image). We parse the HTML DOM to know:
1. Which `<img>` tags exist and their filenames
2. Where each `<img>` falls in the document hierarchy (after which text paragraph / step)

We then correlate this with the CU markdown by matching the surrounding text. For example:
- CU markdown has: `In RUN, go to Companies > Settings > Security > Manage user security.`
- HTML has the same text followed by 3 `<img>` tags
- We insert the 3 image description blocks after that paragraph in the merged markdown

**Pros:**
- **No PDF conversion dependency** — removes Playwright/Chromium from the pipeline
- **No PDF cropping complexity** — no bounding polygon parsing, no PyMuPDF, no DPI calculations
- **Original high-quality images** — the source PNGs are used directly, not degraded by PDF rendering + re-cropping
- **Simpler dependency tree** — drops `playwright`, `PyMuPDF`, `Pillow`
- **Faster pipeline** — no headless browser rendering step
- **Full control over image processing** — each image gets individual CU analysis with a domain-tuned prompt
- **Hyperlinks recoverable** — we parse them from the HTML directly, no dependency on CU extracting them

**Cons:**
- **CU gives less structured JSON for HTML** — no `paragraphs`, `hyperlinks`, `tables` arrays; we compensate with HTML DOM parsing
- **Position matching is heuristic** — correlating CU markdown positions with HTML `<img>` positions requires text matching, which could be fragile for edge cases
- **N+1 API calls** — 1 HTML analysis + N image analyses (same as the two-pass PDF approach though)

### Option 2: PDF Pipeline (Current Architecture, Refined)

**Keep the HTML→PDF conversion.** The PDF gives CU a complete rendered document with images inline.

```
kb/1_html/<article>/
  │
  ▼  Step 1: HTML → PDF (Playwright headless Chromium)
kb/2_pdf/<article>/article.pdf
  │
  ▼  Step 2: PDF → CU (prebuilt-documentSearch)
  │  → Rich markdown with figure refs + descriptions + hyperlinks
  │  → Bounding polygons for every figure
  │
  ▼  Step 3: Crop figures from PDF using bounding polygons (PyMuPDF)
  │  → Per-image: re-analyze with custom image analyzer for domain-tuned descriptions
  │
  ▼  Step 4: Reconstruct markdown with enriched descriptions + image links
  │
kb/4_output/<article>/ → AI Search Index
```

**Pros:**
- **Richest CU output** — figures, hyperlinks, tables, paragraphs all structured in JSON
- **No position matching needed** — CU tells us exactly where each figure is in the markdown (via `span` offsets)
- **Proven pipeline** — already working in current code

**Cons:**
- **PDF conversion adds complexity** — Playwright/Chromium dependency, rendering artifacts, potential styling issues
- **Image degradation** — original PNGs are rendered into PDF (rasterized at print resolution), then cropped back out; quality may drop
- **Bounding polygon cropping** — parsing `D(page,x1,y1,...,x8,y8)` format, handling coordinate systems, DPI conversion
- **More dependencies** — `playwright`, `PyMuPDF`, `Pillow` all needed
- **Slower** — headless browser rendering adds 5-10 seconds per article

### Option 3: Hybrid — HTML for Text, Source Images Direct (No CU for text)

**Skip CU for the HTML entirely.** Use a Python HTML→Markdown converter (e.g., `markdownify` or `beautifulsoup4`) to convert the HTML to markdown directly, preserving structure, links, and image positions natively. Then use CU only for image analysis.

```
kb/1_html/<article>/
  │
  ▼  Step 1: HTML → Markdown (Python library, e.g. markdownify)
  │  → Markdown with all hyperlinks, image positions, tables preserved
  │  → Image refs point to local files
  │
  ▼  Step 2: Analyze each image via CU (custom image analyzer)
  │  → Per-image: Description, UIElements, NavigationPath
  │
  ▼  Step 3: Replace image refs in markdown with description blocks + image links
  │
kb/3_output/<article>/ → AI Search Index
```

**Pros:**
- **No CU needed for text at all** — HTML→MD conversion is deterministic, fast, free
- **Perfect link preservation** — `markdownify` keeps all `<a href>` links
- **Perfect image placement** — images stay exactly where they were in the HTML
- **Cheapest option** — only N API calls (one per image), no document analysis
- **Simplest pipeline** — no position matching heuristics, no parsing CU JSON

**Cons:**
- **No AI Summary field** — CU's generated Summary is useful for the search index; would need a separate LLM call to generate it
- **HTML quality dependency** — if the HTML is messy/complex, the markdown converter may produce lower quality output than CU's AI-powered extraction
- **No CU-level table understanding** — markdown converters may not handle complex nested tables as well as CU
- **Losing the AI structuring** — CU can clean up noisy HTML; a converter is literal

---

## Recommendation: Option 1 (HTML-Direct) with Option 3 as Fallback

**Start with Option 1** — it keeps CU in the loop for text extraction (AI-powered cleanup of the complex HTML, Summary generation) while eliminating the PDF conversion. The position matching is solvable because:
1. The HTML structure is regular (DITA-generated, consistent patterns)
2. The CU markdown preserves the same text, just without images/links
3. We have the full HTML DOM as ground truth for image and link positions

**If position matching proves too fragile**, fall back to **Option 3** — skip CU for text entirely and use a Python HTML→MD converter. This is the simplest possible pipeline.

**In both cases, the image processing is identical:** analyze each image individually through a custom CU image analyzer (based on `prebuilt-image`) with a domain-tuned prompt for UI screenshots.

**Option 2 (PDF pipeline) should be kept as a reference** but deprioritized. It's more complex and the PDF conversion step introduces unnecessary dependencies and potential quality degradation.

---

## Image Analyzer (Shared Across All Options)

For all options, we need a custom image analyzer. This is created once and reused for every article's images.

### Using `prebuilt-documentSearch` for Images (Quick Start)

We confirmed that `prebuilt-documentSearch` can analyze individual PNG images out of the box — no custom analyzer needed. It returns:
- Figure descriptions in the markdown
- A Summary field
- OCR text from the image

This is a good starting point to validate the pipeline before investing in a custom analyzer.

### Custom Image Analyzer (Production Quality)

Create a custom analyzer based on `prebuilt-image` with a domain-tuned prompt for UI screenshots:

```json
{
  "analyzerId": "article-image-analyzer",
  "description": "Analyzes screenshots and UI images from technical support KB articles. Generates detailed descriptions focusing on UI elements, navigation paths, form fields, and visual indicators like buttons, menus, and highlighted areas.",
  "baseAnalyzerId": "prebuilt-image",
  "models": {
    "completion": "gpt-4.1"
  },
  "fieldSchema": {
    "name": "ArticleImageFields",
    "fields": {
      "Description": {
        "type": "string",
        "method": "generate",
        "description": "A detailed description of the screenshot or UI image, focusing on: what screen/page is shown, key UI elements visible, any highlighted or annotated areas, navigation steps illustrated, and any text visible in the image. Write as if explaining the image to someone who cannot see it."
      },
      "UIElements": {
        "type": "array",
        "method": "generate",
        "description": "List of key UI elements visible in the image (buttons, menus, fields, labels)",
        "items": { "type": "string" }
      },
      "NavigationPath": {
        "type": "string",
        "method": "generate",
        "description": "The navigation path shown in the image, e.g. 'Settings > Security > Manage user security'"
      }
    }
  }
}
```

**Pros:**
- Best image descriptions — each image analyzed individually with a domain-tuned prompt
- Custom fields per image (`UIElements`, `NavigationPath`) enriches the search index
- Can be very specific about what to extract from screenshots (the articles are mostly UI screenshots)

**Cons:**
- Must manage analyzer lifecycle (create, version, delete)
- Requires model deployment (gpt-4.1) to be set up
- N API calls per document (one per image)

---

## Step 3: Post-Processing Script — Option 1 (HTML-Direct)

New script: `src/postprocess_html_article.py`

### Functionality

```python
"""Post-process an HTML KB article into article.md + images/.

Input:  kb/1_html/<article>/index.html  (HTML + local .image files)
        kb/3_md/analyze-html-documentSearch/<article>/index-result.result.json  (CU result)
Output: kb/3_output/<article>/article.md
        kb/3_output/<article>/images/<filename>.png
"""
```

### Algorithm

1. **Load** the CU JSON result (markdown + Summary) and the original HTML file.
2. **Parse HTML DOM** to extract:
   - **Image map:** For each `<img>`, record the filename (from `src` attribute) and its position in the document (which heading/step it belongs to, and the preceding text).
   - **Link map:** For each `<a href>`, record the link text and URL.
3. **Analyze each image individually via CU:**
   - Read image bytes from the article folder (the `.image` files are PNGs)
   - Send to `prebuilt-documentSearch` (quick start) or custom `article-image-analyzer` (production)
   - Get back a description for each image
4. **Reconstruct markdown:**
   - Start with the CU markdown from Step 1 (good text/tables/headings)
   - **Re-inject hyperlinks:** Find link text in the markdown (e.g., "Adding or Changing RUN User Roles") and wrap it with the URL from the HTML link map → `[Adding or Changing RUN User Roles](https://kmsearch.adpcorp.com/...)`
   - **Insert image blocks:** Use the image position map to locate where each image belongs in the markdown. Insert an image description block after the matching text:
     ```markdown
     > **[Image: zzy1770827101433](images/zzy1770827101433.png)**
     > {AI-generated description from CU image analysis}
     ```
   - Each image block links to the actual PNG in the `images/` subfolder
5. **Copy/rename images:** Copy `.image` files to `images/<filename>.png`
6. **Write outputs:** `article.md` + `images/` folder.

### Image Position Matching Strategy

The HTML articles are DITA-generated with a consistent structure:
```
<article>
  <h2>Section Title</h2>
  <ol class="steps">
    <li class="step">
      <span class="cmd">Step text...</span>
      <div class="info">
        <p><img src="..."/></p>     ← images are inside step info blocks
      </div>
    </li>
  </ol>
</article>
```

**Matching approach:**
1. Parse the HTML and walk the DOM to build an ordered list: `[(text_before, image_filename), ...]`
2. For each image, the "text before" is the step instruction text (e.g., "In RUN, go to Companies > Settings > Security > Manage user security.")
3. Search for that text in the CU markdown (it preserves the same text faithfully)
4. Insert the image block immediately after the matching text

This works because:
- The CU markdown text matches the HTML text almost verbatim (confirmed empirically)
- Each image follows a unique step instruction, so text matching is unambiguous
- The articles have a regular DITA structure with images always inside step `<div class="info">` blocks

---

## Step 4: Chunking + AI Search Indexing

New script: `src/index_to_search.py`

**No LangChain.** Chunking and embedding are done with plain Python and direct Azure Foundry API calls.

### Chunk Strategy

Split `article.md` by **markdown headers** (H1, H2, H3). Each header-delimited section becomes one chunk. Paragraphs within a section are assumed to be small enough that no further splitting is needed.

Image descriptions are treated as **paragraphs within their section** — they stay with the surrounding text in the same chunk. This means a single chunk may contain 0, 1, or many image references.

Implementation: a simple regex/line-based splitter that walks the markdown, splitting on `^#{1,3} ` lines. Each chunk inherits the header hierarchy for context.

### Embedding

Call the **Azure Foundry embedding model endpoint** directly via `httpx` or `azure-ai-inference` SDK (no LangChain):

```python
from azure.ai.inference import EmbeddingsClient
from azure.identity import DefaultAzureCredential

client = EmbeddingsClient(
    endpoint=MODELS_ENDPOINT,
    credential=DefaultAzureCredential(),
)
response = client.embed(model="text-embedding-3-small", input=[chunk_text])
vector = response.data[0].embedding
```

### Image-Aware Chunking

After splitting by headers, scan each chunk for image references matching the pattern `[Image: <filename>](images/<filename>.png)`. Extract all matched image paths into a list. A chunk can reference **0 to N images**.

### AI Search Index Schema

```json
{
  "name": "kb-articles",
  "fields": [
    { "name": "id",            "type": "Edm.String",  "key": true },
    { "name": "article_id",    "type": "Edm.String",  "filterable": true },
    { "name": "chunk_index",   "type": "Edm.Int32",   "sortable": true },
    { "name": "content",       "type": "Edm.String",  "searchable": true },
    { "name": "content_vector", "type": "Collection(Edm.Single)",
      "searchable": true, "vectorSearchDimensions": 1536,
      "vectorSearchProfileName": "default-profile" },
    { "name": "image_urls",    "type": "Collection(Edm.String)", "filterable": false,
      "comment": "0-N Blob Storage URLs to article images related to this chunk" },
    { "name": "source_url",    "type": "Edm.String",  "filterable": false,
      "comment": "Original HTML article URL if available" },
    { "name": "title",         "type": "Edm.String",  "searchable": true },
    { "name": "section_header", "type": "Edm.String", "filterable": true,
      "comment": "H2/H3 heading this chunk belongs to" },
    { "name": "key_topics",    "type": "Collection(Edm.String)", "filterable": true }
  ]
}
```

The image descriptions are **part of `content`** (they're inline paragraphs in the markdown), so they get vectorized naturally with the surrounding text. No separate `image_description` field needed.

### Image Storage

Article images are uploaded to **Azure Blob Storage** by the indexing script. The `image_urls` array stores the full Blob URLs (with SAS tokens or public container access depending on policy). This makes them directly resolvable by an agent.

Structure: `<container>/articles/<article_id>/images/<filename>.png`

### How It Works for an Agent

When an agent queries the index:
1. **Text-only chunks:** `content` has the text, `image_urls` is empty. Agent uses text to answer.
2. **Chunks with images:** `content` has section text + inline image descriptions (vectorized together). `image_urls` has 1-N Blob Storage URLs. Agent reads the description for reasoning and can surface the actual images to the user.

---

## Output Format — Example `article.md`

```markdown
# Identifying RUN for Partners (Wholesale) User Roles in RUN

February 11, 2026

## Identifying Firm Users

Follow the steps below to identify Firm User roles for R4P (Wholesale) accounts.

1. In RUN, go to Companies > Settings > Security > Manage user security.

> **[Image: zzy1770827101433](images/zzy1770827101433.png)**
> Screenshot of the RUN dashboard showing the left navigation menu with
> Dashboard, Companies, Reports & tax forms, and Settings options.
> The Companies menu item is highlighted with a green border.

> **[Image: mnz1770827151034](images/mnz1770827151034.png)**
> Screenshot showing the Settings submenu selected in the left navigation,
> displaying the Companies list view with search and filter options.

> **[Image: qvd1770827174448](images/qvd1770827174448.png)**
> Screenshot of the Security settings panel showing three options:
> Add users, Manage user security (highlighted), and Manage company groups.

2. In the Role field, you can see the user's role. Refer to the table
below to see the available user roles for Firm Users.

| Users | Roles |
|---|---|
| Firm | Can access all payroll-related functions... |
| Firm Limited PR & EE Entry | Limited access to multiple clients... |

...

For more info, see [Adding or Changing RUN User Roles](https://kmsearch.adpcorp.com/#/Articles/taz1560436150553_en-us/index.html?doc_id=aef14f91-b06f-4c20-86e9-2bb4d08dc4cd%3A39894).
```

---

## Implementation Plan

### Phase 1: HTML-Direct Pipeline (core — no PDF)

| # | Task | New/Modified File |
|---|---|---|
| 1 | Create `src/parse_html_article.py` — parse HTML DOM, extract image map + link map | `src/parse_html_article.py` |
| 2 | Create `src/analyze_images.py` — send each `.image` file to CU, collect descriptions | `src/analyze_images.py` |
| 3 | Create `src/postprocess_html_article.py` — merge CU markdown + image descriptions + links | `src/postprocess_html_article.py` |
| 4 | Add `make process-html` target (runs steps 1a→1b→2→3) | `Makefile` |
| 5 | Test with `ymr1770823224196_en-us` article | manual |

### Phase 2: Custom Image Analyzer

| # | Task | New/Modified File |
|---|---|---|
| 6 | Create `analyzers/article-image-analyzer.json` — domain-tuned for UI screenshots | `analyzers/article-image-analyzer.json` |
| 7 | Create `src/manage_analyzers.py` — create/update/delete custom analyzers | `src/manage_analyzers.py` |
| 8 | Update `src/analyze_images.py` to use custom analyzer instead of `prebuilt-documentSearch` | `src/analyze_images.py` |

### Phase 3: AI Search Integration

| # | Task | New/Modified File |
|---|---|---|
| 9 | Create `src/chunk_markdown.py` — header-based markdown splitter (no LangChain) | `src/chunk_markdown.py` |
| 10 | Create `src/index_to_search.py` — embed via Azure Foundry + index to AI Search | `src/index_to_search.py` |
| 11 | Create `src/upload_images.py` — upload images to Blob Storage | `src/upload_images.py` |
| 12 | Create search index definition | `search/index-definition.json` |
| 13 | Add `make index` target | `Makefile` |

---

## Full Pipeline (end-to-end `make all` — Option 1)

```
make all
  ├── analyze-html        # Step 1a: HTML → CU (text/tables/summary)
  ├── parse-html          # Step 1b: HTML DOM → image map + link map
  ├── analyze-images      # Step 2:  Each .image → CU → descriptions
  ├── postprocess         # Step 3:  Merge markdown + images + links → article.md
  └── index               # Step 4:  article.md → AI Search index
```

---

## Dependencies

| Package | Purpose | Already present? |
|---|---|---|
| `azure-ai-contentunderstanding` | Content Understanding SDK | ✅ |
| `azure-identity` | Azure auth | ✅ |
| `python-dotenv` | Config | ✅ |
| `beautifulsoup4` | HTML DOM parsing for image/link extraction | ❌ Add to pyproject.toml |
| `azure-ai-inference` | Azure Foundry embedding model calls | ❌ Add for Phase 3 |
| `azure-search-documents` | AI Search SDK | ❌ Add for Phase 3 |
| `azure-storage-blob` | Upload images to Blob Storage | ❌ Add for Phase 3 |

**Removed dependencies** (vs PDF pipeline): `playwright`, `PyMuPDF`, `Pillow` — none needed.

---

## Design Decisions (Resolved)

| # | Question | Decision |
|---|---|---|
| 1 | **Image hosting** | Azure Blob Storage. Original article images uploaded during indexing; `image_urls` stores Blob URLs. |
| 2 | **Hyperlink fixup** | Parse from HTML DOM directly (not from CU). The HTML `<a href>` tags give us the exact URLs. Re-inject into CU markdown by text-matching the link label. |
| 3 | **Description quality** | Two-pass: CU for document text, separate CU calls per image. Start with `prebuilt-documentSearch` for images (works out of the box), upgrade to custom `article-image-analyzer` in Phase 2. |
| 4 | **Chunk granularity** | Image descriptions are paragraphs within their section. A chunk = one header-delimited section. A chunk can reference 0–N images. The index `image_urls` field is `Collection(Edm.String)`. |
| 5 | **Table format** | Markdown tables. CU already produces markdown tables from HTML input. |
| 6 | **No LangChain** | All chunking is plain Python (split on markdown headers). Embeddings via Azure Foundry `azure-ai-inference` SDK. No LangChain dependency anywhere. |
| 7 | **No PDF conversion** | HTML is processed directly. Images are from the article folder, not cropped from PDF. Eliminates Playwright, PyMuPDF, Pillow dependencies. |

## Remaining Open Questions

1. **Image position matching robustness** — the text-matching approach works for the test article (regular DITA structure). Need to validate against more articles to confirm it's reliable. If fragile, fall back to Option 3 (pure HTML→MD conversion, no CU for text).

2. **Blob Storage container structure** — recommended: `<container>/articles/<article_id>/images/<filename>.png`.

3. **Custom image analyzer ROI** — is the custom `article-image-analyzer` description quality noticeably better than `prebuilt-documentSearch` for these UI screenshots? Will need a side-by-side comparison in Phase 2.
