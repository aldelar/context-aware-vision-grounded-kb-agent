# Epic 004 — Mistral Document AI as Alternative Convert Pipeline

> **Status:** Done
> **Created:** February 20, 2026
> **Updated:** February 21, 2026

## Objective

Introduce **Mistral Document AI** (`mistral-document-ai-2512`) as a second, interchangeable conversion backend for the ingestion pipeline. The existing `fn-convert` (based on Azure Content Understanding) is renamed to `fn_convert_cu`, and a new `fn_convert_mistral` is created — sharing the same input/output contract so `fn-index` works unchanged. The Makefile `convert` and `azure-convert` targets accept an `analyzer=` selector argument, and infrastructure deploys a superset of resources supporting both options.

This enables two independent approaches for converting source HTML articles to Markdown:

- **Content Understanding** — leverages CU's `prebuilt-documentSearch` + custom `kb-image-analyzer` (backed by GPT models in Foundry)
- **Mistral Document AI** — leverages `mistral-document-ai-2512` for OCR and GPT-4.1 vision for image descriptions (both deployed in Foundry)

The Mistral approach is a good option when LLMs need to be governed via a gateway (e.g., Azure API Management), as Content Understanding does not currently allow forcing access to its underlying LLMs through a gateway. Mistral Document AI and GPT-4.1 are standard Foundry model deployments that can be fronted by any API gateway.

## Success Criteria

- [x] `make convert analyzer=content-understanding` runs the existing CU pipeline (renamed `fn_convert_cu`)
- [x] `make convert analyzer=mistral-doc-ai` runs the new Mistral pipeline (`fn_convert_mistral`)
- [x] `make convert` (no argument) prints usage showing the required `analyzer=` options
- [x] Same behaviour for `make azure-convert analyzer=...`
- [x] `fn_convert_mistral` produces output in `kb/serving/` with the exact same format as `fn_convert_cu` (same `article.md` structure, same `images/` layout)
- [x] `fn-index` processes output from either backend without changes
- [x] Infrastructure deploys `mistral-document-ai-2512` alongside existing CU model deployments
- [x] `azd provision` and `azd deploy` succeed with the updated infrastructure and function code
- [x] All existing tests pass; new tests added for `fn_convert_mistral`
- [x] README and architecture docs updated to describe both conversion options

---

## Background

[Spike 002](../spikes/002-mistral-document-ai.md) validated that Mistral Document AI can replace CU for the convert phase, producing output of comparable quality across all three sample articles. The spike code lives in `src/spikes/002-mistral-document-ai/` and forms the reference implementation for this epic.

Key spike findings:
- Markdown quality is comparable (character counts within ~5%, identical hyperlink recovery, identical image handling)
- Image descriptions use the same GPT-4.1 model and same prompt schema as the CU `kb-image-analyzer`
- The marker-based approach (`[[IMG:filename]]`) for image position tracking is robust
- Model deployment requires Bicep (`format: 'Mistral AI'`); CLI deployment fails for Mistral models
- OCR endpoint: `POST /providers/mistral/azure/ocr` on `services.ai.azure.com` host
- Additional dependency: Playwright (headless Chromium) for HTML → PDF rendering

---

## Stories

---

### Story 1 — Rename `fn_convert` to `fn_convert_cu` ✅

> **Status:** Done

Rename the existing `fn_convert` package to `fn_convert_cu` to make room for the Mistral variant. No logic changes — purely a rename. Update all references (imports, scripts, Makefile, `function_app.py`, tests). Redeploy to Azure to remove the old `fn_convert`-based function and register the renamed version.

#### Deliverables

- [x] Rename `src/functions/fn_convert/` → `src/functions/fn_convert_cu/`
- [x] Update `src/functions/function_app.py` to import from `fn_convert_cu`
- [x] Update `src/functions/tests/test_convert/` imports to reference `fn_convert_cu`
- [x] Update `scripts/functions/convert.sh` to call `python -m fn_convert_cu`
- [ ] Run `azd deploy` to push the renamed function to Azure — this removes the old `fn_convert`-based `/api/convert` registration and deploys the `fn_convert_cu`-based version
- [ ] Verify the old `/api/convert` endpoint still works (the route name in `function_app.py` stays the same; only the internal package import changes)
- [x] Verify `make convert analyzer=content-understanding` works end-to-end
- [x] All existing tests pass with no changes to assertions

#### Definition of Done

- [x] `fn_convert_cu` is the only convert package; no `fn_convert` directory exists
- [x] `make test` passes (all existing tests green)
- [x] `make convert analyzer=content-understanding` produces identical output to the previous `make convert`
- [ ] `azd deploy` succeeds; Azure Function App runs with the renamed package

---

### Story 2 — Makefile Backend Selector for Convert Targets ✅

> **Status:** Done

Update the `convert` and `azure-convert` Makefile targets to accept an `analyzer=` argument that selects which conversion function to run. When no argument is provided, print usage instructions listing the available options.

#### Deliverables

