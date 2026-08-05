import json

import matplotlib.pyplot as plt
import numpy as np
import pytest

from afplotter.genericplot import GenericPlot, GenericPlotter


def test_generic_plot_creates_own_axes_if_none_given():
    gp = GenericPlot("plot", [0, 1], [0, 1])
    ax = gp.plot()
    assert ax is not None
    assert len(ax.lines) == 1
    plt.close(ax.figure)


def test_generic_plot_self_ax_matches_returned_axes_when_created_internally():
    # `plot()` binds a local `ax` and separately assigns `self.ax = ax` when it
    # creates its own axes. That assignment reads as redundant next to the local
    # and is easy for a future simplifier to delete unnoticed. GenericPlot is
    # public API and callers may legitimately read `.ax` after calling `plot()`,
    # so pin the identity relationship, not just non-None-ness.
    gp = GenericPlot("plot", [0, 1], [0, 1])
    ax = gp.plot()
    assert gp.ax is ax
    plt.close(ax.figure)


def test_generic_plot_uses_provided_axes():
    fig, ax = plt.subplots()
    gp = GenericPlot("scatter", [0, 1, 2], [2, 1, 0], color="red")
    gp.ax = ax
    result_ax = gp.plot()
    assert result_ax is ax
    assert len(ax.collections) == 1
    plt.close(fig)


def test_generic_plotter_saves_file(tmp_path):
    # plot(save=True) calls plt.clf() before returning, so ax content can't
    # be checked afterward — only that the file was written.
    plotter = GenericPlotter()
    plotter.xlabel = "x"
    plotter.ylabel = "y"
    plotter.add_generic_plot("plot", [0, 1, 2], [0, 1, 4], label="curve")
    plotter.savedir = str(tmp_path)
    plotter.savename = "generic_test"
    plotter.saveformat = "png"
    plotter.plot(save=True)
    assert (tmp_path / "generic_test.png").exists()


def test_generic_plotter_add_and_plot_returns_axes_with_content():
    plotter = GenericPlotter()
    plotter.add_generic_plot("plot", [0, 1, 2], [0, 1, 4], label="curve")
    ax = plotter.plot(save=False)
    assert len(ax.lines) == 1
    plt.close(ax.figure)


def test_generic_plotter_add_generic_plot_object():
    plotter = GenericPlotter()
    gp = GenericPlot("plot", [0, 1], [1, 0])
    plotter.add_generic_plot_object(gp)
    ax = plotter.plot(save=False)
    assert len(ax.lines) == 1
    plt.close(ax.figure)


def test_generic_plotter_applies_log_and_xlog():
    plotter = GenericPlotter()
    plotter.log = True
    plotter.xlog = True
    plotter.add_generic_plot("plot", [1, 2, 3], [1, 2, 3])
    ax = plotter.plot(save=False)
    assert ax.get_yscale() == "log"
    assert ax.get_xscale() == "log"
    plt.close(ax.figure)


def test_generic_plotter_multiple_plots_share_one_axes():
    plotter = GenericPlotter()
    plotter.add_generic_plot("plot", [0, 1], [0, 1], label="a")
    plotter.add_generic_plot("plot", [0, 1], [1, 0], label="b")
    ax = plotter.plot(save=False)
    assert len(ax.lines) == 2
    plt.close(ax.figure)


def test_generic_plotter_add_inset_default_plots_and_render():
    plotter = GenericPlotter()
    plotter.add_generic_plot("plot", [0, 1, 2, 3], [0, 1, 4, 9], label="curve")
    plotter.add_inset(xlim=(0, 1), title="Zoom")
    ax = plotter.plot(save=False)
    assert len(ax.figure.axes) == 2
    inset_ax = ax.figure.axes[1]
    assert len(inset_ax.lines) == 1
    assert inset_ax.get_title() == "Zoom"
    assert inset_ax.get_xlim() == (0.0, 1.0)
    plt.close(ax.figure)


def test_generic_plotter_add_inset_with_explicit_plots_and_ylim():
    plotter = GenericPlotter()
    plotter.add_generic_plot("plot", [0, 1, 2], [0, 1, 2], label="main")
    inset_only_plot = GenericPlot("plot", [0, 1, 2], [2, 1, 0], label="inset-only")
    plotter.add_inset(xlim=(0, 2), ylim=(0, 2), plots=[inset_only_plot])
    ax = plotter.plot(save=False)
    inset_ax = ax.figure.axes[1]
    assert len(inset_ax.lines) == 1
    # The explicit `plots=` override must be honored, not silently fall back
    # to the main plotter's own queued plots — check the actual rendered
    # data, not just the line count (both lists produce exactly one line).
    assert list(inset_ax.lines[0].get_ydata()) == [2, 1, 0]
    assert inset_ax.get_ylim() == (0.0, 2.0)
    plt.close(ax.figure)


def test_generic_plotter_add_inset_mark_region_false_still_renders():
    plotter = GenericPlotter()
    plotter.add_generic_plot("plot", [0, 1], [0, 1])
    plotter.add_inset(xlim=(0, 1), mark_region=False)
    ax = plotter.plot(save=False)
    assert len(ax.figure.axes) == 2
    plt.close(ax.figure)


