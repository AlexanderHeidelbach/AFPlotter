from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Experiment:
    """
    Describes a plotting style tied to a specific experiment.

    :param name: Unique experiment identifier, e.g. "BelleII".
    :param mplstyle: Path to the matplotlib style file for this experiment.
    :param colors: Named color roles (e.g. "signal", "background").
    :param labels: Named text roles (e.g. "experiment", "status").
    """

    name: str
    mplstyle: Path
    colors: dict[str, str]
    labels: dict[str, str]

    def apply_style(self) -> None:
        """Apply this experiment's matplotlib style globally."""
        import matplotlib.pyplot as plt

        plt.style.use(self.mplstyle)
