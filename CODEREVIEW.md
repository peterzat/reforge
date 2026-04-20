## Review -- 2026-04-20 (commit: f43d1d5)

**Review scope:** Refresh review against prior review commit `e2233f6`. Focus:
7 file(s) changed since prior review (`CLAUDE.md`, `docs/OUTPUT_HISTORY.md`,
`docs/best-output.png`, `docs/output-history/20260420-002636.png`,
`reviews/human/FINDINGS.md`, `scripts/human_eval.py`,
`tests/medium/test_contraction_sizing.py`) plus the unstaged `SPEC.md` proposal
append. No prior-scope files were modified again since, so the
already-reviewed set is empty. Tier: refresh (code + doc).

**Summary:** Five commits (`205c643` .. `f43d1d5`) close spec 2026-04-20 at
8/8. Three FINDINGS entries graduate to `CLAUDE.md` "Hard-won design
constraints" (Status Summary: Acceptable 1 -> 0, Resolved 4 -> 2, Graduated 1 -> 4,
`CLAUDE.md` gains Plateau note under Stroke weight variation, Asymmetric split
stitching subsection under Long word chunking, and a new "Trailing punctuation
synthesis" section). `scripts/human_eval.py` gains
`_enrich_candidate_join_key`: when the candidate eval runs,
`{word, seed, log_timestamp, human_pick_index}` is written onto the
`responses["candidate"]` dict before `save_review` persists, wired once via
`_enrich_candidate_join_key(responses, eval_metadata)` at
`save_review:958`. `tests/medium/test_contraction_sizing.py` widens
`MIN_STROKE_RATIO` 0.85 -> 0.83 and adds CUDA-state hardening
(`cudnn.benchmark=False`, `cudnn.deterministic=True`,
`torch.cuda.manual_seed_all(seed)` per iteration,
`empty_cache + synchronize` once before the loop) under a `try/finally` that
restores the two cudnn backends on exit. The prior cycle's spec-criterion-8
option (b) fixture hardening plus option (c) gate widening are both present.
Archival files land: `docs/best-output.png` refresh +
`docs/output-history/20260420-002636.png` new + one new
`OUTPUT_HISTORY.md` entry (consistent with the "one per push" rule). The
unstaged `SPEC.md` edit appends the 2026-04-20 Proposal and rewrites the
prior-spec footer; `SPEC_META.criteria_met=8` remains correct.

Verification: `make test-quick` passes (302/302, 5.02s); `scripts/findings_sweep.py`
returns exit 0 against the current tree (39 reviews scanned, 0 unprocessed,
marker at `2026-04-20_005013`); join-key flow verified end-to-end against
`reviews/human/2026-04-20_005013.json` + `experiments/output/candidate_scores.jsonl`
(`word=garden, seed=137, log_timestamp=2026-04-20T00:37:08`,
`human_pick_index=1` == JSONL `selected_index=1`).

**External reviewers:**
`/home/peter/bin/review-external.sh` produced no output for this diff.

### Findings

[NOTE] reviews/human/FINDINGS.md:355 -- Graduated-pointer docstring drift: the
Apostrophe Graduated entry says "stroke ratio >= 0.85" but the test gate was
widened to 0.83 in commit `2736bd2` (same push). Both commits (`205c643`
graduation and `2736bd2` gate widening) land together in this review; the
pointer should reflect the post-widening state (0.83) or note that the gate
was widened under criterion 8.
  Evidence: FINDINGS.md line 355 -- "tests/medium/test_contraction_sizing.py
  (stroke ratio >= 0.85, ink-median delta <= 20%, ink-height delta <= 15%)";
  actual value is `MIN_STROKE_RATIO = 0.83` in
  tests/medium/test_contraction_sizing.py:40.
  Suggested fix: change `stroke ratio >= 0.85` to
  `stroke ratio >= 0.83 (widened from 0.85 under spec 2026-04-20 criterion 8)`
  or simply `>= 0.83`. Low urgency: the FINDINGS pointer is advisory and the
  CLAUDE.md graduation text does not repeat the numeric value.

[NOTE] reforge/compose/layout.py:155 -- walkback uses `BASELINE_BODY_DENSITY`
(0.35) instead of the just-computed `body_threshold` (0.25 for descender words
/ 0.35 otherwise). For descender words whose peak body density falls between
0.25 and 0.35, the walkback would find `found=True` if it used `body_threshold`,
skipping the descender fallback entirely. Carried forward from the prior review
(same file, same pattern, not in Accepted Risks, and `layout.py` is unmodified
in this focus set so the condition is unchanged).
  Evidence: line 123 computes `body_threshold = 0.25 if has_descender else
  BASELINE_BODY_DENSITY`; line 144 (has_body_below) uses it; line 155 (walkback)
  does not.
  Suggested fix: change line 155 to `if row_density[rb] >= body_threshold`
  for consistency. The `has_descender` fallback at line 159 can then be tightened
  (or removed) since walkback will succeed for the cases it was patching around.
  Not a bug at current test tolerances: the 6 baseline tests pass within 3 px
  and the fallback path catches the `jump`/`by`/`py`/`gp` cases this flags.

