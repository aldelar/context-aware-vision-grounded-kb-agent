# Epic 014 — Extended Data Sources: Phase 1 (HTML, PDF, PPTX, DOCX)

> **Status:** Draft
> **Created:** March 19, 2026
> **Updated:** March 19, 2026

## Objective

Rebuild the KB pipeline to support **4 document formats** (HTML, PDF, PPTX, DOCX) across **3 departments**, with a clean `original/` + `derived/` serving structure, `article` → `document` terminology rename, persona switcher in the web UI, and all accompanying index schema changes. This is Phase 1 of the Extended Data Sources roadmap from [Research 007](../research/007-extended-data-sources-support.md).

After this epic:

- **Multi-format pipeline** — `fn-convert` (MarkItDown) processes HTML, PDF, PPTX, and DOCX; CU/Mistral skip non-HTML with WARNING
- **Clean serving structure** — every document uses `original/` + `derived/images/` from day one, with `metadata.json` carrying `department`, `source_type`, and `original` fields
- **Terminology rename complete** — `article` → `document` across all code, paths, index fields, API routes, and tests
- **Index schema upgraded** — `kb-documents` index with `document_id`, `source_type`, `original_url` fields
- **Persona switcher** — 3-persona toggle in Chainlit UI (Sam/Support, Jordan/Marketing, Casey/Engineering) controlling department-scoped search
- **Vision middleware works for all formats** — images from PDFs, PPTXs, and HTMLs all flow through `derived/images/` to the LLM
- **"View Original" button** — users can open/download the source document from citation panels

## Success Criteria

- [ ] `article` → `document` rename complete across all services, paths, index fields, API routes, and tests
- [ ] Serving format uses `original/` + `derived/images/` structure for all documents
- [ ] `metadata.json` includes `department`, `source_type`, and `original` fields
- [ ] `fn-convert` (MarkItDown) processes HTML, PDF, PPTX, and DOCX documents
- [ ] CU and Mistral converters skip non-HTML with WARNING log (no errors)
- [ ] Each converter declares `SUPPORTED_FORMATS` and uses `detect_source_type()` 
- [ ] PDF images extracted and placed in `derived/images/` (approach validated by Epic 013 spike)
- [ ] PPTX images and speaker notes extracted (approach validated by Epic 013 spike)
- [ ] AI Search index renamed to `kb-documents` with `document_id`, `source_type`, `original_url` fields
- [ ] Vision middleware reads from `derived/images/` path
- [ ] Persona switcher in Chainlit UI toggles between Support/Marketing/Engineering
- [ ] Agent answers differ per persona (same question, different department-scoped results)
- [ ] "View Original" button on citations links to source document via `original_url`
- [ ] Source type badge (HTML/PDF/PPTX/DOCX) shown on citation elements
- [ ] All existing tests updated for rename; new tests for multi-format and persona switcher
- [ ] `make test` passes with zero regressions
- [ ] Epic doc updated with completion status

---

## Background

See [docs/research/007-extended-data-sources-support.md](../research/007-extended-data-sources-support.md) for the full research proposal. Key sections: 5 (Serving Format), 6 (Architecture Changes), 7 (Phase 1 Roadmap).

### Depends On

| Epic | Dependency |
|------|------------|
| Epic 012 | Content creation — documents must exist in staging before pipeline can process them |
| Epic 013 | PDF/PPTX spike — image extraction approach and speaker notes handling must be validated |

### Current vs. Proposed

| Aspect | Current | After Epic 014 |
|--------|---------|----------------|
| Terminology | `article` / `article_id` / `kb-articles` | `document` / `document_id` / `kb-documents` |
| Source formats | HTML only | HTML, PDF, PPTX, DOCX |
| Serving structure | `article.md` + `images/` + `metadata.json` | `document.md` + `original/` + `derived/images/` + `metadata.json` |
| Metadata fields | `department` | `department`, `source_type`, `original` |
| Index fields | `article_id`, `image_urls` | `document_id`, `image_urls`, `source_type`, `original_url` |
| Converter model | All assume HTML | Each declares `SUPPORTED_FORMATS`; unsupported → skip with WARNING |
| Vision middleware path | `images/` | `derived/images/` |
| Web UI personas | None (dev mode defaults to engineering) | 3-persona toggle: Sam/Jordan/Casey |
| Citation UI | Text-only refs | Source type badge + "View Original" button |

---

### Story 1 — Terminology Rename: `article` → `document`

