from pathlib import Path

from afplotter.experiments.experiment import Experiment
from afplotter.experiments.registry import register

register(
    Experiment(
        name="Generic",
        mplstyle=Path(__file__).parent / "generic.mplstyle",
        colors={"signal": "#bd1f01", "background": "#3f90da"},
        labels={"experiment": "", "status": ""},
    )
)