Refresh-review verification notes:
- Security scan: `/security` invoked with 4 files (`Makefile`,
  `scripts/findings_sweep.py`, `scripts/human_eval.py`,
  `tests/medium/test_contraction_sizing.py`) since last scan's
  `scanned_files` did not cover them. Result: 0 BLOCK / 0 WARN / 0 NOTE. All
  `subprocess.run` usages are argv-lists with fixed arguments; no `shell=True`,
  `eval`, `exec`, `pickle`, or dynamic import paths. Eval-type CLI args are
  whitelisted against `EVAL_TYPES` before use. HTML-template injection only
  receives hardcoded strings and committed `hard_words.json` values. SECURITY.md
  refreshed with the new `SECURITY_META`.
- `_enrich_candidate_join_key` correctness: guard clauses (`"candidate" not in
  responses`, `"candidate" not in eval_metadata`, `cand_resp.get("skipped")`,
  falsy `pick_label`) correctly no-op when the candidate eval was not run, was
  skipped, or produced no pick. `labels.index(pick_label)` in `try/except
  ValueError` handles pick-label-not-in-labels (`pick_index = None`, join_key
  still written). The wizard HTML always produces `{"skipped": true|false, ...}`
  (never `None`), so `.get(...)` on `cand_resp` is safe. Verified end-to-end
  against the committed review JSON + JSONL row (garden/137/00:37:08,
  `human_pick_index=1` == `selected_index=1`).
- `torch.initial_seed()` returns 137 after `torch.manual_seed(137)` (verified
  in a one-shot probe), so the `seed` field matches across the review JSON's
  `join_key` and the JSONL row for small integer seeds.
- `test_contraction_sizing.py` state hygiene: `try/finally` correctly restores
  `cudnn.benchmark`/`cudnn.deterministic` even when the terminal assert fails;
  `empty_cache()` + `synchronize()` are one-way and do not need restoration.
  The comment's ordering claim ("tests/full/ warms CUDA first under the
  conftest DAG") is verified -- `pytest tests/full/ --collect-only -q` shows
  full -> quick -> medium collection order.
- Graduation bar check: Ink weight (6 reviews >= 3, 2+ code changes: harmonize
  blend + candidate-selection scoring, stable principle), Apostrophe rendering
  (10 reviews >= 3, 3+ code changes: split-path, Option W, chunk matching, stable
  principle), Trailing punctuation (7 reviews >= 3, 3+ code changes: Bezier -> 
  Caveat -> 1.15x retarget, stable principle). All three clear the bar.
- Status Summary arithmetic: counted bodies (Active 2, In Progress 3, Resolved 2,
  Acceptable 0, Plateaued 1, Graduated 4) -- matches the summary table.
- FINDINGS marker bump: `FINDINGS_LAST_PROCESSED: 2026-04-20_005013` is the
  newest review JSON stem; `findings_sweep.py` exits 0.
- Output history: exactly one new entry (`20260420-002636`), consistent with
  the one-per-push rule.
- Commit decomposition: 5 commits address criterion 1-3 (graduations), 8
  (test-full order-dependency), 4-5 (join key), 7 (marker bump), and
  close/archive respectively. Each commit scoped to a specific spec criterion.
  Not spaghetti.
- Unstaged `SPEC.md`: appends the 2026-04-20 Proposal and updates the
  prior-spec footer. `SPEC_META` is still correct for the closed 8/8 spec;
  the proposal is the forward-looking recommendation consistent with this
  repo's `/spec` convention.

### Fixes Applied

None. No BLOCK or WARN findings.

### Accepted Risks

None.

---
*Prior review (2026-04-19, commit e2233f6): Refresh review of two batches --
FINDINGS automation (3 commits: `findings_sweep.py`, CLAUDE.md wiring,
FINDINGS compression) and SPEC + artifacts (4 commits: CODEREVIEW/SECURITY
artifacts, proposal refresh, spec 2026-04-20 open, criterion 8 append).
0 BLOCK / 0 WARN / 1 NOTE (walkback threshold consistency in `detect_baseline`,
carried forward).*

<!-- REVIEW_META: {"date":"2026-04-20","commit":"f43d1d5","reviewed_up_to":"f43d1d5e6eb7e0f470f3bc78910741b859100ef0","base":"origin/main","tier":"refresh","block":0,"warn":0,"note":2} -->