> **Status:** Not Started
> **Depends on:** None

Rename all `article` references to `document` across the entire codebase. Since we're rebuilding the index from scratch (new content from Epic 012), there's no migration needed — the rename is a clean sweep.

#### Deliverables

- [ ] **Shared utilities** — `src/functions/shared/blob_storage.py`:
  - `list_articles()` → `list_documents()`
  - `download_article()` → `download_document()`
  - `upload_article()` → `upload_document()`
- [ ] **Indexer** — `src/functions/fn_index/indexer.py`:
  - Index name: `kb-articles` → `kb-documents`
  - Field: `article_id` → `document_id`
- [ ] **Chunker** — `src/functions/fn_index/chunker.py`:
  - `chunk_article()` → `chunk_document()`
  - `article_title` → `document_title`
- [ ] **Converters** — `src/functions/fn_convert_*/function_app.py`:
  - Variable names, log messages: `article` → `document`
- [ ] **Agent image service** — `src/agent/agent/image_service.py`:
  - `download_image(article_id, ...)` → `download_image(document_id, ...)`
  - API route: `/api/images/{article_id}/...` → `/api/images/{document_id}/...`
- [ ] **Web app image service** — `src/web-app/app/image_service.py`:
  - Same changes as agent image service
- [ ] **Web app main** — `src/web-app/app/main.py`:
  - `article_id` references in Citation handling, image proxy route
- [ ] **Web app models** — `src/web-app/app/models.py`:
  - `Citation.article_id` → `Citation.document_id`
- [ ] **Agent search tool** — `src/agent/agent/search_tool.py` or `kb_agent.py`:
  - Field references in search results parsing
- [ ] **Serving file** — `article.md` → `document.md` (in converter output)
- [ ] **All test files** — update all assertions, fixtures, mocks referencing article

#### Implementation Notes

- See Research 007, Section 6.1 for the complete rename mapping table
- This is a mechanical rename — find-and-replace with careful review
- The AI Search index `kb-documents` is created fresh on `make index` (no migration)
- API routes change: `/api/images/{article_id}/...` → `/api/images/{document_id}/...`
- Run `make test` after each service to catch missed renames

#### Definition of Done

- [ ] `grep -rE "article_id|article_dir|article_title|kb-articles|list_articles|download_article|upload_article|chunk_article|article\.md" src/` returns zero matches
- [ ] `make test` passes across all services
- [ ] `make convert analyzer=markitdown` produces `document.md` (not `article.md`)
- [ ] `make index` creates `kb-documents` index with `document_id` field

---

### Story 2 — Serving Format: `original/` + `derived/`

> **Status:** Not Started
> **Depends on:** Story 1

Update the serving format from flat `document.md` + `images/` to the structured `original/` + `derived/images/` model. Update `metadata.json` to include `source_type` and `original` fields.

#### Deliverables

- [ ] **Converter output structure** — all `fn-convert` variants write:
  ```
  serving/{document-id}/
    ├── document.md
    ├── metadata.json        # {"department": "...", "source_type": "...", "original": "filename.ext"}
    ├── original/            # Complete copy of source from staging
    │     └── <source files>
    └── derived/
          └── images/        # Extracted images (from HTML, PDF, PPTX)
  ```
- [ ] **HTML handling** — `original/` contains `index.html` + all source images; `derived/images/` gets copies of the images (pipeline reads from `derived/` only)
- [ ] **PDF handling** — `original/` contains the PDF; `derived/images/` gets extracted images
- [ ] **PPTX handling** — `original/` contains the PPTX; `derived/images/` gets extracted slide images
- [ ] **DOCX handling** — `original/` contains the DOCX; `derived/images/` gets extracted images
- [ ] **metadata.json** updated:
  - `source_type`: detected from staging content (html, pdf, pptx, docx)
  - `original`: just the filename (e.g., `"product-overview.pdf"`) — code knows the `original/` folder
- [ ] **Blob storage utilities** — update to handle the deeper folder structure

#### Implementation Notes

- The converter detects source type from the staging directory (see `detect_source_type()` in Research 007, Section 6.2)
- For HTML: copy `index.html` + images to `original/`, copy images to `derived/images/` (pipeline and vision middleware only read from `derived/`)
- The `original/` folder is the complete, unmodified source — used for "View Original" in UI
- `metadata.json` is the contract between `fn-convert` and `fn-index`

#### Definition of Done

