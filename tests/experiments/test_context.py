import warnings

import pytest

from afplotter.experiments import context


def test_set_experiment_by_name():
    exp = context.set_experiment("BelleII")
    assert exp.name == "BelleII"
    assert context.get_experiment().name == "BelleII"


def test_set_experiment_none_defaults_to_generic():
    exp = context.set_experiment(None)
    assert exp.name == "Generic"


def test_get_experiment_without_set_warns_and_falls_back():
    with pytest.warns(RuntimeWarning, match="No experiment set"):
        exp = context.get_experiment()
    assert exp.name == "Generic"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        # second call must not warn again
        context.get_experiment()
