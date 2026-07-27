from typing import Dict

from afplotter.experiments.experiment import Experiment

EXPERIMENTS: Dict[str, Experiment] = {}
_LOADED = False


def register(exp: Experiment) -> None:
    """
    Register a new experiment.

    :param exp: The experiment to register.
    :raises ValueError: If an experiment with the same name is already registered.
    :return: None
    """
    if exp.name in EXPERIMENTS:
        raise ValueError(f"Experiment {exp.name} already registered")
    EXPERIMENTS[exp.name] = exp


def _load_experiments() -> None:
    """Import the built-in experiment modules once, registering them as a side effect."""
    global _LOADED
    if _LOADED:
        return

    # Import submodules to trigger their registration logic
    import afplotter.experiments.belle2  # noqa: F401
    import afplotter.experiments.icecube  # noqa: F401
    import afplotter.experiments.generic  # noqa: F401

    _LOADED = True


def get(name: str) -> Experiment:
    """
    Look up a registered experiment by name.

    :param name: Experiment name, e.g. "BelleII".
    :raises ValueError: If no experiment with that name is registered.
    :return: The matching Experiment.
    """
    _load_experiments()

    try:
        return EXPERIMENTS[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown experiment '{name}'. Available: {', '.join(EXPERIMENTS)}"
        ) from exc
