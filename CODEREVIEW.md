## Review -- 2026-04-17 (commit: 3a710b3 + uncommitted)

**Summary:** Full review of spec 2026-04-17 implementation: `quality_score_breakdown` extraction (score.py), candidate-score JSONL logging gated on `REFORGE_LOG_CANDIDATES` (generator.py, Makefile, human_eval.py), `_reinforce_thin_strokes` variance-check env-var guard (font_scale.py), `check_punctuation_visibility` CV metric + wiring (visual.py, test_evaluate.py), `CONTRACTION_RIGHT_SIDE_WIDTH` config hook for 1-2 char right-side parts (config.py, generator.py), E1 housekeeping (stale `kill 897414` permission removed), two new experiment drivers (`experiments/reinforce_variance.py`, `experiments/contraction_right_side.py`), FINDINGS.md updates reflecting A decision (keep reinforcement, promoted to Resolved) and C decision (reject 128px narrow right side). 287 quick tests pass.

**External reviewers:**
`[qwen] Qwen/Qwen2.5-Coder-14B-Instruct-AWQ -- 7367 in / 5 out -- 28s` -- no findings.

### Findings

No BLOCK or WARN findings.

Verified correctness of the implementation against the spec:
- `CONTRACTION_RIGHT_SIDE_WIDTH`: function-level `from reforge.config import ...` inside `_generate_contraction` correctly re-reads the module attribute on each call, so `experiments/contraction_right_side.py`'s pattern of mutating `config.CONTRACTION_RIGHT_SIDE_WIDTH` between runs behaves as intended. Override is rounded up to a multiple of `WIDTH_MULTIPLE` (16) and clamped to `[64, MAX_CANVAS_WIDTH=320]`, preserving the UNet convolutional-width constraint. Scope gate (`is_right_side and len(text) <= 2`) matches the spec.
- `_log_candidate_scores`: `torch.initial_seed()` returns the last value passed to `torch.manual_seed()` even after DDIM advances the RNG (verified interactively); seed field is correct for the `generate_candidate_eval` fixture. Output path (`experiments/output/candidate_scores.jsonl`) is in the gitignored `experiments/output/` tree. Write failures are swallowed so logging cannot break generation.
- `_candidate_logging_enabled`: empty string (the Makefile's non-candidate branch yields `REFORGE_LOG_CANDIDATES=` with empty value) is correctly treated as disabled. Verified via `REFORGE_LOG_CANDIDATES= python -c ...`.
- Makefile `$(if $(EVAL),$(if $(findstring candidate,$(EVAL)),1,),1)`: verified expansion for EVAL values {empty, candidate, stitch, candidate,stitch}. Sets the env var when the candidate eval will actually run.
- `check_punctuation_visibility`: returns 1.0 for `expected == 0` (matches docstring); tail-region geometry (10% width, min 6px; +30% descender extension for `,`/`;`) matches the spec; only gated into `overall_quality_score` when both `word_positions` and `words` are provided, so existing callers (`archive-output.sh`, `test_quality_thresholds.py`) remain correct.
- `_reinforce_thin_strokes` env-var short-circuit: only consulted on the short-word path (`word_len == 1 and scale < 0.6`), so the runtime impact when `REFORGE_DISABLE_REINFORCEMENT` is unset is one environment lookup per single-char word. Acceptable.
- `quality_score_breakdown` / `quality_score`: all existing callers (`_generate_contraction._gen_part`, `_generate_punctuated_word`, module-level imports in generator.py) continue to use the float-returning wrapper. The tuple-returning function is only used by `_generate_chunk` (for logging) and `generate_candidate_eval` (for logging).
- FINDINGS.md status counts match the counts table (Active=2, In Progress=4, Resolved=3, Acceptable=1, Plateaued=1; verified by grep).
- SPEC.md `criteria_met=15 / criteria_total=18` matches the checkbox counts; three deferred items (D3, F3, F4) are correctly left unchecked with "Deferred..." notes.
- `.claude/settings.local.json`: change is exactly the E1 removal; no other entries touched.
- 287 quick tests pass (including four new `TestPunctuationVisibility` cases).
- Security scan (9 files): 0 issues.

### Fixes Applied

None. No BLOCK or WARN findings.

### Accepted Risks

None.

Informational observation (not auto-fixed):
- Candidate logging is wired into the main `_generate_chunk` best-of-N loop only. `_generate_contraction._gen_part` and `_generate_punctuated_word` also perform best-of-N selection but do not emit log rows. Spec D1 reads "the best-of-N selection path" (singular) and `make test-human EVAL=candidate` uses the non-contraction fixture "garden", so the documented join target works. If future candidate-log analysis includes contractions or trailing-punctuation words, those two paths will need matching log calls.

---
*Prior review (2026-04-17, commit a88a600): Light doc-only review of SPEC.md promotion to formal spec with 18 acceptance criteria. 0 findings, verified factual spec claims against the repository.*

<!-- REVIEW_META: {"date":"2026-04-17","commit":"3a710b3","reviewed_up_to":"3a710b3e1ab3ff55e53c400332d5c242ae088fc5","base":"origin/main","tier":"full","block":0,"warn":0,"note":0} -->
