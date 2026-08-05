import json

import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.colors import to_hex
from matplotlib.patches import Polygon

from afplotter.genericplot import GenericPlot
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
    data_hist.add_entry(HistogramEntry(name="Data", array=np.random.default_rng(1).normal(5, 1, 300)))
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
    yhist.add_entry(HistogramEntry(name="signal", array=np.random.default_rng(2).normal(5, 1, 500)))
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


def _render_stacked(hist: Histogram, sig_extra: bool = False, uncertainty: bool = False) -> plt.Axes:
    """Render ``hist`` as a stacked plot and return the main axes."""
    histplot = HistogramPlot(hist)
    histplot.stacked = True
    histplot.sig_extra = sig_extra
    histplot.uncertainty = uncertainty
    plotter = HistogramPlotter(histplot, HistogramVariable("$M$", "GeV"))
    ax, _ = plotter.plot(save=False)
    return ax


def _stack_layers(ax: plt.Axes) -> dict[str, tuple[str, float]]:
    """Map each *filled* stack layer's label to its (facecolor, top y).

    ``stepfilled`` stack layers are filled Polygons; the ``sig_extra`` outline overlay
    and the uncertainty band are not, so filtering on ``get_fill()`` separates them.
    A layer's top y is the cumulative stack height, which is how "on top" is checked.
    """
    return {
        p.get_label(): (to_hex(p.get_facecolor()), float(np.max(p.get_xy()[:, 1])))
        for p in ax.patches
        if isinstance(p, Polygon) and p.get_fill()
    }


def _overlay_outlines(ax: plt.Axes) -> dict[str, tuple[str, float]]:
    """Map each *unfilled* ``sig_extra`` outline's label to its (edgecolor, top y)."""
    return {
        p.get_label(): (to_hex(p.get_edgecolor()), float(np.max(p.get_xy()[:, 1])))
        for p in ax.patches
        if isinstance(p, Polygon) and not p.get_fill()
    }


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
    hist.add_entry(
        HistogramEntry(
            name="bkg0", latex_name="B0", array=np.random.default_rng(1).uniform(0, 10, 400), color="#00ff00"
        )
    )
    hist.add_entry(HistogramEntry(name="bkg1", latex_name="B1", array=np.random.default_rng(2).uniform(0, 10, 400)))
    colors = _rendered_colors(hist)
    assert colors["B0"][0] == "#00ff00"
    assert colors["B1"][0] == PETROFF_PALETTE.background[1]


def _rendered_step_colors_and_hatches(hist: Histogram) -> dict[str, tuple[str, str | None]]:
    histplot = HistogramPlot(hist)
    histplot.stacked = False
    plotter = HistogramPlotter(histplot, HistogramVariable("$M$", "GeV"))
    ax, _ = plotter.plot(save=False)
    result = {patch.get_label(): (to_hex(patch.get_edgecolor()), patch.get_hatch()) for patch in ax.patches}
    plt.close(ax.figure)
    return result


def test_step_backfills_only_missing_entry_colors_and_keeps_hatches():
    hist = _uncolored_histogram(n_entries=0)
    hist.add_entry(
        HistogramEntry(
            name="bkg0",
            latex_name="B0",
            array=np.random.default_rng(1).uniform(0, 10, 400),
            color="#00ff00",
            hatch="///",
        )
    )
    hist.add_entry(HistogramEntry(name="bkg1", latex_name="B1", array=np.random.default_rng(2).uniform(0, 10, 400)))
    result = _rendered_step_colors_and_hatches(hist)
    assert result["B0"] == ("#00ff00", "///")
    assert result["B1"][0] == PETROFF_PALETTE.background[1]


def test_signal_is_the_topmost_stack_layer():
    hist = _uncolored_histogram(n_entries=3, n_signals=1)
    ax = _render_stacked(hist)
    layers = _stack_layers(ax)
    signal_top = layers["S0"][1]
    # The signal layer closes the stack, so its top is the full S+B total and every
    # background layer sits strictly below it.
    assert signal_top == pytest.approx(float(np.max(hist.get_total_bin_count())))
    assert all(layers[f"B{i}"][1] < signal_top for i in range(3))
    plt.close(ax.figure)


