# Architecture Research — Dropping the PDF Conversion Step

> Research notes for the Content Understanding spike.
> Updated 2026-02-13 with empirical testing results.

---

## Question

Can we eliminate the HTML→PDF conversion step from the pipeline? The PDF step (Playwright headless Chromium) adds complexity, dependencies, and potential image quality degradation. We want to explore processing HTML directly for text and processing the source images individually.

## Experiments Conducted

### Experiment 1: Base64-Embedded Images in HTML → CU

**Hypothesis:** Encoding article images as `data:image/png;base64,...` data URIs in the HTML `<img>` tags might let CU detect and describe them.

- Created `index-base64.html` with all 4 images embedded (173 KB total, under 1 MB limit)
- Sent to `prebuilt-documentSearch` via binary upload (`content_type="text/html"`)

**Result:** ❌ **No change.** Same 2,919-char markdown, 0 figures, 0 hyperlinks. CU strips data URIs.

### Experiment 2: HTML vs PDF → CU Side-by-Side

| Feature | HTML → CU | HTML+Base64 → CU | PDF → CU |
|---|---|---|---|
| Markdown length | 2,919 chars | 2,919 chars | 7,305 chars |
| Figures | 0 | 0 | 4 |
| Hyperlinks (JSON) | 0 | 0 | 1 |
| Tables (JSON) | 0 | 0 | 2 |
| Tables (in MD text) | ✅ Present | ✅ Present | ✅ Present |
| Summary field | ✅ Good | ✅ Good | ✅ Good |
| kmsearch link in MD | ❌ Text only, no URL | ❌ Text only, no URL | ✅ Full link |

### Experiment 3: Individual Image Analysis via CU

- `prebuilt-documentSearch` on a single PNG (23 KB): ✅ Works — 3 sub-figures detected, descriptions generated, Summary field returned
- `prebuilt-image` on a single PNG: ❌ Requires custom analyzer with `fieldSchema` — not runnable standalone

### Experiment 4: HTML Image Mapping

All `<img>` tags use absolute server paths. The filename portion maps 1:1 to local `.image` files (confirmed PNGs, 13–40 KB each). The `<img>` position in the HTML DOM reliably indicates where in the document each image belongs.

## Conclusion

**The PDF conversion step can be dropped.** The recommended approach:
1. Send HTML to CU for text/table extraction + Summary
2. Parse the HTML DOM to extract image positions and hyperlink URLs
3. Analyze each image individually through CU
4. Merge all results into the final markdown

See [architecture-proposal.md](architecture-proposal.md) for the full pipeline design (Option 1: HTML-Direct Pipeline).
