## Review -- 2026-04-20 (commit: ab25600)

**Review scope:** Light review. Staged diff is documentation + archived images
only (`docs/OUTPUT_HISTORY.md`, `docs/best-output.png`,
`docs/output-history/20260420-030258.png` added, `docs/output-history/20260419-161539.png`
deleted). No code, configuration, tests, Makefile, scripts, or dependency
manifests touched. Per skill tier rules: skipped test-suite run (Step 3),
security chain (Step 5), external reviewers (Step 5.5), preliminary
CODEREVIEW writeback (Step 6.5), and fix loop (Step 7).

**Summary:** Routine end-of-push output archival: new demo output
`20260420-030258.png` captured at HEAD `ab25600` becomes the current
`docs/best-output.png` (verified byte-identical via sha256), and the matching
markdown entry replaces the prior top entry in `OUTPUT_HISTORY.md`. The
pre-existing `20260420-002636` entry shifts to second-newest, displacing
`20260419-161539` which is also deleted from disk. Pixel-difference check
confirms the new archive is a genuine new run (MAD 21.7 vs prior archive,
above the 3.0 dedup threshold in `scripts/archive-output.sh:47`). All 12
image references in the updated `OUTPUT_HISTORY.md` resolve on disk. HEAD SHA
`ab25600` cited in the new entry's Git state field resolves in git and matches
the current working-tree HEAD.

One issue is worth flagging: the deleted `20260419-161539.png` is still
referenced from a test-module docstring at
`tests/medium/test_contraction_sizing.py:8` as the "defect visible in" image
for Spec 2026-04-19 criterion 1. After the push, that pointer becomes a dead
path. Treating as a paper-trail NOTE consistent with the prior-review
convention for documentation-drift findings, not a WARN.

**External reviewers:**
Skipped (light review; docs/images-only diff).

### Findings

[NOTE] docs/output-history/20260419-161539.png -- Deleting this PNG breaks a
docstring reference in `tests/medium/test_contraction_sizing.py:8`:
"the defect visible in `docs/output-history/20260419-161539.png`". After
this push the cited evidence file will not exist in the working tree. The
docstring is the "before the fix" pedagogical pointer for Spec 2026-04-19
criterion 1 (contraction chunk sizing); a reader who follows it will hit
a missing-file path. The test itself still runs (the docstring is not
evaluated), so this is documentary, not a runtime defect.
  Evidence: `grep -n 20260419-161539 tests/medium/test_contraction_sizing.py`
  matches line 8 in the module docstring. The staged diff shows
  `D docs/output-history/20260419-161539.png` as a hard delete. No other
  in-repo path provides an equivalent defect-image substitute.
  Suggested fix (smallest footprint): do not delete the PNG. It is
  acceptable to remove the markdown entry from `OUTPUT_HISTORY.md` without
  deleting the underlying file; nothing in `scripts/archive-output.sh`
  requires one-to-one parity between MD entries and on-disk PNGs. Run
  `git restore --staged docs/output-history/20260419-161539.png &&
  git checkout docs/output-history/20260419-161539.png`. Alternative:
  retarget the docstring at `test_contraction_sizing.py:8` to a retained
  image, or phrase it as a git-blob reference
  (`git show 1a6e03e:docs/output-history/20260419-161539.png`).