def test_stacked_signal_is_filled_red_at_its_true_yield():
    hist = _uncolored_histogram(n_entries=2, n_signals=1)
    ax = _render_stacked(hist)
    layers = _stack_layers(ax)
    assert layers["S0"][0] == get_palette().signal
    # Stacked at the true yield, not peak-matched to the background stack the way the
    # sig_extra overlay is: the stack top must exceed the background-only maximum by
    # the signal's own counts, not by a scale factor.
    background_max = float(np.max(np.sum(hist.get_bin_counts(), axis=0)))
    assert layers["S0"][1] > background_max
    assert layers["S0"][1] == pytest.approx(float(np.max(hist.get_total_bin_count())))
    plt.close(ax.figure)


def test_stacked_signal_red_overrides_an_explicit_entry_color():
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
    ax = _render_stacked(hist)
    assert _stack_layers(ax)["S0"][0] == get_palette().signal
    plt.close(ax.figure)


def test_uncertainty_band_covers_the_signal_layer_too():
    hist = _uncolored_histogram(n_entries=2, n_signals=1)
    ax = _render_stacked(hist, uncertainty=True)
    band = next(c for c in ax.containers if c.get_label() == "Stat. unc.")
    band_tops = np.array([bar.get_y() + bar.get_height() for bar in band.patches])

    # Build the expectation from the raw components rather than from the total
    # accessors under test, so a regression that drops signal from the totals shows up.
    background = np.sum(hist.get_bin_counts(), axis=0)
    signal = np.sum(hist.get_raw_signal_bin_counts(), axis=0)
    errors = np.sqrt(np.sum([e**2 for e in hist.get_bin_errors() + hist.get_raw_signal_bin_errors()], axis=0))
    assert band_tops == pytest.approx(background + signal + errors)
    plt.close(ax.figure)


def test_sig_extra_excludes_signal_from_the_stack():
    hist = _uncolored_histogram(n_entries=2, n_signals=1)
    ax = _render_stacked(hist, sig_extra=True)
    # sig_extra means the signal is drawn *only* as the peak-matched outline overlay --
    # it must not also be a filled stack layer, or it is drawn, and legended, twice.
    assert "S0" not in _stack_layers(ax)
    outline_color, outline_top = _overlay_outlines(ax)["S0"]
    assert outline_color == get_palette().signal
    # The outline is still peak-matched to the background stack, so it is taller than
    # the raw signal but shorter than the full S+B stack.
    background_max = float(np.max(np.sum(hist.get_bin_counts(), axis=0)))
    assert outline_top == pytest.approx(background_max)
    plt.close(ax.figure)


def test_sig_extra_does_not_duplicate_the_signal_legend_entry():
    hist = _uncolored_histogram(n_entries=2, n_signals=1)
    ax = _render_stacked(hist, sig_extra=True)
    _, labels = ax.get_legend_handles_labels()
    assert labels.count("S0") == 1


def test_sig_extra_stat_unc_band_covers_background_only():
    hist = _uncolored_histogram(n_entries=2, n_signals=1)
    ax = _render_stacked(hist, sig_extra=True, uncertainty=True)
    band = next(c for c in ax.containers if c.get_label() == "Stat. unc.")
    band_tops = np.array([bar.get_y() + bar.get_height() for bar in band.patches])

    # With sig_extra, signal is not part of the stack, so the band must hug the
    # background-only bars underneath it, not the S+B total.
    background = np.sum(hist.get_bin_counts(), axis=0)
    errors = np.sqrt(np.sum([e**2 for e in hist.get_bin_errors()], axis=0))
    assert band_tops == pytest.approx(background + errors)
    plt.close(ax.figure)


def _pull_values(plotter: HistogramPlotter) -> np.ndarray:
    """The y values of the pull errorbar queued by add_pull()."""
    errorbar = next(p for p in plotter.pull_plots if p.plotmethod == "errorbar")
    return np.asarray(errorbar.args[1])


