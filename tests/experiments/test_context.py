import sys
import warnings

import pytest

from afplotter.experiments import context, registry


def _cleanup_experiments():
    """Explicitly clean up experiment modules and registry state."""
    registry.EXPERIMENTS.clear()
    registry._LOADED = False
    context._CURRENT_EXPERIMENT = None
    context._WARNED_DEFAULT = False
    for module_name in list(sys.modules.keys()):
        if "afplotter.experiments" in module_name and any(
            exp in module_name for exp in ("belle2", "generic", "icecube")
        ):
            del sys.modules[module_name]


def test_set_experiment_by_name():
    _cleanup_experiments()
    exp = context.set_experiment("BelleII")
    assert exp.name == "BelleII"
    assert context.get_experiment().name == "BelleII"


def test_set_experiment_none_defaults_to_generic():
    _cleanup_experiments()
    exp = context.set_experiment(None)
    assert exp.name == "Generic"


def test_get_experiment_without_set_warns_and_falls_back():
    _cleanup_experiments()
    with pytest.warns(RuntimeWarning, match="No experiment set"):
        exp = context.get_experiment()
    assert exp.name == "Generic"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        # second call must not warn again
        context.get_experiment()
