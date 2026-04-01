## Spec -- 2026-04-01 -- Word clipping: diagnose and fix truncated characters

**Goal:** Words in the generated output are missing characters at the left edge, right edge, or both. "morning" renders as "mor", "quiet" as "ciet", "favorite" as "vorite", "fingers" as "ingers". The user sees white regions where ink should be. Diagnose whether the cause is generation (canvas too narrow, model not placing ink), postprocessing (defense layers blanking legitimate ink), or composition (clipping during layout), then fix it so every word is fully rendered and readable.

### Acceptance Criteria

- [ ] A diagnostic script or test exists that, given a word image and its target text, reports: (a) whether ink extends to within 5px of the left/right canvas edge before postprocessing, (b) how many ink columns each postprocessing layer removes from the left 25% and right 25% of the image, (c) OCR accuracy before vs. after postprocessing. This instrument is the foundation for root-cause analysis and must exist before any fix is attempted.
- [ ] Running the diagnostic on at least 10 words from the demo text identifies which layer(s) are responsible for the majority of character loss (generation, body-zone removal, isolated-cluster filter, word-level gray cleanup, font normalization, or compositor ink threshold). The finding is recorded in a comment or log, not just observed interactively.
- [ ] After the fix, demo.sh produces output where every word achieves OCR accuracy >= 0.5 (per-word, not just average). Currently roughly half the words score below 0.5 due to clipping.
- [ ] After the fix, no word in the demo output loses more than 1 character from either edge compared to its target text, as measured by OCR. Words like "morning" must not render as "mor".
- [ ] The fix does not reintroduce gray-box artifacts. The existing `check_gray_boxes()` test must still pass, and the quick test suite (`tests/quick/`) must still pass without modification.
- [ ] A medium-tier test generates at least 5 words of varying length (3-8 chars) and asserts that per-word OCR accuracy averages above 0.6 and no single word scores below 0.3. This replaces or extends the existing medium OCR test.
- [ ] The diagnostic instrument is preserved as a reusable function (not a throwaway script) so future postprocessing changes can be regression-tested against it.

### Context

**What the output looks like (2026-04-01).** Inspecting result.png shows approximately half of all words are truncated. The pattern is a mix of left-side and right-side clipping: "morning" -> "mor", "shadows" -> "shado" (right-side); "quiet" -> "ciet", "songs" -> "ongs", "fingers" -> "ingers" (left-side); some words lose characters from both sides. The missing regions appear as white space, consistent with either the model not generating ink in that area or postprocessing blanking columns to 255.

**Candidate root causes (must be confirmed by diagnostic, not assumed).**

1. Canvas width too narrow. The 256px canvas fits ~8 characters naturally. `compute_canvas_width()` only widens for 9-10 char words. But many 5-7 char words are also clipped on the right. This could mean the model sometimes places ink too large or too spread out, running off the right edge.

2. Body-zone noise removal (Layer 2). This layer blanks columns where body-zone ink ratio is below 5% (`BODY_ZONE_INK_THRESHOLD`). The connected-component preservation logic was added to fix left-clipping of "T", but it uses strong ink (< 128) for connectivity. If edge characters are rendered as medium-gray (128-180), they will not form connected components with the main body, and their columns will be blanked.

3. Isolated-cluster filter (Layer 3). Discards ink clusters separated by >= 20px gaps from the main cluster. If a character is separated from the rest by a wide gap (common with DiffusionPen's variable spacing), it gets removed entirely.

4. Word-level gray cleanup (Layer 3b). Removes gray pixels (160-220) not adjacent to strong ink (< 128) within a 5x5 dilation radius. Edge characters that are faint could be removed here.

5. Font normalization. `normalize_font_size()` scales images using `cv2.resize()` with `INTER_AREA`. The scale factor clamp of 0.3-1.2 and the area-per-char target could result in images being scaled down, with edge pixels lost to interpolation at the boundary.

6. Compositor ink threshold. `COMPOSITOR_INK_THRESHOLD = 200` means any pixel >= 200 is not composited. Faint edge strokes above this threshold are invisible in the final output.

**Investigation approach.** The diagnostic instrument should run on raw VAE output (before any postprocessing) and after each layer, measuring ink extent and OCR accuracy at each stage. This will show exactly where characters are being lost. Only after the cause is confirmed should fixes be attempted. If the cause is generation (canvas too narrow), the fix is in `compute_canvas_width()` or how the model is conditioned. If the cause is postprocessing, the fix is in the specific defense layer(s). Multiple causes are likely; the diagnostic will reveal their relative contribution.

**Coding practices (from zat.env).** Work in small increments: build the diagnostic first, observe the data, then fix one cause at a time. Run tests after each change. If a fix causes regression (gray boxes, test failures), revert and try a different approach. Two consecutive failed attempts means stop and re-evaluate.

---
*Prior spec (2026-04-01): Readable output: fix clipped characters, add OCR validation, repair quality score (18/18 criteria met).*

<!-- SPEC_META: {"date":"2026-04-01","title":"Word clipping: diagnose and fix truncated characters","criteria_total":7,"criteria_met":0} -->
