# Style input strategy

Moved from CLAUDE.md on 2026-10-13. Status: only step 1 exists. None of the
subdirectories below have been created; `styles/` holds `hw-sample.png` only.

## Planned directory structure

```
styles/
  hw-sample.png          Peter's handwriting (primary reference, committed)
  README.md              Notes on each style source, writer ID, quality observations
  friends/               Contributed samples from other writers
  datasets/              Samples extracted from public handwriting datasets
  synthetic/             DiffusionPen-generated best outputs used as style references
```

## Sourcing plan (incremental)

1. **hw-sample.png** is the primary style. demo.sh always uses it.
2. Friends: gather 3-5 samples from different writers for diversity testing.
3. Public datasets: IAM, RIMES, or other public handwriting corpora. Use
   high-quality samples as additional test styles.
4. Synthetic: use DiffusionPen's own best-quality outputs (carefully selected,
   understanding that these are model outputs, not real handwriting) as
   supplementary style references for testing generalization.
5. All style images should be 5-word sentences with each word >= 4 chars.

Note for multi-writer work: `ZONE_HEIGHT_RATIOS` and the weak-ascender "t"
in `reforge/quality/font_scale.py` were measured on hw-sample output. Another
hand may need its own ratios (they could be measured from the style crops).
