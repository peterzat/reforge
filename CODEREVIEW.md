## Review -- 2026-04-20 (commit: 369a5df)

**Review scope:** Refresh review against prior review commit `f43d1d5`. Focus:
1 file changed since the prior review (`reviews/human/FINDINGS.md`; the
CODEREVIEW.md / SECURITY.md / SPEC.md meta-files in the same commit are
excluded per skill scope). The prior already-reviewed set (`CLAUDE.md`,
`docs/OUTPUT_HISTORY.md`, `docs/best-output.png`,
`docs/output-history/20260420-002636.png`, `scripts/human_eval.py`,
`tests/medium/test_contraction_sizing.py`) was not re-modified. Tier:
**light** (markdown-only change across all reviewed files).

**Summary:** One new commit (`369a5df`) since the prior review, scoped to
(a) fix the NOTE from the prior review by updating the Apostrophe Graduated
pointer in `reviews/human/FINDINGS.md:355` from `stroke ratio >= 0.85` to
`stroke ratio >= 0.83 after spec 2026-04-20 criterion 8 widened it from 0.85`,
(b) refresh `CODEREVIEW.md` (the prior review result) and `SECURITY.md` (the
2026-04-20 scan result), and (c) append a forward-looking `### Proposal
(2026-04-20)` section plus updated prior-spec footer to `SPEC.md`. No code
files, configuration files, tests, CI, scripts, Makefile, or dependency
manifests touched. Scope of change is pure documentation.

Verification: FINDINGS.md:355 now reflects `MIN_STROKE_RATIO = 0.83` in
`tests/medium/test_contraction_sizing.py:40` (verified match). All 11
referenced commit SHAs (`205c643`, `2736bd2`, `3bdcb1b`, `894de99`,
`f43d1d5`, `e2233f6`, `d0c3276`, `d2bd957`, `ea9ea73`, `16f0e48`,
`369a5df`) resolve in git. `scripts/findings_sweep.py` exits 0 (39 reviews
scanned, marker at `2026-04-20_005013`). FINDINGS.md Status Summary
(Active 2, In Progress 3, Resolved 2, Acceptable 0, Plateaued 1,
Graduated 4) is internally consistent with the SPEC.md Proposal's open-count
claim ("2 Active, 3 In Progress, 1 Plateaued"). SPEC_META remains
`criteria_total=8, criteria_met=8`.

**External reviewers:**
Skipped (light review; docs-only diff).

### Findings

