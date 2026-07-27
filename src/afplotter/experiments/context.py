import warnings
from typing import Optional

from afplotter.experiments.experiment import Experiment
from afplotter.experiments.registry import get as _get_experiment

_CURRENT_EXPERIMENT: Optional[Experiment] = None
_WARNED_DEFAULT = False


def set_experiment(name: Optional[str] = None) -> Experiment:
    """
    Select and apply an experiment's plotting style.

    :param name: Experiment name, e.g. "BelleII". If None, selects "Generic".
    :return: The now-current Experiment.
    """
    global _CURRENT_EXPERIMENT

    _CURRENT_EXPERIMENT = _get_experiment("Generic") if name is None else _get_experiment(name)
    _CURRENT_EXPERIMENT.apply_style()
    return _CURRENT_EXPERIMENT


def get_experiment() -> Experiment:
    """
    Get the current experiment, defaulting to "Generic" (with a one-time warning)
    if none has been explicitly set.

    :return: The current Experiment.
    """
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
