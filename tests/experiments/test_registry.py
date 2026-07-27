import sys

import pytest

from afplotter.experiments.experiment import Experiment
from afplotter.experiments import registry


def _dummy_experiment(name: str) -> Experiment:
    from pathlib import Path
    return Experiment(name=name, mplstyle=Path("dummy.mplstyle"), colors={}, labels={})


def _cleanup_experiments():
    """Explicitly clean up experiment modules and registry state."""
    registry.EXPERIMENTS.clear()
    registry._LOADED = False
    for module_name in list(sys.modules.keys()):
        if "afplotter.experiments" in module_name and any(
            exp in module_name for exp in ("belle2", "generic", "icecube")
        ):
            del sys.modules[module_name]


def test_register_and_get():
    _cleanup_experiments()
    registry._LOADED = True  # prevent _load_experiments from re-registering built-ins
    exp = _dummy_experiment("TestExp")
    registry.register(exp)
    assert registry.get("TestExp") is exp


def test_register_duplicate_raises():
    _cleanup_experiments()
    registry._LOADED = True
    exp = _dummy_experiment("TestExp")
    registry.register(exp)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(exp)


def test_get_unknown_raises():
    _cleanup_experiments()
    registry._LOADED = True
    with pytest.raises(ValueError, match="Unknown experiment"):
        registry.get("NoSuchExperiment")


def test_builtin_experiments_are_discoverable():
    _cleanup_experiments()
    assert registry.get("BelleII").name == "BelleII"
    assert registry.get("Generic").name == "Generic"
    assert registry.get("IceCube").name == "IceCube"
