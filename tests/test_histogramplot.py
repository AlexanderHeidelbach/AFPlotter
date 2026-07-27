import matplotlib.pyplot as plt
import numpy as np
import pytest

from afplotter.histogramplot import (
    Histogram2DPlot,
    Histogram2DPlotter,
    HistogramPlot,
    HistogramPlotter,
    HistogramVariable,
    poisson_ratio,
    weighted_mean_and_error,
)
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


def test_histogram_2d_plotter_end_to_end(synthetic_histogram):
    xhist = synthetic_histogram
    yhist = Histogram()
    yhist.binning = np.linspace(0, 10, 21)
    yhist.add_entry(
        HistogramEntry(name="signal", array=np.random.default_rng(3).normal(5, 1, 500))
    )
    xvar = HistogramVariable("$M_x$", "GeV")
    yvar = HistogramVariable("$M_y$", "GeV")
    plotter = Histogram2DPlotter(Histogram2DPlot(xhist, yhist), xvar, yvar)
    ax = plotter.plot(save=False)
    assert ax is not None
    plt.close(ax.figure)
