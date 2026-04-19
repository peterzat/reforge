## Spec -- 2026-04-20 -- Graduation sweep + candidate-eval join key

**Goal:** Close the graduation arc opened by spec 2026-04-19's FINDINGS cleanup by promoting three near-bar findings to CLAUDE.md, and unblock the `QUALITY_WEIGHTS` reweighting path by landing the candidate-eval human-pick join key that has been missing since spec 2026-04-17 D1.

### Acceptance Criteria

- [ ] 1. **Ink weight inconsistency graduates.** The meta-principle "stroke-weight harmonization at the post-processing stage has plateaued; further stroke-weight gains come from candidate selection (stroke width scoring during best-of-N), not from the harmonize pass" is captured in `CLAUDE.md` under *Hard-won design constraints > Stroke weight variation* in the same Problem / Required solution voice as surrounding entries. The FINDINGS.md entry is compressed to a pointer under `## Graduated Findings` matching the existing Chunk stitching pattern, status changed from `Acceptable` to `Graduated` with today's date. The Status Summary table is updated.

- [ ] 2. **Apostrophe rendering graduates.** The principle "asymmetric split-word stitching (e.g. `can` + `'t` via Option W) needs `_match_chunk_to_reference`-style matching of the short chunk's ink height, stroke width, and ink median to the long chunk" is captured in `CLAUDE.md` under *Hard-won design constraints > Long word chunking* (extending the existing entry). The FINDINGS.md entry is compressed to a pointer under `## Graduated Findings`, status changed from `Resolved` to `Graduated`.

- [ ] 3. **Trailing punctuation graduates.** The principle "OFL-font synthetic marks at production body_height require morphological dilation retargeted against the measured Bezier-equivalent stroke width with `TRAILING_MARK_TARGET_MULTIPLIER = 1.15`; nominal `body_height * 0.12` underestimates the dot-component strokes of `!` and `?`" is captured in `CLAUDE.md` under *Hard-won design constraints* as a new subsection (e.g. "Trailing punctuation synthesis"). The FINDINGS.md entry is compressed to a pointer under `## Graduated Findings`, status changed from `Resolved` to `Graduated`.

- [ ] 4. **Candidate join key lands.** `scripts/human_eval.py` records the human-selected candidate identifier for every candidate comparison in the persisted review JSON, keyed such that each selection can be matched against the corresponding row logged by `_log_candidate_scores` (word + seed + session timestamp is the minimum sufficient key; richer schemas are acceptable). The key is populated only when the `candidate` eval runs and does not affect other eval types.

- [ ] 5. **One `make test-human EVAL=candidate` session executes and verifies the join.** The resulting review JSON is inspected (eyeball, `jq`, or a one-shot python snippet) and contains a populated human-pick key for every comparison presented in the session, matching the candidate-score JSONL rows produced by the same run. If any comparison in the session lands with an empty or unjoinable key, revert the criterion 4 change before closing the spec (execute-and-record, not a lift gate).

- [ ] 6. `make test-quick` and `make test-regression` pass on seeds 42/137/2718. No pipeline code changes are expected; these are guardrails to catch accidental touches via the `human_eval.py` change.

- [ ] 7. `scripts/findings_sweep.py` exits 0 after the spec closes. The `FINDINGS_LAST_PROCESSED` marker at the top of `reviews/human/FINDINGS.md` is bumped to cover any review created during criterion 5.

### Context

This spec consumes the `### Proposal (2026-04-19, refreshed)` section of the prior SPEC.md under the "Recommended default: (4) + (3)" path. Directions (1), (2), and the `"by"` descender revisit stay deferred; see the consumed proposal's commit (`ea9ea73`) for the rationale. The other two proposal directions (5 -- promote findings_sweep hook to zat.env skill; 4 non-adopted items) are not in scope here.

**Graduation bar:** 3+ reviews, 2+ code changes, stable + generalizable principle. All three candidates clear it per `reviews/human/FINDINGS.md`: Ink weight (6 reviews, `Acceptable`), Apostrophe rendering (10 reviews, `Resolved`), Trailing punctuation (7 reviews, `Resolved`).

**Graduation structural pattern (single precedent, Chunk stitching):**

```
### <title>
- **Graduated:** YYYY-MM-DD to `CLAUDE.md` > <section>.
- **Core principle:** <1-3 sentences>.
- **Review trajectory:** <short summary>.
- **Code:** <path> hint.
```

The consumed proposal flagged all three graduations as low risk and doc-only. The spec scope is exactly that: no pipeline code changes for criteria 1-3.

**Join key (criterion 4):**

Existing infrastructure:

- `REFORGE_LOG_CANDIDATES=1` (set by default in the Makefile `test-human` target when `candidate` is among the requested evals) activates `_log_candidate_scores` in `reforge/model/generator.py:1188` to write per-candidate scores to a JSONL.
- `scripts/candidate_preference_analysis.py:61-74` already reads this JSONL and detects whether per-candidate scores are present, but cannot link rows back to the human's preferred candidate.
- `scripts/human_eval.py:273-274` gates the logging on the env var; the human's `candidate` selection flows through the qpeek HTML and lands in the review JSON's `evaluations.candidate` structure.

The missing piece is a shared key. Record it in the review JSON (the human-visible artifact) rather than the JSONL (the machine log) so review JSON remains the source of truth for human intent.

**Out of scope:**

- `QUALITY_WEIGHTS` reweighting itself. Blocked until 15+ paired samples accumulate across future `EVAL=candidate` sessions; this spec lands the key so future sessions can contribute.
- Per-word `size_inconsistent` eval type (proposal direction 2).
- Compose-layer baseline-offsets lever for `size_inconsistent` (proposal direction 1).
- `"by"` descender clipping revisit (proposal revisit candidate).
- Promoting the findings_sweep hook from project CLAUDE.md into `~/src/zat.env/skills/spec/SKILL.md`.

**Failure protocol:**

- Criteria 1/2/3 (graduations): if during drafting the principle turns out to be narrower than "stable and generalizable" or specific to a code path that will likely change soon, leave that finding in its current status and note the reason in SPEC.md alongside the checkbox. Do not force-graduate.
- Criterion 4: if the join key cannot be populated cleanly via the current `human_eval.py` flow (e.g., the qpeek response path does not carry the candidate index into `evaluations.candidate`), revert the code change, document the blocker, mark criterion 4 unmet and skip criterion 5.
- Criterion 5: if the verification session reveals any unpopulated key, revert criterion 4's change before closing the spec.
- Criterion 6: any regression is almost certainly caused by the criterion 4 code change; revert that specifically, not the graduation work.
- Criterion 7: if a review lands during criterion 5, process it into FINDINGS.md as a pointer + update the marker in the same edit, following the loop hook in CLAUDE.md.

**zat.env practices carried in:**

- Smallest change that closes each criterion. Do not refactor surrounding doc structure.
- Work in small committable increments. Each graduation is its own commit; the join-key code + verification is one commit.
- If the verification session fails, revert + re-evaluate rather than patching the test to accommodate.
- Project CLAUDE.md files are the reforge project, not zat.env; edits to CLAUDE.md here are in scope.

---
*Prior spec (2026-04-19, body-zone sizing): escaped 6/6 via the failure-protocol two-attempts path. x-height-spread ruled out as a lever for `size_inconsistent`. Follow-on FINDINGS automation landed in 5 commits (837 -> 403 line cleanup, `findings_sweep.py`, `/spec` loop hook, BACKLOG retirement).*

<!-- SPEC_META: {"date":"2026-04-20","title":"Graduation sweep + candidate-eval join key","criteria_total":7,"criteria_met":0} -->