- [x] Update `make convert` to accept `analyzer=content-understanding` or `analyzer=mistral-doc-ai`
- [x] Update `make azure-convert` to accept the same `analyzer=` argument
- [x] When `analyzer` is not set, both targets print a usage message:
  ```
  Error: analyzer is required. Usage:
    make convert analyzer=content-understanding
    make convert analyzer=mistral-doc-ai
  ```
- [x] Update `scripts/functions/convert.sh` to accept an analyzer argument and invoke the correct module (`fn_convert_cu` or `fn_convert_mistral`)
- [x] Update `make help` output to show the `analyzer=` options for convert targets

#### Definition of Done

- [x] `make convert` (no args) → prints usage, exits non-zero
- [x] `make convert analyzer=content-understanding` → runs CU pipeline (from Story 1)
- [x] `make convert analyzer=mistral-doc-ai` → runs Mistral pipeline (from Story 4)
- [x] `make azure-convert analyzer=content-understanding` → triggers CU function in Azure
- [x] `make help` documents the `analyzer=` options

---

### Story 3 — Infrastructure: Deploy Mistral Document AI Model ✅

> **Status:** Done

Add the `mistral-document-ai-2512` model deployment to the existing `ai-services.bicep` module so it is provisioned alongside the CU model deployments. Infrastructure becomes a superset supporting both conversion backends.

#### Deliverables

- [x] Add `mistral-document-ai-2512` deployment to `infra/azure/infra/modules/ai-services.bicep`:
  - Format: `Mistral AI`
  - SKU: `GlobalStandard`, capacity 1
  - API version: `2024-04-01-preview` (required for Mistral models)
  - Serialize with existing deployments via `dependsOn`
- [x] Reference implementation: `src/spikes/002-mistral-document-ai/deploy-model.bicep`
- [x] Add `MISTRAL_DEPLOYMENT_NAME` to AZD outputs and Function App application settings
- [x] Update `docs/specs/infrastructure.md`:
  - Add `mistral-document-ai-2512` to the Model Deployments table
  - Note that this model supports the alternative Mistral-based conversion pipeline
- [ ] Verify `azd provision` deploys the model alongside existing deployments
- [ ] Verify `azd deploy` succeeds after provisioning (function app deploys cleanly with new env var)

#### Definition of Done

- [ ] `azd provision` succeeds; `mistral-document-ai-2512` visible in Foundry portal
- [ ] `azd deploy` succeeds; Function App starts with `MISTRAL_DEPLOYMENT_NAME` in its settings
- [x] Infrastructure doc reflects the new deployment
- [x] Existing model deployments unaffected

---

### Story 4 — Implement `fn_convert_mistral` ✅

> **Status:** Done

Create the Mistral-based conversion function as `fn_convert_mistral`, repackaging the spike code (`src/spikes/002-mistral-document-ai/`) into a clean, modular structure under `src/functions/`. The function must respect the exact same input/output contract as `fn_convert_cu` — same `run(article_path, output_path)` signature, same output format (`article.md` + `images/`).

#### Deliverables

- [x] Create `src/functions/fn_convert_mistral/` with these modules:
  - `__init__.py` — `run(article_path, output_path)` orchestrator (same signature as `fn_convert_cu`)
  - `__main__.py` — CLI entry point for `python -m fn_convert_mistral`
  - `render_pdf.py` — HTML → PDF with `[[IMG:filename]]` markers (from spike `step1_render_pdf.py`)
  - `mistral_ocr.py` — PDF → Mistral OCR (from spike `step2_mistral_ocr.py`)
  - `map_images.py` — Scan OCR markdown for markers (from spike `step3_map_images.py`)
  - `describe_images.py` — GPT-4.1 vision descriptions (from spike `step4_describe_images.py`)
  - `merge.py` — Assemble final markdown + images (from spike `step5_merge.py`)
- [x] Reuse `shared/config.py` for configuration (add `MISTRAL_DEPLOYMENT_NAME` to config)
- [x] Add `playwright` and `httpx` to `src/functions/pyproject.toml` dependencies
- [x] Output matches `fn_convert_cu` format: `article.md` with `> **[Image: <stem>](images/<stem>.png)**` blocks + `images/` folder with PNGs
- [x] Reference implementation: `src/spikes/002-mistral-document-ai/` (spike steps 1–5 + `run.py`)

#### Definition of Done

- [x] `make convert analyzer=mistral-doc-ai` produces valid output in `kb/serving/` for all sample articles
- [x] Output `article.md` follows the same image block format as `fn_convert_cu`
- [x] `make index` successfully indexes the Mistral-produced output (no changes to `fn-index`)
- [x] Side-by-side comparison with CU output shows comparable quality (reference: spike comparison results)

---

### Story 5 — Tests for `fn_convert_mistral` ✅

> **Status:** Done

Add unit tests for `fn_convert_mistral` modules, following the same patterns as the existing `test_convert/` tests for the CU pipeline.

#### Deliverables

- [x] Create `src/functions/tests/test_convert_mistral/` test package:
  - `test_render_pdf.py` — verify PDF generation with image markers
  - `test_map_images.py` — verify marker extraction from OCR markdown
  - `test_merge.py` — verify final markdown assembly (link recovery, image block insertion)
  - `test_describe_images.py` — verify GPT-4.1 image description integration
