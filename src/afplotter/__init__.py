"""AFPlotter: a standalone HEP plotting library."""

from afplotter.baseplotter import BasePlotter
from afplotter.convenience import plot_2d_histogram, plot_histogram, plot_histogram_from_files
from afplotter.experiments.context import get_experiment, set_experiment
from afplotter.genericplot import GenericPlot, GenericPlotter, InsetPlot
from afplotter.histogramplot import (
    Histogram2DPlot,
    Histogram2DPlotter,
    HistogramPlot,
    HistogramPlotter,
    HistogramVariable,
)
from afplotter.palettes import (
    KIT_PALETTE,
    LMU_PALETTE,
    PETROFF_PALETTE,
    KITColors,
    LMUColors,
    Palette,
    PetroffColors,
    get_palette,
    register_palette,
    set_palette,
)
from afplotter.selectionparser.polars import SelectionOperator, SelectionParser
from afplotter.utilities.histogram import Histogram, HistogramEntry
from afplotter.utilities.lazyhistogram import LazyHistEntry, LazyHistWrapper
