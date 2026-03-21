# Epic 012 — Contoso Robotics Content Creation

> **Status:** Draft
> **Created:** March 19, 2026
> **Updated:** March 19, 2026

## Objective

Create the full corpus of **~24 Contoso Robotics documents** across 3 departments (Support, Marketing, Engineering) to replace the existing 3 Azure-themed engineering articles. Every document uses the unified Contoso Robotics theme, includes 2–3 images, and contains deliberate cross-references to documents in other departments.

After this epic:

- **3 departments are populated** — Support (10 HTML), Marketing (6 PDF/PPTX/DOCX), Engineering (6 PDF + 2 HTML) — ready for pipeline ingestion
- **Cross-references are woven throughout** — every document references at least 1–2 documents from other departments, enabling multi-hop queries
- **Images are embedded in every document** — diagrams, schematics, product photos, charts — maximizing vision middleware value
- **Staging folder structure is ready** — `kb/staging/{department}/{document-id}/` with source files + images per the existing convention
- **Content is realistic and coherent** — a fictional but plausible robotics company with consistent terminology, product names, and technical details

## Success Criteria

- [ ] 10 Support HTML documents created under `kb/staging/support/`
- [ ] 6 Marketing documents created (4 PDF + 1 PPTX + 1 DOCX) under `kb/staging/marketing/`
- [ ] 8 Engineering documents created (6 PDF + 2 HTML) under `kb/staging/engineering/`
- [ ] Every document contains at least 2–3 images (diagrams, photos, charts, schematics)
- [ ] Every document cross-references at least 1–2 documents from other departments
- [ ] Cross-reference map (Appendix A of Research 007) is fully realized in the content
- [ ] `make convert analyzer=markitdown` processes all HTML documents without errors (PDF/PPTX require Epic 014 multi-format support)
- [ ] `make index` indexes all HTML documents successfully
- [ ] Existing 3 Azure-themed articles removed from `kb/staging/engineering/`
- [ ] Old snapshots archived or removed from `kb_snapshot/`

---

## Background

See [docs/research/007-extended-data-sources-support.md](../research/007-extended-data-sources-support.md) for the full research proposal.

### Current vs. Proposed

| Aspect | Current | After Epic 012 |
|--------|---------|----------------|
| Documents | 3 Azure-themed HTML articles | ~24 Contoso Robotics documents |
| Departments | 1 (engineering) | 3 (support, marketing, engineering) |
| File formats | HTML only | HTML, PDF, PPTX, DOCX |
| Company theme | Mixed Azure topics | Unified Contoso Robotics |
| Cross-references | None | Every doc references 1–2 other-dept docs |
| Images | Minimal | 2–3 per document |
| Demo value | Limited | Rich multi-hop, cross-dept, multi-format |

### Company Theme: Contoso Robotics

> **Contoso Robotics** is a fictional manufacturer of collaborative industrial robots. Their flagship product, the **CoBot Pro**, is a collaborative robot arm for manufacturing and logistics.

| Product | Description |
|---------|-------------|
| CoBot Pro | Collaborative robot arm, 12 kg payload, 1300 mm reach |
| CoBot Vision Module | Add-on 3D camera + AI perception system |
| CoBot Safety Controller | Certified safety monitoring unit (ISO 10218, ISO/TS 15066) |

### Content Creation Principles

1. **Fewer, better docs** — each document is rich enough to generate multiple meaningful search chunks
2. **Cross-reference heavily** — creates multi-hop query paths for compelling demos
3. **Image-rich** — diagrams, schematics, product photos, charts in every document
4. **Create > Source** — fictional but realistic content gives full control over quality and cross-references

---

### Story 1 — Content Outlines & Cross-Reference Plan

> **Status:** Not Started
> **Depends on:** None

Create detailed content outlines for all ~24 documents. Define the exact cross-references between documents. Establish consistent terminology and product details.

#### Deliverables

- [ ] Content outline document listing all ~24 documents with: title, format, sections, key images needed, cross-references
- [ ] Terminology glossary (product names, error codes, standards references, component names) for consistency
- [ ] Image inventory: list of diagrams/photos/charts needed across all documents
- [ ] Cross-reference validation: every link in Appendix A of Research 007 mapped to specific section/paragraph targets

#### Definition of Done

- [ ] Outline document reviewed and approved
- [ ] Every document has 3+ planned sections and 2+ planned images
- [ ] Cross-reference map has bidirectional links (source → target and target → source)

