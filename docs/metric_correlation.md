# Metric-Human Correlation

- Generated: 2026-04-10T14:18:08Z
- Reviews directory: `reviews/human`
- Reviews with composition rating: 16
- Correlation: Spearman rank (`scipy.stats.spearmanr`), two-sided p.

Spearman rank correlation between each cv_metric and the human composition rating (1-5). Sample size is small; p-values are indicative, not strict. Prefer the magnitude and sign of rho.

## Correlations

| metric | rho | p | n |
| --- | ---: | ---: | ---: |
| `height_outlier_ratio` | -0.302 | 0.255 | 16 |
| `height_outlier_score` | +0.302 | 0.255 | 16 |
| `baseline_alignment` | +0.273 | 0.307 | 16 |
| `layout_regularity` | -0.250 | 0.350 | 16 |
| `composition_score` | -0.240 | 0.372 | 16 |
| `background_cleanliness` | -0.223 | 0.406 | 16 |
| `style_fidelity` | -0.206 | 0.443 | 16 |
| `word_readability_rate` | +0.175 | 0.628 | 10 |
| `overall` | +0.126 | 0.643 | 16 |
| `blank_word_ratio` | -0.094 | 0.728 | 16 |
| `stroke_weight_consistency` | -0.083 | 0.761 | 16 |
| `ocr_accuracy` | -0.018 | 0.947 | 16 |
| `ocr_min` | -0.009 | 0.973 | 16 |
| `word_height_ratio` | +0.002 | 0.995 | 16 |

## Constant metrics

These metrics had zero variance across the dataset and cannot be correlated:

- `gray_boxes`: constant = 1.0000 (n=16)
- `ink_contrast`: constant = 1.0000 (n=16)
- `slant_consistency`: constant = 0.0000 (n=16)

## Candidate-pick agreement

Candidate-pick agreement: insufficient data (n<10), observed n=4, agreements=1

## Primary metric selection (spec 2026-04-10 B1)

Selection bar: positive rho, |rho| >= 0.2, p < 0.3. At most 3. If fewer clear the bar, pick only those that do.

**Selected (these gate the regression test):**

- `height_outlier_score`: rho = +0.302, p = 0.255, n = 16

**Near misses** (positive rho with |rho| >= 0.2 but p >= 0.3):

- `baseline_alignment`: rho = +0.273, p = 0.307. Tracked as a diagnostic; watch on future runs. If it clears the p-bar after more review data, promote via an explicit spec update.

## Negative correlations (why this spec exists)

The following metrics have *negative* rank correlation with human composition rating at |rho| >= 0.2: `height_outlier_ratio`, `layout_regularity`, `composition_score`, `background_cleanliness`, `style_fidelity`.

This is the direct evidence behind the 2026-04-10 spec's framing that "the loop is a competent hill-climber but not a convergence machine because its proxies are misaligned." On this dataset, higher values of these CV metrics coincide with *lower* human composition ratings, not higher ones. They are tracked as diagnostics (printed in the ledger and on regression) but they do not gate.

Plausible explanations, none confirmed (that is a task for a future spec, not this one):

- **Dataset contamination.** Many of the reviews were taken during active iteration, so code changes covary with metric changes. A metric that moved up because of a change the human disliked looks negatively correlated even if the metric itself is neutral. N=16 cannot separate this from a genuine inverse relationship.
- **Over-normalization.** `composition_score` and `layout_regularity` both reward geometric regularity. Humans tolerate and even prefer some irregularity in handwriting; pipelines that hit these metrics harder may look more machine-generated, which degrades the "handwritten note" impression.
- **Wrong ground truth.** `style_fidelity` measures similarity to the style image, not to "good handwriting." If the style image has quirks, matching them may reduce human rating.
- **Saturation + noise.** `background_cleanliness` is near 1.0 on every review; the tiny variance it does have may be driven by rendering artifacts unrelated to composition quality.

**Treat these negative signals with caution.** Do not invert them into "minimize X" objectives without new evidence. The honest reading is that the dataset does not support using them as gating metrics at all, in either direction. They remain tracked so future turns can see if the sign stabilizes or flips as more reviews arrive.

## Methodology notes

- N = 16 is small. p-values come from `scipy.stats.spearmanr` (two-sided Student's t) and should be read as "plausibly non-zero" rather than strict significance.
- Rerun this script after each `make test-human` session. The script is idempotent: `python scripts/metric_correlation.py --output docs/metric_correlation.md` regenerates the full document including selection rationale.
- The candidate-pick sample (n=4) is below the 10-review reporting threshold. When n >= 10, the agreement-rate section will populate and a candidate-disagreement gate can be considered.
- Negative correlations (when present) are logged above as diagnostics. They are NOT used to flip metric directions; the correlation is too weak and confounded by dataset contamination during active iteration.
