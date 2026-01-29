from pathlib import Path
from afplotter.experiments.experiment import Experiment
from afplotter.experiments.registry import register

register(
    Experiment(
        name="IceCube",
        mplstyle=Path(__file__).parent / "icecube.mplstyle",
        colors={
            "signal": "#E41A1C",
            "background": "#377EB8",
        },
        labels={
            "experiment": "Ice Cube",
            "status": "(Own Work)",
        },
    )
)
