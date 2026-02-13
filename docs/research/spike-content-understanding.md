# Spike: Azure Content Understanding — HTML KB Articles

Test how Azure Content Understanding processes HTML knowledge base articles that contain links/references to images, and whether converting to PDF unlocks figure detection.

## Project Structure

```
content-understanding/
├── kb/                          # Knowledge base articles
│   ├── 1_html/                  # Source HTML articles (one folder per article)
│   │   ├── <article-id>/
│   │   │   ├── *.html           # Article HTML (index.html or named)
│   │   │   └── images/ | *.image  # Supporting images
│   ├── 2_pdf/                   # Generated PDFs (from html-to-pdf conversion)
│   │   └── <article-id>/
│   │       └── *.pdf
│   └── 3_md/                    # CU analysis outputs (one folder per method)
│       ├── analyze-html-layout/<article-id>/
│       │   ├── *-result.md
│       │   └── *-result.result.json
│       ├── analyze-html-documentSearch/<article-id>/
│       │   ├── *-result.md
│       │   └── *-result.result.json
│       └── analyze-pdf-documentSearch/<article-id>/
│           ├── *-result.md
│           └── *-result.result.json
├── src/                         # Python scripts
│   ├── convert_html_to_pdf.py   # HTML → PDF via Playwright
│   ├── analyze_html-layout.py   # HTML → prebuilt-layout
│   ├── analyze_html-documentSearch.py  # HTML → prebuilt-documentSearch
│   ├── analyze_pdf-documentSearch.py   # PDF → prebuilt-documentSearch
│   ├── setup_defaults.py        # One-time model deployment registration
│   └── config.py                # Env config & credential loading
├── docs/                        # Research notes
├── Makefile                     # Batch processing targets
└── README.md
```

## Prerequisites

- Python 3.11+
- [UV](https://docs.astral.sh/uv/) installed
- A **Microsoft Foundry / AIServices resource** in a [supported region](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/language-region-support)
- Deployed models (see [Model Requirements](#model-requirements) below)
- **Cognitive Services User** role assigned to your identity on the resource

## Model Requirements

> **Critical lesson learned**: `prebuilt-documentSearch` requires **`text-embedding-3-large`** (not `small`).
> If the model is missing, the API **silently returns 0 contents with no error or warning**.

| Model | Purpose | Required By |
|---|---|---|
| `gpt-4.1` | Completion model for field extraction, summarization | `prebuilt-documentSearch` |
| `gpt-4.1-mini` | Lighter completion model | `prebuilt-layout`, general use |
| `text-embedding-3-small` | Embedding model (general) | General use |
| **`text-embedding-3-large`** | **Embedding model for documentSearch** | **`prebuilt-documentSearch`** (hard requirement) |

The `prebuilt-documentSearch` analyzer definition specifies `models.embedding: "text-embedding-3-large"`.
You must deploy this model **and** register it via `setup_defaults.py` before `prebuilt-documentSearch` will return results.

## Endpoint

Use the **`cognitiveservices.azure.com`** endpoint, not `services.ai.azure.com` (Foundry).
The Foundry endpoint cannot see or manage CU model deployments.

```
CONTENTUNDERSTANDING_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
```

## Setup

```bash
cd content-understanding/src

# Create env and install deps
uv sync

# Install Chromium for HTML→PDF conversion (one-time)
uv run playwright install chromium

# Configure environment
cp .env.sample .env
# Edit .env with your endpoint (cognitiveservices.azure.com)

# One-time: map model deployments to prebuilt analyzers
uv run python setup_defaults.py
```

## Usage

### Makefile Targets (batch processing)

From the `content-understanding/` directory:

```bash
make help                 # Show all targets
make html-to-pdf          # Convert all HTML articles → PDF
make html-layout          # Run prebuilt-layout on all HTML articles
make html-documentSearch  # Run prebuilt-documentSearch on all HTML articles
make pdf-documentSearch   # Convert HTML→PDF, then run documentSearch on PDFs
make all                  # Run all pipelines
make clean                # Remove all generated PDFs and markdown
```

### Individual Scripts

From the `content-understanding/src` directory:

```bash
# Convert a single article to PDF
uv run python convert_html_to_pdf.py --article content-understanding-html_en-us

# Analyze HTML with prebuilt-layout
uv run python analyze_html-layout.py --article content-understanding-html_en-us

# Analyze HTML with prebuilt-documentSearch
uv run python analyze_html-documentSearch.py --article content-understanding-html_en-us

# Analyze HTML by URL (documentSearch)
uv run python analyze_html-documentSearch.py --url https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/overview

# Analyze PDF with prebuilt-documentSearch (requires html-to-pdf first)
uv run python analyze_pdf-documentSearch.py --article content-understanding-html_en-us
```

## Key Findings

### Figure / Image Detection

| Input Format | Analyzer | Figures Detected | Notes |
|---|---|---|---|
| HTML (binary) | `prebuilt-layout` | **No** | Images dropped entirely from output |
| HTML (binary) | `prebuilt-documentSearch` | **No** | Images dropped; text/summary/hyperlinks extracted |
| HTML (URL) | `prebuilt-documentSearch` | **No** | Same — no figure analysis for HTML |
| **PDF (binary)** | **`prebuilt-documentSearch`** | **Yes (2)** | **Full figure descriptions generated** |

**Conclusion**: Figure analysis is only supported for PDF and image file formats (per docs).
To process HTML KB articles with images, convert HTML → PDF first (using Playwright/Chromium),
then run `prebuilt-documentSearch` on the PDF.

### Output Comparison (same article)

| Metric | HTML + layout | HTML + docSearch | PDF + docSearch |
|---|---|---|---|
| Markdown length | 10,713 chars | 10,713 chars | 16,080 chars |
| Figures | 0 | 0 | 2 (with descriptions) |
| Summary | N/A | Yes | Yes |
| Hyperlinks | N/A | Yes (85) | Yes (85) |

### HTML → PDF Conversion

WeasyPrint was tried first but cannot generically scale images to fit pages (CSS page-based layout clips oversized images). **Playwright** (headless Chromium `page.pdf()`) works reliably — Chrome's print-to-PDF automatically scales content and flows across pages with no per-document tuning.

The converter handles articles with non-standard image references (e.g. absolute paths like `/sites/KMSearch/...`, `.image` extensions) by intercepting Playwright resource requests and serving files from the article's local directory.

## Authentication

By default uses `DefaultAzureCredential` (i.e., `az login`).
Set `CONTENTUNDERSTANDING_KEY` in `.env` to use API key auth instead.

## References

- [Content Understanding overview](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/overview)
- [Python SDK docs](https://learn.microsoft.com/python/api/overview/azure/ai-contentunderstanding-readme?view=azure-python-preview)
- [Supported models](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/models)
- [prebuilt-documentSearch](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/prebuilt/document-search)
