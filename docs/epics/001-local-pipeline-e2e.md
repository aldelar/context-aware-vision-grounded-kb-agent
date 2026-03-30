# Epic 001 — Local Pipeline End-to-End

> **Status:** Done
> **Created:** February 13, 2026
> **Updated:** February 14, 2026

## Objective

Implement the full ingestion pipeline (`fn-convert` + `fn-index`) as local Python code that processes KB articles from `kb/staging/` through to a populated Azure AI Search index. Functions run locally against local folders but call live Azure services (Content Understanding, AI Foundry, AI Search) provisioned via the existing infrastructure code.

## Success Criteria

- [x] `make convert` processes every article in `kb/staging/` and writes clean Markdown + images to `kb/serving/`
- [x] `make index` processes every article in `kb/serving/` and populates the `kb-articles` AI Search index
- [x] End-to-end: raw HTML article → searchable chunks with image URLs in AI Search
- [x] Unit tests pass for all core modules (75 tests)

---

## Source Layout Reference

This epic establishes the production `src/` structure. All code delivered in this epic follows this layout:

```
src/
└── functions/
    ├── function_app.py              # Azure Functions v2 entry point (both fn-convert & fn-index)
    ├── pyproject.toml               # Single project — all function dependencies
    ├── .env.sample                  # Required environment variables template
    │
    ├── fn_convert/                  # Stage 1 — HTML → Markdown + images
    │   ├── __init__.py              # run(article_path) orchestrator
    │   ├── html_parser.py           # BeautifulSoup: image map + link map from HTML DOM
    │   ├── cu_text.py               # CU prebuilt-documentSearch → Markdown
    │   ├── cu_images.py             # CU kb-image-analyzer → per-image descriptions
    │   └── merge.py                 # Combine CU Markdown + recovered links + image blocks
    │
    ├── fn_index/                    # Stage 2 — Markdown → AI Search index
    │   ├── __init__.py              # run(article_path) orchestrator
    │   ├── chunker.py               # Split MD by headers, extract image refs per chunk
    │   ├── embedder.py              # Azure AI Foundry embedding calls
    │   └── indexer.py               # Push chunks to Azure AI Search
    │
    ├── shared/                      # Shared utilities (functions-scoped)
    │   ├── __init__.py
    │   ├── config.py                # Environment / config loading + validation
    │   ├── blob.py                  # Blob Storage read/write helpers (local file I/O for now)
    │   └── cu_client.py             # Content Understanding client factory
    │
    └── manage_analyzers.py          # CU analyzer deploy/delete CLI

scripts/
├── dev-setup.sh                     # (existing) Install dev prerequisites
└── functions/
    ├── convert.sh                   # Iterate kb/staging/*, call fn_convert per article
    └── index.sh                     # Iterate kb/serving/*, call fn_index per article

src/
└── functions/
    └── tests/                       # pytest test suite
        ├── conftest.py              # Shared fixtures
        ├── test_convert/
        │   ├── test_html_parser.py
        │   ├── test_cu_text.py
        │   ├── test_cu_images.py
        │   └── test_merge.py
        └── test_index/
            ├── test_chunker.py
            ├── test_embedder.py
            └── test_indexer.py
```

---

## Stories

---

### ✅ Story 1 — Project Scaffolding

> **Status:** Done

Set up the `src/functions/` project structure, dependency management, shared configuration, and update the Makefile and scripts to use the new layout.

#### Deliverables

- [x] Create `src/functions/` directory structure matching the layout above (empty `__init__.py` files, package folders)
- [x] Create `src/functions/pyproject.toml` with all required dependencies:
  - `azure-ai-contentunderstanding>=1.0.0b1`
  - `azure-identity>=1.19.0`
  - `azure-storage-blob`
  - `azure-search-documents`
  - `azure-ai-inference`
  - `beautifulsoup4`
  - `python-dotenv`
  - `pytest` (dev dependency)
