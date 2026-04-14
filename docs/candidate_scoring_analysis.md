# Candidate Scoring Preference Analysis

## Summary

- Total candidate reviews: 8
- Human-metric agreements: 2/8 (25%)
- Human-metric disagreements: 6/8 (75%)

## Human Pick Distribution

- Candidate A: 2 time(s)
- Candidate B: 2 time(s)
- Candidate C: 2 time(s)
- Candidate D: 1 time(s)
- Candidate E: 1 time(s)

## Per-Candidate Score Data

**No per-candidate score breakdowns are recorded in the review data.**

The current review system records only:
- Which candidate the human picked (A-E)
- Whether the human agreed with the metric's pick (boolean)

To perform sub-score correlation analysis (D2), the review
system would need to record, for each candidate:
- Individual sub-scores (background, ink_density, edge_sharpness,
  height_consistency, contrast, OCR accuracy)
- The metric's combined score and rank
- The style similarity tiebreak score (if applicable)

## Assessment

Agreement rate is 25%, well below chance (20% for 5 candidates).
This suggests the current scoring features are measuring something
orthogonal or inversely related to human preference. Simple reweighting
of the existing features is unlikely to fix this.

**Recommendation:** The existing quality_score features (background,
ink_density, edge_sharpness, height_consistency, contrast) may be
measuring 'image cleanliness' rather than 'handwriting quality.'
Before attempting reweighting:

1. Add per-candidate score logging to the review system so each
   candidate's sub-scores are recorded alongside the human pick.
2. Collect at least 15 reviews with per-candidate scores.
3. Then run sub-score correlation analysis to identify which
   features (if any) predict human preference.
4. If no existing features correlate positively, consider VGG-based
   perceptual features (HWD) as described in the research survey.

## Data Requirements for D2 (Score Reweighting)

- Simple reweighting (rank features by agreement): N >= 15
  Current N = 8. Need 7 more reviews.
- Logistic regression (5 features): N >= 50
  Current N = 8. Need 42 more reviews.

**Critical prerequisite:** Per-candidate sub-scores must be logged
in the review JSON. Without them, no reweighting is possible
regardless of N.
