# Epic 013 — PDF/PPTX Conversion Quality Spike

> **Status:** Done ✅
> **Issue:** #13
> **Branch:** `copilot/epic-013-pdf-pptx-conversion-quality-spike`

## Objective

Validate that **MarkItDown** produces acceptable Markdown output from PDF and PPTX inputs — with particular focus on **embedded image extraction quality** and **PPTX speaker notes inclusion**. This spike de-risks Phase 1 (Epic 014) by identifying any conversion gaps before we build 24 documents around the pipeline.

## Stories

### Story 1 — PDF Conversion & Image Extraction ✅

Test MarkItDown PDF conversion with a representative sample document. Evaluate image extraction quality with multiple approaches (MarkItDown native vs. PyMuPDF). Key metrics: image resolution, format, visual quality, extraction completeness.

**Acceptance Criteria:**

- [x] Sample PDF with embedded diagrams and tables converted via MarkItDown — output quality assessed
- [x] PDF image extraction tested with at least 2 approaches (MarkItDown native + PyMuPDF)
- [x] Image quality compared: resolution, artifacts, completeness

**Findings:**

| Aspect | Result | Notes |
|--------|--------|-------|
| Text extraction | ✅ Good | All paragraph text, sub-headings, and content preserved |
| Heading formatting | ⚠️ Partial | Headings present as text but no `#` Markdown markers |
| Table extraction | ⚠️ Partial | Second table (API Endpoints) perfect; first table partially broken |
| Long table (30 rows) | ✅ Preserved | Cross-page table preserved as single Markdown table (31 rows) |
| Bullet points | ⚠️ Artifacts | Rendered as `(cid:127)` — PDF character ID, not `•` or `-` |
| Image references | ❌ None | MarkItDown does not generate `![](...)` for embedded PDF images |
| PyMuPDF images | ✅ Excellent | Extracts all 3 embedded images at original resolution — architecture diagram (600×400), bar chart (500×350), photo-like (500×350) |
| Hyperlinks | ❌ Lost | All hyperlinks completely lost during PDF conversion |

### Story 2 — PPTX Conversion & Speaker Notes ✅

Test MarkItDown PPTX conversion. Verify speaker notes inclusion and image extraction. If speaker notes are missing, create a python-pptx extraction prototype.

**Acceptance Criteria:**

- [x] Sample PPTX with speaker notes converted via MarkItDown — speaker notes presence confirmed
- [x] PPTX image extraction tested — slide images extractable at usable resolution
- [x] DOCX conversion spot-checked (low risk — MarkItDown DOCX support is mature)

**Findings:**

| Aspect | Result | Notes |
|--------|--------|-------|
| Slide content | ✅ Excellent | All slide titles, bullet points, and text preserved |
| Speaker notes | ✅ Included | MarkItDown outputs `### Notes:` section per slide — all 8/8 notes present |
| Table extraction | ✅ Good | PPTX table rendered as pipe-delimited Markdown |
| Long table (30 rows) | ✅ Preserved | Long table preserved as single Markdown table (38 rows) |
| Image references | ✅ Present | `![name](PictureN.jpg)` — all 3 image types referenced |
| Slide markers | ✅ Present | `<!-- Slide number: N -->` comments for structure |
| python-pptx images | ✅ Works | 3 images extracted at original resolution via python-pptx |
| Hyperlinks | ❌ Lost | External hyperlinks lost — link text preserved but URLs stripped |
| DOCX spot check | ✅ Excellent | Headings, lists, tables (incl. long), images (all 3 types), **and hyperlinks** all preserved |

### Story 3 — Spike Documentation & Recommendation ✅

Compile all findings into `docs/spikes/004-pdf-pptx-conversion.md`. Provide clear go/no-go recommendation for Phase 1. Document known limitations and mitigations.

**Acceptance Criteria:**

- [x] Spike findings documented in `docs/spikes/004-pdf-pptx-conversion.md`
- [x] Go/no-go recommendation for proceeding with MarkItDown in Phase 1
- [x] Known limitations documented with mitigation strategies
- [x] Impact on Epic 014 implementation plan assessed

## Definition of Done

- [x] Sample PDF with embedded diagrams and tables converted — output quality assessed
- [x] PDF image extraction tested with 2 approaches (MarkItDown native + PyMuPDF)
- [x] Image quality compared: resolution, artifacts, completeness
- [x] Sample PPTX with speaker notes converted — speaker notes presence confirmed
- [x] PPTX image extraction tested — slide images extractable
- [x] DOCX conversion spot-checked
- [x] Spike findings documented in `docs/spikes/004-pdf-pptx-conversion.md`
- [x] Go/no-go recommendation for Phase 1

## Deliverables

| File | Purpose |
|------|---------|
| `src/spikes/004-pdf-pptx-conversion/create_samples.py` | Generates sample PDF, PPTX, DOCX with embedded images/tables/notes |
| `src/spikes/004-pdf-pptx-conversion/run.py` | Spike orchestrator — tests all formats, compares approaches, prints results |
| `docs/spikes/004-pdf-pptx-conversion.md` | Spike findings document with go/no-go recommendation |
| `docs/epics/013-pdf-pptx-conversion-spike.md` | This epic tracking document |
