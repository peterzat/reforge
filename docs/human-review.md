# Human review reference

Moved from CLAUDE.md on 2026-10-13. The agent-facing rules (when to run a
review, the FINDINGS loop, qpeek URL format) stay in CLAUDE.md.

## Two kinds of review

**Blind pairwise A/B on cached generations (preferred for decisions).** Cache
`generate_word()` outputs once per seed, render both arms of the change from
the cache so only the variable under test differs, randomize A/B order per
pair, keep the key in a separate file, and serve with
`qpeek --batch --group 2 --ask "..." --choices "A,B,same"`. Record the result
as a review JSON in `reviews/human/`. The 2026-10-13 sizing-policy A/B
(`reviews/human/2026-10-13_170905.json`) produced the first clear-cut human
choice in the project's history (3/3 seeds). Run the blind model judge (a
fresh-context subagent with a fixed rubric, images only) on the same pairs
first as a cheap pre-screen, and log its agreement with the human.

**`make test-human` sessions (health checks).** A multi-step qpeek wizard over
the eval types below, rating a single composition page 1-5 plus targeted
comparisons. Ratings cluster at 3/5 and pool generation noise with the change
under test, so use them for trend and defect discovery, not for deciding
between two variants.

```bash
make test-human                          # all eval types (~2 min generation + review time)
make test-human EVAL=candidate,stitch    # run only specific types
```

## Evaluation types

- **candidate**: best-of-N candidate selection calibration
- **stitch**: chunk stitching overlap comparison
- **sizing**: short vs long word size consistency
- **baseline**: baseline alignment with descenders
- **spacing**: word spacing and jitter comparison
- **ink_weight**: stroke weight consistency comparison
- **composition**: full two-paragraph composition rating with defect flags
  (seeds 42/137/2718, `run(seed=...)`; the median-`overall` seed is shown and
  the review JSON records the archived image paths)
- **hard_words**: curated hard words readability check
- **punctuation**: contraction and trailing-mark rendering

Reviews are saved to `reviews/human/<timestamp>.json` (tracked in git; images
under `reviews/human/images/` stay local). `make test-full` prints a staleness
notice when pipeline files have changed since the last review.

## Eval type to code area mapping

| Eval type | Code areas | When to run |
|-----------|-----------|-------------|
| candidate | quality/score.py, config.py (QUALITY_WEIGHTS) | After scoring weight changes |
| stitch | model/generator.py (stitch_chunks, split_word) | After chunking or stitching changes |
| sizing | quality/font_scale.py, config.py (SIZING_POLICY, ZONE_*) | After sizing changes |
| baseline | compose/layout.py, compose/render.py | After baseline detection or placement changes |
| spacing | config.py (WORD_SPACING), compose/layout.py | After spacing or layout changes |
| ink_weight | quality/harmonize.py, config.py (STROKE_WEIGHT_*) | After harmonization changes |
| composition | full pipeline (end-to-end) | After any quality-affecting change; uses quality preset |
| hard_words | model/generator.py (generate_word, postprocess) | After generation or gray-box defense changes |
| punctuation | model/generator.py (stitch_contraction, trailing marks), model/font_glyph.py | After contraction or punctuation changes |

## qpeek

[qpeek](https://github.com/peterzat/qpeek) is installed in the venv for visual
inspection on this headless box. It starts a transient web server, serves the
file, and exits when the browser tab closes. Wrapper: `./qpeek.sh <file>`.

Modes: view-only (default), survey with freeform text (`--ask "question"`),
survey with button choices (`--ask "question" --choices "a,b,c"`), batch
(`--batch`, with `--group N` files per step), and custom HTML (`--html`, used by
`make test-human`). Survey modes print structured JSON to stdout. Binds to
`0.0.0.0:2020` by default.

## Quality review without a human

`make review` runs demo.sh (seed 42) and prints the run manifest's metrics.
Claude Code reads `result.png` directly; there is no need to paste images into
a separate conversation.
