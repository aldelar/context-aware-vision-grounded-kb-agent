# Epic 001 — Local Pipeline End-to-End

> **Status:** Not Started
> **Created:** February 13, 2026
> **Updated:** February 13, 2026

## Objective

Implement the full ingestion pipeline (`fn-convert` + `fn-index`) as local Python code that processes KB articles from `kb/staging/` through to a populated Azure AI Search index. Functions run locally against local folders but call live Azure services (Content Understanding, AI Foundry, AI Search) provisioned via the existing infrastructure code.

## Success Criteria

- [ ] `make convert` processes every article in `kb/staging/` and writes clean Markdown + images to `kb/serving/`
- [ ] `make index` processes every article in `kb/serving/` and populates the `kb-articles` AI Search index
- [ ] End-to-end: raw HTML article → searchable chunks with image URLs in AI Search
- [ ] Unit tests pass for all core modules

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

### Story 1 — Project Scaffolding ✱

> **Status:** Not Started

Set up the `src/functions/` project structure, dependency management, shared configuration, and update the Makefile and scripts to use the new layout.

#### Deliverables

- [ ] Create `src/functions/` directory structure matching the layout above (empty `__init__.py` files, package folders)
- [ ] Create `src/functions/pyproject.toml` with all required dependencies:
  - `azure-ai-contentunderstanding>=1.0.0b1`
  - `azure-identity>=1.19.0`
  - `azure-storage-blob`
  - `azure-search-documents`
  - `azure-ai-inference`
  - `beautifulsoup4`
  - `python-dotenv`
  - `pytest` (dev dependency)
- [ ] Create `src/functions/.env.sample` listing all required environment variables with placeholder values
- [ ] Implement `src/functions/shared/config.py` — loads `.env`, exposes typed config (CU endpoint, Search endpoint, Foundry endpoint, storage paths, etc.), validates required vars on import
- [ ] Create `scripts/functions/convert.sh` — iterates `kb/staging/*/`, calls the fn-convert entry point per article folder
- [ ] Create `scripts/functions/index.sh` — iterates `kb/serving/*/`, calls the fn-index entry point per article folder
- [ ] Update `Makefile` — `convert` target calls `scripts/functions/convert.sh`, `index` target calls `scripts/functions/index.sh`, `azure-deploy` references new `manage_analyzers.py` path
- [ ] Move existing spike code: move `src/spikes/` contents to `src/spikes/` (no change) and remove old top-level `src/*.py` files if any
- [ ] Add `make test` target to Makefile (runs `cd src/functions && uv run pytest tests/`)
- [ ] `uv sync` succeeds in `src/functions/` with no errors

#### Definition of Done

- [ ] `cd src/functions && uv sync` installs all dependencies
- [ ] `make help` shows updated target descriptions
- [ ] `make test` runs (with 0 tests collected — no tests yet)
- [ ] `.env.sample` documents every required variable

---

### Story 2 — Validate Azure Infrastructure ✱

> **Status:** Not Started

Create a validation script/make target that confirms the deployed Azure infrastructure is ready for local pipeline execution. This unblocks all subsequent stories.

#### Deliverables

- [ ] Create `scripts/functions/validate-infra.sh` (or a Python script under `src/functions/`) that checks:
  - Azure AI Search service is reachable and `kb-articles` index exists with the expected schema
  - Content Understanding resource is reachable
  - `kb-image-analyzer` custom analyzer exists in the CU resource
  - Azure AI Foundry embedding endpoint is reachable (`text-embedding-3-small`)
  - Staging and serving blob storage accounts/containers are accessible (or local `kb/staging/` and `kb/serving/` exist)
- [ ] Add `make validate-infra` target to Makefile
- [ ] Implement `src/functions/manage_analyzers.py` — CLI with `deploy` and `delete` subcommands for the `kb-image-analyzer` (reads definition from `analyzers/kb-image-analyzer.json`)
- [ ] Create `analyzers/kb-image-analyzer.json` with the analyzer definition from architecture.md
- [ ] Validation script prints clear pass/fail per check with actionable error messages
- [ ] If `kb-articles` index does not exist, offer to create it (or document the manual step)

#### Definition of Done