[NOTE] docs/OUTPUT_HISTORY.md -- This working-tree state bundles "add new
archive entry (`20260420-030258`)" with "delete prior archive entry
(`20260419-161539`, PNG + markdown row)" into one push-worth of changes.
Prior convention is that deletions of output-history entries are their own
commits with explicit removal-rationale messages: `git log --oneline
--diff-filter=D -- 'docs/output-history/*.png'` returns 7 prior
dedicated-removal commits (e.g. `5b41dc0` "Remove duplicate output history
entry 20260414-043601", `1fc02ad` "Remove output history entry
20260409-041732") and zero prior bundled add+remove commits. The MEMORY
convention "One output history entry per push" also reads more naturally
under the separate-commits convention. Bundling both operations hides the
removal behind an archival commit message.
  Evidence: `git log --oneline --diff-filter=D -- 'docs/output-history/*.png'`
  enumerated above. Archive-output.sh only *adds* entries (never removes),
  so the deletion was manual.
  Suggested fix: if the `20260419-161539` deletion is intentional, split it
  into its own commit with a clear removal-rationale message. Combined with
  the docstring-pointer finding above, the simpler resolution is to leave
  the PNG in place entirely and remove only the markdown row (which also
  closes the first finding). Low urgency: structural, not a defect.

[NOTE] docs/OUTPUT_HISTORY.md:19 -- The Metrics column for the new entry
`20260420-030258` carries forward the identical seed=42 baseline values
already shown for `20260420-002636`, `20260418-173035`, `20260414-161121`,
`20260410-144654` (all read `overall=0.790, composition_score=0.323,
stroke_weight_consistency=0.913, ...`). The underlying image is a genuinely
new run (MAD 21.7 vs prior archive), but the Metrics row does not describe
the archived image -- it describes `tests/medium/quality_baseline.json`
at seed=42 at the time of archival. Pre-existing behavior of
`scripts/archive-output.sh:91-120` (reads the baseline JSON, falls back to
image-only scoring only if the baseline file is missing), not a new
regression. Worth noting because a reader could assume per-entry metrics
are per-image rather than per-baseline-at-HEAD.
  Evidence: `scripts/archive-output.sh:91-137` reads
  `tests/medium/quality_baseline.json` and formats the Metrics block from
  the `seeds['42'].metrics` dict; it only falls back to image-only scoring
  if the baseline file is missing.
  Suggested fix (optional, pre-existing, out of scope for this push):
  label the Metrics row as "Baseline metrics (seed 42)" in the archive
  template, or actually re-score the archived image. Flagging so the
  convention is not forgotten.

Light-review verification notes:
- Link check: all 12 image paths referenced in the updated OUTPUT_HISTORY.md
  resolve to files on disk. Commit SHA `ab25600` cited in the new entry
  resolves via `git rev-parse --verify` and matches HEAD.
- Secret-leak check: `git diff --cached | grep -iE
  "(password|secret|api[_-]?key|token|credential|aws|ssh|private)"` returns
  no matches across the staged diff.
- Factual accuracy: `sha256sum` confirms `docs/best-output.png` is
  byte-identical to `docs/output-history/20260420-030258.png`
  (4d841ab661848f58394cda32877b99ef5598ab2a2eba696983d2a31598360dcb).
  Pixel diff vs `20260420-002636.png` is MAD 21.7, well above the 3.0
  archive-dedup threshold, confirming the archive is a genuine new run.
  The "Commit message" field for `20260420-030258` captures `ab25600`'s
  message ("CODEREVIEW.md refresh for 369a5df (light tier, docs-only)"),
  which matches `git log -1 --format='%s'` at the moment of archival --
  correct `archive-output.sh:78` behavior even though the archive happens
  to land on a doc-only commit.
- Commit scope: a single push bundles archive add + archive delete +
  best-output refresh (raised as the second NOTE above). Not raised as
  spaghetti because all three are routine archival bookkeeping of the
  same output event.

### Prior-review findings carried forward

From the prior review entry (`ab25600`, 2026-04-20, light tier, 0 BLOCK /
0 WARN / 3 NOTE):

- `CODEREVIEW.md:46` stale-finding paper-trail inconsistency: obsolete.
  Paper-trail inconsistency was specific to commit `369a5df`; this refresh
  overwrites that entry, closing the inconsistency.
- `SECURITY.md:11` off-by-one line pointer for the Katherine PII reference
  (`scripts/human_eval.py:556` vs `:555`): not in Accepted Risks, not
  auto-fixed. Per skill rules, carried forward at NOTE severity:

[NOTE] SECURITY.md:11 -- Off-by-one line pointer in Accepted Risks:
the Katherine PII pointer cites `scripts/human_eval.py:556`, but the
actual string literal `"We grabbed two, maybe three? Katherine laughed..."`
is on line 555. The summary narrative at `SECURITY.md:3` has the same
`:556` pointer. Surrounding file and literal are correct; only the line
number is off by one. Low urgency: documentary, not affecting code or
scan coverage.
  Evidence: `scripts/human_eval.py:555` contains the Katherine literal;
  line 556 is the continuation fragment.
  Suggested fix: retarget both pointers to `:555` (or `:553-557`).

- `reforge/compose/layout.py:155` walkback uses `BASELINE_BODY_DENSITY`
  (0.35) instead of the just-computed `body_threshold` (0.25 for descender
  words / 0.35 otherwise). Not in Accepted Risks, not auto-fixed,
  `layout.py` unmodified in this focus set so the pattern is still present.
  Per skill rules, carried forward at NOTE severity:

[NOTE] reforge/compose/layout.py:155 -- walkback uses
`BASELINE_BODY_DENSITY` (0.35) instead of the just-computed
`body_threshold` (0.25 for descender words / 0.35 otherwise). For
descender words whose peak body density falls between 0.25 and 0.35, the
walkback would find `found=True` if it used `body_threshold`, skipping
the descender fallback entirely. Not a bug at current test tolerances
(the 6 baseline tests pass within 3 px and the fallback path at line 159
catches the `jump`/`by`/`py`/`gp` cases this flags).
  Evidence: line 123 computes `body_threshold = 0.25 if has_descender
  else BASELINE_BODY_DENSITY`; line 144 (has_body_below) uses it; line
  155 (walkback) does not.
  Suggested fix: change line 155 to `if row_density[rb] >= body_threshold`
  for consistency. The `has_descender` fallback at line 159 can then be
  tightened (or removed) since walkback will succeed for the cases it
  was patching around.

### Fixes Applied

None. Five NOTEs total (3 new, 2 carried-forward), no BLOCK/WARN findings.

### Accepted Risks

None.

---
*Prior review (2026-04-20, commit ab25600): Light refresh of the `369a5df`
CODEREVIEW.md entry after the `ab25600` meta-commit. 0 BLOCK / 0 WARN / 3
NOTE (stale prior-review NOTE fixed in `369a5df`; off-by-one PII line
pointer in SECURITY.md; `layout.py:155` walkback threshold consistency --
both carried forward here).*

<!-- REVIEW_META: {"date":"2026-04-20","commit":"ab25600","reviewed_up_to":"ab256004d2e5c1d3e30e508ff0b939af3aab50d5","base":"origin/main","tier":"light","block":0,"warn":0,"note":5} -->
