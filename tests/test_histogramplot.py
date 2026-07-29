import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.colors import to_hex

from afplotter.histogramplot import (
    Histogram2DPlot,
    Histogram2DPlotter,
    HistogramPlot,
    HistogramPlotter,
    HistogramVariable,
    poisson_ratio,
    weighted_mean_and_error,
)
from afplotter.palettes import PETROFF_PALETTE, get_palette
from afplotter.utilities.histogram import Histogram, HistogramEntry


def test_poisson_ratio_both_zero_gives_one():
    ratio, err = poisson_ratio(np.array([0.0]), np.array([0.0]))
    assert ratio[0] == 1.0
    assert err[0] == 0.0


def test_poisson_ratio_normal_case():
    ratio, err = poisson_ratio(np.array([10.0]), np.array([5.0]))
    assert ratio[0] == 2.0
    assert err[0] > 0.0


def test_weighted_mean_and_error():
    mean, err = weighted_mean_and_error([1.0, 2.0, 3.0], [1.0, 1.0, 1.0])
    assert mean == pytest.approx(2.0)
    assert err > 0.0


def test_histogram_plot_step(synthetic_histogram):
    histplot = HistogramPlot(synthetic_histogram)
    fig, ax = plt.subplots()
    histplot.ax = ax
    histplot.plot()
    assert len(ax.patches) > 0 or len(ax.containers) > 0
    plt.close(fig)


def test_histogram_plot_stacked(synthetic_histogram):
    histplot = HistogramPlot(synthetic_histogram)
    histplot.stacked = True
    histplot.uncertainty = True
    fig, ax = plt.subplots()
    histplot.ax = ax
    histplot.plot()
    plt.close(fig)


def test_histogram_plot_data_only(synthetic_histogram):
    data_hist = Histogram()
    data_hist.binning = synthetic_histogram.binning
    data_hist.add_entry(
        HistogramEntry(name="Data", array=np.random.default_rng(1).normal(5, 1, 300))
    )
    histplot = HistogramPlot(synthetic_histogram)
    histplot.data_hist = data_hist
    histplot.data_only = True
    fig, ax = plt.subplots()
    histplot.ax = ax
    histplot.plot()
    assert len(ax.containers) == 1  # plot_data() draws via ax.errorbar(), which populates containers, not lines
    plt.close(fig)


def test_histogram_2d_plot(synthetic_histogram):
    xhist = synthetic_histogram
    yhist = Histogram()
    yhist.binning = np.linspace(0, 10, 21)
    yhist.add_entry(
        HistogramEntry(name="signal", array=np.random.default_rng(2).normal(5, 1, 500))
    )
    plot2d = Histogram2DPlot(xhist, yhist)
    fig, ax = plt.subplots()
    plot2d.ax = ax
    plot2d.plot()
    plt.close(fig)


def test_histogram_plotter_end_to_end(synthetic_histogram, tmp_path):
    histplot = HistogramPlot(synthetic_histogram)
    histplot.stacked = True
    variable = HistogramVariable("$M$", "GeV")
    plotter = HistogramPlotter(histplot, variable)
    plotter.savedir = str(tmp_path)
    plotter.savename = "hist_test"
    plotter.saveformat = "png"
    ax, ax_diff = plotter.plot(save=True)
    assert (tmp_path / "hist_test.png").exists()
    assert ax is not None
    assert ax_diff is None


def test_histogram_plotter_add_function_and_pull(synthetic_histogram):
    histplot = HistogramPlot(synthetic_histogram)
    histplot.stacked = True
    variable = HistogramVariable("$M$", "GeV")
    plotter = HistogramPlotter(histplot, variable)

    def flat_model(x):
        return np.ones_like(x) * 100.0

    plotter.add_function(flat_model, binwidth=True, label="model", color="black")
    plotter.add_pull(flat_model, binwidth=True, color="black", label="model", max_sigma=5.0)
    ax, ax_diff = plotter.plot(save=False)
    assert ax_diff is not None
    plt.close(ax.figure)


def test_histogram_plotter_add_inset_default_plots(synthetic_histogram):
    histplot = HistogramPlot(synthetic_histogram)
    histplot.stacked = True
    variable = HistogramVariable("$M$", "GeV")
    plotter = HistogramPlotter(histplot, variable)
    plotter.add_inset(xlim=(2, 4), title="Peak")
    ax, ax_diff = plotter.plot(save=False)
    assert len(ax.figure.axes) >= 2
    assert any(a.get_title() == "Peak" for a in ax.figure.axes)
    plt.close(ax.figure)


def _uncolored_histogram(n_entries: int = 3, n_signals: int = 0) -> Histogram:
    """A Histogram whose entries carry no explicit colour, so the cycle has to supply them."""
    rng = np.random.default_rng(seed=7)
    hist = Histogram()
    hist.binning = np.linspace(0, 10, 21)
    for i in range(n_entries):
        hist.add_entry(HistogramEntry(name=f"bkg{i}", latex_name=f"B{i}", array=rng.uniform(0, 10, 400)))
    for i in range(n_signals):
        hist.add_entry(
            HistogramEntry(
                name=f"sig{i}",
                latex_name=f"S{i}",
                array=rng.normal(5, 1, 300),
                type="signal",
            )
        )
    return hist


