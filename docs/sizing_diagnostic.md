# Body-zone sizing diagnostic (spec 2026-04-19)

Tracks the `size_inconsistent` composition defect using an x-height-spread
statistic measured on the demo.sh two-paragraph sentence. The diagnostic
utility is `scripts/measure_word_sizing.py`; this doc captures pre-fix
baselines and post-fix outcomes.

## Metric

`x_height_spread = max(x_heights) / min(x_heights)` across word tokens that
are alphabetic (via `str.isalpha`) and >= 2 chars. Single-char tokens (`I`,
`a`) and contractions with punctuation (`can't`, `they'd`) are excluded:
contractions are stitched from two DP passes with a different sizing path,
and single-char tokens are handled by an independent short-word code path.
The metric is measured at the stage that feeds composition, i.e. after
`normalize_font_size` + `equalize_body_zones` + `harmonize_words`. This is
the composition-ready state. Measuring earlier (pre-harmonize) paints a
misleading picture because `harmonize_heights` then inflates short no-
ascender words and shifts where the body-zone outliers live.

The spec's quantitative target is: reduce spread by >= 15% from baseline,
or reach <= 1.4.

## Pre-fix baseline — seed 42, preset quality, HEAD before body-zone fix

    Seed: 42
    Preset: quality (steps=50, guidance=3.0, candidates=3)
    Style: styles/hw-sample.png
    Stage: post harmonize_words (composition-ready state)

    idx  word                  ink_h   x_h
      1  I                        24     4
      2  can't                    25    19
      3  remember                 27    11
      4  exactly,                 28    10
      5  but                      28    12
      6  it                       25     4
      7  was                      24    21
      8  a                        23    19
      9  Thursday;                28     9
     10  the                      27    12
     11  bakery                   28    11
     12  on                       24    20
     13  Birchwood                27    11
     14  had                      25    13
     15  croissants               25    12
     16  so                       25    22
     17  perfect                  28    12
     18  they'd                   28    12
     19  disappear                28    12
     20  by                       25     7
     21  noon.                    24    18
     22  We                       24    14
     23  grabbed                  28     9
     24  two,                     24    17
     25  maybe                    27    12
     26  three?                   25    12
     27  Katherine                28    12
     28  laughed                  28    11
     29  and                      28    11
     30  said                     25    17
     31  something                28     9
     32  wonderful                27    12
     33  about                    27    12
     34  mornings                 28     9
     35  being                    28    10
     36  too                      25    15
     37  beautiful                28     9
     38  for                      28     8
     39  ordinary                 28    10
     40  breakfast.               28    11

    Excluded from x_height_spread (single-char or contains apostrophe):
      I (x_h=4), can't (x_h=19), exactly, (x_h=10), a (x_h=19),
      Thursday; (x_h=9), they'd (x_h=12), noon. (x_h=18), two, (x_h=17),
      three? (x_h=12), breakfast. (x_h=11)

    x_heights (30 eligible): [11, 12, 4, 21, 12, 11, 20, 11, 13, 12, 22,
                              12, 12, 7, 14, 9, 12, 12, 11, 11, 17, 9,
                              12, 12, 9, 10, 15, 9, 8, 10]
    min x_h = 4 (it)
    max x_h = 22 (so)
    x_height_spread (max/min) = 5.500

### Interpretation

- `it` has x_h = 4 despite ink_h = 25. `harmonize_heights` has already
  inflated its total height to match the median, but its body zone stays
  small because compute_x_height measures the "dense" rows and `it` has
  mostly ascender-like sparse rows.
- `so`, `was`, `on`, `a`, `noon,`, `two,`, `said`, `too` (short words
  without ascenders/descenders) have x_h = 14 to 22. `harmonize_heights`
  scales their total ink up to the median band, but since their whole
  glyph IS body zone (no ascender or descender eats the scaled-up
  height), the body zone balloons. That's the visual "short word looks
  chunky next to tall word" effect.
- `by` has x_h = 7 (actually closer to median than pre-harmonize, because
  harmonize pulled its ink height up from 7 to 25). Still a negative
  outlier because the `y` descender takes most of the ink height.
- Mechanism: `normalize_font_size` scales by TOTAL ink, which gives
  descender-heavy words starved bodies. `equalize_body_zones` (pre-
  harmonize) scales down oversized bodies, but at that stage short
  words have not yet been ink-inflated, so their bodies aren't visibly
  oversized yet. `harmonize_heights` then inflates short words, creating
  post-harmonize body-zone outliers that the pre-harmonize pass never
  saw.
