## Review -- 2026-04-14 (commit: cfb3bba)

**Summary:** Light refresh review of 2 unpushed commits plus uncommitted changes. Focus: `docs/OUTPUT_HISTORY.md` (metric correction for top entry), `docs/output-history/20260416-012853.png` (new archive image). Already-reviewed: `.claude/settings.local.json` (4 new permissions), `docs/best-output.png` (updated image), `reforge/data/hard_words.json` (1 new OCR candidate). No code files modified. Security scan skipped (light review).

**External reviewers:**
Skipped (light review).

### Findings

[NOTE] .claude/settings.local.json:69 -- Hardcoded PID in permission entry
  Evidence: `Bash(kill 897414)` grants permission to kill a specific PID that is almost certainly no longer running. This is a stale artifact from a debugging session.
  Suggested fix: Remove the `Bash(kill 897414)` entry. The broader `Bash(ps:*)` + manual kill is sufficient.

[NOTE] docs/output-history/20260414-220530.png -- Orphaned untracked image
  Evidence: The duplicate OUTPUT_HISTORY.md entry for 20260414-220530 was removed in commit 73525c6, but the corresponding image file remains on disk as an untracked file. It is not referenced by any committed file.
  Suggested fix: Delete the file (`rm docs/output-history/20260414-220530.png`).

### Fixes Applied

None.

### Accepted Risks

None.

---
*Prior review (2026-04-14, commit ca86055): Light review. 1 WARN (duplicate output history entry, since resolved in commit 73525c6), 1 NOTE (hardcoded PID, carried forward).*

<!-- REVIEW_META: {"date":"2026-04-14","commit":"cfb3bba","reviewed_up_to":"cfb3bbaa88c201a0f6652fbab85644e7ff3c696c","base":"origin/main","tier":"light","block":0,"warn":0,"note":2} -->