- [ ] `make convert analyzer=markitdown` produces `original/` + `derived/images/` structure for all documents
- [ ] `metadata.json` contains `department`, `source_type`, and `original` for every document
- [ ] Vision middleware reads from `derived/images/` (not `images/`)
- [ ] `make test-functions` passes

---

### Story 3 — Converter Multi-Format Support

> **Status:** Not Started
> **Depends on:** Story 2, Epic 013 (spike results)

Add `SUPPORTED_FORMATS` declaration and `detect_source_type()` to all converters. Extend the MarkItDown converter to handle PDF, PPTX, and DOCX with image extraction.

#### Deliverables

- [ ] **`detect_source_type()`** — shared utility that inspects a staging directory and returns the source type (html, pdf, pptx, docx) or None
- [ ] **`SUPPORTED_FORMATS` constant** — each converter declares its supported set:
  - CU: `{"html"}`
  - Mistral: `{"html"}`
  - MarkItDown: `{"html", "pdf", "pptx", "docx"}`
- [ ] **Processing guard** — each converter checks `source_type in SUPPORTED_FORMATS` before processing; logs WARNING and skips if unsupported
- [ ] **PDF image extraction** — using the approach validated by Epic 013 spike (PyMuPDF or pdfminer)
- [ ] **PPTX image + speaker notes extraction** — using the approach validated by Epic 013 spike (python-pptx if needed)
- [ ] **DOCX image extraction** — MarkItDown native or python-docx complement
- [ ] **Dependencies** — add PyMuPDF, python-pptx, python-docx (as needed per spike findings) to `src/functions/pyproject.toml`

#### Implementation Notes

- `detect_source_type()` goes in `src/functions/shared/` — it's used by all converters
- The converter main loop: `for doc in list_documents() → detect type → check supported → process`
- PDF image extraction is the riskiest part — implementation depends entirely on Epic 013 spike findings
- PPTX speaker notes: if MarkItDown doesn't include them (per spike), add a `python-pptx` post-processing step that appends notes to the Markdown output
- Each image extracted from PDF/PPTX gets a filename like `{document_id}-img-{n}.png` and goes to `derived/images/`

#### Definition of Done

- [ ] `make convert analyzer=markitdown` processes HTML, PDF, PPTX, and DOCX documents successfully
- [ ] `make convert analyzer=cu` skips non-HTML with WARNING (no errors)
- [ ] `make convert analyzer=mistral` skips non-HTML with WARNING (no errors)
- [ ] PDF documents: extracted images in `derived/images/`, text in `document.md`
- [ ] PPTX documents: slide images in `derived/images/`, speaker notes in `document.md`
- [ ] DOCX documents: embedded images in `derived/images/`, text in `document.md`
- [ ] Unit tests for `detect_source_type()` and format-specific extraction
- [ ] `make test-functions` passes

---

### Story 4 — Index Schema: `kb-documents` with New Fields

> **Status:** Not Started
> **Depends on:** Story 1, Story 2

Update the AI Search index schema to `kb-documents` with the new `source_type` and `original_url` fields. Update the indexer to populate these fields from `metadata.json`.

#### Deliverables

- [ ] **Index schema** — `src/functions/fn_index/indexer.py`:
  - Index name: `kb-documents` (from Story 1 rename)
  - New field: `source_type` (Edm.String, filterable, facetable)
  - New field: `original_url` (Edm.String) — blob path to `{document-id}/original/{filename}`
- [ ] **Indexer logic** — read `metadata.json` fields:
  - `source_type` → index `source_type` field directly
  - `original` (filename) → construct `original_url` as `{document_id}/original/{original}`
- [ ] **Chunker update** — ensure `source_type` and `original_url` are propagated to every chunk

#### Implementation Notes

- `original_url` is constructed by the indexer, not stored in metadata: `f"{document_id}/original/{metadata['original']}"`
- `source_type` enables faceted search in the UI (filter by format)
- Every chunk in a document gets the same `source_type` and `original_url` values

#### Definition of Done

- [ ] `make index` creates `kb-documents` index with `document_id`, `source_type`, `original_url` fields
- [ ] Azure AI Search explorer confirms `source_type` and `original_url` are populated on all documents
- [ ] `source_type` is filterable and facetable
- [ ] Unit tests for index schema creation and field population
- [ ] `make test-functions` passes

---

### Story 5 — Vision Middleware Path Update

> **Status:** Not Started
> **Depends on:** Story 2

Update the vision middleware in the agent to read images from `derived/images/` instead of `images/`. This is a small but critical change — without it, injected images won't resolve for any document format.

