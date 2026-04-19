## Review -- 2026-04-19 (commit: e2233f6)

**Review scope:** Refresh review against prior review commit `d0c3276`. Focus:
5 file(s) changed since prior review (`CLAUDE.md`, `Makefile`,
`reviews/human/FINDINGS.md`, `scripts/findings_sweep.py`,
`scripts/human_eval.py`). No prior-scope files were modified again since, so
the already-reviewed set is empty. Tier: refresh (code + doc).

**Summary:** Five unpushed commits split into two self-contained batches.

Batch 1 (FINDINGS automation, 3 commits): `59148ef` compresses FINDINGS.md 837
-> 403 lines via per-finding audit + status re-classification, promotes
"Chunk stitching" from Resolved to Graduated (the only graduation in this push),
and adds a cross-file methodology note on x-height-spread. `91da547` adds a
new read-only utility `scripts/findings_sweep.py` that lists review JSONs newer
than the `FINDINGS_LAST_PROCESSED` marker at the top of FINDINGS.md; bootstraps
the marker at `2026-04-19_215858`; exits 0 when nothing unprocessed, 1 otherwise.
`df77ec6` wires the sweep into CLAUDE.md's "Findings workflow" section (new
`/spec` loop hook + status-change triggers), adds `make findings-sweep` target,
and replaces the dead-end end-of-review message in `scripts/human_eval.py`. This
batch is doc-heavy; the only new executable code is `findings_sweep.py` (pure
file I/O + JSON parsing; no subprocess/shell/network/eval; read-only).

Batch 2 (SPEC + artifacts, 4 commits): `d2bd957` commits the CODEREVIEW.md and
SECURITY.md artifacts that the prior push's pre-push codereview produced.
`ea9ea73` refreshes the 2026-04-19 proposal in SPEC.md to fold in the FINDINGS
automation turn. `16f0e48` opens spec 2026-04-20 ("Graduation sweep +
candidate-eval join key", `criteria_met: 0`), `e2233f6` appends criterion 8
(fix `make test-full` order-dependency). The spec body describes *future*
work -- none of criteria 1-8 are met in this push, which is expected:
`SPEC_META.criteria_met = 0`.

Verification: `make test-quick` passes (302/302, 5.09s); `scripts/findings_sweep.py`
returns exit 0 against the current tree (38 reviews scanned, 0 unprocessed).

**External reviewers:**
Not re-run during the refresh cycle (per skill: external reviewers run once at
initial review).

### Findings

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
- Security scan: `scripts/findings_sweep.py` is the only new executable file.
  Verified no subprocess / shell / eval / exec / pickle / dynamic import paths;
  uses `Path.glob`/`read_text`/`json.load` against a fixed directory rooted at
  the repo; `json.load` is wrapped in `try/except (OSError, JSONDecodeError)` in
  the caller. `scripts/human_eval.py` delta is a 3-line print-statement rewrite
  (no behavioral change). `Makefile` delta is a phony target that calls
  `.venv/bin/python scripts/findings_sweep.py`. No security findings.
  SECURITY.md does not need an update since no net security-surface change
  (the two new code locations are read-only doc-infra scripts).
- `findings_sweep.py` correctness spot-checks:
  - `TIMESTAMP_RE = r"^\d{4}-\d{2}-\d{2}_\d{6}$"` correctly excludes `images/`
    directory, hidden files, and malformed stems; verified with a unit-style
    probe over 5 filenames.
  - Empty-marker branch (line 126-128) surfaces every review on first run -- a
    deliberate "force bootstrap" as the module docstring states.
  - `_summarize` is defensive about `evaluations` being missing or non-dict.
  - Minor: `argparse(description=__doc__.splitlines()[0])` would crash under
    `python -OO` (which strips docstrings to None). Non-issue under normal
    invocation; not worth a NOTE at this project's tooling norms.
- FINDINGS.md compression (`59148ef`): verified Status Summary arithmetic
  (`Active 2, In Progress 3, Resolved 4, Acceptable 1, Plateaued 1, Graduated 1`)
  matches the bodies below. The prior push's summary claimed
  `0 Graduated`, and the delta of +1 corresponds exactly to Chunk stitching
  moving from Resolved to Graduated. The compressed bodies preserve all
  load-bearing claims (principles, code-changes lists, resolutions,
  trajectories); the cuts are per-review trajectory commentary subsumed by
  aggregated trajectory lines. Spot-checked the Composition finding's
  trajectory line "4, 4, 3, 4, 4, 3, 2, 2, 3, 3" against the prior full-history
  block -- consistent.
- FINDINGS automation bundling: the 3 commits are properly decomposed (cleanup
  / utility / wiring), each with a clear scope and a referenced phase of the
  plan in `~/.claude/plans/deep-greeting-conway.md`. Not spaghetti.
- SPEC.md (`16f0e48`, `e2233f6`) describes *future* work. Criterion 8 was added
  after criteria 1-7 were drafted because the `test-full` order-dependency
  surfaced mid-turn. `SPEC_META.criteria_total = 8`, `criteria_met = 0`
  accurately reflects the current state. The narrative claim "`can't` seed=2718
  right-chunk stroke 5.40 vs left 6.39, ratio 0.845 < 0.85 gate" was verified
  against `tests/medium/test_contraction_sizing.py:29` (`MIN_STROKE_RATIO = 0.85`).
- SPEC.md prior-spec footer says "Follow-on FINDINGS automation landed in
  5 commits". The strict FINDINGS automation set is 3 commits (`59148ef`,
  `91da547`, `df77ec6`). The footer appears to count adjacent commits
  (`d2bd957` codereview artifacts, `ea9ea73` proposal refresh) under the same
  narrative banner. Minor narrative drift; not a correctness finding.
- CLAUDE.md "Findings workflow" rewrite (`df77ec6`): the `/spec in evolve mode
  at turn close` hook is spelled out precisely enough for future agents to
  act on (entry point, exit-code semantics, diff-in-terminal no-qpeek, marker
  bump in same edit). The status-change triggers (Resolved / Plateaued /
  Graduated) are consistent with FINDINGS.md's "How this file works" section.

### Fixes Applied

None. No BLOCK or WARN findings.

### Accepted Risks

None.

---
*Prior review (2026-04-19, commit d0c3276): Refresh review of the
`size_inconsistent` body-zone turn (diagnostic + two reverted attempts),
rating-window analysis, and duplicate-letter hard-words promotion. 0 BLOCK /
0 WARN / 1 NOTE (walkback threshold consistency in `detect_baseline`, carried
forward). Three test runs verified (302 quick / 303 with new contraction
sizing / 303 with duplicate-letter / 304 with regression).*

<!-- REVIEW_META: {"date":"2026-04-19","commit":"e2233f6","reviewed_up_to":"e2233f6a6dd346164b3911f9cd2bdd851925738d","base":"origin/main","tier":"refresh","block":0,"warn":0,"note":1} -->
