## Spec -- 2026-04-18 -- Adopt zat.env BACKLOG.md mechanism

**Goal:** Migrate reforge from its custom `docs/BACKLOG.md` + CLAUDE.md pointer convention to the upstream zat.env BACKLOG.md mechanism once the upstream `/spec` skill changes land. The upstream version reads `BACKLOG.md` from the project root automatically (no per-project CLAUDE.md pointer needed), adds a `/spec backlog <description>` append command with pressure-tested entries, and runs a turn-close sweep that classifies entries as keep/revisit-candidate/recommend-delete. Reforge's 12 existing entries already conform to the upstream format; the migration is mechanically trivial.

### Acceptance Criteria

- [x] 1. `BACKLOG.md` exists at the reforge project root.
- [x] 2. `docs/BACKLOG.md` does not exist.
- [x] 3. `CLAUDE.md` no longer contains the "Deferred proposals register" subsection (or any equivalent pointer directing agents to read BACKLOG.md).
- [x] 4. `grep -rn "docs/BACKLOG" /home/peter/src/reforge --exclude-dir=.git --exclude=SPEC.md` returns zero matches. (SPEC.md itself describes the migration and legitimately references the prior path.)
- [ ] 5. Running `/spec` in evolve mode on an active spec produces a Step 5 output line that mentions `BACKLOG.md` and its entry count (verifies the upstream skill's Step 1 auto-read and Step 5 surfacing are both active, without any CLAUDE.md pointer being required).
- [ ] 6. Running `/spec backlog <short test description>` appends an entry to BACKLOG.md containing all five fields (short-name heading in kebab-case, One-line description, Why deferred, Revisit criteria, Origin). The entry count in BACKLOG.md increases by exactly one.
- [x] 7. `make test-quick` passes.

### Context

Adopted from plan `~/.claude/plans/soft-shimmying-parnas.md`. Read that plan for the full upstream-proposal assessment, including the "what I'd question upstream" commentary that informed this spec.

**Precondition — do not start this spec until this holds:** the upstream zat.env `/spec` SKILL.md updates (Step 1 auto-read of `BACKLOG.md`, Step 3f append mode, Step 3c.5 turn-close sweep, Step 3.6 overlap scan, Step 5 surfacing line) must be installed locally at `~/.claude/skills/spec/SKILL.md` (which is a symlink to `~/src/zat.env/claude/skills/spec/SKILL.md`). Running the migration before the upstream changes are installed leaves `BACKLOG.md` orphaned: the file exists at the new path but no `/spec` mode reads it and criteria 5 and 6 fail.

**Migration mechanics (carried from the plan):**
- `git mv docs/BACKLOG.md BACKLOG.md` preserves content. Reforge's current 12 entries already use the upstream `### <short name>` + five-field format (as of commit `0a5c1cf`). No content rewrites required.
- Retain reforge's existing `## ...` thematic subheads ("Rejected by user, unlikely to revisit", "Cantt-specific proposals deferred from turn 2026-04-17 (Plan B if F/K fail)", "Scoped out for dedicated work later") by default — the upstream format spec does not forbid them, and they aid readability for ~12+ entries. Flatten only if the upstream spec explicitly rejects them.
- The CLAUDE.md pointer to remove was introduced in commit `accc455` (roughly 11 lines). Locate via `grep -n "Deferred proposals register" CLAUDE.md`.

**Out of scope:**
- Editing or contributing to zat.env's `/spec` SKILL.md. That is a separate workstream on the zat.env repo; feedback for its finalization is in the plan file's "What I'd question for upstream" section and must be carried across to the zat.env session manually, not via this spec.
- Changing BACKLOG.md entry format, adding new fields, or reorganizing existing entries beyond preserving the `##` thematic subheads.
- Addressing D3 from the prior 2026-04-17 spec (candidate eval human-pick join key). Remains unaddressed; if it isn't picked up directly in a follow-up turn, it should be captured as a BACKLOG.md entry.

**zat.env practices carried in:**
- Small committable increments. Suggested commit order: (1) `git mv docs/BACKLOG.md BACKLOG.md`, (2) edit CLAUDE.md to remove the pointer, (3) verify grep + tests. One commit is also acceptable given the small scope.
- Do not push to the remote unless explicitly asked.
- If criteria 5 or 6 fail, the zat.env install has drifted from the proposal — do not modify reforge to compensate; instead, verify the upstream skill state and defer this turn until the upstream state matches the precondition.

---
*Prior spec (2026-04-17): Contraction right-side, punctuation CV metric, variance check (17/18 criteria met; D3 unmet, carried forward).*

<!-- SPEC_META: {"date":"2026-04-18","title":"Adopt zat.env BACKLOG.md mechanism","criteria_total":7,"criteria_met":5} -->
