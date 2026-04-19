## Security Review -- 2026-04-19 (scope: paths)

**Summary:** No security issues identified across 9 reviewed files. The scope is image-processing math and diagnostic scripts: baseline detection, font-glyph rasterization, word generation orchestration, and a rating-window statistics script. No subprocess, shell, network, SQL, pickle, `eval`/`exec`, or dynamic import paths. All file I/O is to hardcoded local paths: the font path resolves from a constant (`PUNCTUATION_GLYPH_FALLBACK_FONT = "fonts/Caveat-VariableFont_wght.ttf"`) against a computed `repo_root`; the JSONL candidate-score log writes to a fixed relative path gated on `REFORGE_LOG_CANDIDATES=1`; `scripts/compute_rating_window.py` globs `reviews/human/*.json` and uses `json.load` with `JSONDecodeError` caught; `scripts/measure_word_sizing.py` reads `styles/hw-sample.png`. User-controllable strings (text input tokens, mark characters) reach only character-membership checks against hardcoded sets (`DESCENDER_LETTERS = {g,j,p,q,y}`, `SYNTHETIC_MARKS = {",",".","!","?",";"}`) and single-char validation (`len(mark) != 1` raises `ValueError`). Logging calls use parameterized `%s`/`%r` formatting, not concatenation. The only PII is the generic first name `Katherine` in demo-sentence string literals, already accepted in prior reviews. Git history for the 6 scope files new to this scan shows only algorithmic/diagnostic commits, no credentials.

### Findings

No security issues identified.

### Accepted Risks

- Generic first name `Katherine` in demo sentence literals (`scripts/measure_word_sizing.py:38`, `reforge/model/generator.py:51`, `reforge/model/generator.py:66`). Accepted in prior 2026-04-17 and 2026-04-18 reviews; not re-flagged.

---

*Prior review (2026-04-18): No issues across 3 reviewed files (`reforge/compose/layout.py`, `tests/quick/test_baseline.py`, `tests/quick/test_contraction.py`); all pure image-processing math with no dangerous sinks.*

<!-- SECURITY_META: {"date":"2026-04-19","commit":"d0c32762c1c6683a69d597bcefcfa784c013345a","scope":"paths","scanned_files":["reforge/compose/layout.py","reforge/model/font_glyph.py","reforge/model/generator.py","scripts/compute_rating_window.py","scripts/measure_word_sizing.py","tests/medium/test_contraction_sizing.py","tests/medium/test_duplicate_letter_hallucinations.py","tests/quick/test_baseline.py","tests/quick/test_font_glyph.py"],"block":0,"warn":0,"note":0} -->