def _rendered_colors(hist: Histogram, sig_extra: bool = False) -> dict[str, tuple[str, str]]:
    """Render ``hist`` and map each artist's label to its (facecolor, edgecolor) hex.

    Stacked ``stepfilled`` bars are filled Polygons; overlaid ``step`` signals are
    unfilled Polygons whose colour lives on the edge. Keying by label rather than by
    index matters because matplotlib emits the stack in reverse draw order.
    """
    histplot = HistogramPlot(hist)
    histplot.stacked = True
    histplot.sig_extra = sig_extra
    plotter = HistogramPlotter(histplot, HistogramVariable("$M$", "GeV"))
    ax, _ = plotter.plot(save=False)
    colors = {patch.get_label(): (to_hex(patch.get_facecolor()), to_hex(patch.get_edgecolor())) for patch in ax.patches}
    plt.close(ax.figure)
    return colors


def test_stacked_entries_use_the_petroff_cycle():
    colors = _rendered_colors(_uncolored_histogram(n_entries=3))
    assert [colors[f"B{i}"][0] for i in range(3)] == PETROFF_PALETTE.background[:3]


def test_no_stacked_entry_is_ever_signal_red():
    # 12 entries wraps past the end of the 9-colour cycle; red must still never appear.
    colors = _rendered_colors(_uncolored_histogram(n_entries=12))
    assert get_palette().signal not in [face for face, _ in colors.values()]


def test_single_signal_is_drawn_in_signal_red():
    colors = _rendered_colors(_uncolored_histogram(n_entries=2, n_signals=1), sig_extra=True)
    assert colors["S0"][1] == get_palette().signal
    assert [colors[f"B{i}"][0] for i in range(2)] == PETROFF_PALETTE.background[:2]


def test_single_signal_red_overrides_an_explicit_entry_color():
    hist = _uncolored_histogram(n_entries=2)
    hist.add_entry(
        HistogramEntry(
            name="sig0",
            latex_name="S0",
            array=np.random.default_rng(8).normal(5, 1, 300),
            type="signal",
            color="#00ff00",
        )
    )
    colors = _rendered_colors(hist, sig_extra=True)
    assert colors["S0"][1] == get_palette().signal


def test_multiple_signals_fall_back_to_the_cycle():
    colors = _rendered_colors(_uncolored_histogram(n_entries=2, n_signals=2), sig_extra=True)
    signal_edges = [colors["S0"][1], colors["S1"][1]]
    assert signal_edges == PETROFF_PALETTE.background[:2]
    assert get_palette().signal not in signal_edges


def test_stacked_backfills_only_missing_entry_colors():
    hist = _uncolored_histogram(n_entries=0)
    hist.add_entry(HistogramEntry(name="bkg0", latex_name="B0", array=np.random.default_rng(1).uniform(0, 10, 400), color="#00ff00"))
    hist.add_entry(HistogramEntry(name="bkg1", latex_name="B1", array=np.random.default_rng(2).uniform(0, 10, 400)))
    colors = _rendered_colors(hist)
    assert colors["B0"][0] == "#00ff00"
    assert colors["B1"][0] == PETROFF_PALETTE.background[1]


def _rendered_step_colors_and_hatches(hist: Histogram) -> dict[str, tuple[str, str | None]]:
    histplot = HistogramPlot(hist)
    histplot.stacked = False
    plotter = HistogramPlotter(histplot, HistogramVariable("$M$", "GeV"))
    ax, _ = plotter.plot(save=False)
    result = {
        patch.get_label(): (to_hex(patch.get_edgecolor()), patch.get_hatch())
        for patch in ax.patches
    }
    plt.close(ax.figure)
    return result


def test_step_backfills_only_missing_entry_colors_and_keeps_hatches():
    hist = _uncolored_histogram(n_entries=0)
    hist.add_entry(
        HistogramEntry(
            name="bkg0", latex_name="B0", array=np.random.default_rng(1).uniform(0, 10, 400),
            color="#00ff00", hatch="///",
        )
    )
    hist.add_entry(
        HistogramEntry(name="bkg1", latex_name="B1", array=np.random.default_rng(2).uniform(0, 10, 400))
    )
    result = _rendered_step_colors_and_hatches(hist)
    assert result["B0"] == ("#00ff00", "///")
    assert result["B1"][0] == PETROFF_PALETTE.background[1]


def test_histogram_2d_plotter_end_to_end(synthetic_histogram):
    xhist = synthetic_histogram
    yhist = Histogram()
    yhist.binning = np.linspace(0, 10, 21)
    yhist.add_entry(HistogramEntry(name="signal", array=np.random.default_rng(3).normal(5, 1, 500)))
    xvar = HistogramVariable("$M_x$", "GeV")
    yvar = HistogramVariable("$M_y$", "GeV")
    plotter = Histogram2DPlotter(Histogram2DPlot(xhist, yhist), xvar, yvar)
    ax = plotter.plot(save=False)
    assert ax is not None
    plt.close(ax.figure)
