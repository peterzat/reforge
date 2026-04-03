## Spec -- 2026-04-03 -- Finding-driven quality iteration loop

**Goal:** Establish the pattern for using human evaluation findings as work items: lifecycle management in FINDINGS.md, targeted evaluation runs, and one completed feedback loop on chunk stitching height mismatch (the most actionable open finding after the spacing fix).

### Acceptance Criteria

#### A. Finding lifecycle in FINDINGS.md

FINDINGS.md currently has 8 active findings with no status differentiation. Add structure so the agent and human can track progress without re-reviewing everything each iteration.

- [x] A1. Each finding in FINDINGS.md has a status field: `Active`, `In Progress`, `Resolved`, `Acceptable`, or `Graduated`. Active means identified but not yet worked on. In Progress means code changes are underway. Resolved means the human confirmed improvement via a targeted eval. Acceptable means the human reviewed it and decided current quality is good enough (escape hatch). Graduated means promoted to CLAUDE.md per the existing graduation rules.
- [x] A2. The "Word spacing is too loose" finding is marked `Resolved` with a note referencing the code change (WORD_SPACING 16->6, horizontal tight-crop) and the confirming review (2026-04-03_024039, composition 2/5->3/5).
- [x] A3. FINDINGS.md has a "Status Summary" section at the top showing counts by status (e.g., "Active: 5, In Progress: 1, Resolved: 1, Acceptable: 0, Graduated: 0"). This summary updates whenever findings change status.

#### B. Targeted evaluation runs

Currently every eval run reviews all 8 types. The proposal asks for targeted runs that only exercise affected eval types after a code change.

- [x] B1. `make test-human` accepts an `EVAL=` parameter to run a subset of eval types (e.g., `make test-human EVAL=stitch,composition`). This already exists per CLAUDE.md. Verify it works and document the pattern: after a code change to generator.py's stitch_chunks, run `EVAL=stitch,composition`, not the full suite.
- [x] B2. CLAUDE.md documents when to run targeted vs full eval: targeted after specific code changes (listing which eval types map to which code areas), full eval after major changes or every 3 spec iterations as a health check.

#### C. Chunk stitching improvement (feedback loop demonstration)

The "chunk stitching produces visible height mismatch" finding is the target for this iteration's feedback loop. The problem: chunks render at different heights, looking like two separate words, and the current median-height normalization in stitch_chunks does not fix it.

- [x] C1. Investigate and implement an improved stitching strategy in `stitch_chunks()` that reduces visible height mismatch between chunks. The fix should target ink-height alignment (the actual ink region, not the bounding box) rather than overall image height.
- [x] C2. `make test-hard` passes after the change (hard words include chunking-boundary words like "everything", "understand", "impossible"). No regression in average hard-word OCR accuracy below 0.5.
- [x] C3. A targeted human eval (`make test-human EVAL=stitch,composition`) is run. The human rates chunk stitching quality. The result is recorded in a new review JSON.
- [x] C4. The "chunk stitching" finding in FINDINGS.md is updated to reflect the code change and eval result. Status moves to Resolved (if human confirms improvement), Acceptable (if human says good enough), or remains In Progress (if more work needed).

#### D. Quality preset for composition eval

The proposal notes that fast preset (20 steps, 1 candidate) may mask quality that the quality preset (50 steps, 3 candidates) would reveal. Composition eval should use the best the pipeline can produce.

- [x] D1. The composition evaluation type in `scripts/human_eval.py` uses the quality preset (50 steps, 3 candidates) instead of the fast preset. Other eval types continue using fast preset for speed.
- [x] D2. The composition section of the review JSON records which preset was used, so future analysis can distinguish fast vs quality preset results.

#### E. Agent workflow documentation

The finding-driven iteration pattern should be documented so it persists across sessions.

- [x] E1. CLAUDE.md's "Human review workflow" section documents the finding-driven iteration pattern: (1) pick the most actionable active finding, (2) implement a fix, (3) run targeted eval, (4) update finding status based on human feedback, (5) repeat or move to next finding.
- [x] E2. CLAUDE.md documents which eval types correspond to which code areas (e.g., stitch -> generator.py stitch_chunks; spacing -> config.py WORD_SPACING + compose/render.py; composition -> full pipeline).

### Context

**Why chunk stitching first?** Of the 8 active findings, chunk stitching is the most actionable: the problem is clearly identified (height mismatch, not seam artifacts), the code is localized (stitch_chunks in generator.py), and it directly affects the longest-standing user complaint ("croissants" illegibility). The spacing fix proved the feedback loop works; this is the second iteration to establish the pattern.

**Why not quality_score disagreement?** That finding needs more data points (multiple reviews where human disagrees with metric). One review is not enough signal to retune scoring weights. It stays Active, collecting evidence.

**Why not ink weight harmonization?** The human found "no visible effect." This is a candidate for Acceptable status, not a code change. The finding-lifecycle mechanics will handle it.

**Interaction with existing test gates.** None of these changes affect pre-commit (quick tests) or pre-push (regression test) gates. The human eval and FINDINGS.md are advisory infrastructure. Hard words regression (`make test-hard`) is the automated quality check for stitching changes.

---

*Prior spec (2026-04-03): Hard words watchlist and targeted quality stress testing (14/14 criteria met).*

*Prior spec (2026-04-02): Human-in-the-loop quality evaluation (25 criteria). Infrastructure built, first feedback loop completed.*

<!-- SPEC_META: {"date":"2026-04-03","title":"Finding-driven quality iteration loop","criteria_total":14,"criteria_met":14} -->
