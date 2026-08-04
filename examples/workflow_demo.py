# examples/workflow_demo.py
"""
Three-step version of the actual AFPlotter workflow: a user asks for a plot,
then asks for changes across follow-up turns. Mirrors the escalation path in
.claude/skills/afplotter/SKILL.md -- convenience layer first, engine once the
request needs a pull panel, then a palette switch.

Writes its output to docs/img/workflow/ (committed, unlike examples/output/)
since these images are embedded in the README.

Run: python examples/workflow_demo.py
"""

import os

import numpy as np

from afplotter import (
    Histogram,
    HistogramEntry,
    HistogramPlot,
    HistogramPlotter,
    HistogramVariable,
    PetroffColors,
    get_palette,
    plot_histogram,
    set_experiment,
    set_palette,
)
from afplotter.baseplotter import set_matplotlibrc_params
from _synthetic_data import make_signal_background

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(REPO_ROOT, "docs", "img", "workflow")

N_SIGNAL, N_BACKGROUND = 600, 1200
X_MIN, X_MAX = 0.0, 10.0


def step1_convenience(data: dict[str, np.ndarray]) -> None:
    """Prompt: "Plot signal vs background for pt" -- convenience layer."""
    plot_histogram(
        entries=data,
        bins=(X_MIN, X_MAX, 41),
        xlabel="$p_T$",
        unit="GeV",
        stacked=False,
        save=os.path.join(OUTPUT_DIR, "01-histogram.png"),
    )


def _model(x: np.ndarray) -> np.ndarray:
    """dN/dx for the Gaussian signal plus flat background that generated the data."""
    signal = N_SIGNAL / (0.8 * np.sqrt(2 * np.pi)) * np.exp(-0.5 * ((x - 5.0) / 0.8) ** 2)
    background = N_BACKGROUND / (X_MAX - X_MIN)
    return signal + background


def _build_stacked_pull_plotter(data: dict[str, np.ndarray]) -> HistogramPlotter:
    """
    Shared by steps 2 and 3: builds the stacked+pull plot using whichever
    palette is active at call time, so switching the palette before calling
    this is the entire diff between "stack + pull panel" and "switch to KIT
    colors".
    """
    palette = get_palette()

    hist = Histogram()
    hist.binning = np.linspace(X_MIN, X_MAX, 41)
    hist.add_entry(
        # background[1] (not [0]): amber for Petroff, blue for KIT -- both contrast
        # cleanly against the reserved signal red. background[0] is KIT's green,
        # which (unlike Petroff's blue at [0]) reads muddier against signal red here.
        HistogramEntry(
            name="background", latex_name="Background", array=data["background"], color=palette.background[1]
        )
    )
    # type="signal" routes this into Histogram.signal instead of Histogram.entries, so
    # plot_stacked() always closes the stack with it on top (at its true yield, in the
    # palette's reserved signal red) regardless of add_entry() call order -- unlike a
    # plain entry, whose stack position is just insertion order.
    hist.add_entry(HistogramEntry(name="signal", latex_name="Signal", array=data["signal"], type="signal"))

    histplot = HistogramPlot(hist)
    histplot.stacked = True
    histplot.uncertainty = True

    variable = HistogramVariable("$p_T$", "GeV")
    plotter = HistogramPlotter(histplot, variable)
    plotter.watermark = "(Own Work)"
    # "best" (the default) places the legend over the empty upper-left corner of the
    # axes -- which is exactly where the watermark text lives, so it occludes
    # "(Own Work)". With the default legend_max_rows=4 the 5 legend entries here
    # spill into a 2-column box wide enough to span the axes regardless of anchor,
    # so also force a single narrow column (legend_max_rows >= len(labels)) before
    # anchoring it to the upper-right corner, away from the watermark.
    plotter.legend_max_rows = 5
    plotter.legend_loc = "upper right"

    # add_pull draws its own copy of this line on the main panel (to pick up
    # `color` for the pull-panel markers); omit its label so the legend
    # doesn't get "Model" twice.
    plotter.add_function(_model, binwidth=True, label="Model", color=PetroffColors.purple, lw=2)
    plotter.add_pull(_model, binwidth=True, color=PetroffColors.purple, lw=2, max_sigma=5.0)
    return plotter


def step2_engine_pull(data: dict[str, np.ndarray]) -> None:
    """Prompt: "Now stack them and add a pull panel comparing to the model"."""
    plotter = _build_stacked_pull_plotter(data)
    plotter.savepath = os.path.join(OUTPUT_DIR, "02-stacked-pull.png")
    plotter.plot(save=True)


def step3_kit_palette(data: dict[str, np.ndarray]) -> None:
    """Prompt: "Switch to KIT colors"."""
    set_palette("KIT")
    try:
        plotter = _build_stacked_pull_plotter(data)
        plotter.savepath = os.path.join(OUTPUT_DIR, "03-kit-colors.png")
        plotter.plot(save=True)
    finally:
        set_palette("Petroff")


def main() -> None:
    set_experiment("BelleII")
    set_matplotlibrc_params(36)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    data = make_signal_background(n_signal=N_SIGNAL, n_background=N_BACKGROUND, seed=3)

    step1_convenience(data)
    print("Saved to", os.path.join(OUTPUT_DIR, "01-histogram.png"))
    step2_engine_pull(data)
    print("Saved to", os.path.join(OUTPUT_DIR, "02-stacked-pull.png"))
    step3_kit_palette(data)
    print("Saved to", os.path.join(OUTPUT_DIR, "03-kit-colors.png"))


if __name__ == "__main__":
    main()