def test_generic_plotter_add_inset_bbox_to_anchor_positioning():
    plotter = GenericPlotter()
    plotter.add_generic_plot("plot", [0, 1], [0, 1])
    plotter.add_inset(xlim=(0, 1), bbox_to_anchor=(0.5, 0.5, 0.3, 0.3), width="100%", height="100%")
    ax = plotter.plot(save=False)
    assert len(ax.figure.axes) == 2
    plt.close(ax.figure)


def test_generic_plotter_save_load_round_trips_the_base_block(tmp_path):
    """Every asserted value is deliberately non-default: a freshly-constructed plotter fails."""
    plotter = GenericPlotter()
    plotter.figsize = (7, 3)
    plotter.label = "my label"
    plotter.xlabel = "mass"
    plotter.ylabel = "events"
    plotter.watermark = "internal"
    plotter.luminosity_value = 362.4
    plotter.luminosity_unit = "ab"
    plotter.log = True
    plotter.xlog = True
    plotter.legend_max_rows = 7
    plotter.legend_title = "samples"
    plotter.legend_loc = "upper right"
    plotter.xlim = (0.5, 9.5)
    plotter.ylim = (1.0, 1e4)
    plotter.savedir = "/tmp/plots"
    plotter.saveformat = "pdf"
    plotter.savename = "limit"
    plotter.savepath = "/tmp/plots/limit.pdf"
    plotter.watermark_position = (0.1, 0.8)
    plotter.add_text("a note")
    plotter.add_generic_text(s="x", x=0.1, y=0.2)

    path = tmp_path / "p.json"
    plotter.save(path)
    loaded = GenericPlotter.load(path)

    assert loaded.figsize == (7, 3)
    assert isinstance(loaded.figsize, tuple)
    assert loaded.label == "my label"
    assert loaded.xlabel == "mass"
    assert loaded.ylabel == "events"
    assert loaded.watermark == "internal"
    assert loaded.luminosity_value == 362.4
    assert loaded.luminosity_unit == "ab"
    assert loaded.log is True
    assert loaded.xlog is True
    assert loaded.legend_max_rows == 7
    assert loaded.legend_title == "samples"
    assert loaded.legend_loc == "upper right"
    assert loaded.xlim == (0.5, 9.5)
    assert isinstance(loaded.xlim, tuple)
    assert loaded.ylim == (1.0, 1e4)
    assert loaded.savedir == "/tmp/plots"
    assert loaded.saveformat == "pdf"
    assert loaded.savename == "limit"
    assert loaded.savepath == "/tmp/plots/limit.pdf"
    assert loaded.watermark_position == (0.1, 0.8)
    assert isinstance(loaded.watermark_position, tuple)
    assert loaded.text == ["a note"]
    assert loaded.generic_text == [{"s": "x", "x": 0.1, "y": 0.2}]


def test_generic_plotter_save_load_round_trips_plots_and_insets(tmp_path):
    plotter = GenericPlotter()
    plotter.add_generic_plot("plot", np.array([1.0, 2.0]), np.array([3.0, 4.0]), color="red")
    plotter.add_generic_plot("scatter", np.array([1.0]), np.array([2.0]), marker="x")
    plotter.add_inset(xlim=(1.0, 2.0), ylim=(3.0, 4.0), title="zoom")

    path = tmp_path / "p.json"
    plotter.save(path)
    loaded = GenericPlotter.load(path)

    assert [plot.plotmethod for plot in loaded._plots] == ["plot", "scatter"]
    assert np.allclose(loaded._plots[0].args[0], [1.0, 2.0])
    assert loaded._plots[0].kwargs == {"color": "red"}
    assert loaded._plots[1].kwargs == {"marker": "x"}

    assert len(loaded._insets) == 1
    assert loaded._insets[0].xlim == (1.0, 2.0)
    assert loaded._insets[0].title == "zoom"
    # The inset must reference the loaded plotter's own live plots, not copies of them.
    assert loaded._insets[0].plots[0] is loaded._plots[0]
    assert loaded._insets[0].plots[1] is loaded._plots[1]


def test_generic_plotter_save_refuses_an_unserializable_kwarg_and_writes_nothing(tmp_path):
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    plotter = GenericPlotter()
    plotter.add_generic_plot("plot", np.array([1.0]), color="red")
    plotter.add_generic_plot("plot", np.array([1.0]), transform=ax.transAxes)

    path = tmp_path / "p.json"
    with pytest.raises(ValueError, match=r"_plots\[1\].*transform"):
        plotter.save(path)
    plt.close("all")
    assert not path.exists()


def test_generic_plotter_save_can_skip_and_load_warns(tmp_path):
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    plotter = GenericPlotter()
    plotter.add_generic_plot("plot", np.array([1.0]), color="red", transform=ax.transAxes)

    path = tmp_path / "p.json"
    plotter.save(path, skip_unserializable=True)
    plt.close("all")

    with pytest.warns(UserWarning, match="transform"):
        loaded = GenericPlotter.load(path)
    assert loaded._plots[0].kwargs == {"color": "red"}


def test_generic_plotter_load_rejects_an_unknown_format_version(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"format_version": 99, "base": {}, "plots": [], "insets": []}))
    with pytest.raises(ValueError, match="99"):
        GenericPlotter.load(path)
