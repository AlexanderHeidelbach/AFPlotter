import os

import matplotlib.pyplot as plt
import numpy as np
import pytest

from afplotter.baseplotter import BasePlotter
from afplotter.histogramplot import HistogramPlot, HistogramPlotter, HistogramVariable
from afplotter.palettes import PETROFF_PALETTE, KITColors, LMUColors, PetroffColors, get_palette
from afplotter.utilities.histogram import Histogram, HistogramEntry
from afplotter.experiments.context import set_experiment


class ConcretePlotter(BasePlotter):
    """BasePlotter is abstract only in intent (ABC with no abstract methods); subclass for testing."""


def test_baseplotter_constructs_without_env_vars(monkeypatch):
    monkeypatch.delenv("ALPS_PATH", raising=False)
    plotter = ConcretePlotter()
    assert plotter.figsize == (12, 8)


def test_default_properties():
    plotter = ConcretePlotter()
    assert plotter.xlabel == "x"
    assert plotter.ylabel == "y"
    assert plotter.log is False
    assert plotter.legend_max_rows == 4


def test_property_setters_roundtrip():
    plotter = ConcretePlotter()
    plotter.figsize = (6, 4)
    plotter.xlabel = "p_T"
    plotter.log = True
    plotter.xlim = (0.0, 10.0)
    assert plotter.figsize == (6, 4)
    assert plotter.xlabel == "p_T"
    assert plotter.log is True
    assert plotter.xlim == (0.0, 10.0)


def test_savedir_creates_directory(tmp_path):
    plotter = ConcretePlotter()
    target = tmp_path / "plots"
    plotter.savedir = str(target)
    assert target.exists()


def test_get_savestring_uses_savedir_savename_saveformat(tmp_path):
    plotter = ConcretePlotter()
    plotter.savedir = str(tmp_path)
    plotter.savename = "myplot"
    plotter.saveformat = "pdf"
    assert plotter._get_savestring() == os.path.join(str(tmp_path), "myplot.pdf")


def test_get_savestring_prefers_explicit_savepath(tmp_path):
    plotter = ConcretePlotter()
    plotter.savepath = str(tmp_path / "explicit.png")
    assert plotter._get_savestring() == str(tmp_path / "explicit.png")


def test_add_text_and_generic_text():
    plotter = ConcretePlotter()
    plotter.add_text("extra info")
    plotter.add_generic_text(x=0.1, y=0.1, s="hello")
    assert plotter.text == ["extra info"]
    assert plotter.generic_text == [{"x": 0.1, "y": 0.1, "s": "hello"}]


def test_luminosity_formats_with_zero_decimals():
    plotter = ConcretePlotter()
    plotter.luminosity_value = 408.11
    plotter.luminosity_unit = "fb"
    assert "408$" in plotter.luminosity
    assert "408.11" not in plotter.luminosity


def test_luminosity_uses_plain_integral_sign_not_mathtext_int():
    """The \\int mathtext glyph has a tall ascender/descender that overlaps
    the watermark row at large text_size; the plain unicode character avoids
    that by rendering in the regular (non-math) font instead."""
    plotter = ConcretePlotter()
    plotter.luminosity_value = 408.0
    assert "\\int" not in plotter.luminosity
    assert "∫" in plotter.luminosity


def test_add_text_to_plot_renders_watermark_and_luminosity():
    set_experiment("BelleII")
    plotter = ConcretePlotter()
    plotter.luminosity_value = 408.0
    plotter.add_text("(Preliminary)")
    fig, ax = plt.subplots()
    plotter._add_text_to_plot(ax=ax)
    texts = {t.get_text(): t for t in ax.texts}
    assert "Belle II" in texts
    assert plotter.watermark in texts
    assert plotter.luminosity in texts
    assert texts[plotter.luminosity].get_fontsize() == pytest.approx(plt.rcParams["xtick.labelsize"])
    assert "(Preliminary)" in texts
    plt.close(fig)


def test_add_text_to_plot_experiment_name_follows_set_experiment():
    """The big experiment-name text must track set_experiment(), not be hardcoded."""
    set_experiment("Generic")
    plotter = ConcretePlotter()
    fig, ax = plt.subplots()
    plotter._add_text_to_plot(ax=ax)
    texts = [t.get_text() for t in ax.texts]
    assert "Belle II" not in texts
    plt.close(fig)

    set_experiment("BelleII")
    fig, ax = plt.subplots()
    plotter._add_text_to_plot(ax=ax)
    texts = [t.get_text() for t in ax.texts]
    assert "Belle II" in texts
    plt.close(fig)


def _watermark_gap(plotter, ax):
    """Horizontal gap (axes-fraction) between the experiment-name text and the
    watermark text that follows it. Negative means they overlap."""
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    texts = {t.get_text(): t for t in ax.texts}
    experiment_bbox = texts["Belle II"].get_window_extent(renderer=renderer).transformed(ax.transAxes.inverted())
    watermark_bbox = texts[plotter.watermark].get_window_extent(renderer=renderer).transformed(ax.transAxes.inverted())
    return watermark_bbox.x0 - experiment_bbox.x1


