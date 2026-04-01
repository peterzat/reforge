## Review -- 2026-04-01 (commit: 55497ae)

**Review scope:** Refresh review. Focus: 16 files changed since prior review (commit 6aabf76). No already-reviewed files; all changes are new.

**Summary:** Reviewed one unpushed commit that fixes character clipping in postprocessing (connected-component analysis preserves columns contiguous with body-zone-valid ink), adds TrOCR-based OCR evaluation as a quality factor, wires OCR rejection into generate_word, expands the A/B harness with multi-run statistics and JSON logging, tightens stroke weight harmonization, and adds 6 new test files (101 quick, 132 total). Architecture is sound: OCR runs on CPU to avoid GPU contention, the model is cached with lru_cache, and the OCR retry loop is bounded.

### Findings

[WARN] demo.sh:41 -- Unused OCR imports force unnecessary TrOCR model download
  Evidence: `from reforge.evaluate.ocr import ocr_read, ocr_accuracy` imported but never used directly. `overall_quality_score(arr)` on line 55 is called without `word_imgs` or `words` args, so the OCR code path inside it never executes. The OCR quality gate on lines 75-76 (`if 'ocr_accuracy' in scores`) can never trigger.
  Suggested fix: Remove the unused import line. The OCR gate remains as a no-op safety net.

[NOTE] demo.sh:55 -- overall_quality_score called without word-level data
  Evidence: `overall_quality_score(arr)` does not pass `word_imgs` or `words`, so OCR accuracy, blank word detection, stroke weight consistency, word height ratio, and baseline alignment are all excluded. The score is computed from only 3 metrics (gray_boxes, ink_contrast, background_cleanliness). The pipeline's own call (pipeline.py:221) correctly passes all args.
  Suggested fix: If per-word metrics are desired in demo.sh, the script would need to run generation via the Python API (which returns word images) rather than invoking the CLI. Current approach is acceptable for a demo script.

### Fixes Applied

1. Removed unused `from reforge.evaluate.ocr import ocr_read, ocr_accuracy` from `demo.sh` (WARN).

---

*Prior review (2026-04-01): Reviewed SPEC.md rewrite and demo.sh quality metrics addition. No issues found.*

<!-- REVIEW_META: {"date":"2026-04-01","commit":"55497ae","reviewed_up_to":"55497ae0fa55550ef2d0d39347507cf4e492548a","base":"origin/main","tier":"refresh","block":0,"warn":1,"note":1} -->
