import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_hex

from afplotter import palettes
from afplotter.experiments.context import set_experiment
from afplotter.histogramplot import HistogramPlot, HistogramPlotter, HistogramVariable
from afplotter.utilities.histogram import Histogram, HistogramEntry


def test_set_palette_by_name():
    p = palettes.set_palette("KIT")
    assert p.name == "KIT"
    assert palettes.get_palette().name == "KIT"


def test_set_palette_defaults_to_petroff():
    p = palettes.set_palette()
    assert p.name == "Petroff"


def test_get_palette_without_set_defaults_to_petroff():
    assert palettes.get_palette().name == "Petroff"


def test_set_palette_updates_rcparams_immediately():
    plt.rcParams["axes.prop_cycle"] = plt.cycler("color", ["#123456"])
    palettes.set_palette("KIT")
    assert plt.rcParams["axes.prop_cycle"].by_key()["color"] == palettes.KIT_PALETTE.background


def test_kit_palette_excludes_kit_red_and_reserves_it_as_signal():
    assert palettes.KITColors.kit_red not in palettes.KIT_PALETTE.background
    assert palettes.KIT_PALETTE.signal == palettes.KITColors.kit_red


def test_lmu_palette_excludes_lmu_red_and_reserves_it_as_signal():
    assert palettes.LMUColors.lmu_red not in palettes.LMU_PALETTE.background
    assert palettes.LMU_PALETTE.signal == palettes.LMUColors.lmu_red


def test_petroff_palette_excludes_red_and_reserves_it_as_signal():
    assert palettes.PetroffColors.red not in palettes.PETROFF_PALETTE.background
    assert palettes.PETROFF_PALETTE.signal == palettes.PetroffColors.red


def test_kit_palette_survives_an_experiment_switch_end_to_end():
    """A non-default palette must still be the one that reaches rendered pixels.

    Regression guard for a hardcoded ``axes.prop_cycle`` in a bundled .mplstyle
    silently overriding whatever palette the user selected via set_palette().
    """
    palettes.set_palette("KIT")
    set_experiment("BelleII")

    rng = np.random.default_rng(seed=3)
    hist = Histogram()
    hist.binning = np.linspace(0, 10, 21)
    hist.add_entry(HistogramEntry(name="bkg0", latex_name="B0", array=rng.uniform(0, 10, 400)))
    hist.add_entry(HistogramEntry(name="bkg1", latex_name="B1", array=rng.uniform(0, 10, 400)))
    hist.add_entry(
        HistogramEntry(name="sig0", latex_name="S0", array=rng.normal(5, 1, 300), type="signal")
    )

    histplot = HistogramPlot(hist)
    histplot.stacked = True
    histplot.sig_extra = True
    plotter = HistogramPlotter(histplot, HistogramVariable("$M$", "GeV"))
    ax, _ = plotter.plot(save=False)

    colors = {
        patch.get_label(): (to_hex(patch.get_facecolor()), to_hex(patch.get_edgecolor()))
        for patch in ax.patches
    }
    plt.close(ax.figure)

    assert colors["B0"][0] == palettes.KIT_PALETTE.background[0]
    assert colors["S0"][1] == palettes.KIT_PALETTE.signal
    assert palettes.KIT_PALETTE.signal == "#a22223"
