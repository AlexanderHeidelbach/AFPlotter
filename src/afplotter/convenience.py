"""High-level one-call plotting functions for common ad-hoc requests.

For composed/analysis plots (multiple overlays, fills, insets, fit curves),
use GenericPlotter/HistogramPlotter directly instead — see docs/.
"""
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from afplotter.baseplotter import PathType
from afplotter.histogramplot import (
    Histogram2DPlot,
    Histogram2DPlotter,
    HistogramPlot,
    HistogramPlotter,
    HistogramVariable,
)
from afplotter.selectionparser.polars import SelectionOperator
from afplotter.utilities.histogram import Histogram, HistogramEntry
from afplotter.utilities.lazyhistogram import LazyHistEntry, LazyHistWrapper

BinsSpec = np.ndarray | list[float] | tuple[float, float, int]


def _resolve_bins(bins: BinsSpec) -> np.ndarray:
    if isinstance(bins, tuple) and len(bins) == 3:
        return np.linspace(bins[0], bins[1], bins[2])
    return np.asarray(bins)


def plot_histogram(
    entries: dict[str, np.ndarray],
    bins: BinsSpec,
    xlabel: str = "",
    stacked: bool = False,
    save: PathType | None = None,
    **histogram_plotter_kwargs: Any,
) -> plt.Axes:
    """
    Plot a single-variable histogram from in-memory arrays.

    :param entries: Mapping of entry name to its data array.
    :param bins: A bin-edges array/list, or a (start, stop, num) tuple.
    :param xlabel: X-axis label.
    :param stacked: Whether entries are drawn stacked rather than as outlined steps.
    :param save: If given, the plot is saved to this path instead of shown.
    :param histogram_plotter_kwargs: Extra HistogramPlotter properties to set
        (e.g. figsize=(8, 6), log=True).
    :return: The matplotlib Axes the histogram was drawn on.
    """
    hist = Histogram()
    hist.binning = _resolve_bins(bins)
    for name, array in entries.items():
        hist.add_entry(HistogramEntry(name=name, latex_name=name, array=np.asarray(array)))

    histplot = HistogramPlot(hist)
    histplot.stacked = stacked

    plotter = HistogramPlotter(histplot, HistogramVariable(xlabel))
    for key, value in histogram_plotter_kwargs.items():
        setattr(plotter, key, value)

    if save:
        plotter.savepath = str(save)
    ax, _ = plotter.plot(save=bool(save))
    return ax


def plot_histogram_from_files(
    files: dict[str, PathType | list[PathType]],
    column: str,
    bins: BinsSpec,
    xlabel: str = "",
    stacked: bool = False,
    selection: str | None = None,
    save: PathType | None = None,
    **histogram_plotter_kwargs: Any,
) -> plt.Axes:
    """
    Plot a single-variable histogram straight from parquet file(s) via Polars.

    :param files: Mapping of entry name to a parquet path (or list of paths).
    :param column: Column name to histogram.
    :param bins: A bin-edges array/list, or a (start, stop, num) tuple.
    :param xlabel: X-axis label.
    :param stacked: Whether entries are drawn stacked rather than as outlined steps.
    :param selection: Optional query string (e.g. "pt > 5 and eta > -2 and eta < 2")
        applied to each entry before histogramming.
    :param save: If given, the plot is saved to this path instead of shown.
    :param histogram_plotter_kwargs: Extra HistogramPlotter properties to set.
    :return: The matplotlib Axes the histogram was drawn on.
    """
    wrapper = LazyHistWrapper()
    lazy_entries = []
    for name, path in files.items():
        entry = LazyHistEntry(name=name, input=path)
        if selection:
            entry.data = SelectionOperator(entry.data, selections={"selection": selection}).apply_selections()
        lazy_entries.append(entry)
    wrapper.add_lazy_entry(lazy_entries)

    wrapper.add_hist(column=column, bins=_resolve_bins(bins), identifier="convenience_hist")
    wrapper.lazy_execute()
    hist = wrapper.get_hist("convenience_hist")

    histplot = HistogramPlot(hist)
    histplot.stacked = stacked

    plotter = HistogramPlotter(histplot, HistogramVariable(xlabel))
    for key, value in histogram_plotter_kwargs.items():
        setattr(plotter, key, value)

    if save:
        plotter.savepath = str(save)
    ax, _ = plotter.plot(save=bool(save))
    return ax


def plot_2d_histogram(
    xdata: np.ndarray,
    ydata: np.ndarray,
    xbins: BinsSpec,
    ybins: BinsSpec,
    xlabel: str = "",
    ylabel: str = "",
    save: PathType | None = None,
    **histogram2d_plotter_kwargs: Any,
) -> plt.Axes:
    """
    Plot a 2D histogram from two in-memory arrays.

    :param xdata: X-axis data array.
    :param ydata: Y-axis data array.
    :param xbins: X bin-edges array/list, or a (start, stop, num) tuple.
    :param ybins: Y bin-edges array/list, or a (start, stop, num) tuple.
    :param xlabel: X-axis label.
    :param ylabel: Y-axis label.
    :param save: If given, the plot is saved to this path instead of shown.
    :param histogram2d_plotter_kwargs: Extra Histogram2DPlotter properties to set.
    :return: The matplotlib Axes the histogram was drawn on.
    """
    xhist = Histogram()
    xhist.binning = _resolve_bins(xbins)
    xhist.add_entry(HistogramEntry(name="x", array=np.asarray(xdata)))

    yhist = Histogram()
    yhist.binning = _resolve_bins(ybins)
    yhist.add_entry(HistogramEntry(name="y", array=np.asarray(ydata)))

    plot2d = Histogram2DPlot(xhist, yhist)
    plotter = Histogram2DPlotter(plot2d, HistogramVariable(xlabel), HistogramVariable(ylabel))
    for key, value in histogram2d_plotter_kwargs.items():
        setattr(plotter, key, value)

    if save:
        plotter.savepath = str(save)
    return plotter.plot(save=bool(save))
