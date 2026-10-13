# Computer-vision instruments: what to trust for what

Measured 2026-10-13 on this box (RTX 4000 SFF Ada, 20 GB). Every instrument
here was checked against cases with known answers before being recommended.
The datasets and harnesses are committed, so a new model or metric can be
scored the same way in minutes.

## Summary

| Job | Use | Evidence | Do not use |
|-----|-----|----------|------------|
| Decide between two pages (A/B) | Fresh-context Claude subagent, images only, fixed rubric, blind A/B order | 15/15 on known-answer pairs (12 injected-defect canaries + 3 human-validated pairs); 6/6 agreement with the human across two sessions | Local VLMs <= 20 GB: Qwen3.5-9B 6/12 and Qwen3-VL-8B 3/12 on canaries judged in both orders |
| Read a word (legibility) | Local Qwen3.5-9B-AWQ via `REFORGE_OCR_BACKEND=vlm`, Latin-constrained | 93% exact on well-formed words (92% on 1-2 letter words) vs TrOCR-small 88% (83%) | TrOCR-large (44% exact, misreads and spaced punctuation); Qwen3-VL-8B (89%, 82% on short words) |
| Catch misspelled renderings ("disapppear") | Fresh-context Claude subagent on word sheets labeled with the intended spelling | Agreement with blind by-eye labels on 213 crops: 31 both flagged, 3 only by eye, 7 only by Claude (recall 0.91, precision 0.82, Cohen's kappa 0.83) | Any OCR score (readers "correct" 59-68% of malformed renderings); the local VLM's targeted check (53% caught, 17% false alarms) |
| Choose among best-of-N candidates | TrOCR-small (current) | Blind judge preferred TrOCR-selected pages on 3/3 seeds over VLM-selected ones | The VLM reader: it reads split, broken and overinked candidates ("o n", "thi eee?", heavy "and") as the right word, so it stops filtering them |
| Body-size consistency | `x_height_consistency` (gates) | 3/3 human A/B direction; 0.94-0.98 vs 0.49-0.68 between approved and rejected sizing | `height_outlier_score`, `word_height_ratio` (reward the rejected policy) |
| Baseline placement | `baseline_consistency` (diagnostic) | clean 0.92 vs jitter canary 0.63-0.65 on all 3 seeds | `baseline_alignment` (retired: measures canvas bottoms; noisy 0.14-0.36, ranks some defective pages above clean) |
| Word spacing | `word_gap_ratio` (diagnostic measurement) | clean 0.81-0.89 vs minimum-gap layout 0.65 | A pass/fail gap threshold (layout floors gaps at 4px; "run-together" is perceptual) |
| Gross defects (blur, shouted words) | Either judge, or the local VLM | Local VLM 6/6 on blur and shout canaries in both orders | |

The pattern: geometric defects (baseline, spacing, size) are best measured
deterministically; holistic "which looks better" calls need a strong judge;
small local VLMs are good readers and gross-defect detectors but have strong
position bias on subtle page comparisons (they flip with A/B order).

## Datasets and harnesses

- `experiments/cv_bench/word_crops.npz` + `word_labels.json`: 213 raw
  `generate_word()` crops (demo text, a short-word batch, gate words; seeds
  42/137/2718) with intended text and a blind by-eye transcription. 179
  well-formed, 34 malformed.
- `experiments/cv_bench/bench_readers.py trocr_small,vlm`: reader benchmark.
- `experiments/cv_bench/canaries.py OUT CACHE.npz ... [--judge vlm]`: builds
  known-answer page pairs (clean vs shout / blur / jitter / spacing) and
  blind sheets for a Claude judge; with `--judge vlm` scores the local VLM in
  both A/B orders.
- `experiments/replay_cache.py generate|compose`: cache seeded generations,
  compose them with the working tree or any git ref.
- `tests/quick/fixtures/descender_baselines.*`: 81 real crops with
  eye-verified baselines (golden test for `detect_baseline`).

## Local VLM server

`scripts/vlm_server.sh start|stop|status` serves
`cyankiwi/Qwen3.5-9B-AWQ-4bit` (pinned revision) with the vision tower on, at
127.0.0.1:8100, ~14 GB VRAM, about 0.13-0.3 s per word read. It reuses
daydream's vLLM 0.30 install (`REFORGE_VLLM_BIN` to override). The GPU is
shared: do not stop another project's server to make room.
`reforge/evaluate/vlm.py` is the stdlib client; nothing in production
depends on it.

Models that do not fit 20 GB with the vision encoder and KV cache:
Qwen3.5-27B-AWQ (18.7 GiB weights), Qwen3-VL-32B-AWQ, Qwen3.5-35B-A3B-AWQ.

## Reader benchmark (213 crops)

| Reader | s/word | well-formed exact | 1-2 letters | 3-4 | 5+ | malformed read as intended | AUC ok vs malformed |
|--------|-------:|------:|------:|------:|------:|------:|------:|
| TrOCR-small (default) | 0.13 | 0.877 | 0.833 | 0.952 | 0.840 | 0.588 | 0.638 |
| Qwen3.5-9B-AWQ (vlm) | 0.27 | 0.927 | 0.924 | 0.905 | 0.960 | 0.676 | 0.622 |
| Qwen3-VL-8B-FP8 | 0.36 | 0.888 | 0.818 | 0.921 | 0.940 | 0.676 | 0.594 |
| TrOCR-large | 0.09 | 0.436 | 0.470 | 0.444 | 0.380 | 0.147 | 0.542 |

TrOCR-small's short-word failures are hallucinated continuations ("by" read
as "by by" on 3 of 3 seeds, "it" as "if", "me" as "men"). The VLM's
characteristic failure without constraints is script confusion ("gym" read
as Cyrillic "дут"); `read_word` constrains output to Latin characters.

A targeted check ("the writer intended X; is it written letter for
letter?") does not rescue spelling detection: the model's yes/no answer said
"not exact" for 97% of well-formed words, and its own transcription differed
from the target on 53% of malformed vs 17% of well-formed words.

## Page judges (known-answer pairs)

| Judge | shout | blur | jitter | spacing | human pairs |
|-------|------:|-----:|-------:|--------:|------------:|
| Claude (fresh subagent, one order) | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| Qwen3.5-9B, both orders | 3/3 | 3/3 | 0/3 | 0/3 | (1/3, one order) |
| Qwen3-VL-8B, both orders | 0/3 | 3/3 | 0/3 | 0/3 | |

The Claude judge named the affected words for every defect (for example
"'but' raised above 'exactly.', 'was' sunk"). The local models' stated
reasons repeated the rubric regardless of which page they picked.

## Candidate selection: a better reader is a worse selector

Same seeds, so each word's first three candidates were identical in both
arms; only the reader scoring them (and triggering retries) changed. A blind
Claude judge compared the three page pairs word by word and preferred the
TrOCR-selected page each time. The VLM accepted candidates TrOCR rejects
because it recovers the word anyway: "o n" and "per fect" (split), "thi eee?"
(broken), and an overinked "and" picked on every seed. Selection needs a
reader that fails on visual defects; legibility measurement needs one that
does not. Different jobs, different instruments.

## Open directions

- Use the Claude word-sheet rater as the hard-words review between human
  sessions (kappa 0.83 against blind labels).
- An automated stroke-weight outlier check at selection time: the heavy
  "and" was the most visible defect on every VLM-selected page.
- Calibrate the Claude judge on every future human A/B; promote it to a
  pre-push advisory only after agreement holds over ~10 sessions.
