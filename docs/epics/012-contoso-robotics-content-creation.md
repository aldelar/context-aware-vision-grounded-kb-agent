# Epic 012 — Contoso Robotics Content Creation

**Status:** Done
**Created:** 2026-03-20

## Objective

Create the full corpus of **24 Contoso Robotics documents** across 3 departments (Support, Marketing, Engineering) to replace the existing 3 Azure-themed engineering articles. Every document uses the unified Contoso Robotics theme, includes 2–3 images, and contains deliberate cross-references to documents in other departments.

## Stories

### Story 1 — Content Outlines & Cross-Reference Plan ✅

Created detailed content outlines for all 24 documents. Defined exact cross-references between documents. Established consistent terminology and product details.

**Contoso Robotics Product Line:**
- **CoBot Pro 500** — 5 kg payload, 6-axis collaborative robot
- **CoBot Pro 700** — 14 kg payload, 6-axis collaborative robot (flagship)
- **CoBot Vision Module VM-200** — AI-powered 3D vision system
- **Safety Controller SC-100** — SIL 2 certified safety PLC
- **CoBot OS v4.2** — Real-time operating system
- **CoBot Studio IDE** — Programming and configuration software
- **CoBot ROS 2 Bridge** — ROS 2 integration middleware
- **Force-Torque Sensor FTS-600** — 6-axis strain gauge sensor

Acceptance Criteria:
- [x] All 24 document outlines created
- [x] Cross-reference map defined
- [x] Terminology and product details consistent

### Story 2 — Support Department: 10 HTML Documents ✅

Created 10 Support department HTML documents under `kb/staging/support/`.

| Document | Directory | Images |
|----------|-----------|--------|
| CoBot Pro Quick Start Guide | `cobot-pro-quick-start/` | 3 |
| CoBot Pro Installation Manual | `cobot-pro-installation-manual/` | 3 |
| Vision Module VM-200 Setup Guide | `vision-module-setup-guide/` | 3 |
| Safety Controller SC-100 Configuration | `safety-controller-configuration/` | 3 |
| Joint Error Troubleshooting | `joint-error-troubleshooting/` | 2 |
| Vision System Troubleshooting | `vision-system-troubleshooting/` | 2 |
| Firmware Update Procedure | `firmware-update-procedure/` | 2 |
| Preventive Maintenance Schedule | `preventive-maintenance-schedule/` | 3 |
| ROS 2 Integration Guide | `ros2-integration-guide/` | 3 |
| Safety Standards & Compliance | `safety-standards-compliance/` | 2 |

Acceptance Criteria:
- [x] 10 Support HTML documents created
- [x] Each document contains 2–3 images
- [x] Each document cross-references at least 1–2 documents from other departments

### Story 3 — Marketing Department: 6 HTML Documents ✅

Created 6 Marketing department HTML documents under `kb/staging/marketing/`. These are HTML source files that represent the content of PDF/PPTX/DOCX marketing materials.

| Document | Directory | Images |
|----------|-----------|--------|
| CoBot Pro Product Overview Brochure | `cobot-pro-product-overview/` | 3 |
| CoBot Pro 700 Launch Presentation | `cobot-pro-launch-presentation/` | 3 |
| Vision Module VM-200 Technical Brief | `vision-module-technical-brief/` | 3 |
| Customer Success: Meridian Automotive | `customer-success-automotive/` | 3 |
| Competitive Analysis Report | `competitive-analysis-report/` | 2 |
| Safety Certification Factsheet | `safety-certification-factsheet/` | 2 |

Acceptance Criteria:
- [x] 6 Marketing HTML documents created
- [x] Each document contains 2–3 images
- [x] Each document cross-references at least 1–2 documents from other departments

### Story 4 — Engineering Department: 8 HTML Documents ✅

Created 8 Engineering department HTML documents under `kb/staging/engineering/`.

| Document | Directory | Images |
|----------|-----------|--------|
| System Architecture Overview | `system-architecture-overview/` | 3 |
| Force-Torque Sensor FTS-600 Spec | `force-torque-sensor-spec/` | 3 |
| Perception Pipeline Design | `perception-pipeline-design/` | 3 |
| Safety Controller SC-100 Firmware | `safety-controller-firmware/` | 3 |
| EtherCAT Communication Stack | `ethercat-communication-stack/` | 3 |
| ROS 2 Node Reference Manual | `ros2-node-reference/` | 3 |
| Electrical Schematics Reference | `electrical-schematics/` | 3 |
| Firmware Release Notes v4.2.0 | `firmware-release-notes-v420/` | 2 |

Acceptance Criteria:
- [x] 8 Engineering HTML documents created
- [x] Each document contains 2–3 images
- [x] Each document cross-references at least 1–2 documents from other departments

### Story 5 — Retire Old Content & Validate Full Corpus ✅

Removed old Azure-themed articles from `kb/staging/` and validated the complete corpus.

**Removed:**
- `kb/staging/agentic-retrieval-overview-html_en-us/`
- `kb/staging/content-understanding-overview-html_en-us/`
- `kb/staging/search-security-overview-html_en-us/`

**Validation Results:**
- 24 HTML documents across 3 departments
- 65 placeholder images
- All cross-references verified
- All image references resolve to existing files

Acceptance Criteria:
- [x] Old Azure-themed articles removed from `kb/staging/`
- [x] 24 documents validated across all departments
- [x] All image references verified

## Definition of Done

- [x] 10 Support HTML documents created under `kb/staging/support/`
- [x] 6 Marketing HTML documents created under `kb/staging/marketing/`
- [x] 8 Engineering HTML documents created under `kb/staging/engineering/`
- [x] Every document contains at least 2–3 images
- [x] Every document cross-references at least 1–2 documents from other departments
- [x] Old Azure-themed articles removed from `kb/staging/`
- [x] Epic doc reflects implementation state