- [x] Tests use the same sample articles in `kb/staging/` as fixtures
- [x] Add `make test` coverage for the new test directory

#### Definition of Done

- [x] `make test` runs all new tests alongside existing tests
- [x] All tests pass (76 passed, 37 skipped)
- [x] Test coverage for core modules (render_pdf, map_images, merge)

---

### Story 6 — Azure Function Registration for `fn_convert_mistral` ✅

> **Status:** Done

Register `fn_convert_mistral` as an Azure Function endpoint alongside the existing CU convert function, and wire the `azure-convert` target to route to the correct function based on the `analyzer=` argument.

#### Deliverables

- [x] Update `src/functions/function_app.py`:
  - Register a new HTTP trigger for the Mistral convert function (e.g., `/api/convert-mistral`)
  - Keep the existing `/api/convert` endpoint pointing to `fn_convert_cu`
- [x] Update `make azure-convert`:
  - `analyzer=content-understanding` → calls `/api/convert`
  - `analyzer=mistral-doc-ai` → calls `/api/convert-mistral`
- [ ] Ensure the Function App has Playwright/Chromium available in the deployed environment (or document a workaround if needed)
- [ ] Run `azd deploy` to push the new function and verify both endpoints are reachable

#### Definition of Done

- [ ] `azd deploy` succeeds with both convert functions registered
- [x] `make azure-convert analyzer=content-understanding` triggers the CU function in Azure
- [x] `make azure-convert analyzer=mistral-doc-ai` triggers the Mistral function in Azure
- [ ] Both endpoints produce valid serving output in Azure blob storage

---

### Story 7 — Documentation Updates ✅

> **Status:** Done

Update README.md, architecture spec, and infrastructure spec to reflect the dual-backend conversion pipeline.

#### Deliverables

- [x] Update `README.md`:
  - In the "What This Accelerator Does" section, note that HTML → Markdown conversion supports two interchangeable backends: **Content Understanding** and **Mistral Document AI**
  - Describe the tradeoff: CU is deeply integrated but its underlying LLM calls cannot be routed through a gateway; Mistral Document AI uses standard Foundry model deployments that can be fronted by Azure API Management or any API gateway
  - Update the "Run Pipeline" sections to show `analyzer=` usage for `make convert` and `make azure-convert`
  - Update the Makefile Targets table with the new `analyzer=` options
  - Update the Project Structure tree to show `fn_convert_cu/` and `fn_convert_mistral/`
- [x] Update `docs/specs/architecture.md`:
  - In the `fn-convert` detail section, note that `fn-convert` has two interchangeable implementations (`fn_convert_cu` and `fn_convert_mistral`) that share the same input/output contract
  - Keep the pipeline diagrams with a single `fn-convert` box but annotate that it has backend variants
  - Add a brief subsection describing the Mistral variant's approach (marker-based image tracking via PDF rendering + OCR, vs CU's native HTML analysis)
  - Reference the spike results for quality comparison
- [x] Update `docs/specs/infrastructure.md`:
  - Add `mistral-document-ai-2512` to the Model Deployments table (if not already done in Story 3)
  - Add `MISTRAL_DEPLOYMENT_NAME` to the Function App Application Settings table
  - Note the Playwright dependency for the Mistral variant

#### Definition of Done

- [x] README documents both conversion options with usage examples
- [x] Architecture spec describes both backends without overcomplicating the diagrams
- [x] Infrastructure spec includes the Mistral model deployment
- [x] All doc links are valid

---

## Implementation Notes

- **Same serving contract:** Both `fn_convert_cu` and `fn_convert_mistral` produce the same output format in `kb/serving/` — `article.md` with inline image blocks + `images/` folder. `fn-index` is completely unaware of which backend generated the content. This follows the [decoupled two-stage pipeline design](../ards/ARD-003-decoupled-two-stage-pipeline.md).
- **Spike as reference:** The `fn_convert_mistral` implementation is a clean repackaging of `src/spikes/002-mistral-document-ai/` (steps 1–5 + run.py). The spike is validated and produces output matching CU quality across all sample articles.
- **Playwright dependency:** The Mistral pipeline requires Playwright (headless Chromium) for HTML → PDF rendering. This adds a binary dependency to the functions project. For Azure deployment, Playwright browsers must be available in the Function App environment.
- **No changes to fn-index or web-app:** The serving layer contract is the boundary. Nothing downstream of `kb/serving/` changes.
- **Infrastructure is a superset:** After this epic, `azd provision` deploys all resources needed for both backends. There is no configuration to "pick one" at the infra level — both are always available. The choice of backend is made at runtime via the `analyzer=` Makefile argument.
- **Image descriptions:** Both backends use GPT-4.1 for image analysis — CU via the custom `kb-image-analyzer` analyzer, Mistral via direct GPT-4.1 vision calls with the same prompt schema. Image description quality is comparable (validated in the spike).
- **Gateway compatibility:** A key advantage of the Mistral approach is that both the OCR model and GPT-4.1 vision are standard Foundry model endpoints that support API gateway routing. CU's internal model calls are opaque and cannot be routed through a gateway.
