## Review -- 2026-03-31 (commit: 8787490)

**Summary:** Reviewed test infrastructure expansion: 6 new medium-tier A/B quality tests with session-scoped GPU fixtures, CV quality assertions added to e2e test, root conftest implementing a tier DAG for automatic lower-tier inclusion, and TESTING.md documentation. One minor fix applied (unused import).

### Findings

[WARN] tests/medium/test_ab_harness.py:7 -- Unused `import numpy as np`
  Evidence: `np` is not referenced anywhere in the file; all numpy operations happen inside the imported evaluation functions.
  Suggested fix: Remove the import.

[NOTE] conftest.py:22-23 -- Dead `pytest_collect_file` hook
  Evidence: The function body is empty (returns None implicitly), which is identical to not defining the hook. The docstring says collection is handled by `pytest_configure`, but this hook does not contribute to that.
  Suggested fix: Remove the no-op function. Not auto-fixed per NOTE policy.

### Fixes Applied

1. Removed unused `import numpy as np` from `tests/medium/test_ab_harness.py` (WARN).

---

<!-- REVIEW_META: {"date":"2026-03-31","commit":"8787490","reviewed_up_to":"87874900c1bd6d1b6838b934fc221aad795f4a1e","base":"origin/main","tier":"full","block":0,"warn":1,"note":1} -->
