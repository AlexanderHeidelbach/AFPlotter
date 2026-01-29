from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Experiment:
    name: str
    mplstyle: Path
    colors: dict[str, str]
    labels: dict[str, str]

    def apply_style(self):
        import matplotlib.pyplot as plt
        plt.style.use(self.mplstyle)
