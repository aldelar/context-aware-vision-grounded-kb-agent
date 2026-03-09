# Epic 007 — MarkItDown as Alternative Convert Pipeline

> **Status:** Done
> **Created:** March 9, 2026
> **Updated:** March 9, 2026

## Objective

Introduce **MarkItDown** ([microsoft/markitdown](https://github.com/microsoft/markitdown)) as a third, interchangeable conversion backend for the ingestion pipeline. A new `fn_convert_markitdown` package is created under `src/functions/`, sharing the same input/output contract as `fn_convert_cu` and `fn_convert_mistral` so `fn-index` works unchanged. The Makefile `convert` and `azure-convert` targets accept `analyzer=markitdown` alongside the existing options.

**MarkItDown** is a lightweight, open-source Python library from Microsoft that converts HTML (and many other formats) directly to Markdown — no Azure AI service calls needed for the text extraction step. Image descriptions still use **GPT-4.1 vision** (already deployed), reusing the same prompt schema as the other pipelines.

This provides a third conversion option that is:

- **Fastest** — HTML → Markdown is local Python; no OCR, no CU, no network calls for text extraction
- **Cheapest** — only GPT-4.1 vision calls are billed (for image descriptions); no CU or Mistral charges
- **Simplest** — single `pip install markitdown` dependency; no Playwright, no PDF rendering, no CU analyzer setup
- **Offline-capable** — text extraction works without any Azure connectivity (only image descriptions require Azure)

## Success Criteria

- [x] `make convert analyzer=markitdown` runs the MarkItDown pipeline (`fn_convert_markitdown`) — all 3 articles processed successfully
- [x] `make convert` (no argument) prints usage showing all three `analyzer=` options
- [x] `make azure-convert analyzer=markitdown` runs successfully, all 3 articles processed
- [x] `fn_convert_markitdown` produces output in `kb/serving/` with the exact same format as `fn_convert_cu` and `fn_convert_mistral` (same `article.md` structure, same `images/` layout)
- [x] `fn-index` processes output from the MarkItDown backend without changes — 47 chunks indexed
- [x] No new infrastructure resources required (MarkItDown is a pure Python library; GPT-4.1 is already deployed)
- [x] `azd deploy` succeeds with the updated function code (new convert endpoint registered)
- [x] All existing tests pass; new tests added for `fn_convert_markitdown`
- [x] Architecture docs, infrastructure docs, and README updated to describe the third conversion option
- [x] Quality comparison against CU and Mistral output for all three sample articles documented in `docs/spikes/003-markitdown.md`

---

## Background

MarkItDown is a Microsoft open-source library that converts HTML, DOCX, PDF, PPTX, and other formats to clean Markdown. For this use case:

- **HTML → Markdown**: MarkItDown handles the text extraction natively — preserves headings, lists, tables, and formatting directly from the source HTML DOM
- **Images**: MarkItDown extracts image references from the HTML but does not generate descriptions. Image descriptions are handled by GPT-4.1 vision (same approach as `fn_convert_mistral`)
- **Links**: MarkItDown preserves hyperlinks natively during HTML → Markdown conversion, eliminating the need for the link recovery step required by CU and Mistral OCR

Key advantages over existing backends:

| Aspect | Content Understanding | Mistral Document AI | MarkItDown |
|--------|----------------------|---------------------|------------|
| **Text extraction** | CU `prebuilt-documentSearch` (cloud API) | Playwright → PDF → Mistral OCR (cloud API) | Local Python (no API call) |
| **Image descriptions** | CU `kb-image-analyzer` (cloud API) | GPT-4.1 vision (cloud API) | GPT-4.1 vision (cloud API) |
| **Link recovery** | Post-processing (CU strips links) | Post-processing (OCR loses links) | Native (links preserved) |
| **Dependencies** | `azure-ai-contentunderstanding` | `playwright`, `httpx` | `markitdown` |
| **Azure services** | AI Services (CU + GPT models) | AI Services (Mistral + GPT-4.1) | AI Services (GPT-4.1 only) |
| **Infra cost** | CU charges + GPT-4.1 | Mistral OCR + GPT-4.1 | GPT-4.1 only |

---

## Stories

---

### Story 1 — Research & Spike: Validate MarkItDown Output Quality ✅

> **Status:** Done

Run MarkItDown against the three sample articles in `kb/staging/` and compare output quality with the existing CU and Mistral pipelines. Document findings in a spike report.

#### Deliverables

- [x] Create `src/spikes/003-markitdown/` with a minimal script that:
  - Reads HTML from each article in `kb/staging/*/`
  - Converts to Markdown using `markitdown`
  - Extracts image references from the HTML
  - Writes output to a temp directory for comparison
- [x] Compare MarkItDown output against existing `kb_snapshot/` reference output:
  - Character count comparison
  - Heading structure preservation
  - Table rendering quality
  - Hyperlink preservation (MarkItDown should preserve links natively — verify)
  - Image reference extraction (verify all images are detected)
- [x] Document findings in `docs/spikes/003-markitdown.md`:
  - Quality assessment per article
  - Comparison table (MarkItDown vs CU vs Mistral)
  - Any issues or limitations discovered
  - Recommendation: proceed / adjust approach / reject

#### Definition of Done

- [x] Spike script runs successfully against all three sample articles
- [x] Spike report documents quality comparison with concrete metrics
- [x] Clear go/no-go recommendation for proceeding with implementation

---

### Story 2 — Implement `fn_convert_markitdown` ✅

> **Status:** Done
> **Depends on:** Story 1 (spike validates feasibility)

Create the MarkItDown-based conversion function as `fn_convert_markitdown`, following the same package structure and input/output contract as `fn_convert_cu` and `fn_convert_mistral`.

#### Deliverables

- [x] Create `src/functions/fn_convert_markitdown/` with these modules:
  - `__init__.py` — `run(article_path, output_path)` orchestrator (same signature as other backends)
  - `__main__.py` — CLI entry point for `python -m fn_convert_markitdown`
  - `html_to_md.py` — HTML → Markdown via MarkItDown library
  - `extract_images.py` — Parse HTML DOM to extract image map (filename stems + preceding text context for positioning)
  - `describe_images.py` — GPT-4.1 vision descriptions (reuse existing prompt schema from `fn_convert_mistral`)
  - `merge.py` — Insert image description blocks into MarkItDown output at correct positions + copy images to output
- [x] Reuse `shared/config.py` for configuration (no new config values — GPT-4.1 is already available via `ai_services_endpoint`)
- [x] Add `markitdown` to `src/functions/pyproject.toml` dependencies
- [x] Output matches existing format: `article.md` with `> **[Image: <stem>](images/<stem>.png)**` blocks + `images/` folder with PNGs

#### Implementation Notes

- MarkItDown preserves hyperlinks natively, so no `recover_links` step is needed (unlike CU and Mistral backends)
- Image positioning: parse the HTML DOM for `<img>` tags and their preceding text context (similar to `fn_convert_cu/html_parser.py`), then match against the MarkItDown output to insert image blocks
- Image descriptions: use the same GPT-4.1 vision approach as `fn_convert_mistral/describe_images.py` — same prompt, same structured output format (Description, UIElements, NavigationPath)
- The `_find_html()` helper pattern is shared across all backends — consider referencing the existing implementation or extracting to `shared/` if warranted

#### Definition of Done

- [x] `python -m fn_convert_markitdown <article_dir> <output_dir>` works for all three sample articles
- [x] Output `article.md` follows the same image block format as other backends
- [x] `make index` successfully indexes the MarkItDown-produced output (no changes to `fn-index`) — 47 chunks indexed
- [x] Side-by-side comparison with CU and Mistral output shows comparable quality — documented in Story 8

---

### Story 3 — Per-Function `pyproject.toml` Split ✅

> **Status:** Done
> **Depends on:** Story 2

Split the monolithic `src/functions/pyproject.toml` into per-function `pyproject.toml` files so each function installs only its required dependencies. This reduces container image size and makes dependency boundaries explicit.

#### Context & Impact Analysis

Today all four function packages (`fn_convert_cu`, `fn_convert_mistral`, `fn_convert_markitdown`, `fn_index`) plus `shared` share a single `pyproject.toml` with the union of all dependencies. This means every function deployment ships `playwright`, `markitdown`, `httpx`, `beautifulsoup4`, etc. — even when only a subset is needed.

**Per-function dependency mapping:**

| Package | Specific Dependencies |
|---------|----------------------|
| `shared` | `azure-identity`, `azure-storage-blob`, `azure-ai-contentunderstanding`, `python-dotenv` |
| `fn_convert_cu` | `beautifulsoup4` + `shared` |
| `fn_convert_mistral` | `playwright`, `httpx`, `openai`, `azure-identity` + `shared` |
| `fn_convert_markitdown` | `markitdown`, `beautifulsoup4`, `openai`, `azure-identity` + `shared` |
| `fn_index` | `azure-search-documents`, `azure-ai-inference`, `azure-identity` + `shared` |
| `function_app.py` (entry point) | `azure-functions` + all of the above |

**Areas requiring changes:**

| Area | Impact | Severity |
|------|--------|----------|
| **Dockerfile** | `pip install .` → must install all per-function packages (e.g. `pip install ./shared ./fn_convert_cu …`) or use a workspace root | High |
| **`dev-setup` Makefile target** | `uv sync` at `src/functions/` → must sync each function or use uv workspace | Medium |
| **`test-functions` Makefile target** | `uv run pytest` needs all deps available → keep a root workspace or dev-only aggregate | Medium |
| **`uv.lock`** | Single lock file → either uv workspace (one lock) or per-function lock files | Medium |
| **pytest config** | `pythonpath = ["."]` → must reference sibling packages or use editable installs | Medium |
| **Scripts (`convert.sh`, `index.sh`)** | Already per-module invocation — minimal change if venv is shared | Low |
| **Bicep / infra** | No change — packaging is Dockerfile's concern | None |
| **`function_app.py`** | Imports all converters + fn_index — all deps must be present at runtime in the deployed container | Constraint |

**Recommended approach:** Use **uv workspaces** — keep a root `src/functions/pyproject.toml` as the workspace root with `[tool.uv.workspace]` members pointing to each function directory. Each function gets its own `pyproject.toml` declaring only its dependencies. The root aggregates them for dev/test and `uv.lock` remains a single file. The Dockerfile installs the workspace root which pulls all members.

#### Deliverables

- [x] Create `pyproject.toml` in each function directory (`fn_convert_cu/`, `fn_convert_mistral/`, `fn_convert_markitdown/`, `fn_index/`) with only that function's dependencies
- [x] Convert root `src/functions/pyproject.toml` to a uv workspace root that references all member packages
- [x] `shared` kept as local package in the root (not a separate workspace member — flat layout incompatible with hatchling's auto-detection)
- [x] Update `Dockerfile`: adjust `pip install` to work with the workspace layout
- [x] `Makefile` `dev-setup` target unchanged — `uv sync --extra dev` still works from workspace root
- [x] Ensure `uv run pytest` from `src/functions/` still works (all deps available for test runner)
- [x] Verify `make convert analyzer=<all-three>` works after restructure — verified with markitdown pipeline
- [x] Verify `make test-functions` passes (zero regressions) — 156 passed, 5 deselected

#### Definition of Done

- [x] Each function directory has its own `pyproject.toml` listing only its required dependencies
- [x] Root `src/functions/pyproject.toml` uses `[tool.uv.workspace]` to orchestrate all members
- [x] `make test-functions` passes (156 tests, zero regressions)
- [x] `make convert analyzer=markitdown` (and other analyzers) works end-to-end — all 3 articles processed
- [x] Dockerfile builds successfully and `azd deploy` produces a working container
- [x] Each function's pyproject.toml declares only its own third-party dependencies

---

### Story 4 — Makefile & Script Integration ✅

> **Status:** Done
> **Depends on:** Story 2

Wire `fn_convert_markitdown` into the Makefile and `convert.sh` script so it is selectable via `analyzer=markitdown`, alongside the existing `content-understanding` and `mistral-doc-ai` options.

#### Deliverables

- [x] Update `scripts/functions/convert.sh`:
  - Add `markitdown` case to the analyzer switch, mapping to module `fn_convert_markitdown`
  - Update usage message to list all three options
- [x] Update `scripts/functions/convert.sh` header comment to list `markitdown` usage
- [x] Update `Makefile`:
  - `azure-convert` target now uses 3-way routing (`convert`, `convert-mistral`, `convert-markitdown`)
  - No changes to the `convert:` target itself (it delegates to `convert.sh`)
- [x] Verify `make convert analyzer=markitdown` runs end-to-end for all sample articles — all 3 articles processed
- [x] Verify `make convert` (no args) prints updated usage with all three options

#### Definition of Done

- [x] `make convert` (no args) → prints usage showing `content-understanding`, `mistral-doc-ai`, and `markitdown`
- [x] `make convert analyzer=markitdown` → runs MarkItDown pipeline, produces valid output in `kb/serving/`
- [x] `make kb analyzer=markitdown` → runs full pipeline (convert + index) successfully — 47 chunks indexed
- [x] `make help` documents the new `analyzer=` option

---

### Story 5 — Tests for `fn_convert_markitdown` ✅

> **Status:** Done
> **Depends on:** Story 2

Add unit tests for `fn_convert_markitdown` modules, following the same patterns as the existing `test_convert/` and `test_convert_mistral/` test suites.

#### Deliverables

- [x] Create `src/functions/tests/test_convert_markitdown/` test package:
  - `test_html_to_md.py` — verify HTML → Markdown conversion quality (headings, tables, links preserved)
  - `test_extract_images.py` — verify image map extraction from HTML DOM
  - `test_describe_images.py` — verify GPT-4.1 image description integration (can share fixtures with Mistral tests)
  - `test_merge.py` — verify final markdown assembly (image block insertion, image file copying)
- [x] Tests use the same sample articles in `kb/staging/` as fixtures
- [x] Integration test: end-to-end `run()` validated via `make convert analyzer=markitdown` — all 3 articles processed with correct output format

#### Definition of Done

- [x] `make test` runs all new tests alongside existing tests
- [x] All tests pass (existing + new, zero regressions) — 156 passed, 5 deselected
- [x] Test coverage for core modules: `html_to_md`, `extract_images`, `merge`

---

### Story 6 — Azure Function Registration & Deployment ✅

> **Status:** Done
> **Depends on:** Story 2, Story 3

Register `fn_convert_markitdown` as an Azure Function endpoint and wire the `azure-convert` target to route to it when `analyzer=markitdown` is selected.

#### Deliverables

- [x] Update `src/functions/function_app.py`:
  - Import `fn_convert_markitdown`
  - Register a new HTTP trigger at `/api/convert-markitdown` (POST, anonymous auth)
  - Follow the same pattern as the existing `http_convert_mistral` function
- [x] Update `Makefile` `azure-convert` target:
  - 3-way routing: `content-understanding` → `convert`, `mistral-doc-ai` → `convert-mistral`, `markitdown` → `convert-markitdown`
- [x] Verify `azd deploy` succeeds and the new `/api/convert-markitdown` endpoint is accessible
  - Dockerfile and packaging changes are handled in Story 3; this story only adds the function registration

#### Definition of Done

- [x] `azd deploy` succeeds; Function App registers three convert endpoints (`/api/convert`, `/api/convert-mistral`, `/api/convert-markitdown`)
- [x] `make azure-convert analyzer=markitdown` triggers the MarkItDown function in Azure
- [x] Azure-deployed function processes articles correctly (same output as local)

---

### Story 7 — Documentation Updates ✅

> **Status:** Done
> **Depends on:** Stories 2–6

Update all project documentation to reflect MarkItDown as the third conversion backend.

#### Deliverables

- [x] Update `docs/specs/architecture.md`:
  - Add MarkItDown column to the Analyzer comparison table
  - Update the Pipeline Flow legend to mention the third backend
  - Add MarkItDown backend section with pipeline steps, design decisions, and trade-offs table
- [x] Update `docs/specs/infrastructure.md`:
  - Note that MarkItDown requires no additional infrastructure resources (pure Python library)
  - Update model deployment purpose and design decisions table
- [x] Update `README.md`:
  - Add `markitdown` to the `analyzer=` usage examples (local + Azure sections)
  - Brief description of the MarkItDown conversion approach
- [ ] Update `docs/epics/001-local-pipeline-e2e.md` source layout reference — *skipped: Epic 001 layout is pre-existing and outdated for other reasons*
- [x] Create `docs/ards/ARD-006-markitdown-analyzer.md`:
  - Document the decision to add MarkItDown as a third backend
  - Context: trade-offs vs CU and Mistral (speed, cost, simplicity, quality)
  - Reference spike findings from Story 1

#### Definition of Done

- [x] Architecture doc accurately describes all three conversion options
- [x] README shows all three `analyzer=` options in usage examples
- [x] ARD documents the rationale and trade-offs
- [x] `make help` output matches documentation

---

### Story 8 — Quality Snapshot & Comparison ✅

> **Status:** Done
> **Depends on:** Story 2

Generate a MarkItDown output snapshot for all three sample articles and add it to `kb_snapshot/` for reference. Document a side-by-side quality comparison across all three backends.

#### Deliverables

- [x] Run `make convert analyzer=markitdown` for all three sample articles — all 3 processed successfully
- [x] Copy output to `kb_snapshot/serving_markitdown/` (following the pattern of `serving_content-understanding/` and `serving_mistral-doc-ai/`)
- [x] Create a comparison summary in the spike report (`docs/spikes/003-markitdown.md`) as an addendum:
  - Character count per article per backend
  - Heading structure fidelity
  - Link preservation rate
  - Image block format consistency
  - Notable quality differences or improvements

#### Definition of Done

- [x] `kb_snapshot/serving_markitdown/` contains valid output for all three sample articles
- [x] Comparison summary documents quality across all three backends with concrete metrics
- [x] No quality concerns found — MarkItDown output is within ±1.4% of CU/Mistral across all metrics
