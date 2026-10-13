"""Client for a local vision-language model behind an OpenAI-compatible API.

Used as an optional development and evaluation instrument (see
docs/cv-instruments.md); production generation never depends on it. Standard
library only, so reforge gains no runtime dependency. Start a server with
scripts/vlm_server.sh; point elsewhere with REFORGE_VLM_URL and
REFORGE_VLM_MODEL.

Measured on 213 labeled word crops (2026-10-13), Qwen3.5-9B-AWQ reads
well-formed words better than TrOCR-small (93-94% exact vs 84%; 92-94% vs
83% on 1-2 letter words) but "corrects" most misspelled renderings to the
intended word, so it measures legibility, not letter-level fidelity.
"""

from __future__ import annotations

import base64
import io
import json
import os
import urllib.error
import urllib.request

import numpy as np
from PIL import Image

DEFAULT_URL = "http://127.0.0.1:8100/v1"
DEFAULT_MODEL = "qwen-vl"

# Latin letters, digits and the reforge charset's word punctuation. vLLM's
# structured decoding enforces it, which removes the Cyrillic look-alike
# readings ("дут" for "gym") an unconstrained VLM produces.
_WORD_PATTERN = "^[A-Za-z0-9'.,;:!?\"()&#*+/_-]{1,32}$"

_READ_PROMPT = (
    "This image shows one handwritten English word in Latin letters, possibly "
    "followed by punctuation. Transcribe exactly the letters that are written, "
    "even if the word is misspelled. Do not correct spelling. "
    'Answer as JSON {"text": ...}.'
)


def _base_url() -> str:
    return os.environ.get("REFORGE_VLM_URL", DEFAULT_URL).rstrip("/")


def _model() -> str:
    return os.environ.get("REFORGE_VLM_MODEL", DEFAULT_MODEL)


def available(timeout: float = 2.0) -> bool:
    """True when a server answers at REFORGE_VLM_URL."""
    try:
        with urllib.request.urlopen(f"{_base_url()}/models", timeout=timeout):
            return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _png_data_url(img: np.ndarray | Image.Image) -> str:
    if isinstance(img, np.ndarray):
        img = Image.fromarray(img)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def ask(
    prompt: str,
    images: list,
    schema: dict | None = None,
    max_tokens: int = 64,
    timeout: float = 120.0,
) -> str:
    """Send images plus a prompt; return the model's text (temperature 0)."""
    content = [{"type": "image_url", "image_url": {"url": _png_data_url(im)}} for im in images]
    content.append({"type": "text", "text": prompt})
    body = {
        "model": _model(),
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }
    if schema is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "out", "schema": schema},
        }
    req = urllib.request.Request(
        f"{_base_url()}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        out = json.load(resp)
    return out["choices"][0]["message"]["content"].strip()


def read_word(img: np.ndarray) -> str:
    """Transcribe one handwritten word image, Latin characters only."""
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string", "pattern": _WORD_PATTERN}},
        "required": ["text"],
    }
    return json.loads(ask(_READ_PROMPT, [img], schema=schema, max_tokens=40))["text"]
