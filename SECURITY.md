## Security Review -- 2026-04-20 (scope: paths)

**Summary:** No security issues identified across 4 reviewed files. The scope is build glue and diagnostic/eval scripts: `Makefile` targets for the test matrix and the findings sweep; `scripts/findings_sweep.py` (pure file I/O over `reviews/human/*.json` with filename-whitelist via `TIMESTAMP_RE`); `scripts/human_eval.py` (model-loading, per-eval image generation, qpeek orchestration, review JSON persistence); `tests/medium/test_contraction_sizing.py` (CUDA-hardened regression test with hardcoded inputs). No `shell=True`, no `eval`/`exec`, no pickle, no dynamic import, no network, no SQL. `subprocess.run` usages are argv-lists with fixed arguments (`git rev-parse --short HEAD` with `cwd=PROJECT_ROOT`; `python -m qpeek --html <path> --timeout 0 <image_files>` where every argument is derived from internal constants or whitelisted eval types). Eval-type strings reach shell only after `EVAL_TYPES` whitelist filtering (`invalid = [e for e in eval_types if e not in EVAL_TYPES]` -> exit 1). Makefile `EVAL` variable expansion requires local shell access to exploit (i.e., already-privileged user), not a new attack surface. HTML-template injection (`build_html_page` replaces `/* INJECT_STEPS_JSON */` / `/* INJECT_EVAL_ORDER */` with `json.dumps(...)`) only receives hardcoded source strings (`"garden"`, `"can't"`, etc.) and values loaded from committed `reforge/data/hard_words.json`; no external/untrusted input flows into the template. The test file performs `torch.cuda` state manipulation (`cudnn.deterministic`, `empty_cache`, `manual_seed_all`) that is intentional per spec 2026-04-20 criterion 8 and is scoped via save/restore. File-handle leak in `hashlib.sha256(open(full, "rb").read()).hexdigest()` (`compute_pipeline_checksums`) is a resource concern, not security. Git history for the 4 scope files shows only algorithmic / CI / doc commits, no credentials. Only PII is the previously-accepted `Katherine` in `scripts/human_eval.py:556` demo text.

### Findings

No security issues identified.

### Accepted Risks

- Generic first name `Katherine` in demo sentence literal (`scripts/human_eval.py:556`). Previously accepted in 2026-04-17, 2026-04-18, and 2026-04-19 reviews; not re-flagged.

---
*Prior review (2026-04-19): No issues across 9 reviewed files (image-processing math, font-glyph rasterization, word-generation orchestration, rating-window statistics, medium-tier sizing/duplicate tests); all pure math or hardcoded-path I/O with no dangerous sinks; `Katherine` PII accepted.*

<!-- SECURITY_META: {"date":"2026-04-20","commit":"f43d1d5e6eb7e0f470f3bc78910741b859100ef0","scope":"paths","scanned_files":["Makefile","scripts/findings_sweep.py","scripts/human_eval.py","tests/medium/test_contraction_sizing.py"],"block":0,"warn":0,"note":0} -->