def test_add_text_to_plot_watermark_does_not_overlap_experiment_name_at_default_size():
    """Regression test for the watermark colliding with the experiment name at the
    default (36pt base) font size — the fixed 0.130 axes-fraction offset was only
    ever tuned for the smaller font size used in the bundled examples."""
    set_experiment("BelleII")
    plotter = ConcretePlotter()
    fig, ax = plt.subplots()
    plotter._add_text_to_plot(ax=ax)
    assert _watermark_gap(plotter, ax) >= 0
    plt.close(fig)


def test_add_text_to_plot_watermark_spacing_holds_at_reduced_font_size():
    """Regression check: the fix must not break spacing at the smaller font size
    used by the bundled examples (examples/histogram_with_pull.py etc.)."""
    set_experiment("BelleII")
    plotter = ConcretePlotter()
    plotter.set_matplotlibrc_params(16)
    fig, ax = plt.subplots()
    plotter._add_text_to_plot(ax=ax)
    assert _watermark_gap(plotter, ax) >= 0
    plt.close(fig)


def _bbox(ax, renderer, label):
    text = {t.get_text(): t for t in ax.texts}[label]
    return text.get_window_extent(renderer=renderer).transformed(ax.transAxes.inverted())


def test_add_text_to_plot_luminosity_does_not_overlap_watermark_row_at_large_font_size():
    """Regression test for the \\int glyph in the luminosity row growing tall
    enough at large text_size to overlap the watermark row above it — this is
    the root cause behind the reported "integral sign overlaps the watermark"
    bug. Confirmed against the pre-fix code: gap was -0.236 (a large overlap)
    at text_size=48 before this fix."""
    set_experiment("BelleII")
    plotter = ConcretePlotter()
    plotter.set_matplotlibrc_params(48)
    plotter.luminosity_value = 408.0
    fig, ax = plt.subplots()
    plotter._add_text_to_plot(ax=ax)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    watermark_bbox = _bbox(ax, renderer, plotter.watermark)
    luminosity_bbox = _bbox(ax, renderer, plotter.luminosity)
    assert watermark_bbox.y0 >= luminosity_bbox.y1
    plt.close(fig)


def test_add_text_to_plot_luminosity_spacing_holds_at_reduced_font_size():
    """Regression check: the fix must not break spacing at the smaller font
    size used by the bundled examples (examples/histogram_with_pull.py etc.)."""
    set_experiment("BelleII")
    plotter = ConcretePlotter()
    plotter.set_matplotlibrc_params(16)
    plotter.luminosity_value = 408.0
    fig, ax = plt.subplots()
    plotter._add_text_to_plot(ax=ax)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    watermark_bbox = _bbox(ax, renderer, plotter.watermark)
    luminosity_bbox = _bbox(ax, renderer, plotter.luminosity)
    assert watermark_bbox.y0 >= luminosity_bbox.y1
    plt.close(fig)


def test_add_text_to_plot_luminosity_does_not_overlap_watermark_through_real_plotter_pipeline():
    """Integration regression: the unit-level tests above call `_add_text_to_plot`
    directly against a bare `plt.subplots()` axes, so they never exercise the real
    `HistogramPlotter.plot()` pipeline where `_add_axislabels`/`_add_legend` run
    *after* `_add_text_to_plot` and `figure.autolayout` can still shrink the axes
    box afterward (see the CLAUDE.md gotcha on layout-timing). Guards against a
    future regression reintroducing the overlap once the real pipeline is involved."""
    set_experiment("BelleII")

    hist = Histogram()
    hist.binning = np.linspace(-3, 3, 21)
    hist.add_entry(HistogramEntry(name="signal", array=np.random.default_rng(0).normal(0, 1, 200)))
    histplot = HistogramPlot(hist)

    variable = HistogramVariable("x", "a.u.")
    plotter = HistogramPlotter(histplot, variable)
    plotter.set_matplotlibrc_params(36)
    plotter.luminosity_value = 62.8
    plotter.add_text("(Preliminary)")

    ax, ax_diff = plotter.plot(save=False)
    assert ax_diff is None

    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    watermark_bbox = _bbox(ax, renderer, plotter.watermark)
    luminosity_bbox = _bbox(ax, renderer, plotter.luminosity)
    assert watermark_bbox.y0 >= luminosity_bbox.y1
    plt.close(ax.figure)


def test_add_text_to_plot_extra_text_rows_do_not_overlap_luminosity_at_large_font_size():
    """add_text() rows must stack below the luminosity row without overlap
    too — the fix applies to every row, not just the luminosity one."""
    set_experiment("BelleII")
    plotter = ConcretePlotter()
    plotter.set_matplotlibrc_params(48)
    plotter.luminosity_value = 408.0
    plotter.add_text("(Preliminary)")
    fig, ax = plt.subplots()
    plotter._add_text_to_plot(ax=ax)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    luminosity_bbox = _bbox(ax, renderer, plotter.luminosity)
    extra_bbox = _bbox(ax, renderer, "(Preliminary)")
    assert luminosity_bbox.y0 >= extra_bbox.y1
    plt.close(fig)


