import sys

import pytest

from afplotter.experiments import context, registry


def _reset_experiment_state():
    registry.EXPERIMENTS.clear()
    registry._LOADED = False
    context._CURRENT_EXPERIMENT = None
    context._WARNED_DEFAULT = False
    for module_name in list(sys.modules.keys()):
        if "afplotter.experiments" in module_name and any(
            exp in module_name for exp in ("belle2", "generic")
        ):
            del sys.modules[module_name]


@pytest.fixture(autouse=True)
def clean_experiment_registry():
    """Reset the module-global experiment registry/context before and after each test.

    Without this, tests that register or select experiments leak state into
    whichever test runs next, so results depend on run order (full-suite vs.
    `pytest -k`, `--last-failed`, or xdist).
    """
    _reset_experiment_state()
    yield
    _reset_experiment_state()
