from typing import Optional
import warnings

from afplotter.experiments.experiment import Experiment
from afplotter.experiments.registry import get as _get_experiment

_CURRENT_EXPERIMENT: Optional[Experiment] = None
_WARNED_DEFAULT = False


def set_experiment(name: Optional[str] = None) -> Experiment:
    global _CURRENT_EXPERIMENT

    if name is None:
        _CURRENT_EXPERIMENT = _get_experiment("Generic")
    else:
        _CURRENT_EXPERIMENT = _get_experiment(name)

    _CURRENT_EXPERIMENT.apply_style()
    return _CURRENT_EXPERIMENT


def get_experiment() -> Experiment:
    global _CURRENT_EXPERIMENT, _WARNED_DEFAULT

    if _CURRENT_EXPERIMENT is None:
        if not _WARNED_DEFAULT:
            warnings.warn(
                "No experiment set. Falling back to 'Generic'. "
                "Call set_experiment(...) to select a specific experiment.",
                RuntimeWarning,
                stacklevel=2,
            )
            _WARNED_DEFAULT = True

        _CURRENT_EXPERIMENT = _get_experiment("Generic")
        _CURRENT_EXPERIMENT.apply_style()

    return _CURRENT_EXPERIMENT