[NOTE] CODEREVIEW.md:46 -- Stale finding in the prior-review entry: the first
listed NOTE (`reviews/human/FINDINGS.md:355 -- Graduated-pointer docstring
drift`) was auto-fixed in the same commit (`369a5df`) that wrote the
CODEREVIEW.md it appears in. At HEAD, FINDINGS.md:355 already reads
`stroke ratio >= 0.83 after spec 2026-04-20 criterion 8 widened it from 0.85`,
so the finding as written ("actual value is `MIN_STROKE_RATIO = 0.83`...
pointer should reflect the post-widening state") no longer describes the
file. The `### Fixes Applied` section in that same entry says "None," which
is inconsistent with the in-commit fix.
  Evidence: `git show 369a5df -- reviews/human/FINDINGS.md` shows the pointer
  updated to `>= 0.83 after spec 2026-04-20 criterion 8 widened it from 0.85`
  in the same commit whose message "Addresses one NOTE finding from
  /codereview" explicitly records the fix.
  Suggested fix: when refreshing the CODEREVIEW.md entry in a future cycle,
  either drop the stale NOTE (addressed), or move it to `### Fixes Applied`
  with attribution to `369a5df`. Not a bug: this is a paper-trail
  inconsistency in the meta-file, not a defect in pipeline code or tests.

[NOTE] SECURITY.md:11 -- Off-by-one line pointer in Accepted Risks: the
Katherine PII pointer cites `scripts/human_eval.py:556`, but the actual
string literal `"We grabbed two, maybe three? Katherine laughed..."` is on
line 555 (verified via `grep -n Katherine`). The summary narrative at
`SECURITY.md:3` has the same `:556` pointer. The surrounding file and
literal are correct; only the line number is off by one.
  Evidence: `scripts/human_eval.py:555` contains the Katherine literal;
  line 556 is the continuation `"wonderful about mornings..."` fragment.
  Suggested fix: retarget both pointers to `:555` (or a small range like
  `:553-557` if line numbers drift). Low urgency: documentary, not
  affecting code or scan coverage.

[NOTE] reforge/compose/layout.py:155 -- walkback uses `BASELINE_BODY_DENSITY`
(0.35) instead of the just-computed `body_threshold` (0.25 for descender
words / 0.35 otherwise). For descender words whose peak body density falls
between 0.25 and 0.35, the walkback would find `found=True` if it used
`body_threshold`, skipping the descender fallback entirely. Carried forward
from the prior review (same file, same pattern, not in Accepted Risks, and
`layout.py` is unmodified in this focus set so the condition is unchanged).
  Evidence: line 123 computes `body_threshold = 0.25 if has_descender else
  BASELINE_BODY_DENSITY`; line 144 (has_body_below) uses it; line 155
  (walkback) does not.
  Suggested fix: change line 155 to `if row_density[rb] >= body_threshold`
  for consistency. The `has_descender` fallback at line 159 can then be
  tightened (or removed) since walkback will succeed for the cases it was
  patching around. Not a bug at current test tolerances: the 6 baseline
  tests pass within 3 px and the fallback path catches the
  `jump`/`by`/`py`/`gp` cases this flags.

Light-review verification notes:
- Link check: all 11 commit SHAs referenced across SPEC.md / CODEREVIEW.md
  / SECURITY.md / FINDINGS.md resolve via `git rev-parse --verify`.
- Secret-leak check: no new secrets introduced in any of the four markdown
  files. Only PII reference is the previously-accepted `Katherine` name,
  still under `### Accepted Risks` in SECURITY.md.
- Factual accuracy: FINDINGS.md:355 value (`>= 0.83`) matches code
  (`MIN_STROKE_RATIO = 0.83` at `tests/medium/test_contraction_sizing.py:40`).
  FINDINGS Status Summary arithmetic consistent with SPEC.md Proposal's
  open-count claim. `scripts/findings_sweep.py` exits 0 at HEAD.
- SPEC.md structure: the appended `### Proposal (2026-04-20)` sits below
  the prior-spec footer within the same-dated spec document. The current
  entry header (line 1, "Spec -- 2026-04-20") and `SPEC_META.criteria_met=8`
  correctly describe the closed-at-8/8 state; the Proposal is forward-looking
  input for the next `/spec` turn and does not contradict the completed
  spec. Acceptable per the project `/spec` convention.
- Commit scope: single commit `369a5df` bundles one NOTE fix plus three
  meta-file refreshes that are normal end-of-push bookkeeping for that fix.
  Not spaghetti.

### Fixes Applied

None. Three NOTEs, all documentary; no BLOCK/WARN findings.

### Accepted Risks

None.

---
*Prior review (2026-04-20, commit f43d1d5): Refresh review of five commits
closing spec 2026-04-20 at 8/8 (three FINDINGS graduations to CLAUDE.md,
`_enrich_candidate_join_key` added to `scripts/human_eval.py`,
`MIN_STROKE_RATIO` widened 0.85 -> 0.83 with CUDA-state hardening,
best-output + OUTPUT_HISTORY refresh, SPEC.md proposal append). 0 BLOCK /
0 WARN / 2 NOTE (FINDINGS.md:355 stroke-ratio drift -- auto-fixed in
commit 369a5df; `reforge/compose/layout.py:155` walkback threshold
consistency -- carried forward).*

<!-- REVIEW_META: {"date":"2026-04-20","commit":"369a5df","reviewed_up_to":"369a5df53de7d179e3ca8eb8187a5a81f2359b4d","base":"origin/main","tier":"light","block":0,"warn":0,"note":3} -->