---

### Story 2 — Support Department: 10 HTML Documents

> **Status:** Not Started
> **Depends on:** Story 1

Create the 10 Support department HTML documents. These are customer-facing docs: installation guides, troubleshooting, maintenance, integration guides.

#### Deliverables

- [ ] `kb/staging/support/cobot-pro-quick-start-guide/` — Quick Start Guide (HTML + images)
- [ ] `kb/staging/support/cobot-pro-installation-manual/` — Installation Manual (HTML + images)
- [ ] `kb/staging/support/cobot-vision-module-setup-guide/` — Vision Module Setup Guide (HTML + images)
- [ ] `kb/staging/support/cobot-safety-controller-configuration/` — Safety Controller Config Guide (HTML + images)
- [ ] `kb/staging/support/troubleshooting-joint-errors-faults/` — Joint Errors Troubleshooting (HTML + images)
- [ ] `kb/staging/support/troubleshooting-vision-system-issues/` — Vision System Troubleshooting (HTML + images)
- [ ] `kb/staging/support/firmware-update-procedure/` — Firmware Update Procedure (HTML + images)
- [ ] `kb/staging/support/preventive-maintenance-schedule/` — Preventive Maintenance (HTML + images)
- [ ] `kb/staging/support/ros2-integration-guide/` — ROS 2 Integration Guide (HTML + images)
- [ ] `kb/staging/support/safety-standards-compliance-overview/` — Safety Standards Overview (HTML + images)

#### Implementation Notes

- Each document is an `index.html` + `images/` folder under the document ID directory
- Use consistent HTML structure: `<article>` with `<h1>`, `<h2>`, `<h3>`, `<p>`, `<table>`, `<img>` tags
- Images: create diagrams with draw.io, product illustrations, screenshots of fictional UI
- Cross-references: explicit mentions like "For detailed technical specifications, see the *Force-Torque Sensor Hardware Specification* (Engineering)"
- Content adapted from public collaborative robotics documentation patterns (Universal Robots, ROS 2 docs) — rebranded for Contoso Robotics

#### Definition of Done

- [ ] All 10 documents exist with valid HTML and embedded images
- [ ] Each document contains at least 2 images
- [ ] Each document cross-references at least 1 Engineering or Marketing document
- [ ] `make convert analyzer=markitdown` processes all Support documents without errors

---

### Story 3 — Marketing Department: 4 PDF + 1 PPTX + 1 DOCX Documents

> **Status:** Not Started
> **Depends on:** Story 1

Create the 6 Marketing department documents: 4 PDF documents (brochure, technical brief, competitive analysis, safety factsheet), 1 PPTX (launch presentation), and 1 DOCX (customer success case study).

#### Deliverables

- [ ] `kb/staging/marketing/cobot-pro-product-overview-brochure/` — Product Overview Brochure (PDF with photos and specs)
- [ ] `kb/staging/marketing/cobot-pro-launch-presentation/` — Launch Presentation (PPTX with diagrams, speaker notes)
- [ ] `kb/staging/marketing/cobot-vision-module-technical-brief/` — Vision Module Technical Brief (PDF with benchmarks)
- [ ] `kb/staging/marketing/customer-success-meridian-auto-parts/` — Customer Success Story (DOCX with deployment photos)
- [ ] `kb/staging/marketing/competitive-landscape-analysis/` — Competitive Analysis (PDF with comparison tables)
- [ ] `kb/staging/marketing/cobot-pro-safety-certification-factsheet/` — Safety Certification Factsheet (PDF with badges)

#### Implementation Notes

- **PDFs**: Create in LibreOffice Writer or Google Docs, export to PDF. Include charts, tables, product images (from Creative Commons robotics imagery)
- **PPTX**: Create in LibreOffice Impress. Include diagrams, product photos, data charts. Speaker notes contain important context (these should produce separate chunks)
- **DOCX**: Create in LibreOffice Writer. The Meridian case study stays as `.docx` (not exported to PDF) to validate the DOCX conversion pipeline end-to-end
- Each document goes in its own staging folder as the primary file (e.g., `product-overview.pdf`, `case-study.docx`)
- Cross-references woven into text: "Based on the *Force-Torque Sensor Hardware Specification* developed by our Engineering team..."

#### Definition of Done