- [x] Create `src/functions/.env.sample` listing all required environment variables (sourced from AZD outputs — see infrastructure.md):
  - `AI_SERVICES_ENDPOINT` — Content Understanding + embedding endpoint
  - `EMBEDDING_DEPLOYMENT_NAME` — model deployment name (`text-embedding-3-small`)
  - `SEARCH_ENDPOINT` — Azure AI Search endpoint
  - `SEARCH_INDEX_NAME` — target index name (default: `kb-articles`)
  - Note: no storage endpoints needed for local mode (local file I/O)
  - Include comment showing how to populate from AZD: `azd env get-values > .env`
- [x] Implement `src/functions/shared/config.py` — loads `.env`, exposes typed config, validates required vars on import. Uses `DefaultAzureCredential` for auth (falls back to `az login` identity for local dev)
- [x] Create `scripts/functions/convert.sh` — iterates `kb/staging/*/`, calls the fn-convert entry point per article folder
- [x] Create `scripts/functions/index.sh` — iterates `kb/serving/*/`, calls the fn-index entry point per article folder
- [x] Update `Makefile` — `convert` target calls `scripts/functions/convert.sh`, `index` target calls `scripts/functions/index.sh`, `azure-deploy` references new `manage_analyzers.py` path
- [x] Move existing spike code: spike code stays in `src/spikes/`; no old top-level `src/*.py` files present
- [x] Add `make test` target to Makefile (runs `cd src/functions && uv run pytest tests/`)
- [x] `uv sync --extra dev` succeeds in `src/functions/` with no errors

#### Definition of Done

- [x] `cd src/functions && uv sync --extra dev` installs all dependencies (27 + 7 dev packages)
- [x] `make help` shows updated target descriptions (including `validate-infra`)
- [x] `make test` runs (0 tests collected — no tests yet)
- [x] `.env.sample` documents every required variable

---

### Story 2 — Validate Azure Infrastructure ✅

> **Status:** Done

Create a validation script/make target that confirms the deployed Azure infrastructure is ready for local pipeline execution. This unblocks all subsequent stories.

> **Note:** The infra (Bicep) deploys the Azure services and grants RBAC roles to the **Function App's managed identity**. For local development, `DefaultAzureCredential` uses the developer's `az login` identity, which also needs RBAC roles on these resources. The `kb-articles` search index and `kb-image-analyzer` CU analyzer are **not** deployed by infra — they are created by application code (`ensure_index_exists()` in Story 9 and `manage_analyzers.py` in this story).

> **Implementation Note:** CU requires a completion model from its supported list (gpt-4o, gpt-4o-mini, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano). We deployed `gpt-4.1` (GlobalStandard, 30K TPM) to the AI Services account since `gpt-5-mini` is not CU-supported. CU defaults must be set via `manage_analyzers.py setup` before deploying custom analyzers. The `deploy` command auto-runs `setup`. The analyzer ID uses underscores (`kb_image_analyzer`) because CU forbids hyphens in analyzer IDs.

#### Deliverables