#### Deliverables

- [ ] **Agent image service** — `src/agent/agent/image_service.py`:
  - Update blob path construction from `{document_id}/images/{filename}` to `{document_id}/derived/images/{filename}`
- [ ] **Web app image service** — `src/web-app/app/image_service.py`:
  - Same path update
- [ ] **Web app main** — `src/web-app/app/main.py`:
  - Update image proxy route if path pattern changes
  - Update `_CONTENT_IMAGE_RE` regex if image reference format changes in `document.md`
- [ ] **Agent vision middleware** — update any hardcoded `images/` path references

#### Implementation Notes

- The image URL format in the index `image_urls` field may also need updating — verify what the indexer writes
- The proxy route `/api/images/{document_id}/derived/images/{filename}` or keep the proxy route simpler and map internally
- Test with an actual document that has images to confirm the full chain works

#### Definition of Done

- [ ] Images from `derived/images/` are served correctly through the proxy endpoint
- [ ] Vision middleware injects images into LLM prompts for HTML, PDF, and PPTX documents
- [ ] Image proxy route works in both local dev and deployed environments
- [ ] Unit tests updated for new path structure
- [ ] `make test-agent` and `make test-app` pass

---

### Story 6 — Web UI: Persona Switcher

> **Status:** Not Started
> **Depends on:** Epic 012 (content must be indexed); Epic 011 (department field + SecurityFilterMiddleware already exist)

Add a 3-persona toggle to the Chainlit web UI that controls department-scoped search. The switcher integrates with the existing `SecurityFilterMiddleware` (Epic 011) — in dev/demo mode, the selected persona overrides the default department claim.

#### Deliverables

- [ ] **Persona toggle UI** — implement using Chainlit's `cl.ChatSettings` with a `Select` widget:
  ```python
  @cl.on_settings_update
  async def on_settings_update(settings):
      department = settings.get("persona")
      cl.user_session.set("department", department)
  ```
  Options: `Sam (Support)` → `support`, `Jordan (Marketing)` → `marketing`, `Casey (Engineering)` → `engineering`
- [ ] **Department header injection** — when calling the agent, send the selected department as a custom header or in `extra_body` so the agent's middleware can use it
- [ ] **Agent middleware update** — when `REQUIRE_AUTH=false`, read department from the incoming request (header or body parameter) instead of hardcoded `"engineering"` default
- [ ] **Welcome message** — update to reflect current persona: "You're chatting as Sam (Support). Switch personas in Settings."
- [ ] **Starter prompts** — update to be persona-appropriate:
  - Support: "How do I troubleshoot joint error E012?", "What's the preventive maintenance schedule?"
  - Marketing: "What are the CoBot Pro's key differentiators?", "Tell me about the Meridian case study"
  - Engineering: "What's the force-torque sensor measurement range?", "Describe the EtherCAT communication stack"

#### Implementation Notes

- **Chainlit `ChatSettings`** is the recommended approach for persistent user preferences. It renders as a settings icon in the header. Users click it, see a panel with a dropdown, and select their persona. The selected value persists for the session.
- The `@cl.on_chat_start` hook should initialize the default persona (Support or a "All departments" option)
- The persona value needs to flow from the web-app to the agent. Options:
  1. Custom header on the OpenAI client request (requires agent to read it)
  2. Include in `extra_body` alongside `conversation.id`
  3. Prefix the user message with a system instruction (least clean)
- Option 2 (`extra_body`) is simplest — the agent's Starlette handler can read it from the request body
- Fall back to `/persona support` chat command if `ChatSettings` doesn't render well

#### Definition of Done

- [ ] Persona switcher visible in Chainlit UI (settings panel or header)
- [ ] Selecting a persona changes the department filter on subsequent searches
- [ ] Same question returns different results per persona
- [ ] Welcome message and starter prompts reflect the selected persona
- [ ] Unit tests for persona settings handling
- [ ] `make test-app` passes

---

### Story 7 — Web UI: Source Type Badge & View Original

> **Status:** Not Started
> **Depends on:** Story 4, Story 5

Add source type badges and "View Original" buttons to citation elements in the Chainlit UI.

#### Deliverables

- [ ] **Source type badge** — show format indicator (HTML, PDF, PPTX, DOCX) on each citation element:
  - Read `source_type` from search results
  - Display as prefix or badge in the citation title: "📄 PDF — Force-Torque Sensor Spec"
