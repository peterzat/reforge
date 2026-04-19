# Rating Window Analysis

**Date:** 2026-04-19
**Spec:** 2026-04-19 (Composition rating window: data-driven decision)
**Utility:** `scripts/compute_rating_window.py`

## Question

Is the persistent composition 3/5 median across the last 5 reviews a true
quality plateau, or is the 5-window dragging on older sub-3 ratings? A wider
window might reveal a hidden lift that the rolling 5-window is masking, or
confirm that the plateau is genuine. Two recent reviews (Review 12 and Review
8) gave positive freeform notes ("punctuation is improved", "every word +
punctuation improved over prior runs") while the composition number held at
3/5 — the mismatch is the trigger.

## Method

Compute the median composition rating at window sizes {3, 5, 7, 10, all} over
every `reviews/human/*.json` file with a non-skipped composition rating,
sorted ascending by review timestamp. Apply the decision rule from spec
criterion 3: if last-10 median is at least 0.5 higher than last-5 median,
widen the CLAUDE.md human-preference target window to 10; otherwise, leave
the window at 5 and record the hypothesis as ruled out.

## Utility output (verbatim)

```
Reviews with composition rating: 33

Per-review ratings (ascending by timestamp):
  2026-04-03T01:27:36  3  2026-04-03_012736.json
  2026-04-03T02:18:29  2  2026-04-03_021829.json
  2026-04-03T02:40:39  3  2026-04-03_024039.json
  2026-04-03T16:20:51  3  2026-04-03_162051.json
  2026-04-03T16:42:43  3  2026-04-03_164243.json
  2026-04-04T01:03:17  3  2026-04-04_010317.json
  2026-04-09T02:32:55  2  2026-04-09_023255.json
  2026-04-09T02:46:32  3  2026-04-09_024632.json
  2026-04-09T03:34:41  2  2026-04-09_033441.json
  2026-04-09T03:41:48  2  2026-04-09_034148.json
  2026-04-09T22:08:12  2  2026-04-09_220812.json
  2026-04-10T00:08:11  3  2026-04-10_000811.json
  2026-04-10T00:27:57  4  2026-04-10_002757.json
  2026-04-10T02:31:03  4  2026-04-10_023103.json
  2026-04-10T02:38:24  3  2026-04-10_023824.json
  2026-04-10T03:00:53  3  2026-04-10_030053.json
  2026-04-13T21:33:30  3  2026-04-13_213330.json
  2026-04-14T04:17:53  3  2026-04-14_041753.json
  2026-04-14T14:37:35  4  2026-04-14_143735.json
  2026-04-14T15:41:17  4  2026-04-14_154117.json
  2026-04-14T17:05:08  2  2026-04-14_170508.json
  2026-04-14T21:14:47  3  2026-04-14_211447.json
  2026-04-14T21:28:10  4  2026-04-14_212810.json
  2026-04-16T01:17:18  4  2026-04-16_011718.json
  2026-04-16T02:14:00  3  2026-04-16_021400.json
  2026-04-17T14:13:20  2  2026-04-17_141320.json
  2026-04-18T15:47:57  2  2026-04-18_154757.json
  2026-04-18T21:38:57  2  2026-04-18_213857.json
  2026-04-18T23:33:50  3  2026-04-18_233350.json
  2026-04-19T02:16:32  3  2026-04-19_021632.json
  2026-04-19T15:49:26  3  2026-04-19_154926.json
  2026-04-19T17:31:30  3  2026-04-19_173130.json
  2026-04-19T18:13:54  3  2026-04-19_181354.json

Median by window:
  window   median   n
  last-3   3        3
  last-5   3        5
  last-7   3        7
  last-10  3        10
  all      3        33
```

## Decision

**Branch (b): keep the window at 5. Rating-window hypothesis ruled out.**

Last-5 median is 3. Last-10 median is 3. Delta is 0.0, well below the 0.5
threshold that criterion 3 required to justify widening. The wider window
does not pull in a hidden lift; it pulls in the same 3/5 plateau plus a few
2/5 entries, giving the same median.

Criterion 4 (feasibility guard) is therefore not activated. Even if the delta
had been large, the last-10 median would also need to be within 1 point of
4/5 to be a plausible target; the observed last-10 median of 3 would have
just cleared that guard (within 1 point of 4). The guard does not save us
from the decision rule in this case.

The plateau is real across every window we can measure. The positive
freeform notes in recent reviews ("punctuation improved", "every word
improved") describe *directional* progress that is not yet large enough to
push the integer rating from 3 to 4. Further lift must come from work that
materially raises the composite impression, not from tuning the window.

## Consequences

- `CLAUDE.md` human-preference target window stays at last-5.
- A short note is added to `reviews/human/FINDINGS.md` under a new
  **Methodology notes** section, recording this ruling so the
  rating-window question does not resurface as a live hypothesis in a
  future spec.
- `scripts/compute_rating_window.py` is re-runnable on demand; this
  document should be regenerated (or superseded) the next time the
  question is revisited with meaningfully more data.
