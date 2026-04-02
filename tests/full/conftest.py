"""Shared fixtures for full e2e tests."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--update-demo-baseline", action="store_true", default=False,
        help="Regenerate demo_baseline.json unconditionally",
    )
    parser.addoption(
        "--update-demo-reference", action="store_true", default=False,
        help="Regenerate demo_reference.png unconditionally",
    )