- [ ] **"View Original" button** — link to the source document using `original_url`:
  - Construct a proxy URL or SAS URL for the blob at `{document_id}/original/{filename}`
  - For PDFs: link opens in browser (most browsers render PDFs natively)
  - For PPTX/DOCX: link triggers download
- [ ] **PDF inline viewer** — embed PDF.js for in-browser viewing from the citation panel (renders PDF without requiring download)
- [ ] **Citation model update** — `Citation` dataclass includes `source_type` and `original_url` fields
- [ ] **Search result parsing** — extract `source_type` and `original_url` from agent response annotations

#### Implementation Notes

- The `original_url` from the index is a blob-relative path. The web app needs to either:
  1. Proxy the file (like the image proxy) — safest for auth
  2. Generate a SAS URL — simpler but needs SAS token management
- Option 1 (proxy) is consistent with existing image proxy pattern
- Route: `/api/originals/{document_id}/{filename}` serving from `{document_id}/original/{filename}` in blob storage
- Source type badge is purely a UI concern — format the citation element's title/label

#### Definition of Done

- [ ] Citations show source type badge (format indicator)
- [ ] "View Original" link on citations opens/downloads the source document
- [ ] Proxy route serves original files from blob storage
- [ ] Works for HTML, PDF, PPTX, and DOCX documents
- [ ] `make test-app` passes

---

### Story 8 — Integration Testing & Validation

> **Status:** Not Started
> **Depends on:** Story 3, Story 4, Story 5, Story 6, Story 7

End-to-end validation of the complete Phase 1 pipeline: multi-format conversion → indexing → department-scoped search → persona-aware answers → vision injection → View Original.

#### Deliverables

- [ ] **Pipeline test** — `make convert analyzer=markitdown` → `make index` processes all ~24 documents with correct serving structure
- [ ] **Search validation** — queries return results from all formats and departments with correct `source_type` and `original_url` values
- [ ] **Cross-department queries** — verify multi-hop scenarios:
  - "CoBot Pro safety" → Support + Engineering + Marketing results
  - "force-torque sensor" → Engineering spec + Support troubleshooting
  - "Vision Module" → Support guide + Engineering pipeline + Marketing brief
- [ ] **Persona filtering** — same query with different personas returns different result sets
- [ ] **Vision injection** — images from PDFs, PPTXs, and HTMLs are injected into LLM answers
- [ ] **View Original** — clicking "View Original" on a PDF citation opens the PDF
- [ ] **Regression check** — all existing test suites pass: `make test`

#### Implementation Notes

- Run the full pipeline on the complete Epic 012 content corpus
- Test both local dev (no auth, persona switcher) and deployed (APIM + auth) scenarios
- Verify CU and Mistral converters gracefully skip non-HTML documents
- Check AI Search explorer for correct field population across all document types

#### Definition of Done

- [ ] `make convert analyzer=markitdown` completes for all ~24 documents
- [ ] `make index` populates `kb-documents` index with all documents
- [ ] Cross-department search queries validated (at least 3 scenarios)
- [ ] Persona switcher produces different results per department
- [ ] Vision middleware injects images from PDF and PPTX documents
- [ ] "View Original" works for at least one PDF and one PPTX
- [ ] `make test` passes with zero regressions
- [ ] Demo walkthrough: all 3 personas answer "What are the safety certifications?" differently

---

### Story 9 — Documentation Update

> **Status:** Not Started
> **Depends on:** Story 8

Update all project documentation to reflect Phase 1 changes.

#### Deliverables

- [ ] **`README.md`** — update:
  - KB description: 3 departments, ~24 documents, 4 formats
  - Serving format description: `original/` + `derived/`
  - Core patterns: note multi-format pipeline
- [ ] **`docs/specs/architecture.md`** — update:
  - Serving layer format description
  - Converter model (SUPPORTED_FORMATS)
  - Index schema (kb-documents, new fields)
- [ ] **`docs/specs/infrastructure.md`** — update:
  - AI Search index field list (new fields)
  - Blob storage structure (new folder layout)
- [ ] **`docs/setup-and-makefile.md`** — update:
  - Any new or changed Makefile targets
  - New environment variables if any
- [ ] **This epic file** — mark all stories as Done, update status

#### Definition of Done

- [ ] All docs reflect the `document` terminology (no stale `article` references)
- [ ] Architecture doc describes `original/` + `derived/` serving format
- [ ] Infrastructure doc lists the new index fields
- [ ] README accurately describes the KB contents and formats
- [ ] Epic status set to Done
