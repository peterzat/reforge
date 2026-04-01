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
SHORT_WORD_HEIGHT_TARGET = 32  # pixels, for 1-3 char words
LONG_WORD_AREA_TARGET = 550    # px^2 per char, for 4+ char words
HEIGHT_OUTLIER_THRESHOLD = 1.05  # scale down if > 105% of median
HEIGHT_UNDERSIZE_THRESHOLD = 0.93  # scale up if < 93% of median

# Stroke weight harmonization
STROKE_WEIGHT_SHIFT_STRENGTH = 0.85  # blend factor toward global median

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
WORD_SPACING = 16
PAGE_MARGIN = 30
DEFAULT_PAGE_WIDTH = 800

# Dynamic page sizing
MIN_PAGE_WIDTH = 300
MAX_PAGE_WIDTH = 1200
TARGET_ASPECT_MIN = 0.7   # minimum width:height ratio
TARGET_ASPECT_MAX = 1.3   # maximum width:height ratio
MARGIN_H_RATIO = 0.06     # left/right margin as fraction of page width (5-8% range)
MARGIN_V_RATIO = 0.04     # top/bottom margin as fraction of page height (3-5% range)

# Overlap blending for chunk stitching
STITCH_OVERLAP_PX = 8

# Quality scoring weights
QUALITY_WEIGHTS = {
    "background": 0.20,
    "ink_density": 0.15,
    "edge_sharpness": 0.15,
    "height_consistency": 0.25,
    "contrast": 0.25,
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