- [ ] All 6 documents exist in their staging folders
- [ ] PDFs contain embedded images (photos, charts, diagrams)
- [ ] PPTX contains 15+ slides with speaker notes and images
- [ ] DOCX contains embedded images and formatted text (validates DOCX pipeline)
- [ ] Each document cross-references at least 1 Engineering or Support document
- [ ] Documents open correctly in standard viewers (PDF reader, PowerPoint/LibreOffice, Word/LibreOffice Writer)

---

### Story 4 — Engineering Department: 6 PDF + 2 HTML Documents

> **Status:** Not Started
> **Depends on:** Story 1

Create the 8 Engineering department documents: 6 PDF specifications/architecture docs and 2 HTML documents (ROS 2 node reference, release notes).

#### Deliverables

- [ ] `kb/staging/engineering/cobot-pro-system-architecture-overview/` — System Architecture Overview (PDF with diagrams)
- [ ] `kb/staging/engineering/force-torque-sensor-hardware-spec/` — Force-Torque Sensor Spec (PDF with datasheets)
- [ ] `kb/staging/engineering/cobot-vision-perception-pipeline-design/` — Perception Pipeline Design (PDF with ML diagrams)
- [ ] `kb/staging/engineering/safety-controller-firmware-architecture/` — Safety Controller Firmware (PDF with block diagrams)
- [ ] `kb/staging/engineering/ethercat-communication-stack-spec/` — EtherCAT Comm Stack Spec (PDF with protocol diagrams)
- [ ] `kb/staging/engineering/cobot-pro-ros2-node-reference/` — ROS 2 Node Reference (HTML with API tables)
- [ ] `kb/staging/engineering/electrical-schematics-cobot-pro/` — Electrical Schematics (PDF with wiring diagrams)
- [ ] `kb/staging/engineering/release-notes-firmware-v4-2-0/` — Release Notes v4.2.0 (HTML with changelog)

#### Implementation Notes

- **Architecture/spec PDFs**: Create with realistic system diagrams (Mermaid/draw.io exported to PNG, embedded in PDF). Include measurement data, specification tables, wiring diagrams.
- **HTML docs**: Follow the same HTML patterns as Support docs but with API-reference and changelog structures
- Schematics and wiring diagrams created with draw.io — they need to be visually representative, not electrically correct
- ROS 2 node reference: adapted from ROS 2 Iron/Humble documentation structure, rebranded for CoBot Pro nodes

#### Definition of Done

- [ ] All 8 documents exist in their staging folders
- [ ] PDFs contain embedded technical diagrams (architecture, schematics, datasheets)
- [ ] HTML documents have valid structure with embedded images
- [ ] Each document cross-references at least 1 Support or Marketing document
- [ ] `make convert analyzer=markitdown` processes all Engineering documents without errors

---

### Story 5 — Retire Old Content & Validate Full Corpus

> **Status:** Not Started
> **Depends on:** Story 2, Story 3, Story 4

Remove the old Azure-themed articles, validate the complete corpus of ~24 documents through the pipeline, and verify cross-department search results.

#### Deliverables

- [ ] Remove old articles from `kb/staging/engineering/` (the 3 Azure-themed docs)
- [ ] Archive old content to `kb_snapshot/` if not already there
- [ ] Run `make convert analyzer=markitdown` on HTML documents (12 HTML across Support + Engineering) — all convert successfully
- [ ] Run `make index` — HTML documents indexed with correct `department` fields
- [ ] Note: Full-corpus pipeline validation (including PDF/PPTX) is deferred to Epic 014 Story 8 which adds multi-format converter support
- [ ] Validate search queries return cross-department results (HTML docs only):
  - "CoBot Pro safety" → results from Support, Engineering, and Marketing
  - "force-torque sensor" → results from Engineering spec + Support troubleshooting + Marketing competitive analysis
  - "Vision Module setup" → results from Support guide + Engineering pipeline + Marketing brief

#### Definition of Done

- [ ] Old Azure articles removed from staging (archived in `kb_snapshot/`)
- [ ] `make convert analyzer=markitdown` completes with zero errors for all HTML documents (12 HTML across Support + Engineering)
- [ ] `make index` completes with correct department assignments for HTML documents
- [ ] PDF/PPTX documents exist in staging and are structurally valid, but pipeline validation requires Epic 014
- [ ] At least 3 cross-department queries validated manually via AI Search explorer (using HTML docs)
- [ ] `make test` passes with zero regressions
