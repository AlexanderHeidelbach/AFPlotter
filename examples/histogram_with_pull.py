# examples/histogram_with_pull.py
"""
Mirrors a real fit-result plot: a stacked histogram with signal/background
model curves and a pull panel, styled with BelleII settings and the default
Petroff color cycle (signal in the reserved SIGNAL_COLOR red).

Run: python examples/histogram_with_pull.py
"""

import os

import numpy as np

from afplotter import (
    Histogram,
    HistogramEntry,
    HistogramPlot,
    HistogramPlotter,
    HistogramVariable,
    SIGNAL_COLOR,
    PetroffColors,
    set_experiment,
)
from _synthetic_data import make_signal_background

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def main() -> None:
    set_experiment("BelleII")
    n_signal, n_background = 600, 1200
    x_min, x_max = 0.0, 10.0
    data = make_signal_background(n_signal=n_signal, n_background=n_background, seed=3)

    hist = Histogram()
    hist.binning = np.linspace(x_min, x_max, 41)
    # Colors are all-or-nothing per stack: set every entry or none of them (in
    # which case the Petroff cycle supplies them in order).
    hist.add_entry(HistogramEntry(name="signal", latex_name="Signal", array=data["signal"], color=SIGNAL_COLOR))
    hist.add_entry(
        HistogramEntry(name="background", latex_name="Background", array=data["background"], color=PetroffColors.blue)
    )

    histplot = HistogramPlot(hist)
    histplot.stacked = True
    histplot.uncertainty = True

    variable = HistogramVariable("$M_{\\gamma\\gamma}$", "GeV/c$^2$")
    plotter = HistogramPlotter(histplot, variable)
    plotter.set_matplotlibrc_params(18)
    plotter.watermark = "(Own Work)"
    plotter.luminosity_value = 62.8

    def model(x: np.ndarray) -> np.ndarray:
        # dN/dx for the Gaussian signal plus flat background that generated
        # `data`, so the overlay (added with density=True, i.e. "already an
        # absolute dN/dx curve") actually tracks the histogram once
        # multiplied by the bin width below.
        signal = n_signal / (0.8 * np.sqrt(2 * np.pi)) * np.exp(-0.5 * ((x - 5.0) / 0.8) ** 2)
        background = n_background / (x_max - x_min)
        return signal + background

    plotter.add_function(model, binwidth=True, label="Model", color=PetroffColors.purple, lw=2)
    plotter.add_pull(model, binwidth=True, color=PetroffColors.purple, label="Model", lw=2, max_sigma=5.0)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    plotter.savedir = OUTPUT_DIR
    plotter.savename = "histogram_with_pull"
    plotter.saveformat = "png"
    plotter.plot(save=True)
    print("Saved to", plotter.savepath or plotter._get_savestring())


if __name__ == "__main__":
    main()
