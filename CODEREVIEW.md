## Review -- 2026-04-17 (commit: 278b61f)

**Review scope:** Refresh review. Focus: 0 files changed since prior review
(commit 3a710b3 + uncommitted). The unpushed commit `278b61f` commits the
same code that was reviewed in the prior session as uncommitted changes;
a byte-level diff against the prior state shows no code changes, only
the metadata-file updates (CODEREVIEW.md, SECURITY.md, SPEC.md) that the
prior review itself produced. All 11 code/config files in the focus set
match the state at the prior review. Two previously-unscanned files
(`experiments/contraction_right_side.py`, `experiments/reinforce_variance.py`)
were given a fresh security pass to close the scanned_files gap.

**Summary:** No code changes since the prior successful review. All criteria
covered in the prior `3a710b3 + uncommitted` review remain verified:
`quality_score_breakdown` extraction (score.py), candidate-score JSONL
logging gated on `REFORGE_LOG_CANDIDATES` (generator.py, Makefile,
human_eval.py), `_reinforce_thin_strokes` variance-check env-var guard
(font_scale.py), `check_punctuation_visibility` CV metric + wiring
(visual.py, test_evaluate.py), `CONTRACTION_RIGHT_SIDE_WIDTH` config hook
for 1-2 char right-side parts (config.py, generator.py), E1 housekeeping,
two new experiment drivers, FINDINGS.md updates. 287 quick tests pass.

**External reviewers:**
Skipped (no code changes since prior review; external reviewers ran at the
prior initial review with no findings and are not re-run during refresh).

### Findings

No BLOCK or WARN findings.

Refresh-review verification notes:
- `git diff 3a710b3..HEAD -- ':!*.md'` on the scanned file set confirms the
  code content is byte-identical to the prior-review state for all 9
  previously-scanned files.
- The two new experiment files (`experiments/contraction_right_side.py`,
  `experiments/reinforce_variance.py`) were re-checked for refresh-specific
  regression risk. They are offline, single-process drivers. The `config`
  mutation (`CONTRACTION_RIGHT_SIDE_WIDTH`) and env-var flip
  (`REFORGE_DISABLE_REINFORCEMENT`) are both reset implicitly on process
  exit (script mode), so they cannot leak into later test runs in the
  dev loop.
- Canvas-width override math at generator.py:1163-1165 re-verified: for
  the intended candidates (None, 128) the round-up to WIDTH_MULTIPLE and
  clamp to [64, MAX_CANVAS_WIDTH=320] produces 128. Edge cases (50, 321,
  10) also produce correctly-clamped multiples of 16. Function-level
  `from reforge.config import CONTRACTION_RIGHT_SIDE_WIDTH` rebinds the
  local name per outer call, so the experiment's pattern of mutating the
  module attribute between `run()` invocations behaves correctly.
- `torch.initial_seed()` re-verified: returns the last explicit
  `torch.manual_seed()` value (CPU), and `torch.manual_seed()` also seeds
  CUDA, so the log `seed` field is correct for both device paths. In the
  candidate-eval fixture, `torch.manual_seed(137)` sets the seed before
  generation; the log timestamp is explicitly passed for join consistency.
- `_candidate_logging_enabled` correctly treats the Makefile's empty-value
  case (`REFORGE_LOG_CANDIDATES=`) as disabled.
- Makefile logic `$(if $(EVAL),$(if $(findstring candidate,$(EVAL)),1,),1)`
  re-verified for {empty, candidate, stitch, candidate,stitch}. No false
  positive from substring match on existing eval names.
- 287 quick tests pass (including four `TestPunctuationVisibility` cases).
- Security scan (2 new files): 0 issues. SECURITY.md refreshed to commit
  278b61f with scanned_files covering the experiment driver pair.

### Fixes Applied

None. No BLOCK or WARN findings.

### Accepted Risks

None.

Informational observation (carried forward from prior review, not a finding):
- Candidate logging is wired into the main `_generate_chunk` best-of-N loop
  only. `_generate_contraction._gen_part` and `_generate_punctuated_word`
  also perform best-of-N selection but do not emit log rows. Spec D1 reads
  "the best-of-N selection path" (singular) and
  `make test-human EVAL=candidate` uses the non-contraction fixture "garden",
  so the documented join target works. If future candidate-log analysis
  includes contractions or trailing-punctuation words, those two paths will
  need matching log calls.

---
*Prior review (2026-04-17, commit 3a710b3 + uncommitted): Full review of the
spec 2026-04-17 implementation (punctuation CV metric, candidate log,
CONTRACTION_RIGHT_SIDE_WIDTH hook, reinforcement variance guard, housekeeping).
0 BLOCK / 0 WARN / 0 NOTE. External reviewers: qwen
(Qwen2.5-Coder-14B-Instruct-AWQ), no findings. Security scan (9 files):
0 issues.*

<!-- REVIEW_META: {"date":"2026-04-17","commit":"278b61f","reviewed_up_to":"278b61fcbf66596227bdc54ba27715038270ffa8","base":"origin/main","tier":"refresh","block":0,"warn":0,"note":0} -->
