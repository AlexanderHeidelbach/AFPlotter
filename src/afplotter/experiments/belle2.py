from pathlib import Path

from afplotter.experiments.experiment import Experiment
from afplotter.experiments.registry import register

register(
    Experiment(
        name="BelleII",
        mplstyle=Path(__file__).parent / "belle2_modern.mplstyle",
        colors={"signal": "#bd1f01", "background": "#3f90da"},
        labels={"experiment": "Belle II", "status": "Simulation (Own Work)"},
    )
)