- [ ] `make validate-infra` passes against the provisioned Azure environment
- [ ] `make azure-deploy` successfully deploys the CU analyzer
- [ ] `kb-image-analyzer` is confirmed queryable in the CU resource
- [ ] `kb-articles` index is confirmed in Azure AI Search with correct field schema

---

### Story 3 — fn-convert: HTML Text Extraction ✱

> **Status:** Not Started

Implement the CU text extraction module that sends HTML to `prebuilt-documentSearch` and returns clean Markdown.

#### Deliverables

- [ ] Implement `src/functions/fn_convert/cu_text.py`:
  - Accepts HTML file path (local), reads content
  - Sends to CU `prebuilt-documentSearch` analyzer (content type `text/html`)
  - Returns the extracted Markdown string and the Summary field
  - Handles CU API errors gracefully with clear logging
- [ ] Implement `src/functions/shared/cu_client.py`:
  - Factory function that creates an authenticated CU client using `DefaultAzureCredential`
  - Reads endpoint from shared config
- [ ] Unit test: `tests/test_convert/test_cu_text.py` — test with a sample HTML article from `kb/staging/`
- [ ] Verify extracted Markdown quality against the spike results in `kb/3_md/`

#### Definition of Done

- [ ] `cu_text.py` produces Markdown from a sample KB article HTML
- [ ] Output quality matches or exceeds spike results
- [ ] CU client authenticates using managed identity / DefaultAzureCredential
- [ ] Tests pass

---

### Story 4 — fn-convert: HTML DOM Parsing ✱

> **Status:** Not Started

Implement the BeautifulSoup-based HTML parser that extracts image and link maps from the source HTML DOM.

#### Deliverables

- [ ] Implement `src/functions/fn_convert/html_parser.py`:
  - `extract_image_map(html_path)` → returns ordered list of `(preceding_text, image_filename)` tuples
  - `extract_link_map(html_path)` → returns list of `(link_text, url)` tuples
  - Handles DITA-generated HTML structure (images inside `<div class="info">` blocks following step instructions)
  - Robust to missing/malformed tags (logs warnings, skips gracefully)
- [ ] Unit test: `tests/test_convert/test_html_parser.py`:
  - Test `extract_image_map` against both sample articles in `kb/staging/`
  - Test `extract_link_map` against both sample articles
  - Test edge cases: no images, no links, malformed HTML
- [ ] Verify image map ordering matches visual document order

#### Definition of Done

- [ ] Image map correctly identifies all images and their preceding text for both sample articles
- [ ] Link map captures all hyperlinks with correct URLs
- [ ] Tests pass with assertions on expected image count and link count

---

### Story 5 — fn-convert: Image Analysis ✱

> **Status:** Not Started

Implement the per-image CU analysis module that sends each article image to the custom `kb-image-analyzer` and returns structured descriptions.

#### Deliverables

- [ ] Implement `src/functions/fn_convert/cu_images.py`:
  - `analyze_image(image_path)` → returns dict with `Description`, `UIElements`, `NavigationPath`
  - `analyze_all_images(image_paths)` → returns ordered list of image analysis results
  - Sends each image to `kb-image-analyzer` analyzer in CU
  - Handles images that fail analysis gracefully (log error, return placeholder description)
- [ ] Unit test: `tests/test_convert/test_cu_images.py`:
  - Test with sample `.image` files from `kb/staging/`
  - Verify returned fields (Description is non-empty, UIElements is a list, NavigationPath is a string)
- [ ] Verify description quality — descriptions should mention specific UI elements visible in the screenshots

#### Definition of Done

- [ ] Each image in the sample articles gets a meaningful `Description`
- [ ] `UIElements` and `NavigationPath` are populated for UI screenshots
- [ ] Failed images produce a logged warning and a fallback description, not a crash
- [ ] Tests pass

---

### Story 6 — fn-convert: Merge & Output ✱

> **Status:** Not Started

Implement the merge module that combines CU Markdown, recovered hyperlinks, and image description blocks into the final `article.md`, and the fn-convert orchestrator.

#### Deliverables

- [ ] Implement `src/functions/fn_convert/merge.py`:
  - `recover_links(markdown, link_map)` → returns Markdown with hyperlinks re-injected by text-matching link labels
  - `insert_image_blocks(markdown, image_map, image_analyses)` → returns Markdown with image description blocks inserted at correct positions (after preceding text match)
  - Each image block follows the format from architecture.md (blockquote with image link + description)
  - Handles unmatched images/links gracefully (logs, skips)
