"""All constants for the reforge pipeline."""

import string

# Charset: 80 characters supported by DiffusionPen (IAM dataset)
CHARSET = (
    string.ascii_lowercase
    + string.ascii_uppercase
    + string.digits
    + ' _!"#&\'()*+,-./:;?'
)
assert len(CHARSET) == 80

# Style image constraints
NUM_STYLE_WORDS = 5
MIN_WORD_CHARS = 4
STYLE_TENSOR_SHAPE = (1, 3, 64, 256)
STYLE_FEATURE_DIM = 1280

# Generation
MAX_WORD_LENGTH = 10
DEFAULT_CANVAS_HEIGHT = 64
DEFAULT_CANVAS_WIDTH = 256
MAX_CANVAS_WIDTH = 320
WIDTH_MULTIPLE = 16

# DDIM sampling
DEFAULT_DDIM_STEPS = 50
DEFAULT_GUIDANCE_SCALE = 3.0
DEFAULT_NUM_CANDIDATES = 3

# Generation presets (from sweep experiments, 2026-04-01)
# Steps sweep: quality plateaus at 20 steps (0.977 overall, 0.45s/word).
#   Higher steps (30-50) show no improvement but cost 0.6-1.0s/word.
# Guidance sweep: 2.0-4.0 range is the sweet spot. 1.0 tanks quality.
#   3.0 is a safe default; 2.0 works for draft quality.
# Candidates sweep: diminishing returns beyond 3 candidates.
#   1 candidate: 0.8s/word, 3 candidates: 1.5s/word.
PRESET_DRAFT = {"steps": 10, "guidance_scale": 2.0, "candidates": 1}
PRESET_FAST = {"steps": 20, "guidance_scale": 3.0, "candidates": 1}
PRESET_QUALITY = {"steps": 50, "guidance_scale": 3.0, "candidates": 3}
PRESETS = {"draft": PRESET_DRAFT, "fast": PRESET_FAST, "quality": PRESET_QUALITY}

# VAE scale factor
VAE_SCALE_FACTOR = 0.18215

# Font normalization
SHORT_WORD_HEIGHT_TARGET = 26  # pixels, for 1-2 char words
# A1 lesson: these thresholds must not be tightened beyond 1.10/0.88.
# Tightening to 1.05/0.93 achieved word_height_ratio 1.00 but distorted
# letterforms (over-normalization, "The" -> "Tle"). The honest 0.91 at
# 1.10/0.88 produces visually better output.
HEIGHT_OUTLIER_THRESHOLD = 1.10  # scale down if > 110% of median
HEIGHT_UNDERSIZE_THRESHOLD = 0.88  # scale up if < 88% of median

# Second-pass height harmonization (E2): applied after font normalization
# where variance is already reduced, so tighter thresholds are safe.
HEIGHT_OUTLIER_THRESHOLD_PASS2 = 1.05  # scale down if > 105% of median
HEIGHT_UNDERSIZE_THRESHOLD_PASS2 = 0.93  # scale up if < 93% of median

# Stroke weight harmonization
STROKE_WEIGHT_SHIFT_STRENGTH = 0.92  # blend factor toward global median (B3: increased from 0.85)

# Gray-box defense thresholds
BACKGROUND_PERCENTILE = 90
INK_THRESHOLD_RATIO = 0.70
BODY_ZONE_TOP = 0.20
BODY_ZONE_BOTTOM = 0.80
BODY_ZONE_INK_THRESHOLD = 0.05
CLUSTER_GAP_PX = 20
COMPOSITOR_INK_THRESHOLD = 200
HALO_DILATE_RADIUS = 4
HALO_GRAY_THRESHOLD = 230

# Syllable splitting
MIN_CHUNK_CHARS = 4
CONSONANT_PENALTY = -3
CC_BOUNDARY_BONUS = 2
CV_BOUNDARY_BONUS = 1

# Baseline detection
BASELINE_DENSITY_DROP = 0.15
BASELINE_BODY_DENSITY = 0.35
BASELINE_MIN_DIP_RATIO = 0.15

# Composition
LINE_SPACING = 12
PARAGRAPH_SPACING = 30
PARAGRAPH_INDENT = 40
WORD_SPACING = 6  # reduced from 16; human eval found 8 "still over spaced", 16 much too wide
PAGE_MARGIN = 30
DEFAULT_PAGE_WIDTH = 800

