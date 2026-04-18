## Security Review -- 2026-04-17 (scope: paths)

**Summary:** No security issues identified across 8 reviewed files (`.claude/settings.local.json`, two throwaway experiment drivers, `reforge/config.py`, the new OFL-font glyph rasterizer and its test, the generator, and the human-evaluation orchestrator). The font rasterizer (`reforge/model/font_glyph.py`) and its fallback path in `generator.py::_render_trailing_mark_or_fallback` resolve font paths from a fixed config constant (`PUNCTUATION_GLYPH_FALLBACK_FONT`), not user input; path joining happens only after the `os.path.isabs` branch, and the fallback returns the Bezier mark on `OSError`/`ValueError`. `scripts/human_eval.py` uses `subprocess.run` with an explicit argv list in two places (`git rev-parse` and `python -m qpeek`) and never `shell=True`; CLI args are validated against fixed lists. JSON data injected into the HTML review template comes from internally-constructed dicts, rendered via `json.dumps` into a JS literal context, with no external-input flow. No secrets, no shell/SQL/SSRF paths, no deserialization of untrusted data, and no PII beyond fictional story names (`Birchwood`, `Katherine`) already present in prior composition fixtures.

### Findings

No security issues identified.

### Accepted Risks

(none)

---

*Prior review (2026-04-17): No issues across 2 reviewed experiment drivers (`experiments/contraction_right_side.py`, `experiments/reinforce_variance.py`).*

<!-- SECURITY_META: {"date":"2026-04-17","commit":"0a5c1cfa0421992c911e95ea8a55a29522d93749","scope":"paths","scanned_files":[".claude/settings.local.json","experiments/diagnose_contraction.py","experiments/smoke_caveat_marks.py","reforge/config.py","reforge/model/font_glyph.py","reforge/model/generator.py","scripts/human_eval.py","tests/quick/test_font_glyph.py"],"block":0,"warn":0,"note":0} -->