- [ ] Implement `src/functions/fn_convert/__init__.py` — `run(article_path, output_path)` orchestrator:
  1. Call `cu_text.extract(article_path/index.html)` → Markdown
  2. Call `html_parser.extract_image_map(article_path/index.html)` → image map
  3. Call `html_parser.extract_link_map(article_path/index.html)` → link map
  4. Call `cu_images.analyze_all_images(article_path/*.image)` → image analyses
  5. Call `merge.recover_links(markdown, link_map)` → Markdown with links
  6. Call `merge.insert_image_blocks(markdown, image_map, image_analyses)` → final Markdown
  7. Write `output_path/article.md`
  8. Copy/rename `.image` files → `output_path/images/<name>.png`
- [ ] Implement `src/functions/shared/blob.py`:
  - For local mode: simple file I/O wrappers (read file, write file, copy file, list directory)
  - Functions take a base path and article-relative paths
- [ ] Unit test: `tests/test_convert/test_merge.py`:
  - Test `recover_links` with known markdown + link map
  - Test `insert_image_blocks` with known markdown + image data
  - Test edge cases: no links to recover, no images to insert

#### Definition of Done

- [ ] `fn_convert.run()` produces a well-formed `article.md` with inline image blocks and recovered hyperlinks
- [ ] Images are copied and renamed to `images/<name>.png` in the output folder
- [ ] Output matches the format specified in architecture.md
- [ ] Tests pass

---

### Story 7 — fn-convert Local E2E ✱

> **Status:** Not Started

Wire fn-convert end-to-end through the shell script and Makefile, and verify with the sample KB articles.

#### Deliverables

- [ ] `scripts/functions/convert.sh` iterates `kb/staging/*/` and invokes fn-convert per article
- [ ] `make convert` runs successfully for all articles in `kb/staging/`
- [ ] Verify `kb/serving/{article-id}/article.md` exists and is well-formed for each article
- [ ] Verify `kb/serving/{article-id}/images/` contains renamed PNGs for each article
- [ ] Manually review output Markdown for both sample articles:
  - [ ] Text structure preserved (headings, paragraphs, tables)
  - [ ] Hyperlinks recovered and working
  - [ ] Image description blocks present at correct positions
  - [ ] Image references point to valid files in `images/`

#### Definition of Done

- [ ] `make convert` runs end-to-end with zero errors
- [ ] Both sample articles produce complete, correct output in `kb/serving/`
- [ ] Output reviewed and confirmed to match architecture spec

---

### Story 8 — fn-index: Chunking & Image Mapping ✱

> **Status:** Not Started

Implement the Markdown chunker that splits articles by headers and maps image references per chunk.

#### Deliverables

- [ ] Implement `src/functions/fn_index/chunker.py`:
  - `chunk_article(markdown_text)` → returns list of chunk dicts:
    ```python
    {
      "content": "...",           # chunk text including image blocks
      "title": "...",             # article title (H1)
      "section_header": "...",    # H2/H3 header for this chunk
      "image_refs": ["img1.png"]  # image filenames referenced in this chunk
    }
    ```
  - Split by Markdown headers (H1, H2, H3)
  - Each chunk inherits parent header context
  - Image references extracted by regex pattern `[Image: <name>](images/<name>.png)`
- [ ] Unit test: `tests/test_index/test_chunker.py`:
  - Test with sample `article.md` from Story 7 output
  - Verify correct number of chunks, correct header assignments
  - Verify image refs are correctly extracted per chunk
  - Test edge cases: article with no images, single-section article

#### Definition of Done

- [ ] Chunker produces correct chunks from both sample articles
- [ ] Each chunk has the correct `section_header` and `image_refs`
- [ ] No content is lost or duplicated across chunks
- [ ] Tests pass

---

### Story 9 — fn-index: Embedding & Search Indexing ✱

> **Status:** Not Started

Implement the embedding and AI Search indexing modules, and the fn-index orchestrator.

#### Deliverables

- [ ] Implement `src/functions/fn_index/embedder.py`:
  - `embed_text(text)` → returns `list[float]` (1536-dimension vector)
  - `embed_chunks(chunks)` → returns chunks with `content_vector` populated
  - Calls Azure AI Foundry (`text-embedding-3-small`) via `azure-ai-inference` SDK
  - Handles rate limits / retries
