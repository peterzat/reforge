"""reforge.evaluate.vlm and the REFORGE_OCR_BACKEND switch (no server needed)."""

import json

import numpy as np
import pytest


@pytest.mark.quick
def test_available_is_false_without_a_server(monkeypatch):
    from reforge.evaluate import vlm
    monkeypatch.setenv("REFORGE_VLM_URL", "http://127.0.0.1:9/v1")  # discard port
    assert vlm.available(timeout=0.5) is False


@pytest.mark.quick
def test_read_word_sends_constrained_request_and_parses_json(monkeypatch):
    from reforge.evaluate import vlm
    sent = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": '{"text": "by"}'}}]}).encode()

    def fake_urlopen(req, timeout=None):
        sent["body"] = json.loads(req.data)
        return _Resp()

    monkeypatch.setattr(vlm.urllib.request, "urlopen", fake_urlopen)
    img = np.full((64, 128), 255, dtype=np.uint8)
    assert vlm.read_word(img) == "by"
    body = sent["body"]
    assert body["temperature"] == 0.0
    pattern = body["response_format"]["json_schema"]["schema"]["properties"]["text"]["pattern"]
    assert pattern.startswith("^[A-Za-z")
    assert body["messages"][0]["content"][0]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.quick
def test_ocr_backend_switch(monkeypatch):
    from reforge.evaluate import ocr, vlm
    monkeypatch.setattr(vlm, "read_word", lambda img: "by")
    monkeypatch.setenv("REFORGE_OCR_BACKEND", "vlm")
    img = np.full((64, 128), 255, dtype=np.uint8)
    assert ocr.ocr_read(img) == "by"
    assert ocr.ocr_accuracy(img, "by") == 1.0
