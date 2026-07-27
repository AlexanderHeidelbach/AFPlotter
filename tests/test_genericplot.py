import matplotlib.pyplot as plt
import pytest

from afplotter.genericplot import GenericPlot, GenericPlotter


def test_generic_plot_creates_own_axes_if_none_given():
    gp = GenericPlot("plot", [0, 1], [0, 1])
    ax = gp.plot()
    assert ax is not None
    assert len(ax.lines) == 1
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
