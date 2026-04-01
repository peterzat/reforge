"""Postprocessing diagnostic instrument.

Traces a word image through each postprocessing layer, reporting ink extent
changes, column removal counts, and OCR accuracy at each stage. Used for
root-cause analysis of character clipping and regression testing.
"""

import numpy as np


def _ink_columns(img: np.ndarray, threshold: int = 200) -> np.ndarray:
    """Return boolean array: True for columns containing ink pixels."""
    return np.any(img < threshold, axis=0)


def _edge_ink_extent(img: np.ndarray, threshold: int = 200) -> dict:
    """Measure how close ink extends to left/right canvas edges."""
    ink_cols = _ink_columns(img, threshold)
    if not np.any(ink_cols):
        return {"left_gap": img.shape[1], "right_gap": img.shape[1],
                "ink_width": 0, "total_width": img.shape[1]}
    first_ink = int(np.argmax(ink_cols))
    last_ink = len(ink_cols) - 1 - int(np.argmax(ink_cols[::-1]))
    return {
        "left_gap": first_ink,
        "right_gap": img.shape[1] - 1 - last_ink,
        "ink_width": last_ink - first_ink + 1,
        "total_width": img.shape[1],
    }


def _count_ink_columns_in_region(img: np.ndarray, start_frac: float,
                                  end_frac: float, threshold: int = 200) -> int:
    """Count columns with ink in a fractional region of the image."""
    w = img.shape[1]
    start = int(w * start_frac)
    end = int(w * end_frac)
    region = img[:, start:end]
    return int(np.sum(np.any(region < threshold, axis=0)))


def diagnose_postprocessing(
    raw_img: np.ndarray,
    target_word: str | None = None,
) -> dict:
    """Trace a raw VAE output through each postprocessing layer.

    Args:
        raw_img: Grayscale uint8 word image directly from VAE decode
            (before any postprocessing).
        target_word: The intended text, for OCR accuracy measurement.

    Returns:
        Dict with per-layer diagnostics:
        - "raw": edge extent and OCR before any processing
        - "layer2_body_zone": after body-zone noise removal
        - "layer3_cluster": after isolated-cluster filter
        - "layer3b_gray_cleanup": after word-level gray cleanup
        - Each entry has: edge_extent, left25_ink_cols, right25_ink_cols,
          cols_removed_left25, cols_removed_right25, ocr_accuracy (if target given)
    """
    from reforge.model.generator import (
        adaptive_background_estimate,
        apply_ink_threshold,
        body_zone_noise_removal,
        isolated_cluster_filter,
        _word_gray_cleanup,
    )

    ocr_fn = _get_ocr_fn()
    stages = {}

    def _measure(img, stage_name, prev_stage_name=None):
        entry = {
            "edge_extent": _edge_ink_extent(img),
            "left25_ink_cols": _count_ink_columns_in_region(img, 0.0, 0.25),
            "right25_ink_cols": _count_ink_columns_in_region(img, 0.75, 1.0),
        }
        if prev_stage_name and prev_stage_name in stages:
            prev = stages[prev_stage_name]
            entry["cols_removed_left25"] = prev["left25_ink_cols"] - entry["left25_ink_cols"]
            entry["cols_removed_right25"] = prev["right25_ink_cols"] - entry["right25_ink_cols"]
        else:
            entry["cols_removed_left25"] = 0
            entry["cols_removed_right25"] = 0

        if target_word and ocr_fn:
            entry["ocr_accuracy"] = ocr_fn(img, target_word)
        stages[stage_name] = entry
        return entry

    # Raw VAE output
    _measure(raw_img, "raw")

    # Layer 1: background estimation (creates ink mask, doesn't modify image)
    bg_estimate = adaptive_background_estimate(raw_img)
    ink_mask = apply_ink_threshold(raw_img, bg_estimate)

    # Layer 2: body-zone noise removal
    img2 = body_zone_noise_removal(raw_img, ink_mask)
    _measure(img2, "layer2_body_zone", "raw")

    # Recompute ink mask after layer 2
    ink_mask2 = apply_ink_threshold(img2, bg_estimate)

    # Layer 3: isolated cluster filter
    img3 = isolated_cluster_filter(img2, ink_mask2)
    _measure(img3, "layer3_cluster", "layer2_body_zone")

    # Layer 3b: word-level gray cleanup
    img3b = _word_gray_cleanup(img3)
    _measure(img3b, "layer3b_gray_cleanup", "layer3_cluster")

    # Summary
    raw_extent = stages["raw"]["edge_extent"]
    final_extent = stages["layer3b_gray_cleanup"]["edge_extent"]
    stages["summary"] = {
        "target_word": target_word,
        "raw_ink_width": raw_extent["ink_width"],
        "final_ink_width": final_extent["ink_width"],
        "ink_width_lost": raw_extent["ink_width"] - final_extent["ink_width"],
        "raw_left_gap": raw_extent["left_gap"],
        "raw_right_gap": raw_extent["right_gap"],
        "final_left_gap": final_extent["left_gap"],
        "final_right_gap": final_extent["right_gap"],
        "ink_near_left_edge": raw_extent["left_gap"] < 5,
        "ink_near_right_edge": raw_extent["right_gap"] < 5,
        "total_cols_removed_left25": sum(
            stages[s].get("cols_removed_left25", 0)
            for s in ("layer2_body_zone", "layer3_cluster", "layer3b_gray_cleanup")
        ),
        "total_cols_removed_right25": sum(
            stages[s].get("cols_removed_right25", 0)
            for s in ("layer2_body_zone", "layer3_cluster", "layer3b_gray_cleanup")
        ),
    }
    if target_word and ocr_fn:
        stages["summary"]["ocr_before"] = stages["raw"].get("ocr_accuracy")
        stages["summary"]["ocr_after"] = stages["layer3b_gray_cleanup"].get("ocr_accuracy")

    return stages