# Dynamic page sizing
MIN_PAGE_WIDTH = 300
MAX_PAGE_WIDTH = 1200
TARGET_WORDS_PER_LINE = 7.0  # target words per line (compensates for variable word widths)
MARGIN_H_RATIO = 0.06     # left/right margin as fraction of page width (5-8% range)
MARGIN_V_RATIO = 0.04     # top/bottom margin as fraction of page height (3-5% range)

# Overlap blending for chunk stitching
STITCH_OVERLAP_PX = 8

# OCR-aware candidate selection (A1): weight for OCR accuracy in combined score.
# Combined = (1 - OCR_SELECTION_WEIGHT) * image_quality + OCR_SELECTION_WEIGHT * ocr_accuracy.
# 0.4 gives OCR enough influence to override small image quality advantages
# while still penalizing candidates with gray boxes or other visual defects.
OCR_SELECTION_WEIGHT = 0.4

# Primary metrics for the quality regression gate (spec 2026-04-10 B1).
# Selected by Spearman correlation with human composition ratings across
# reviews/human/*.json. Bar: positive rho, |rho| >= 0.2, p < 0.3 (scipy two-
# sided). See docs/metric_correlation.md for the full analysis and rationale.
#
# Only these metrics gate the regression test. All other TRACKED_METRICS are
# diagnostics: logged to the ledger and printed on regression, but not fatal.
# The existing ocr_min floor (0.3) still gates independently as a readability
# guardrail; it is not a correlation-derived primary metric.
#
# The selection is deliberately narrow. Only one metric cleared the bar at
# N=16: `height_outlier_score` (rho = +0.302, p = 0.255). `baseline_alignment`
# was a near-miss (rho = +0.273, p = 0.307) and is tracked as a diagnostic.
# This narrowness is itself a finding: the current CV metric set barely
# contains any signal that positively tracks human composition rating on this
# dataset. Fixing that is a future spec, not this one.
PRIMARY_METRICS = [
    "height_outlier_score",
]

# Quality scoring weights (per-word candidate selection in quality/score.py)
QUALITY_WEIGHTS = {
    "background": 0.20,
    "ink_density": 0.15,
    "edge_sharpness": 0.15,
    "height_consistency": 0.25,
    "contrast": 0.25,
}

# Overall quality score structure (evaluate/visual.py)
# Gate metrics: binary pass/fail, cap overall if failed (not weighted)
QUALITY_GATES = {
    "gray_boxes": {"threshold": 1.0, "cap": 0.30},       # must have no artifacts
    "ink_contrast": {"threshold": 0.70, "cap": 0.40},     # must have decent contrast
    "background_cleanliness": {"threshold": 0.80, "cap": 0.40},  # must be clean
}

# Continuous metrics: weighted into overall score (must sum to 1.0)
# Style fidelity added after C2 variance test showed std=0 across 5 runs.
# Reduced baseline_alignment (saturates at 1.0) and composition_score to
# make room. OCR and stroke consistency remain the dominant signals.
QUALITY_CONTINUOUS_WEIGHTS = {
    "stroke_weight_consistency": 0.20,
    "word_height_ratio": 0.15,
    "composition_score": 0.15,
    "height_outlier_score": 0.15,  # derived from height_outlier_ratio
    "baseline_alignment": 0.05,
    "ocr_accuracy": 0.20,          # redistributed when unavailable
    "style_fidelity": 0.10,        # redistributed when unavailable
}

# Model paths on HuggingFace
HF_REPO_ID = "konnik/DiffusionPen"
UNET_WEIGHT_PATH = "diffusionpen_iam_model_path/models/ema_ckpt.pt"
STYLE_ENCODER_TRIPLET_PATH = "style_models/iam_style_diffusionpen_triplet.pth"
STYLE_ENCODER_CLASS_PATH = "style_models/iam_style_diffusionpen_class.pth"
SD_MODEL_ID = "stable-diffusion-v1-5/stable-diffusion-v1-5"
CANINE_MODEL_ID = "google/canine-c"

# Cache
CACHE_DIR = "~/.cache/reforge"

# UNet constructor args
UNET_IMAGE_SIZE = (64, 256)
UNET_IN_CHANNELS = 4
UNET_MODEL_CHANNELS = 320
UNET_OUT_CHANNELS = 4
UNET_NUM_RES_BLOCKS = 1
UNET_ATTENTION_RESOLUTIONS = (1, 1)
UNET_CHANNEL_MULT = (1, 1)
UNET_NUM_HEADS = 4
UNET_NUM_CLASSES = 339
UNET_CONTEXT_DIM = 320
UNET_VOCAB_SIZE = 79