- Fix direction: add a post-harmonize body-zone pass that scales down
  words with x_h > 1.05 * median(x_h). This catches `so` / `was` / `on`
  etc. after they have been ink-inflated. Simulated target: spread
  drops from 5.5 to ~3.15 (max capped at 12.6, min "it" at 4).
- Target after fix: spread <= 4.67 (15% reduction) or <= 1.4. The
  <= 1.4 path would require rescuing `it` / `by`, which lacks a safe
  lever (all the levers inflate ink_h and break the regression gate).
  4.67 is the practical target.

## Post-fix outcome — spec escaped after two failed attempts

Both attempts reduced the numeric `x_height_spread` but introduced the
same human-observed "superscript" regression. The conclusion is that
x-height-spread is orthogonal to the human perception of
`size_inconsistent`, and the spec's stated lever is wrong.

### Attempt 1 (commit `cdb7dad`, reverted in `484c89b`)

Added `equalize_body_zones_pass2(imgs)` to `font_scale.py` and called
it in `pipeline.py` after `harmonize_words`. Scales DOWN any word
whose `_effective_x_height` exceeds `1.05 * median_xh`. Image height
shrinks with the content.

- Numeric result: spread 5.500 -> 4.333 on seed 42 (21% reduction).
- `make test-regression`: 304 passed, primary gates hold on seeds 42/137/2718.
- `make test-quick`: 306 passed.
- Human review `reviews/human/2026-04-19_215858.json`:
  - sizing A/B: 4/5 (new variant preferred over pre-fix)
  - composition: 3/5 (unchanged numerically)
  - freeform notes: "size and baseline inconsistencies, but only on a
    few specific words. The first sentence widely varies ('I can't' is
    superscript, as is 'it was a', and 'exactly' is also too high.
    Significant visual regression. Other small+superscript words:
    'so', and 'by'".
- Mechanism of the regression: `cv2.resize` produced a shorter image
  for each scaled-down word. `compose_words` computes a per-line
  baseline as the median of per-word baselines and clamps outliers
  (> 20% from median) to the median. A shrunk word's baseline (e.g.
  row 30 of a 38-row image) deviates >20% from the line median
  (row 50 of 64-row neighbors), gets clamped to 50, but the shrunk
  image has no content at row 50 -- its ink is at rows 12 to 28. The
  compose step places the image at the line's y-anchor and the ink
  ends up in the top of its slot, reading as superscript.

### Attempt 2 (uncommitted; discarded after preview)

Same `equalize_body_zones_pass2` algorithm, but image height is
preserved: the scaled-down content is pasted into a canvas matching
the original height, positioned so its ink bottom aligns with the
original ink bottom (baseline preservation). Width scales
proportionally.

- Numeric result: spread 5.500 -> 4.333 on seed 42 (same 21% reduction).
- `make test-regression`: 309 passed.
- `make test-quick`: 307 passed.
- Visual preview via `./demo.sh` + `./qpeek.sh result.png`: user
  confirmed "the 'superscript' issue persists like we saw before".
- Why baseline preservation was not enough: even with
  baseline-correct placement, the shrunk word is *visibly shorter*
  than its neighbors on the same line. The human eye reads a word
  whose top extends less far than its neighbors' as "raised", even
  when its bottom sits on the same baseline. The defect the spec
  calls "size_inconsistent" is not really x-height disparity -- it
  is cross-word *total-height* disparity against a visual reference
  of the taller neighbors, and the only way to fix that within this
  pipeline is to inflate the short words' total ink height, which
  is exactly what `harmonize_heights` already does and exactly what
  CLAUDE.md's `height_outlier_score` gate is designed to tolerate.

### Conclusion

`x_height_spread` reduction is the wrong lever for `size_inconsistent`.
A future turn targeting `size_inconsistent` should either:

1. Attack composition/layout: teach `compose_words` to place
   visually-shorter words so they read as naturally shorter (e.g.
   adjust per-line baselines when word heights are bimodal).
2. Attack the finding definition: the reviewer's "size_inconsistent"
   flag may describe perceived unevenness rather than metric
   disparity. A dedicated human-eval type could elicit which specific
   words are flagged, producing a different, more actionable
   diagnostic than x_height_spread.
3. Accept the plateau: note the finding as a wrapper-layer structural
   limit (like the single-char sizing plateau) and stop iterating.

The diagnostic script (`scripts/measure_word_sizing.py`) and this doc
are preserved so a future lever-investigation turn starts with a
measured baseline rather than speculation.
