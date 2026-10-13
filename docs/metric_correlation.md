# Metric-Human Correlation

- Generated: 2026-10-13T16:45:47Z
- Reviews directory: `reviews/human`
- Reviews with composition rating: 34
- Correlation: Spearman rank (`scipy.stats.spearmanr`), two-sided p.

Spearman rank correlation between each cv_metric and the human composition rating (1-5). Sample size is small; p-values are indicative, not strict. Prefer the magnitude and sign of rho.

## Correlations

| metric | rho | p | n |
| --- | ---: | ---: | ---: |
| `ink_contrast` | -0.339 | 0.050 | 34 |
| `baseline_alignment` | +0.293 | 0.092 | 34 |
| `word_readability_rate` | +0.215 | 0.272 | 28 |
| `background_cleanliness` | -0.175 | 0.323 | 34 |
| `composition_score` | -0.141 | 0.426 | 34 |
| `word_height_ratio` | -0.131 | 0.459 | 34 |
| `overall` | +0.125 | 0.480 | 34 |
| `ocr_accuracy` | +0.115 | 0.517 | 34 |
| `punctuation_visibility` | -0.109 | 0.780 | 9 |
| `layout_regularity` | +0.106 | 0.551 | 34 |
| `style_fidelity` | -0.090 | 0.612 | 34 |
| `stroke_weight_consistency` | -0.087 | 0.626 | 34 |
| `ocr_min` | +0.084 | 0.637 | 34 |
| `blank_word_ratio` | -0.043 | 0.811 | 34 |
| `height_outlier_ratio` | +0.039 | 0.827 | 34 |
| `height_outlier_score` | -0.039 | 0.827 | 34 |

## Constant metrics

These metrics had zero variance across the dataset and cannot be correlated:

- `gray_boxes`: constant = 1.0000 (n=34)
- `slant_consistency`: constant = 0.0000 (n=34)

## Candidate-pick agreement

Candidate-pick agreement: insufficient data (n<10), observed n=9, agreements=3

## Primary metric selection (spec 2026-04-10 B1)

Selection bar: positive rho, |rho| >= 0.2, p < 0.3. At most 3. If fewer clear the bar, pick only those that do.

**Clear the selection bar.** This list does not change what gates: the regression test gates on `PRIMARY_METRICS` in `reforge/config.py` (currently `height_outlier_score`). Promote or demote via an explicit spec update.

- `baseline_alignment`: rho = +0.293, p = 0.092, n = 34
- `word_readability_rate`: rho = +0.215, p = 0.272, n = 28

## Held-out replication (reviews before vs. from `2026-04-10_141808`)

The gating metrics were selected on the reviews before the cutoff. Reviews from the cutoff on are held out: a metric that tracks human preference should keep a positive rho there.

| metric | rho before | n | rho held out | n |
| --- | ---: | ---: | ---: | ---: |
| `height_outlier_score` (gating) | +0.302 | 16 | -0.222 | 18 |
| `background_cleanliness` | -0.223 | 16 | -0.273 | 18 |
| `baseline_alignment` | +0.273 | 16 | +0.113 | 18 |
| `blank_word_ratio` | -0.094 | 16 | +0.000 | 18 |
| `composition_score` | -0.240 | 16 | -0.016 | 18 |
| `gray_boxes` | -- | 16 | -- | 18 |
| `height_outlier_ratio` | -0.302 | 16 | +0.222 | 18 |
| `ink_contrast` | -- | 16 | -0.420 | 18 |
| `layout_regularity` | -0.250 | 16 | +0.337 | 18 |
| `ocr_accuracy` | -0.018 | 16 | +0.048 | 18 |
| `ocr_min` | -0.009 | 16 | +0.087 | 18 |
| `overall` | +0.126 | 16 | +0.048 | 18 |
| `punctuation_visibility` | -- | 0 | -0.109 | 9 |
| `slant_consistency` | -- | 16 | -- | 18 |
| `stroke_weight_consistency` | -0.083 | 16 | +0.080 | 18 |
| `style_fidelity` | -0.206 | 16 | +0.096 | 18 |
| `word_height_ratio` | +0.002 | 16 | -0.171 | 18 |
| `word_readability_rate` | +0.175 | 10 | +0.198 | 18 |

## Negative correlations (why this spec exists)

The following metrics have *negative* rank correlation with human composition rating at |rho| >= 0.2: `ink_contrast`.

This is the direct evidence behind the 2026-04-10 spec's framing that "the loop is a competent hill-climber but not a convergence machine because its proxies are misaligned." On this dataset, higher values of these CV metrics coincide with *lower* human composition ratings, not higher ones. They are tracked as diagnostics (printed in the ledger and on regression) but they do not gate.

Plausible explanations, none confirmed (that is a task for a future spec, not this one):

- **Dataset contamination.** Many of the reviews were taken during active iteration, so code changes covary with metric changes. A metric that moved up because of a change the human disliked looks negatively correlated even if the metric itself is neutral. N=16 cannot separate this from a genuine inverse relationship.
- **Over-normalization.** `composition_score` and `layout_regularity` both reward geometric regularity. Humans tolerate and even prefer some irregularity in handwriting; pipelines that hit these metrics harder may look more machine-generated, which degrades the "handwritten note" impression.
- **Wrong ground truth.** `style_fidelity` measures similarity to the style image, not to "good handwriting." If the style image has quirks, matching them may reduce human rating.
- **Saturation + noise.** `background_cleanliness` is near 1.0 on every review; the tiny variance it does have may be driven by rendering artifacts unrelated to composition quality.

**Treat these negative signals with caution.** Do not invert them into "minimize X" objectives without new evidence. The honest reading is that the dataset does not support using them as gating metrics at all, in either direction. They remain tracked so future turns can see if the sign stabilizes or flips as more reviews arrive.

## Methodology notes

- N = 34 is small. p-values come from `scipy.stats.spearmanr` (two-sided Student's t) and should be read as "plausibly non-zero" rather than strict significance.
- Rerun this script after each `make test-human` session. The script is idempotent: `python scripts/metric_correlation.py --output docs/metric_correlation.md` regenerates the full document including selection rationale.
- The candidate-pick sample (n=9) is below the 10-review reporting threshold. When n >= 10, the agreement-rate section will populate and a candidate-disagreement gate can be considered.
- Multiple comparisons: about 16 metrics are tested against the same ratings. Under the null, p < 0.3 passes about 30% of them, so the selection bar alone expects ~5 false positives. Require held-out replication (table above) before a metric gates.
- Instrument drift: each review's `cv_metrics` were computed by the metric code at that review's commit, and early reviews were unseeded (seeding began 2026-04-17). Correlations pool different instrument versions.
- Known-broken instrument `baseline_alignment`: measures word-canvas bottoms, not ink baselines (evaluate/visual.py check_baseline_alignment ignores img).
- Known-broken instrument `style_fidelity`: one third of it is _xheight_ratio, which is ~1.0 for nearly every word.
- Negative correlations (when present) are logged above as diagnostics. They are NOT used to flip metric directions; the correlation is too weak and confounded by dataset contamination during active iteration.
