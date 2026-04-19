## Security Review -- 2026-04-18 (scope: paths)

**Summary:** No security issues identified across 3 reviewed files (`reforge/compose/layout.py`, `tests/quick/test_baseline.py`, `tests/quick/test_contraction.py`). `layout.py` is pure image-processing math: `detect_baseline` reads pixel density via numpy and uses an optional `word: str | None` only for membership checks against a fixed 5-letter set (`DESCENDER_LETTERS = {g,j,p,q,y}`), which bounds any adversary-controlled string effect to a boolean threshold selection (0.25 vs 0.35). `compute_word_positions` uses `np.random.RandomState(layout_seed)` deliberately for deterministic layout jitter (non-cryptographic use is correct here). No file I/O, subprocess, shell, network, SQL, pickle, `eval`/`exec`, or dynamic import paths anywhere in the three files. The two test modules operate entirely on synthetic `np.full`/`cv2.putText` fixtures and string literals; no external input, no secrets, no PII beyond generic example names (`Katherine's`) already reviewed and accepted in prior runs. Git history for all three files shows only algorithmic tuning commits, no credentials.

### Findings

No security issues identified.

### Accepted Risks

(none)

---

*Prior review (2026-04-17): No issues across 8 reviewed files including `.claude/settings.local.json`, experiment drivers, `reforge/config.py`, the OFL-font glyph rasterizer and its test, the generator, and the human-evaluation orchestrator.*

<!-- SECURITY_META: {"date":"2026-04-18","commit":"20054089a9828068021b7d0140c55d82cc72fae6","scope":"paths","scanned_files":["reforge/compose/layout.py","tests/quick/test_baseline.py","tests/quick/test_contraction.py"],"block":0,"warn":0,"note":0} -->
