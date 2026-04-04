## Review -- 2026-04-04 (commit: 5a33bda)

**Summary:** Refresh review of 2 unpushed commits: per-word readability improvements (cc9280f) and new height consistency spec (5a33bda). Code changes in generator.py (cluster filter, OCR threshold, x-height stitching), new ink_metrics.py function (compute_x_height), test relaxation (upper bound removal). Documentation and output archive updates.

**Review scope:** Refresh review. Focus: 9 file(s) changed since prior review (commit d003145). 0 already-reviewed file(s) checked for interactions only.

### Findings

1. [WARN] reforge/model/generator.py:576 -- Unused import: `compute_ink_height` is imported alongside `compute_x_height` but never used in `stitch_chunks`. The function was replaced by `compute_x_height` for normalization, making the import dead code.
   Evidence: `from reforge.quality.ink_metrics import compute_ink_height, compute_x_height` on line 576; grep of generator.py shows no other reference to `compute_ink_height`.
   Suggested fix: Remove `compute_ink_height` from the import.

2. [NOTE] reforge/quality/ink_metrics.py -- `compute_x_height` has no unit tests. The function is new (42 lines), used in a critical path (chunk stitching), and has edge case handling (all-white, small ink). Quick manual testing confirms edge cases return reasonable values, but no tests in `tests/quick/` exercise this function directly. The SPEC.md (criterion A2/A3) will extend its use to font_scale.py and harmonize.py, making test coverage more important.

3. [NOTE] tests/medium/diagnostic_results.json -- This file is tracked in git but changes nondeterministically with every GPU run (pixel-level inference variation). TESTING.md already flagged this (diagnostic-results-not-gitignored). The SPEC.md criterion C2 also calls it out. Low priority but causes spurious diffs.

### Fixes Applied

1. Removed unused `compute_ink_height` import from stitch_chunks (WARN #1). Tests stable at 151 passed.

Security: 0 BLOCK / 0 WARN / 0 NOTE. No security issues in reviewed files (pure computation, no I/O or attack surface).

---
*Prior review (2026-04-03, commit d003145): Refresh review of 2 commits (demo re-baseline, new readability spec). 1 WARN (human_eval.py docstring count), auto-fixed.*

<!-- REVIEW_META: {"date":"2026-04-04","commit":"5a33bda","reviewed_up_to":"5a33bdae6c5c88c66605508042cf55750842b536","base":"origin/main","tier":"refresh","block":0,"warn":1,"note":2} -->