def test_add_text_to_plot_multiple_extra_text_rows_stack_without_overlap():
    """Two add_text() rows must not overlap each other either."""
    set_experiment("BelleII")
    plotter = ConcretePlotter()
    plotter.set_matplotlibrc_params(48)
    plotter.add_text("(Preliminary)")
    plotter.add_text("Signal region")
    fig, ax = plt.subplots()
    plotter._add_text_to_plot(ax=ax)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    first_bbox = _bbox(ax, renderer, "(Preliminary)")
    second_bbox = _bbox(ax, renderer, "Signal region")
    assert first_bbox.y0 >= second_bbox.y1
    plt.close(fig)


def test_set_axislimits_linear_expands_ylim_for_legend():
    plotter = ConcretePlotter()
    plotter.legend_max_rows = 2
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    original_top = ax.get_ylim()[1]
    plotter._set_axislimits(ax=ax)
    assert ax.get_ylim()[1] > original_top
    plt.close(fig)


def test_set_axislimits_respects_explicit_ylim():
    plotter = ConcretePlotter()
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    plotter._set_axislimits(ax=ax, ylim=(0.0, 5.0))
    assert ax.get_ylim() == (0.0, 5.0)
    plt.close(fig)


def test_add_legend_combines_multiple_axes():
    plotter = ConcretePlotter()
    fig, (ax1, ax2) = plt.subplots(1, 2)
    ax1.plot([0, 1], [0, 1], label="a")
    ax2.plot([0, 1], [1, 0], label="b")
    plotter._add_legend(ax=[ax1, ax2])
    legend_texts = [t.get_text() for t in ax1.get_legend().get_texts()]
    assert legend_texts == ["a", "b"]
    plt.close(fig)


def test_kit_colors_defines_kit_hexes():
    assert KITColors.kit_green == "#009682"
    assert KITColors.kit_red == "#a22223"


def test_lmu_colors_defines_lmu_hexes():
    assert LMUColors.lmu_green == "#00883A"
    assert LMUColors.lmu_blue == "#0F1987"
    assert LMUColors.lmu_orange == "#F18700"


def test_petroff_palette_holds_red_out_of_the_cycle():
    # The full Petroff 10 sequence, minus its red, is what may be handed to
    # background components. Red must be reachable only as the signal colour.
    assert PETROFF_PALETTE.background == [
        "#3f90da",
        "#ffa90e",
        "#94a4a2",
        "#832db6",
        "#a96b59",
        "#e76300",
        "#b9ac70",
        "#717581",
        "#92dadd",
    ]
    assert PetroffColors.red == "#bd1f01"
    assert PetroffColors.red not in PETROFF_PALETTE.background


def test_signal_color_defaults_to_the_reserved_petroff_red():
    assert get_palette().signal == "#bd1f01"
    assert get_palette().signal == PetroffColors.red


def test_constructing_a_plotter_installs_the_petroff_cycle():
    # Regression guard: BasePlotter.__init__ applies the experiment .mplstyle and
    # *then* set_matplotlibrc_params(). The active palette's cycle must survive.
    plt.rcParams["axes.prop_cycle"] = plt.cycler("color", ["#123456"])
    ConcretePlotter()
    assert plt.rcParams["axes.prop_cycle"].by_key()["color"] == PETROFF_PALETTE.background


def test_set_matplotlibrc_params_default_text_size_36():
    plotter = ConcretePlotter()
    plotter.set_matplotlibrc_params()  # default text_size=36
    assert plt.rcParams["xtick.labelsize"] == pytest.approx(28.8)  # 0.8 * 36
    assert plt.rcParams["axes.labelsize"] == pytest.approx(36.0)
    assert plt.rcParams["legend.fontsize"] == pytest.approx(21.6)  # 36 * 0.6
    assert plt.rcParams["legend.title_fontsize"] == pytest.approx(18.0)  # 36 * 0.5
    assert plt.rcParams["font.size"] == pytest.approx(36.0)
    assert plt.rcParams["savefig.dpi"] == pytest.approx(300.0)


def test_set_matplotlibrc_params_scales_with_text_size():
    plotter = ConcretePlotter()
    plotter.set_matplotlibrc_params(text_size=40)
    assert plt.rcParams["xtick.labelsize"] == 32.0  # 0.8 * 40
    assert plt.rcParams["axes.labelsize"] == 40.0
    assert plt.rcParams["legend.fontsize"] == 24.0  # 40 * 0.6


def test_module_level_set_matplotlibrc_params_is_directly_callable():
    from afplotter.baseplotter import set_matplotlibrc_params

    set_matplotlibrc_params(text_size=25)
    assert plt.rcParams["font.size"] == 25.0
