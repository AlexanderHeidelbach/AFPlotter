from pathlib import Path

import pytest

from afplotter.experiments import registry
from afplotter.experiments.experiment import Experiment


def _dummy_experiment(name: str) -> Experiment:
    return Experiment(name=name, mplstyle=Path("dummy.mplstyle"), colors={}, labels={})


def test_register_and_get():
    registry._LOADED = True  # prevent _load_experiments from re-registering built-ins
    exp = _dummy_experiment("TestExp")
    registry.register(exp)
    assert registry.get("TestExp") is exp


def test_register_duplicate_raises():
    registry._LOADED = True
    exp = _dummy_experiment("TestExp")
    registry.register(exp)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(exp)


def test_get_unknown_raises():
    registry._LOADED = True
    with pytest.raises(ValueError, match="Unknown experiment"):
        registry.get("NoSuchExperiment")


def test_builtin_experiments_are_discoverable():
    assert registry.get("BelleII").name == "BelleII"
    assert registry.get("Generic").name == "Generic"