def test_pull_panel_compares_against_signal_plus_background():
    hist = _uncolored_histogram(n_entries=2, n_signals=1)
    centers = hist.get_bin_centers()[0]
    total = hist.get_total_bin_count()
    background = np.sum(hist.get_bin_counts(), axis=0)
    assert not np.allclose(total, background), "fixture must have a non-zero signal"

    histplot = HistogramPlot(hist)
    histplot.stacked = True
    plotter = HistogramPlotter(histplot, HistogramVariable("$M$", "GeV"))
    plotter.add_pull(lambda x: np.interp(x, centers, total), label="S+B")
    # A model equal to the full S+B stack is a perfect fit, so every pull is zero.
    assert _pull_values(plotter) == pytest.approx(np.zeros_like(total))

    plotter_bkg = HistogramPlotter(HistogramPlot(hist), HistogramVariable("$M$", "GeV"))
    plotter_bkg.add_pull(lambda x: np.interp(x, centers, background), label="B only")
    # A background-only model now misses the signal, so pulls must be non-zero.
    assert np.any(np.abs(_pull_values(plotter_bkg)) > 1e-6)


def test_multiple_signal_outlines_fall_back_to_the_cycle():
    # With sig_extra, signal never enters the stack (see
    # test_sig_extra_excludes_signal_from_the_stack); only the outlines' colours are
    # at stake here, and with more than one signal they fall back to the ordinary cycle.
    ax = _render_stacked(_uncolored_histogram(n_entries=2, n_signals=2), sig_extra=True)
    layers = _stack_layers(ax)
    assert "S0" not in layers and "S1" not in layers
    outlines = _overlay_outlines(ax)
    outline_colors = [outlines["S0"][0], outlines["S1"][0]]
    assert outline_colors == PETROFF_PALETTE.background[:2]
    assert get_palette().signal not in outline_colors
    plt.close(ax.figure)


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


def test_2d_plot_rejects_a_histogram_without_raw_data(tmp_path):
    """A loaded (binned-only) histogram must fail with a message naming the real cause.

    Without the guard this reaches hist2d(x=None) and raises from inside matplotlib, naming
    nothing useful. Matching on the message is the point of the test -- asserting merely that
    "something raised" would pass against the broken behaviour too.
    """
    hist = Histogram()
    hist.binning = np.linspace(0.0, 10.0, 6)
    hist.add_entry(HistogramEntry(name="x", array=np.random.default_rng(0).normal(5.0, 2.0, 200)))
    path = tmp_path / "h.json"
    hist.save(path)

    plot2d = Histogram2DPlot(Histogram.load(path), Histogram.load(path))
    fig, ax = plt.subplots()
    plot2d.ax = ax
    with pytest.raises(ValueError, match="raw event data"):
        plot2d.plot()
    plt.close(fig)


def _histogram_plotter(histogram):
    """A plotter whose every saved field differs from its constructed default."""
    histplot = HistogramPlot(histogram)
    histplot.stacked = True
    histplot.sig_extra = True
    histplot.uncertainty = True
    histplot.density = True
    histplot.linewidth = 2.5
    histplot.edgecolor = "navy"
    plotter = HistogramPlotter(histplot, HistogramVariable(name="mass", unit="GeV"))
    plotter.figsize = (7, 3)
    plotter.ylim = (1.0, 500.0)
    plotter.pull_ylim = (-2.5, 2.5)
    plotter.pull_label = "residual"
    plotter.color_map_kwargs = {"min_val": 0.0, "max_val": 1.0, "cmap": "plasma", "label": "score"}
    return plotter


