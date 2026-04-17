## Security Review -- 2026-04-17 (scope: paths)

**Summary:** No security issues identified across 8 reviewed files. The scope covers Claude Code permission config, the Makefile, image-processing modules (config constants, CV metrics, word generation, font scaling, per-word scoring), an offline human-evaluation orchestration script, and a test suite. All external-facing operations use hardcoded paths or list-form subprocess calls; user text input flows through a tokenizer into a local neural network and is never used as a shell argument, SQL query, or HTML literal. The one JSONL log (`experiments/output/candidate_scores.jsonl`) writes through `json.dumps`, so word content is escaped. No secrets, tokens, PII, or credentials were found in file contents or the recent commit history of these paths.

### Findings

No security issues identified.

### Accepted Risks

(none)

---

*Prior review (2026-04-16): No issues across 4 files (settings.local.json, hard_words.json, font_scale.py, human_eval.py); the reviewed code was local-only with no network listeners, secret handling, or shell command construction from user input.*

<!-- SECURITY_META: {"date":"2026-04-17","commit":"3a710b3e1ab3ff55e53c400332d5c242ae088fc5","scope":"paths","scanned_files":[".claude/settings.local.json","Makefile","reforge/config.py","reforge/evaluate/visual.py","reforge/model/generator.py","reforge/quality/font_scale.py","reforge/quality/score.py","scripts/human_eval.py","tests/quick/test_evaluate.py"],"block":0,"warn":0,"note":0} -->
