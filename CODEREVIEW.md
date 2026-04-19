## Review -- 2026-04-19 (commit: 2005408)

**Review scope:** Refresh review against prior review commit `c1782f7`.
Focus and full sets are identical -- all files changed since the prior
review are reviewed at full depth. Delta is one commit (`2005408`,
"Caveat glyph dilate + baseline alignment + Option W split") plus
uncommitted changes to `reforge/compose/layout.py` and
`tests/quick/test_baseline.py` that implement spec 2026-04-19 (short-word
baseline alignment). Tier: full review.

**Summary:** Spec 2026-04-19's detect_baseline fix is correctly targeted.
The relative drop threshold (`min(body_peak * 0.3, BASELINE_DENSITY_DROP)`)
and the descender fallback (`baseline = max(mid, r - 1)` when walkback
fails and `has_descender=True`) together resolve the Review 10 `"two is
super low"` defect at its real root cause: descender words (by, jump, py,
gp) were previously anchoring their baseline on the descender tail
because cv2/handwriting peak body density is 0.12-0.28, well below
BASELINE_BODY_DENSITY=0.35. Verified the new TestBaselineOnRealisticWordShapes
fails on old layout.py (`jump`: baseline=63, target 49) and passes on
new. 302 quick tests pass. Criterion 6's human review (`2026-04-19_154926`)
checksums match the current working-tree state, so the review is
load-bearing against the uncommitted diff.

The committed spec 2026-04-19 (Caveat dilate + `_attach_mark_to_word`
baseline) and spec 2026-04-18 Option W (contraction split) in commit
`2005408` are coherent: contraction path reduces to
`left + right` where right retains the apostrophe (`can't -> can + 't`);
`make_synthetic_apostrophe` and the 3-argument `stitch_contraction`
signature are removed along with their tests; `_attach_mark_to_word`
accepts new `word`/`mark` kwargs and uses detect_baseline for the word
reference and a body-density heuristic for descender marks (`,`, `;`).
Backward compatibility preserved: `None` kwargs fall back to the old
ink-bottom alignment. Font glyph dilation iterates 3x3 grayscale erosion
until median stroke width (measured via distance transform) reaches
`body_height * 0.12`.

**External reviewers:**
[openai] o3 (high) -- 16364 in / 13023 out / 12800 reasoning -- ~$.2393
[qwen] Qwen/Qwen2.5-Coder-14B-Instruct-AWQ -- 16919 in / 5 out -- 35s

External reviewer produced two findings; both downgraded after
verification (details in Findings below).

### Findings

[NOTE] reforge/compose/layout.py:155 (openai) -- walkback uses
`BASELINE_BODY_DENSITY` (0.35) instead of the just-computed
`body_threshold` (0.25 for descender words / 0.35 otherwise). For
descender words whose peak body density falls between 0.25 and 0.35,
the walkback would find `found=True` if it used `body_threshold`,
skipping the descender fallback entirely.
  Evidence: line 123 computes `body_threshold = 0.25 if has_descender
  else BASELINE_BODY_DENSITY`; line 144 (has_body_below check) uses it;
  line 155 (walkback) does not.
  Suggested fix: change line 155 to `if row_density[rb] >= body_threshold`
  for consistency. The `has_descender` fallback at line 159 can then be
  tightened (or removed) since walkback will succeed for the cases it
  was patching around. Not a bug: all 6 new baseline tests pass within
  the spec's 3 px tolerance, and the external reviewer's "risking
  baseline mis-detection" characterization is not supported by the
  test set or by the cv2-rendered density numbers observed in practice
  (`jump` peak 0.277, walkback would match r=49 if using 0.25, currently
  falls back to r-1=51, which is 2 px off the cv2 baseline of 49;
  both satisfy <= 3 px).