- [x] Populate `src/functions/.env` from AZD outputs (`azd env get-values > src/functions/.env` or manual copy)
- [x] Create `scripts/functions/validate-infra.sh` (or a Python script under `src/functions/`) that checks:
  - Azure AI Search service is reachable (does NOT require `kb-articles` index to exist — that's created at runtime by Story 9)
  - Content Understanding resource is reachable (does NOT require `kb-image-analyzer` yet — that's deployed below)
  - Azure AI Foundry embedding deployment is reachable (`text-embedding-3-small`)
  - Local `kb/staging/` folder exists and contains at least one article subfolder
  - Local `kb/serving/` folder exists (may be empty)
  - Developer's `az login` identity has the required RBAC roles (Cognitive Services OpenAI User, Cognitive Services User on AI Services; Search Index Data Contributor, Search Service Contributor on AI Search)
- [x] Add `make validate-infra` target to Makefile
- [x] Implement `src/functions/manage_analyzers.py` — CLI with `setup`, `deploy`, `delete`, and `status` subcommands for the `kb_image_analyzer` (reads definition from `src/analyzers/kb-image-analyzer.json`)
- [x] Create `src/analyzers/kb-image-analyzer.json` with the analyzer definition from architecture.md (+ `models.completion: gpt-4.1`)
- [x] Validation script prints clear pass/fail per check with actionable error messages
- [x] Add a `make grant-dev-roles` target that assigns the developer's identity the same RBAC roles the Function App has on AI Services and AI Search (uses `az role assignment create`)

| File | Status |
|------|--------|
| `src/functions/manage_analyzers.py` | ✅ |
| `src/functions/shared/config.py` | ✅ (added `agent_deployment_name`) |
| `scripts/functions/validate-infra.sh` | ✅ |
| `src/analyzers/kb-image-analyzer.json` | ✅ |
| `Makefile` | ✅ (added `grant-dev-roles`, updated `azure-deploy`) |

#### Definition of Done

- [x] `make validate-infra` passes against the provisioned Azure environment (10/10 checks pass)
- [x] Developer RBAC roles are granted and verified (4 roles: CogSvc OpenAI User, CogSvc User, Search Index Data Contributor, Search Service Contributor)
- [x] `manage_analyzers.py deploy` successfully deploys the CU analyzer (with auto-setup of defaults)
- [x] `kb_image_analyzer` is confirmed queryable in the CU resource (status: READY, fields: Description, UIElements, NavigationPath)

---

### Story 3 — fn-convert: HTML Text Extraction ✅

> **Status:** Done

Implement the CU text extraction module that sends HTML to `prebuilt-documentSearch` and returns clean Markdown.

> **Implementation Note:** `prebuilt-documentSearch` requires both `text-embedding-3-large` AND `gpt-4.1-mini` deployed and registered as CU defaults. Without either, the SDK silently returns 0 contents — the actual error (`ResourceError: No deployment for model 'gpt-4.1-mini' was provided`) is only visible via the REST API polling response. The Python SDK `1.0.0b1` does not propagate CU inner errors. Both models were added to the Bicep template and `manage_analyzers.py MODEL_DEPLOYMENTS`.

#### Deliverables

- [x] Implement `src/functions/fn_convert/cu_text.py`:
  - Accepts HTML file path (local), reads content
  - Sends to CU `prebuilt-documentSearch` analyzer (content type `text/html`)
  - Returns `CuTextResult(markdown, summary)` dataclass
  - Handles CU API errors gracefully with clear logging
- [x] Implement `src/functions/shared/cu_client.py`:
  - Singleton factory `get_cu_client()` with module-level caching
  - Authenticated via `DefaultAzureCredential`, endpoint from `config.ai_services_endpoint`
- [x] Unit test: `tests/test_convert/test_cu_text.py` — parametrized across both sample HTML articles
- [x] Verify extracted Markdown quality against the spike results in `kb/3_md/`
- [x] Deploy `text-embedding-3-large` and `gpt-4.1-mini` models (required by `prebuilt-documentSearch`)
- [x] Add both models to Bicep template and `manage_analyzers.py`

| File | Status |
|------|--------|
| `src/functions/fn_convert/cu_text.py` | ✅ |
| `src/functions/shared/cu_client.py` | ✅ |
| `src/functions/tests/test_convert/test_cu_text.py` | ✅ |
| `infra/azure/infra/modules/ai-services.bicep` | ✅ (added `text-embedding-3-large` + `gpt-4.1-mini` deployments) |
| `src/functions/manage_analyzers.py` | ✅ (added both models to `MODEL_DEPLOYMENTS`) |
| `docs/specs/infrastructure.md` | ✅ (5 model deployments) |

#### Definition of Done

- [x] `cu_text.py` produces Markdown from a sample KB article HTML
- [x] Output quality matches or exceeds spike results
- [x] CU client authenticates using managed identity / DefaultAzureCredential
- [x] Tests pass (9 tests: 2 articles × 4 assertions + 1 error case)

---

### Story 4 — fn-convert: HTML DOM Parsing ✅

> **Status:** Done

> **Implementation Note:** Two strategies for image map extraction: (1) DITA-specific — walks `li.step > span.cmd` siblings to find preceding instruction text for each image, (2) General fallback — traverses all `<img>` tags and collects preceding paragraph text. Link map excludes image wrapper links and bare anchor tags. All text is normalized (collapsed whitespace, `\xa0` → space).

Implement the BeautifulSoup-based HTML parser that extracts image and link maps from the source HTML DOM.

#### Deliverables

- [x] Implement `src/functions/fn_convert/html_parser.py`:
  - `extract_image_map(html_path)` → returns ordered list of `(preceding_text, image_filename)` tuples
  - `extract_link_map(html_path)` → returns list of `(link_text, url)` tuples
  - Handles DITA-generated HTML structure (images inside `<div class="info">` blocks following step instructions)
  - Robust to missing/malformed tags (logs warnings, skips gracefully)
- [x] Unit test: `tests/test_convert/test_html_parser.py`:
  - Test `extract_image_map` against both sample articles in `kb/staging/`
  - Test `extract_link_map` against both sample articles
  - Test edge cases: no images, no links, malformed HTML
- [x] Verify image map ordering matches visual document order

| File | Status |
|------|--------|
| `src/functions/fn_convert/html_parser.py` | ✅ |
| `src/functions/tests/test_convert/test_html_parser.py` | ✅ |

#### Definition of Done

- [x] Image map correctly identifies all images and their preceding text for both sample articles
- [x] Link map captures all hyperlinks with correct URLs
- [x] Tests pass with assertions on expected image count and link count (15 tests, 0.26s)

---

### Story 5 — fn-convert: Image Analysis ✅

> **Status:** Done

> **Implementation Note:** `ImageAnalysisResult` dataclass holds `filename_stem`, `description`, `ui_elements`, `navigation_path`. Content type detection uses magic bytes (PNG/JPEG/GIF headers). Failed images return placeholder description rather than crashing. All `.image` files in staging are PNGs (13–40 KB each).

Implement the per-image CU analysis module that sends each article image to the custom `kb-image-analyzer` and returns structured descriptions.

#### Deliverables

- [x] Implement `src/functions/fn_convert/cu_images.py`:
  - `analyze_image(image_path)` → returns `ImageAnalysisResult` with `description`, `ui_elements`, `navigation_path`
  - `analyze_all_images(image_paths)` → returns ordered list of image analysis results
  - Sends each image to `kb_image_analyzer` analyzer in CU
  - Handles images that fail analysis gracefully (log error, return placeholder description)
- [x] Unit test: `tests/test_convert/test_cu_images.py`:
  - Test with sample `.image` files from `kb/staging/`
  - Verify returned fields (Description is non-empty, UIElements is a list, NavigationPath is a string)
- [x] Verify description quality — descriptions should mention specific UI elements visible in the screenshots

| File | Status |
|------|--------|
| `src/functions/fn_convert/cu_images.py` | ✅ |
| `src/functions/tests/test_convert/test_cu_images.py` | ✅ |

#### Definition of Done

- [x] Each image in the sample articles gets a meaningful `Description`
- [x] `UIElements` and `NavigationPath` are populated for UI screenshots
- [x] Failed images produce a logged warning and a fallback description, not a crash
- [x] Tests pass (7 tests, 64.69s)

---

### Story 6 — fn-convert: Merge & Output ✅

> **Status:** Done

> **Implementation Note:** `recover_links()` text-matches link labels in the CU Markdown and wraps them as Markdown links (first occurrence only, skips already-linked text). `insert_image_blocks()` uses fuzzy regex matching (last 15 words of preceding text, case-insensitive) to position image blockquotes. Short search text (<5 chars) falls back to appending at end. The orchestrator runs steps 1a/1b in parallel (CU text + HTML DOM), then images, then merge. `blob.py` provides local file I/O wrappers (read_text, write_text, copy_file, list_files).

Implement the merge module that combines CU Markdown, recovered hyperlinks, and image description blocks into the final `article.md`, and the fn-convert orchestrator.

#### Deliverables

- [x] Implement `src/functions/fn_convert/merge.py`:
  - `recover_links(markdown, link_map)` → returns Markdown with hyperlinks re-injected by text-matching link labels
  - `insert_image_blocks(markdown, image_map, image_analyses)` → returns Markdown with image description blocks inserted at correct positions (after preceding text match)
  - Each image block follows the format from architecture.md (blockquote with image link + description)
  - Handles unmatched images/links gracefully (logs, skips)
- [x] Implement `src/functions/fn_convert/__init__.py` — `run(article_path, output_path)` orchestrator:
  1. Call `cu_text.extract(article_path/index.html)` → Markdown
  2. Call `html_parser.extract_image_map(article_path/index.html)` → image map
  3. Call `html_parser.extract_link_map(article_path/index.html)` → link map
  4. Call `cu_images.analyze_all_images(article_path/*.image)` → image analyses
  5. Call `merge.recover_links(markdown, link_map)` → Markdown with links
  6. Call `merge.insert_image_blocks(markdown, image_map, image_analyses)` → final Markdown
  7. Write `output_path/article.md`
  8. Copy/rename `.image` files → `output_path/images/<name>.png`
- [x] Implement `src/functions/shared/blob.py`:
  - For local mode: simple file I/O wrappers (read file, write file, copy file, list directory)
  - Functions take a base path and article-relative paths
- [x] Implement `src/functions/fn_convert/__main__.py` — CLI entry point for `python -m fn_convert`
- [x] Unit test: `tests/test_convert/test_merge.py`:
  - Test `recover_links` with known markdown + link map
  - Test `insert_image_blocks` with known markdown + image data
  - Test edge cases: no links to recover, no images to insert

| File | Status |
|------|--------|
| `src/functions/fn_convert/merge.py` | ✅ |
| `src/functions/fn_convert/__init__.py` | ✅ |
| `src/functions/fn_convert/__main__.py` | ✅ |
| `src/functions/shared/blob.py` | ✅ |
| `src/functions/tests/test_convert/test_merge.py` | ✅ |

#### Definition of Done

- [x] `fn_convert.run()` produces a well-formed `article.md` with inline image blocks and recovered hyperlinks
- [x] Images are copied and renamed to `images/<name>.png` in the output folder
- [x] Output matches the format specified in architecture.md
- [x] Tests pass (20 tests, 0.28s)

---

### Story 7 — fn-convert Local E2E ✅

> **Status:** Done

> **Implementation Note:** Both sample articles processed successfully. `content-understanding-html_en-us`: 13218 chars Markdown, 1179 char summary, 1 image analyzed (content-understanding-framework-2025.png), 8 links recovered. `ymr1770823224196_en-us`: 5107 chars Markdown, 418 char summary, 4 images analyzed, 1 link recovered. One expected warning: preceding text for one image in the clean HTML article doesn't match CU Markdown exactly — block is appended at end (no content loss).

Wire fn-convert end-to-end through the shell script and Makefile, and verify with the sample KB articles.

#### Deliverables

- [x] `scripts/functions/convert.sh` iterates `kb/staging/*/` and invokes fn-convert per article
- [x] `make convert` runs successfully for all articles in `kb/staging/`
- [x] Verify `kb/serving/{article-id}/article.md` exists and is well-formed for each article
- [x] Verify `kb/serving/{article-id}/images/` contains renamed PNGs for each article
- [x] Manually review output Markdown for both sample articles:
  - [x] Text structure preserved (headings, paragraphs, tables)
  - [x] Hyperlinks recovered and working
  - [x] Image description blocks present at correct positions
  - [x] Image references point to valid files in `images/`

#### Definition of Done

- [x] `make convert` runs end-to-end with zero errors
- [x] Both sample articles produce complete, correct output in `kb/serving/`
- [x] Output reviewed and confirmed to match architecture spec

---

### Story 8 — fn-index: Chunking & Image Mapping ✅

> **Status:** Done

> **Implementation Note:** `Chunk` dataclass holds `content`, `title`, `section_header`, `image_refs`. H3 chunks inherit parent H2 context with " > " separator (e.g. "H2 > H3"). Image refs extracted via regex `\[Image: ([^\]]+)\]\(images/[^)]+\.png\)`. Preamble before first header becomes its own chunk if non-empty. Tests use real `article.md` outputs from Story 7.

Implement the Markdown chunker that splits articles by headers and maps image references per chunk.

#### Deliverables

- [x] Implement `src/functions/fn_index/chunker.py`:
  - `chunk_article(markdown_text)` → returns list of `Chunk` dataclass instances
  - Split by Markdown headers (H1, H2, H3)
  - Each chunk inherits parent header context
  - Image references extracted by regex pattern `[Image: <name>](images/<name>.png)`
- [x] Unit test: `tests/test_index/test_chunker.py`:
  - Test with sample `article.md` from Story 7 output
  - Verify correct number of chunks, correct header assignments
  - Verify image refs are correctly extracted per chunk
  - Test edge cases: article with no images, single-section article

| File | Status |
|------|--------|
| `src/functions/fn_index/chunker.py` | ✅ |
| `src/functions/tests/test_index/test_chunker.py` | ✅ |

#### Definition of Done

- [x] Chunker produces correct chunks from both sample articles
- [x] Each chunk has the correct `section_header` and `image_refs`
- [x] No content is lost or duplicated across chunks
- [x] Tests pass (16 tests, 0.07s)

---

### Story 9 — fn-index: Embedding & Search Indexing ✅

> **Status:** Done

> **Implementation Note:** `azure-ai-inference` `EmbeddingsClient` requires endpoint URL to include `/openai/deployments/{model}` path — plain AI Services endpoint gives 404. Also needs `credential_scopes=["https://cognitiveservices.azure.com/.default"]`. Lazy singleton pattern for client initialization. Index uses HNSW vector search algorithm with 1536 dimensions, `default-profile` and `default-hnsw` names. Documents use merge-or-upload action for idempotent re-indexing.

Implement the embedding and AI Search indexing modules, and the fn-index orchestrator.

#### Deliverables

- [x] Implement `src/functions/fn_index/embedder.py`:
  - `embed_text(text)` → returns `list[float]` (1536-dimension vector)
  - `embed_chunks(chunks)` → returns chunks with `content_vector` populated
  - Calls Azure AI Foundry (`text-embedding-3-small`) via `azure-ai-inference` SDK
  - Handles rate limits / retries
- [x] Implement `src/functions/fn_index/indexer.py`:
  - `ensure_index_exists()` → creates `kb-articles` index if it doesn't exist (with vector search config)
  - `index_chunks(article_id, chunks)` → pushes chunk documents to AI Search
  - Each document follows the index schema from architecture.md
  - Uses merge-or-upload action (idempotent re-indexing)
- [x] Implement `src/functions/fn_index/__init__.py` — `run(article_path)` orchestrator
- [x] Implement `src/functions/fn_index/__main__.py` — CLI entry point for `python -m fn_index`
- [x] Unit test: `tests/test_index/test_embedder.py` — verify embedding returns 1536-dim vector
- [x] Unit test: `tests/test_index/test_indexer.py` — verify document structure matches schema

| File | Status |
|------|--------|
| `src/functions/fn_index/embedder.py` | ✅ |
| `src/functions/fn_index/indexer.py` | ✅ |
| `src/functions/fn_index/__init__.py` | ✅ |
| `src/functions/fn_index/__main__.py` | ✅ |
| `src/functions/tests/test_index/test_embedder.py` | ✅ |
| `src/functions/tests/test_index/test_indexer.py` | ✅ |

#### Definition of Done

- [x] Embedding calls succeed against Azure AI Foundry
- [x] Chunks are pushed to `kb-articles` index with correct schema
- [x] Re-running indexing for the same article updates (not duplicates) existing chunks
- [x] Tests pass (8 tests, 2.92s)

---

### Story 10 — fn-index Local E2E ✅

> **Status:** Done

> **Implementation Note:** `kb-articles` index auto-created on first run with HNSW vector search. Both articles indexed successfully: content-understanding article → 8 chunks, DITA article → 7 chunks, total 15 documents. Index reused on second article (idempotent). Re-running `make index` updates existing chunks via merge-or-upload.

Wire fn-index end-to-end through the shell script and Makefile, and verify the search index is populated correctly.

#### Deliverables

- [x] `scripts/functions/index.sh` iterates `kb/serving/*/` and invokes fn-index per article
- [x] `make index` runs successfully for all articles in `kb/serving/`
- [x] Verify `kb-articles` index in Azure AI Search:
  - [x] Correct number of documents (chunks) per article (8 + 7 = 15 total)
  - [x] `content` field contains chunk text with image descriptions
  - [x] `content_vector` is populated (1536 dimensions)
  - [x] `image_urls` contains valid URLs for chunks with images
  - [x] `article_id`, `title`, `section_header` are populated correctly
- [x] Test a search query in the Azure portal or via CLI to confirm results are relevant

#### Definition of Done

- [x] `make index` runs end-to-end with zero errors
- [x] Both sample articles are searchable in AI Search
- [x] A semantic search query returns relevant chunks with image URLs

---

### Story 11 — Full Pipeline E2E & Documentation ✅

> **Status:** Done

> **Implementation Note:** Clean pipeline run from scratch: `rm -rf kb/serving/*` → `make convert` (both articles processed, ~4 min) → `make index` (15 chunks indexed, ~13 sec). All 75 tests pass in 127s. README.md updated with complete Getting Started instructions. Architecture doc accurate — no implementation deviations found.

Run the complete pipeline end-to-end (`make convert` → `make index`), verify the final result, and update project documentation.

#### Deliverables

- [x] Clean run: delete `kb/serving/` contents, re-run `make convert` then `make index`
- [x] Verify end-to-end:
  - [x] All articles in `kb/staging/` are processed through both stages
  - [x] AI Search index contains correct chunks with vectors and image URLs
  - [x] A search query returns relevant content with associated image links
- [x] Update `README.md` Getting Started section with actual setup/run instructions
- [x] Update `docs/specs/architecture.md` if any implementation deviations were discovered (none found)
- [x] Ensure `make dev-doctor` + `make validate-infra` + `make convert` + `make index` is the complete local workflow
- [x] All unit tests pass: `make test` (75 tests, 127s)

#### Definition of Done

- [x] Full pipeline runs clean from scratch
- [x] README.md has accurate, tested setup and run instructions
- [x] Architecture doc reflects the implemented design
- [x] `make test` passes (75/75)
- [x] Epic marked complete

---

## Implementation Notes

- **Local file I/O, not blob:** For this epic, `fn-convert` and `fn-index` read/write directly to the local `kb/staging/` and `kb/serving/` folders. Blob Storage integration (for Azure-deployed functions) is a future epic.
- **Live Azure services:** Even though functions run locally, they call real Azure endpoints (CU, AI Foundry, AI Search). A valid `.env` with Azure credentials is required.
- **Developer RBAC:** The developer's `az login` identity needs the same RBAC roles as the Function App's managed identity (Cognitive Services OpenAI User, Cognitive Services User, Search Index Data Contributor, Search Service Contributor). Story 2 provides a `make grant-dev-roles` target for this.
- **`.env` from AZD:** Run `azd env get-values > src/functions/.env` after `azd provision` to populate the environment file with real endpoints. See infrastructure.md Outputs section for the full list.
- **Sample articles:** The `kb/staging/` folder already contains sample articles from the spike. These are the test fixtures for this epic.
- **Idempotent:** Both `make convert` and `make index` should be safe to re-run. Convert overwrites existing output; index uses merge-or-upload.
