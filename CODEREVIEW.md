## Review -- 2026-04-01 (commit: b2bf61d)

**Review scope:** Refresh review. Focus: 4 files changed since prior review (commit b17efe0). No already-reviewed-only files.

**Summary:** One unpushed commit reverts the A1 metric gaming: restores harmonization thresholds to 110%/88% (from 105%/93%), reverts `check_word_height_ratio` from percentile-based to simple max/min, reverts `harmonize_heights` from scale-to-median to scale-to-boundary, and unchecks A1 in SPEC.md. Well-motivated revert backed by visual comparison. No issues found.

### Findings

No issues found.

### Fixes Applied

None.

---
*Prior review (2026-04-01, commit b17efe0): Refresh review of A1 height harmonization. 1 WARN auto-fixed: CLAUDE.md threshold references updated from 92% to 93%. 1 NOTE: test docstrings with stale threshold percentages (pre-existing, accepted).*

<!-- REVIEW_META: {"date":"2026-04-01","commit":"b2bf61d","reviewed_up_to":"b2bf61dd15e0c2af51d4f563672453ebee01f455","base":"origin/main","tier":"refresh","block":0,"warn":0,"note":0} -->
