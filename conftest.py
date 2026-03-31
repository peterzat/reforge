"""Root conftest: test tier DAG.

Running a higher tier automatically includes lower tiers:
  pytest tests/medium/  -> also runs tests/quick/
  pytest tests/full/    -> also runs tests/quick/ and tests/medium/
  pytest tests/quick/   -> only quick tests

Direct marker selection (e.g. -m quick) is unaffected.
"""

import pathlib

ROOT = pathlib.Path(__file__).parent

TIER_INCLUDES = {
    "tests/full": ["tests/quick", "tests/medium"],
    "tests/medium": ["tests/quick"],
}


def pytest_collect_file(parent, file_path):
    """No-op; collection is handled by pytest_configure."""


def pytest_configure(config):
    """When a tier directory is targeted, add lower-tier directories to args."""
    # Only act on explicit path arguments, not bare "pytest" invocations
    raw_args = config.invocation_params.args
    if not raw_args:
        return

    # Resolve which tier directories are targeted
    extra = []
    for tier_dir, includes in TIER_INCLUDES.items():
        tier_path = str(ROOT / tier_dir)
        for arg in raw_args:
            if tier_path in str(pathlib.Path(arg).resolve()) or str(arg).rstrip("/") == tier_dir:
                for inc in includes:
                    inc_path = str(ROOT / inc)
                    # Don't add if already present
                    if not any(inc_path in str(pathlib.Path(a).resolve()) or str(a).rstrip("/") == inc for a in raw_args):
                        extra.append(inc_path)
                break

    if extra:
        # Append extra directories to the args that pytest will collect
        config.args.extend(extra)
