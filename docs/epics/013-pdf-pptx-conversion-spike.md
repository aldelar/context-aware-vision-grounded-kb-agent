# Epic 013 — PDF/PPTX Conversion Quality Spike

> **Status:** Draft
> **Created:** March 19, 2026
> **Updated:** March 19, 2026

## Objective

Validate that **MarkItDown** produces acceptable Markdown output from PDF and PPTX inputs — with particular focus on **embedded image extraction quality** and **PPTX speaker notes inclusion**. This spike de-risks Phase 1 (Epic 014) by identifying any conversion gaps before we build 24 documents around the pipeline.

After this spike:

- **PDF conversion quality is measured** — text extraction fidelity, table rendering, image extraction viability assessed with a representative Engineering-style spec PDF
- **PDF image extraction approach is chosen** — MarkItDown native vs. PyMuPDF (`fitz`) vs. `pdfminer.six`, with quality/resolution comparison
- **PPTX conversion verified** — slide content, speaker notes inclusion, and image extraction confirmed or gaps identified
- **Conversion gaps documented** — any limitations (e.g., complex layouts, encrypted PDFs, SmartArt) documented with mitigation strategies
- **Go/no-go recommendation for Phase 1** — clear decision on whether MarkItDown is sufficient or if additional tooling is needed

## Success Criteria

- [ ] Sample PDF with embedded diagrams and tables converted via MarkItDown — output quality assessed
- [ ] PDF image extraction tested with at least 2 approaches (MarkItDown native + PyMuPDF or pdfminer)
- [ ] Image quality compared: resolution, artifacts, completeness
- [ ] Sample PPTX with speaker notes converted via MarkItDown — speaker notes presence confirmed or denied
- [ ] If speaker notes are missing, `python-pptx` extraction prototype created
- [ ] PPTX image extraction tested — slide images extractable at usable resolution
- [ ] DOCX conversion spot-checked (low risk — MarkItDown's DOCX support is mature)
- [ ] Spike findings documented in `docs/spikes/004-pdf-pptx-conversion.md`
- [ ] Go/no-go recommendation for proceeding with MarkItDown in Phase 1

---

## Background

See [docs/research/007-extended-data-sources-support.md](../research/007-extended-data-sources-support.md) — Section 9 (Open Questions 1 and 3) and Appendix B (MarkItDown Format Support Detail).

### Why Spike Before Building Content?

Phase 1 (Epic 014) depends on MarkItDown processing PDFs and PPTXs with embedded images. If image extraction is poor or speaker notes are missing, we need to know *before* creating ~14 non-HTML documents. The spike answers:

| Question | Impact if "No" |
|----------|----------------|
| Does MarkItDown extract usable images from PDFs? | Need PyMuPDF or alternative; may require converter changes |
| Are extracted PDF images high enough resolution for GPT-4.1 vision? | May need higher-DPI extraction or source image storage strategy |
| Does MarkItDown include PPTX speaker notes? | Need `python-pptx` post-processing; affects content creation approach |
| Does MarkItDown extract PPTX slide images? | Need `python-pptx` image extraction; affects the derived/images pipeline |

### MarkItDown Capabilities (from Research 007)

| Format | Text | Tables | Images | Known Gaps |
|--------|------|--------|--------|------------|
| PDF | Via `pdfminer.six` | Detected → Markdown | References detected; separate extraction may be needed | OCR for scanned PDFs not built-in |
| PPTX | Slides → sections | N/A | Slide images detected | Speaker notes — to be confirmed |
| DOCX | Headings, lists, tables | Preserved | Embedded images extracted | SmartArt, text boxes may be lost |

---

### Story 1 — PDF Conversion & Image Extraction

> **Status:** Not Started
> **Depends on:** None

Test MarkItDown PDF conversion with a representative sample document. Evaluate image extraction quality with multiple approaches.

#### Deliverables

- [ ] Create a sample PDF with: multi-column text, tables, 3+ embedded diagrams/images, headers/footers (representative of an Engineering spec)
- [ ] Convert via MarkItDown — assess: text fidelity, table rendering, heading structure, image references
- [ ] Extract images via MarkItDown native approach — measure: resolution, format, completeness
- [ ] Extract images via PyMuPDF (`fitz`) — compare: resolution, format, completeness
- [ ] Document results in spike doc with before/after comparisons
- [ ] Recommendation: which image extraction approach to use in Phase 1

#### Implementation Notes

- Test in isolation first: `from markitdown import MarkItDown; md = MarkItDown(); result = md.convert("sample.pdf")`
- For PyMuPDF: `pip install PyMuPDF` → `fitz.open("sample.pdf")` → iterate pages → extract images
- Key metrics: image resolution (pixels), format (PNG/JPEG), visual quality, extraction completeness (all images found?)
- Test with a PDF that has both vector diagrams and raster images

#### Definition of Done

- [ ] PDF text conversion quality documented (good/acceptable/poor with examples)
- [ ] Image extraction comparison table: MarkItDown vs. PyMuPDF — resolution, quality, completeness
- [ ] Clear recommendation for Phase 1 image extraction approach

---

### Story 2 — PPTX Conversion & Speaker Notes

> **Status:** Not Started
> **Depends on:** None (parallel with Story 1)

Test MarkItDown PPTX conversion. Specifically verify speaker notes inclusion and image extraction.

#### Deliverables

- [ ] Create a sample PPTX with: 10+ slides, speaker notes on each slide, embedded images/charts, title slides, bullet slides
- [ ] Convert via MarkItDown — assess: slide structure, content completeness, speaker notes presence
- [ ] If speaker notes are **included**: document the format and any quirks
- [ ] If speaker notes are **missing**: create a `python-pptx` extraction prototype that pulls notes and appends them to MarkItDown output
- [ ] Extract images from PPTX — test MarkItDown native and `python-pptx` approaches
- [ ] Document results in spike doc

#### Implementation Notes

- Speaker notes are the most valuable content in many presentations — this is a critical test
- `python-pptx` extraction: `from pptx import Presentation; prs = Presentation("sample.pptx"); for slide in prs.slides: notes = slide.notes_slide.notes_text_frame.text`
- Image extraction via `python-pptx`: iterate `slide.shapes`, check for `shape.image`, extract binary data
- If MarkItDown doesn't include notes, the converter can call `python-pptx` as a complementary step

#### Definition of Done

- [ ] PPTX conversion quality documented (slide structure, content fidelity)
- [ ] Speaker notes inclusion confirmed or denied with evidence
- [ ] If denied: `python-pptx` prototype extracts notes successfully
- [ ] Image extraction approach for PPTX documented

---

### Story 3 — Spike Documentation & Recommendation

> **Status:** Not Started
> **Depends on:** Story 1, Story 2

Compile all findings into the spike document. Provide a clear go/no-go recommendation for Phase 1.

#### Deliverables

- [ ] Create `docs/spikes/004-pdf-pptx-conversion.md` with:
  - Executive summary (go/no-go)
  - PDF conversion findings (text, tables, images)
  - PPTX conversion findings (slides, speaker notes, images)
  - DOCX spot-check results
  - Image extraction recommendation (which library/approach)
  - Known limitations and mitigations
  - Impact on Epic 014 implementation plan
- [ ] Update this epic with findings summary

#### Definition of Done

- [ ] Spike document published at `docs/spikes/004-pdf-pptx-conversion.md`
- [ ] Clear go/no-go recommendation with supporting evidence
- [ ] Any blockers or required changes for Epic 014 documented
- [ ] Epic 013 marked as Done