def test_histogram_plotter_save_load_round_trips_spec_and_data(tmp_path, synthetic_histogram):
    plotter = _histogram_plotter(synthetic_histogram)
    plotter.add_function(lambda x: 30.0 * np.exp(-((x - 5.0) ** 2) / 2.0), density=False, color="red")

    path = tmp_path / "p.json"
    plotter.save(path)
    loaded = HistogramPlotter.load(path)

    assert loaded.figsize == (7, 3)
    assert isinstance(loaded.figsize, tuple)
    assert loaded.ylim == (1.0, 500.0)
    assert loaded.pull_ylim == (-2.5, 2.5)
    assert loaded.pull_label == "residual"
    assert loaded.color_map_kwargs == {"min_val": 0.0, "max_val": 1.0, "cmap": "plasma", "label": "score"}

    assert loaded.variable.name == "mass"
    assert loaded.variable.unit == "GeV"
    # Proves restoration wrote _xlabel: xlabel is a read-only property on this class.
    assert loaded.xlabel == "mass (GeV)"

    assert loaded.histplot.stacked is True
    assert loaded.histplot.sig_extra is True
    assert loaded.histplot.uncertainty is True
    assert loaded.histplot.density is True
    assert loaded.histplot.linewidth == 2.5
    assert loaded.histplot.edgecolor == "navy"

    assert np.allclose(loaded.histplot.histogram.binning, synthetic_histogram.binning)
    assert np.allclose(
        loaded.histplot.histogram.get_bin_counts()[0],
        synthetic_histogram.get_bin_counts()[0],
    )
    assert np.allclose(
        loaded.histplot.histogram.get_bin_errors()[0],
        synthetic_histogram.get_bin_errors()[0],
    )
    assert loaded.histplot.histogram.get_names() == synthetic_histogram.get_names()

    # The overlay add_function sampled is preserved as data, not as a callable.
    assert len(loaded.generic_plots) == 1
    assert loaded.generic_plots[0].plotmethod == "plot"
    assert np.allclose(loaded.generic_plots[0].args[1], plotter.generic_plots[0].args[1])
    assert loaded.generic_plots[0].kwargs == {"color": "red"}


def test_histogram_plotter_save_load_round_trips_pull_plots(tmp_path, synthetic_histogram):
    plotter = _histogram_plotter(synthetic_histogram)
    plotter.add_pull(lambda x: 30.0 * np.exp(-((x - 5.0) ** 2) / 2.0), density=False, color="red")

    path = tmp_path / "p.json"
    plotter.save(path)
    loaded = HistogramPlotter.load(path)

    assert [plot.plotmethod for plot in loaded.pull_plots] == [plot.plotmethod for plot in plotter.pull_plots]
    assert np.allclose(loaded.pull_plots[-1].args[1], plotter.pull_plots[-1].args[1])
    assert loaded.pull_ylim == plotter.pull_ylim


def test_histogram_plotter_inset_references_the_loaded_objects(tmp_path, synthetic_histogram):
    plotter = _histogram_plotter(synthetic_histogram)
    plotter.add_generic_plot(GenericPlot("plot", np.array([1.0, 2.0]), np.array([3.0, 4.0])))
    plotter.add_inset(xlim=(2.0, 4.0), title="zoom")

    path = tmp_path / "p.json"
    plotter.save(path)
    loaded = HistogramPlotter.load(path)

    assert len(loaded._insets) == 1
    assert loaded._insets[0].title == "zoom"
    # Default inset content is [histplot] + generic_plots; both must be the LIVE objects.
    assert loaded._insets[0].plots[0] is loaded.histplot
    assert loaded._insets[0].plots[1] is loaded.generic_plots[0]


def test_histogram_plotter_file_size_does_not_scale_with_sample_size(tmp_path):
    """The point of embedding binned-only data: caching stays viable at any sample size."""
    rng = np.random.default_rng(seed=7)
    sizes = []
    for n_events, name in ((1_000, "small.json"), (100_000, "large.json")):
        histogram = Histogram()
        histogram.binning = np.linspace(0, 10, 21)
        histogram.add_entry(HistogramEntry(name="bkg", array=rng.uniform(0, 10, size=n_events)))
        plotter = HistogramPlotter(HistogramPlot(histogram), HistogramVariable(name="mass"))
        path = tmp_path / name
        plotter.save(path)
        sizes.append(path.stat().st_size)

    assert abs(sizes[1] - sizes[0]) / sizes[0] < 0.10


def test_loaded_histogram_plotter_renders_the_same_overlay(tmp_path, synthetic_histogram):
    """Round-tripping a dict is not the same as re-rendering a plot."""
    plotter = _histogram_plotter(synthetic_histogram)
    plotter.add_function(lambda x: 30.0 * np.exp(-((x - 5.0) ** 2) / 2.0), density=False, color="red")

    path = tmp_path / "p.json"
    plotter.save(path)
    loaded = HistogramPlotter.load(path)

    original_ax, _ = plotter.plot(save=False)
    original_curves = [line.get_ydata() for line in original_ax.lines]
    plt.close("all")

    loaded_ax, _ = loaded.plot(save=False)
    loaded_curves = [line.get_ydata() for line in loaded_ax.lines]
    plt.close("all")

    assert len(loaded_curves) == len(original_curves) > 0
    for restored, original in zip(loaded_curves, original_curves):
        assert np.allclose(restored, original)


