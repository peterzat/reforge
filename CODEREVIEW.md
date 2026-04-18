## Review -- 2026-04-18 (commit: c1782f7)

**Review scope:** Refresh review against prior review commit `e19627d`.
Delta since prior review is docs-only: `BACKLOG.md` (renamed from
`docs/BACKLOG.md` via `git mv`, plus one appended entry), `CLAUDE.md`
(removed the 11-line "Deferred proposals register" pointer), `SPEC.md`
(closed 2026-04-17 spec, opened and closed 2026-04-18 migration spec
7/7), `reviews/human/FINDINGS.md` (three path references updated from
`docs/BACKLOG.md` to `BACKLOG.md`). The one uncommitted change
(`.claude/settings.local.json`) is byte-identical to the state the
prior review approved. Effective tier for the new delta is light
(plain-docs only).

**Summary:** Migrated the deferred-proposals register from
`docs/BACKLOG.md` (+ CLAUDE.md pointer) to project-root `BACKLOG.md`,
matching the upstream zat.env `/spec` skill's auto-read location. `git
log --follow BACKLOG.md` shows the rename preserved history. Grep
confirms no stale `docs/BACKLOG` references outside SPEC.md (which
criterion 4 of the spec legitimately excludes). All three FINDINGS.md
references point at anchor headings that exist in the new file
(`Cantt-specific proposals — status update 2026-04-18`, `Caveat
glyphs too thin in composition (Turn 2d follow-up)`). Entry count
went 20 -> 21 across the migration; the added entry is the D3
carryover (`candidate-eval human-pick join key`) from the prior spec.
Prior review's 297 quick tests still pass (no code changed).

**External reviewers:**
Skipped (light review -- docs-only delta since prior review).

### Findings

No issues found.

Refresh-review verification notes:
- `git mv docs/BACKLOG.md BACKLOG.md` preserved history
  (`accc455` -> `0a5c1cf` -> `86c2570` -> `c1782f7` chain intact under
  `git log --follow`). Content unchanged in the rename commit.
- `grep -rn "docs/BACKLOG" /home/peter/src/reforge --exclude-dir=.git
  --exclude=SPEC.md` returns no matches. SPEC.md references are
  retrospective and called out explicitly in criterion 4.
- All three FINDINGS.md path updates (lines 426, 525, 618) resolve to
  existing anchor headings in the new `BACKLOG.md`.
- CLAUDE.md's 11-line "Deferred proposals register" subsection was
  removed cleanly (no orphaned references elsewhere in CLAUDE.md).
- SPEC.md narrative says "12 existing entries" / "all 12 entries
  unchanged" while the actual count at commit `0a5c1cf` was 20 and
  is 21 post-migration. Prose-level imprecision in a closed spec
  body; no acceptance criterion references the count, and criterion 6
  ("entry count increases by exactly one") is consistent with the
  observed 20 -> 21 delta. Not flagged as a finding.
- `.claude/settings.local.json` uncommitted diff is unchanged since
  the prior review that approved it.

### Fixes Applied

None. No BLOCK or WARN findings.

### Accepted Risks

None.

Informational observations (carried forward, not findings):
- Candidate logging is wired only in the main `_generate_chunk`
  best-of-N loop, not in `_generate_contraction._gen_part` or
  `_generate_punctuated_word`. Spec 2026-04-17 D1 targets the
  singular path and the `EVAL=candidate` fixture uses a
  non-contraction word, so the documented join key is covered.
- `strip_and_reattach_punctuation` (generator.py:1346) is a test-only
  helper that still uses the Bezier `make_synthetic_mark` directly.
  Intentional: the tests that import it pin Bezier behavior. Keep
  the divergence unless a future spec retires the Bezier path, in
  which case this helper and its tests should be updated together.

---
*Prior review (2026-04-18, commit e19627d): Refresh review, no code
changes since `0a5c1cf`. Only delta was the `ff0ea75` output archival
commit plus doc/CODEREVIEW refreshes. 0 BLOCK / 0 WARN / 0 NOTE.
Security scan skipped (covered by SECURITY_META at `0a5c1cf`).*

<!-- REVIEW_META: {"date":"2026-04-18","commit":"c1782f7","reviewed_up_to":"c1782f710d5a9ef1b8be619ef9b0069f0eef7d33","base":"origin/main","tier":"refresh","block":0,"warn":0,"note":0} -->
