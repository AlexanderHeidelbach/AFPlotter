from afplotter.experiments.experiment import Experiment

EXPERIMENTS: dict[str, Experiment] = {}
_LOADED = False


def register(exp: Experiment):
    if exp.name in EXPERIMENTS:
        raise ValueError(f"Experiment {exp.name} already registered")
    EXPERIMENTS[exp.name] = exp


def _load_experiments():
    global _LOADED
    if _LOADED:
        return

    # Side-effect imports happen HERE, not at module import
    from . import belle2
    from . import i3
    from . import generic

    _LOADED = True


def get(name: str) -> Experiment:
    _load_experiments()

    try:
        return EXPERIMENTS[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown experiment '{name}'. "
            f"Available: {', '.join(EXPERIMENTS)}"
        ) from exc