Rejected external findings:
- [BLOCK] reforge/model/font_glyph.py:57 (openai) -- claimed
  `cv2.erode` with default `BORDER_CONSTANT=0` darkens first/last
  rows on every iteration. Verified false: `cv2.erode` uses
  `morphologyDefaultBorderValue()` which is DBL_MAX, so border pixels
  are treated as the maximum value for min-filter (erosion) and do
  NOT darken edges. Confirmed by running erode on an all-white
  image (output all white) and on an image with ink at row 0
  (ink extends downward, no spurious bars). The `dilate_margin`
  added to `canvas_w_padded` is for shape-extent headroom, not border
  correctness. `render_trailing_mark(',', body_height=24)` produces
  shape (50, 14) with first/last row/col all 255. Finding rejected.

Refresh-review verification notes:
- Checkout test: replaced layout.py with commit 2005408's version,
  ran `TestBaselineOnRealisticWordShapes::test_descender_word_returns_body_baseline_not_tail`;
  failed as expected (`jump` baseline=63, target tolerance <= 3 from 49,
  got 14). Confirms criterion 1's "failing-before / passing-after"
  regression pair.
- Review 10 human review (2026-04-19_154926) at commit 2005408 with
  pipeline checksums matching the current working tree: baseline 4/5
  (criterion 6's >= 3/5 floor met with +1), composition 3/5 (criterion
  6's no-drop floor met), no freeform notes citing `two is super low`
  or `by` descender clipping (criterion 6's negative-assertion met).
- `make test-regression` ran against commit 2005408 on 2026-04-19T15:40
  with all 3 seeds passing `height_outlier_score >= 0.9286` and
  `ocr_min >= 0.4286` (criterion 4's gates at 0.90 / 0.30 held). The
  uncommitted layout.py change is applied only to `detect_baseline`;
  its sole downstream consumer in composition is `compose/render.py:124`
  (per-word baseline) and `compose/render.py:149` (line median), where
  a shift from descender-bottom to body-baseline for descender words
  is the intended improvement. No indication the uncommitted change
  would regress `height_outlier_score` or `ocr_min` vs. the 2005408
  regression run.
- SPEC.md SPEC_META correctly reports 6/6 met. Criteria 1-2 verified
  by test assertions; criterion 3 verified (302 passing quick tests);
  criterion 4 verified by ledger + downstream-consumer analysis;
  criterion 5 verified by hard-words ledger (not re-read in this
  review); criterion 6 verified by the 2026-04-19 review JSON.
- Security scan ran on 3 files new to the scan set
  (`reforge/compose/layout.py`, `tests/quick/test_baseline.py`,
  `tests/quick/test_contraction.py`); 0 findings. SECURITY.md updated.

### Fixes Applied

None. No BLOCK or WARN findings.

### Accepted Risks

None.

Informational observations (carried forward, not findings):
- `_attach_mark_to_word` parity: the walkback-threshold inconsistency
  (NOTE above) is analogous to a general "two related thresholds,
  only one is parametrized on has_descender" pattern. Worth a cleanup
  pass in a dedicated spec along with the related suspect-list items
  the current spec's author deliberately deferred (20% clamp tolerance;
  median pull from bad detections). None are currently producing
  human-visible regressions.
- `strip_and_reattach_punctuation` (generator.py:1291) is a test-only
  helper that still wires through the old mark/word kwargs
  (line 1334). Behavior preserved; no action.
- The external reviewer's BORDER_CONSTANT false positive is a known
  trap: OpenCV's morphology uses `DBL_MAX` (whitespace for erosion,
  blackness for dilation) specifically to avoid edge artifacts, which
  differs from cv2.filter2D's default BORDER_REFLECT_101. Reviewers
  that reason by analogy from filter2D can flag this incorrectly.

---
*Prior review (2026-04-18, commit c1782f7): Refresh review, docs-only
delta (BACKLOG.md migration, CLAUDE.md pointer removal, FINDINGS.md
path updates). 0 BLOCK / 0 WARN / 0 NOTE. Security scan skipped
(covered by SECURITY_META at `0a5c1cf`).*

<!-- REVIEW_META: {"date":"2026-04-19","commit":"2005408","reviewed_up_to":"20054089a9828068021b7d0140c55d82cc72fae6","base":"origin/main","tier":"refresh","block":0,"warn":0,"note":1} -->
