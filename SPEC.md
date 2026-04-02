## Spec -- 2026-04-02 -- Word density and natural line composition

**Goal:** The generated output currently fits only ~3-4 words per line (~16 characters including spaces), producing a columnar, spaced-out appearance that does not resemble a handwritten note. A real handwritten note on similar paper would have 6-8 words per line (~35-45 characters). Increase word density to that range, add natural right-edge raggedness, and use demo text that exercises varied word lengths and punctuation.

### Acceptance Criteria

#### A. Word density: more words per line

The current word images are too large relative to the page. The font normalization targets (SHORT_WORD_HEIGHT_TARGET=32, long=35) combined with the dynamic page width algorithm (which shrinks the page to maintain near-square aspect ratio) produce ~3-4 words per line regardless of size changes. Both the word size and the page width computation need to change together.

- [x] A1. The demo output (result.png from demo.sh) contains 5-6 words on the widest non-final line of each paragraph. Measure by counting words per line from the word_positions output. Currently ~3-4 words per line.
- [x] A2. The average characters per line (including spaces, excluding final lines of paragraphs) is between 30 and 50. Currently ~16. Measure from demo output word_positions and the word strings.
- [x] A3. The page aspect ratio targets 3:4 portrait (width:height = 0.75). The dynamic page width algorithm produces a page width that results in the target word density, not a near-square page that defeats size reductions. Replace the current near-square target (0.7-1.3) with a 3:4 portrait target. Blank space below the last line of text is trimmed (bottom margin matches top margin, no excess whitespace).
- [x] A4. The word images remain legible after size reduction. No letter distortion, merging, or loss of detail. Verify by running OCR accuracy check (make test-ocr) and confirming no regression below 0.90 from the current 0.967 baseline.
- [x] A5. A quick test validates that the page width computation produces at least 6 words per line for a 40-word input with average word width representative of post-normalization output.

#### B. Ragged right margin

The D1-D3 changes from the prior spec added jitter and line shortening, but the right edge still looks fairly uniform. Non-final lines cluster at 0.74-0.84 of page width, a span of only 10%. Real handwriting has more variation: some lines end early because of long upcoming words, others because the writer chose to break.

- [x] B1. The standard deviation of right-edge x-positions across non-final lines (excluding last line of each paragraph) is at least 8% of page width. Currently the variation exists but is dominated by paragraph-final lines. The metric should exclude those.
- [x] B2. No two adjacent non-final lines end within 3% of page width of each other. Some variation between consecutive lines is required to break the columnar appearance. This is a stricter requirement than B1's aggregate std.
- [x] B3. The ragged right margin looks natural on visual inspection. Lines should end at varying positions, with some lines noticeably shorter than others, like a typewriter without right justification. The variation should not look random or chaotic.

#### C. Demo text: varied word lengths and punctuation

The current demo text ("The morning sun cast long shadows...") has a narrow word length distribution: avg 4.7 chars, 30% are 1-3 chars, only 9 words are 7+ chars, longest is 8. This monotony contributes to the columnar appearance because most words are similar width. It also under-exercises punctuation (only 5 words have trailing periods or commas).

- [x] C1. Replace the demo text in demo.sh with the following text (two paragraphs, 42 words, exercises varied lengths and punctuation):

    "I can't remember exactly, but it was a Thursday; the bakery on Birchwood had croissants so perfect they'd disappear by noon.\nWe grabbed two, maybe three? Katherine laughed and said something wonderful about mornings being too beautiful for ordinary breakfast."

    Validation: (a) 8+ char words: remember, exactly, Thursday, Birchwood, croissants, something, wonderful, beautiful, mornings, ordinary, breakfast, Katherine, disappear. (b) 1-2 char words: I, it, a, on, so, by, We, (c) mid-sentence punctuation: comma after "exactly" and "two", semicolon after "Thursday". (d) contractions: can't, they'd. (e) non-period punctuation: "three?" (question mark).
- [x] C2. The demo text is at least 2 paragraphs, at least 35 words total, and contains only characters in the supported CHARSET.
- [x] C3. Punctuation attached to words (e.g., "wall," or "right?") does not cause visible artifacts: no extra-wide spacing after punctuation, no missing punctuation in the output, no distortion of the preceding letter. Verify visually on demo output.

#### D. Interaction validation

Changes to word size, page width, and text content interact with existing quality systems (height harmonization, stroke weight, baseline alignment, gray-box defense). These must not regress.

- [x] D1. All quick tests pass (make test-quick).
- [x] D2. All regression tests pass (make test-regression). If baselines shift due to size changes, update them, but no metric should drop more than 5% from its current value.
- [x] D3. The overall quality score from demo.sh remains above 0.5 (the current quality gate).
- [x] D4. The output image (result.png) is a single grayscale PNG with no gray box artifacts (gray_boxes score = 1.0).

### Context

**Why word size alone does not fix density.** The compute_page_width() function in layout.py searches for a page width that brings the aspect ratio close to 1.0 (TARGET_ASPECT_MIN=0.7, TARGET_ASPECT_MAX=1.3). When word images shrink, the algorithm picks a narrower page to maintain the square shape, keeping words/line constant at ~3-4. The fix is to change the aspect ratio target to 3:4 portrait (0.75), so the page is wider relative to its height. The bottom of the page should be trimmed to match the top margin, eliminating blank whitespace below the last line.

**Font height targets and OCR.** Prior experiments (E1 in the previous spec) found that converging the short/long height targets caused OCR regression. The current targets (32/35) are at a tested optimum for the 1.1x ratio. Reducing both targets proportionally (e.g., 22/24 maintaining the 1.1x ratio) is a different change: it preserves the ratio while scaling everything down. This has not been tested and may interact differently with OCR. A/B testing is mandatory.

**Ragged right mechanics.** The current D2 implementation (0-8% line shortening) is too subtle. Real handwriting raggedness comes from word-boundary decisions: a writer does not start a word if it might not fit, leaving extra space. Increasing the shortening range or adding a "don't start a word if it would fill >85% of the line" heuristic would produce more natural breaks.

**Punctuation and canvas width.** Punctuation adds characters to the word string but not proportional ink. A 5-char word and a 5-char+period word ("stone" vs "stone.") get similar canvas width from the adaptive width computation, but the period occupies minimal horizontal space. This can create trailing whitespace inside the word image. The post-generation tight crop should handle this, but worth verifying.

**zat.env practices.** Work in small increments. Test after each change. The recommended order: (1) Change demo text (C1-C2, no code change, just demo.sh). (2) Reduce font height targets and fix page width computation together (A1-A3). (3) Run OCR validation (A4). (4) Tune ragged right (B1-B3). Each step should pass make test-quick before proceeding.

---
*Prior spec (2026-04-02): Natural handwriting: visual fidelity and test performance (16/22 criteria met). Completed: test perf (A), stroke weight (B), layout jitter (D1-D4), height harmonization (E2-E3), ruled-line alignment (F). Open: slant (C1-C3, C5), remaining layout (D5-D6), font target tuning (E1).*

<!-- SPEC_META: {"date":"2026-04-02","title":"Word density and natural line composition","criteria_total":14,"criteria_met":14} -->
