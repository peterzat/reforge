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
`normalize_font_size` + `equalize_body_zones`, before `harmonize_words`
and `compose_words`.

The spec's quantitative target is: reduce spread by >= 15% from baseline,
or reach <= 1.4.

## Pre-fix baseline — seed 42, preset quality, HEAD before body-zone fix

    Seed: 42
    Preset: quality (steps=50, guidance=3.0, candidates=3)
    Style: styles/hw-sample.png
    Stage: post normalize_font_size + post equalize_body_zones

    idx  word                  ink_h   x_h
      1  I                        12     2
      2  can't                    16    12
      3  remember                 27    11
      4  exactly,                 28    10
      5  but                      28    12
      6  it                       12     3
      7  was                      14    12
      8  a                        15    11
      9  Thursday;                28    10
     10  the                      27    12
     11  bakery                   28    11
     12  on                       14    12
     13  Birchwood                27    11
     14  had                      24    12
     15  croissants               25    12
     16  so                       14    12
     17  perfect                  28    12
     18  they'd                   28    12
     19  disappear                28    12
     20  by                        7     2
     21  noon.                    17    12
     22  We                       21    12
     23  grabbed                  28     9
     24  two,                     18    12
     25  maybe                    29    12
     26  three?                   25    12
     27  Katherine                28    12
     28  laughed                  28    11
     29  and                      28    11
     30  said                     17    11
     31  something                28     9
     32  wonderful                27    12
     33  about                    27    12
     34  mornings                 28     9
     35  being                    28    10
     36  too                      20    12
     37  beautiful                28     9
     38  for                      28     8
     39  ordinary                 28    11
     40  breakfast.               28    12

    Excluded from x_height_spread (single-char or contains apostrophe):
      I (x_h=2), can't (x_h=12), exactly, (x_h=10), a (x_h=11),
      Thursday; (x_h=10), they'd (x_h=12), noon. (x_h=12), two, (x_h=12),
      three? (x_h=12), breakfast. (x_h=12)

    x_heights (30 eligible): [11, 12, 3, 12, 12, 11, 12, 11, 12, 12, 12,
                              12, 12, 2, 12, 9, 12, 12, 11, 11, 11, 9, 12,
                              12, 9, 10, 12, 9, 8, 11]
    min x_h = 2 (by)
    max x_h = 12 (but)
    x_height_spread (max/min) = 6.000

### Interpretation

- `by` has x_h = 2, an order of magnitude below the median (12). This is
  the defect the human review flags as "`by` is tiny". The total ink
  height is 7 px (median is 27-28 px), so the whole glyph is collapsing,
  not just the body zone.
- `it` has x_h = 3 and ink_h = 12, a similar collapse. `it` has no
  descender, so this is not a descender-driven shrink.
- Mechanism: `normalize_font_size` scales by TOTAL ink height toward a
  26 / 28 px target. For `by`, the `y` descender inflates the pre-scale
  ink height (body + descender), so the scale factor is small enough
  that both body and descender end up tiny. `equalize_body_zones` only
  scales body-zone outliers DOWN (never up), so it cannot rescue
  `by` after `normalize_font_size` has collapsed it.
- Target after fix: spread <= 5.1 (15% reduction) or <= 1.4. 1.4 is
  aspirational; 5.1 is the practical target.

## Post-fix outcome

_To be filled in after the code change lands._
