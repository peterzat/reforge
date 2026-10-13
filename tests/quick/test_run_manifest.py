"""Run manifest written next to every pipeline output (audit 2026-10-13)."""

import json

import numpy as np
import pytest


@pytest.mark.quick
def test_manifest_records_seed_git_policy_and_metrics(tmp_path):
    from reforge.config import SIZING_POLICY
    from reforge.pipeline import _write_manifest

    out = tmp_path / "result.png"
    path = _write_manifest(str(out), {
        "seed": 42,
        "text": "hello world",
        "quality": {"overall": np.float32(0.75), "ocr_per_word": [1.0, 0.5]},
    })
    assert path == str(tmp_path / "result.json")
    m = json.loads(open(path).read())
    assert m["output"] == "result.png"
    assert m["seed"] == 42
    assert m["sizing_policy"] == SIZING_POLICY
    assert set(m["git"]) == {"commit", "dirty"}
    assert m["quality"]["overall"] == pytest.approx(0.75)
    assert m["quality"]["ocr_per_word"] == [1.0, 0.5]


@pytest.mark.quick
def test_cli_accepts_seed(monkeypatch):
    import sys
    from unittest.mock import patch

    import reforge as _  # noqa: F401  (package import must not need a GPU)
    sys.argv = ["reforge.py", "--text", "hi", "--style", "x.png", "--seed", "7"]
    with patch("reforge.pipeline.run") as run:
        import importlib.util
        spec = importlib.util.spec_from_file_location("reforge_cli", "reforge.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        cli.main()
    assert run.call_args.kwargs["seed"] == 7