def _get_ocr_fn():
    """Return ocr_accuracy function if available, else None."""
    try:
        from reforge.evaluate.ocr import ocr_accuracy
        return ocr_accuracy
    except ImportError:
        return None


def format_diagnostic(diag: dict) -> str:
    """Format diagnostic results as a human-readable string."""
    lines = []
    s = diag.get("summary", {})
    word = s.get("target_word", "?")
    lines.append(f"Word: {word}")
    lines.append(f"  Raw ink width: {s.get('raw_ink_width', '?')} px")
    lines.append(f"  Final ink width: {s.get('final_ink_width', '?')} px")
    lines.append(f"  Ink width lost: {s.get('ink_width_lost', '?')} px")
    lines.append(f"  Raw edge gaps: left={s.get('raw_left_gap', '?')} right={s.get('raw_right_gap', '?')}")
    lines.append(f"  Ink near left edge (<5px): {s.get('ink_near_left_edge', '?')}")
    lines.append(f"  Ink near right edge (<5px): {s.get('ink_near_right_edge', '?')}")
    lines.append(f"  Total cols removed left 25%: {s.get('total_cols_removed_left25', '?')}")
    lines.append(f"  Total cols removed right 25%: {s.get('total_cols_removed_right25', '?')}")

    if "ocr_before" in s:
        lines.append(f"  OCR before postprocess: {s['ocr_before']:.2f}")
        lines.append(f"  OCR after postprocess: {s['ocr_after']:.2f}")

    for stage in ("raw", "layer2_body_zone", "layer3_cluster", "layer3b_gray_cleanup"):
        if stage not in diag:
            continue
        d = diag[stage]
        ext = d["edge_extent"]
        lines.append(f"  {stage}:")
        lines.append(f"    ink cols left25={d['left25_ink_cols']} right25={d['right25_ink_cols']}")
        lines.append(f"    removed left25={d.get('cols_removed_left25', 0)} right25={d.get('cols_removed_right25', 0)}")
        lines.append(f"    edge gaps: left={ext['left_gap']} right={ext['right_gap']}")
        if "ocr_accuracy" in d:
            lines.append(f"    ocr={d['ocr_accuracy']:.2f}")

    return "\n".join(lines)