- [ ] Implement `src/functions/fn_index/indexer.py`:
  - `ensure_index_exists()` → creates `kb-articles` index if it doesn't exist (with vector search config)
  - `index_chunks(article_id, chunks)` → pushes chunk documents to AI Search
  - Each document follows the index schema from architecture.md:
    - `id` = `{article_id}_{chunk_index}`
    - `article_id`, `chunk_index`, `content`, `content_vector`
    - `image_urls` = resolved blob/local URLs for each image ref
    - `title`, `section_header`, `key_topics`
  - Uses merge-or-upload action (idempotent re-indexing)
- [ ] Implement `src/functions/fn_index/__init__.py` — `run(article_path)` orchestrator:
  1. Read `article_path/article.md`
  2. Chunk via `chunker.chunk_article()`
  3. Embed via `embedder.embed_chunks()`
  4. Index via `indexer.index_chunks()`
- [ ] Unit test: `tests/test_index/test_embedder.py` — verify embedding returns 1536-dim vector
- [ ] Unit test: `tests/test_index/test_indexer.py` — verify document structure matches schema

#### Definition of Done

- [ ] Embedding calls succeed against Azure AI Foundry
- [ ] Chunks are pushed to `kb-articles` index with correct schema
- [ ] Re-running indexing for the same article updates (not duplicates) existing chunks
- [ ] Tests pass

---

### Story 10 — fn-index Local E2E ✱

> **Status:** Not Started

Wire fn-index end-to-end through the shell script and Makefile, and verify the search index is populated correctly.

#### Deliverables

- [ ] `scripts/functions/index.sh` iterates `kb/serving/*/` and invokes fn-index per article
- [ ] `make index` runs successfully for all articles in `kb/serving/`
- [ ] Verify `kb-articles` index in Azure AI Search:
  - [ ] Correct number of documents (chunks) per article
  - [ ] `content` field contains chunk text with image descriptions
  - [ ] `content_vector` is populated (1536 dimensions)
  - [ ] `image_urls` contains valid URLs for chunks with images
  - [ ] `article_id`, `title`, `section_header` are populated correctly
- [ ] Test a search query in the Azure portal or via CLI to confirm results are relevant

#### Definition of Done

- [ ] `make index` runs end-to-end with zero errors
- [ ] Both sample articles are searchable in AI Search
- [ ] A semantic search query returns relevant chunks with image URLs

---

### Story 11 — Full Pipeline E2E & Documentation ✱

> **Status:** Not Started

Run the complete pipeline end-to-end (`make convert` → `make index`), verify the final result, and update project documentation.

#### Deliverables

- [ ] Clean run: delete `kb/serving/` contents, re-run `make convert` then `make index`
- [ ] Verify end-to-end:
  - [ ] All articles in `kb/staging/` are processed through both stages
  - [ ] AI Search index contains correct chunks with vectors and image URLs
  - [ ] A search query returns relevant content with associated image links
- [ ] Update `README.md` Getting Started section with actual setup/run instructions
- [ ] Update `docs/specs/architecture.md` if any implementation deviations were discovered
- [ ] Ensure `make dev-doctor` + `make validate-infra` + `make convert` + `make index` is the complete local workflow
- [ ] All unit tests pass: `make test`

#### Definition of Done

- [ ] Full pipeline runs clean from scratch
- [ ] README.md has accurate, tested setup and run instructions
- [ ] Architecture doc reflects the implemented design
- [ ] `make test` passes
- [ ] Epic marked complete

---

## Implementation Notes

- **Local file I/O, not blob:** For this epic, `fn-convert` and `fn-index` read/write directly to the local `kb/staging/` and `kb/serving/` folders. Blob Storage integration (for Azure-deployed functions) is a future epic.
- **Live Azure services:** Even though functions run locally, they call real Azure endpoints (CU, AI Foundry, AI Search). A valid `.env` with Azure credentials is required.
- **Sample articles:** The `kb/staging/` folder already contains sample articles from the spike. These are the test fixtures for this epic.
- **Idempotent:** Both `make convert` and `make index` should be safe to re-run. Convert overwrites existing output; index uses merge-or-upload.