def _2d_histograms():
    rng = np.random.default_rng(seed=11)
    xhist = Histogram()
    xhist.binning = np.linspace(0, 10, 11)
    xhist.add_entry(HistogramEntry(name="x", array=rng.uniform(0, 10, size=400)))
    yhist = Histogram()
    yhist.binning = np.linspace(0, 5, 6)
    yhist.add_entry(HistogramEntry(name="y", array=rng.uniform(0, 5, size=400)))
    return xhist, yhist


def test_histogram_2d_plotter_save_load_round_trips_the_spec(tmp_path):
    """Every asserted value is non-default: cmap defaults to 'viridis', norm to 'linear'."""
    xhist, yhist = _2d_histograms()
    histplot = Histogram2DPlot(xhist, yhist)
    histplot.cmap = "plasma"
    histplot.norm = "log"
    histplot.cmin = 0.5
    histplot.cmax = 42.0
    histplot.cbar_label = "events / bin"
    histplot.density = True
    histplot.log = True
    plotter = Histogram2DPlotter(histplot, HistogramVariable("mass", "GeV"), HistogramVariable("time", "ns"))
    plotter.figsize = (7, 3)
    plotter.add_generic_plot(GenericPlot("plot", np.array([1.0, 2.0]), np.array([3.0, 4.0]), color="red"))

    path = tmp_path / "p2d.json"
    plotter.save(path)

    fresh_x, fresh_y = _2d_histograms()
    loaded = Histogram2DPlotter.load(path, xhistogram=fresh_x, yhistogram=fresh_y)

    assert loaded.figsize == (7, 3)
    assert loaded.xvariable.name == "mass"
    assert loaded.yvariable.unit == "ns"
    assert loaded.xlabel == "mass (GeV)"
    assert loaded.histplot.cmap == "plasma"
    assert loaded.histplot.norm == "log"
    assert loaded.histplot.cmin == 0.5
    assert loaded.histplot.cmax == 42.0
    assert loaded.histplot.cbar_label == "events / bin"
    assert loaded.histplot.density is True
    assert loaded.histplot.log is True
    assert loaded.generic_plots[0].kwargs == {"color": "red"}
    # The data came from the caller, not the file.
    assert loaded.histplot.xhistogram is fresh_x
    assert loaded.histplot.yhistogram is fresh_y


def test_histogram_2d_plotter_save_does_not_embed_event_data(tmp_path):
    """Raw arrays in the payload are exactly what this design rejects."""
    xhist, yhist = _2d_histograms()
    plotter = Histogram2DPlotter(Histogram2DPlot(xhist, yhist), HistogramVariable("mass"), HistogramVariable("time"))
    path = tmp_path / "p2d.json"
    plotter.save(path)

    payload = json.loads(path.read_text())
    assert "histogram" not in payload
    assert path.stat().st_size < 2_000


def test_histogram_2d_plotter_load_requires_both_histograms(tmp_path):
    xhist, yhist = _2d_histograms()
    plotter = Histogram2DPlotter(Histogram2DPlot(xhist, yhist), HistogramVariable("mass"), HistogramVariable("time"))
    path = tmp_path / "p2d.json"
    plotter.save(path)

    with pytest.raises(TypeError):
        Histogram2DPlotter.load(path)


def test_loaded_histogram_2d_plotter_renders(tmp_path):
    xhist, yhist = _2d_histograms()
    plotter = Histogram2DPlotter(Histogram2DPlot(xhist, yhist), HistogramVariable("mass"), HistogramVariable("time"))
    path = tmp_path / "p2d.json"
    plotter.save(path)

    fresh_x, fresh_y = _2d_histograms()
    loaded = Histogram2DPlotter.load(path, xhistogram=fresh_x, yhistogram=fresh_y)
    ax = loaded.plot(save=False)
    assert ax.get_xlabel() == "mass"
    plt.close("all")
