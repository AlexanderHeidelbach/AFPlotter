from typing import Any

from matplotlib import pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import inset_axes, mark_inset

from afplotter.baseplotter import BasePlotter


class GenericPlot:
    def __init__(self, plotmethod: str, *args: Any, **kwargs: Any) -> None:
        self.plotmethod = plotmethod
        self.args = args
        self.kwargs = kwargs
        self._ax: plt.Axes | None = None

    @property
    def ax(self) -> plt.Axes | None:
        return self._ax

    @ax.setter
    def ax(self, ax: plt.Axes) -> None:
        self._ax = ax

    def plot(self) -> plt.Axes:
        if self.ax is None:
            self.ax = plt.subplots()[1]
        plotmethod = getattr(self.ax, self.plotmethod)
        plotmethod(*self.args, **self.kwargs)

        return self.ax


class InsetPlot:
    """A zoomed-in inset axes that replays a set of GenericPlot-like objects."""

    def __init__(
        self,
        plots: list[Any],
        xlim: tuple[float, float],
        ylim: tuple[float, float] | None = None,
        width: str = "38%",
        height: str = "38%",
        loc: str = "upper center",
        borderpad: float = 1.0,
        title: str | None = None,
        mark_region: bool = True,
        mark_kwargs: dict[str, Any] | None = None,
        tick_labelsize: float = 8,
        title_fontsize: float = 15,
        bbox_to_anchor: tuple[float, float, float, float] | None = None,
    ) -> None:
        self.plots = plots
        self.xlim = xlim
        self.ylim = ylim
        self.width = width
        self.height = height
        self.loc = loc
        self.borderpad = borderpad
        self.title = title
        self.mark_region = mark_region
        self.mark_kwargs = mark_kwargs or {}
        self.tick_labelsize = tick_labelsize
        self.title_fontsize = title_fontsize
        self.bbox_to_anchor = bbox_to_anchor  # (x0, y0, w, h)

    def plot(self, parent_ax: plt.Axes) -> plt.Axes:
        """
        Render this inset onto parent_ax: creates the inset axes, replays
        every queued plot object onto it, applies limits/title/tick sizes,
        and optionally marks the zoomed region on the parent axes.

        :param parent_ax: The main axes this inset is placed relative to.
        :return: The new inset Axes.
        """
        if self.bbox_to_anchor is not None:
            axins = inset_axes(
                parent_ax,
                width=self.width,
                height=self.height,
                bbox_to_anchor=self.bbox_to_anchor,
                bbox_transform=parent_ax.transAxes,
                borderpad=0,
            )
        else:
            axins = inset_axes(
                parent_ax,
                width=self.width,
                height=self.height,
                loc=self.loc,
                borderpad=self.borderpad,
            )

        for plot in self.plots:
            plot.ax = axins
            plot.plot()

        axins.set_xlim(*self.xlim)
        if self.ylim:
            axins.set_ylim(*self.ylim)

        if self.title:
            axins.set_title(self.title, fontsize=self.title_fontsize)

        axins.tick_params(labelsize=self.tick_labelsize)

        if self.mark_region:
            kwargs = dict(loc1=2, loc2=4, fc="none", ec="0.35", lw=1.2)
            kwargs.update(self.mark_kwargs)
            mark_inset(parent_ax, axins, **kwargs)

        return axins


class GenericPlotter(BasePlotter):
    def __init__(self) -> None:
        super().__init__()

        self._plots: list[GenericPlot] = []
        self._insets: list[InsetPlot] = []

    def add_generic_plot(self, plotmethod: str, *args: Any, **kwargs: Any) -> None:
        self._plots.append(GenericPlot(plotmethod, *args, **kwargs))

    def add_generic_plot_object(self, generic_plot: GenericPlot) -> None:
        self._plots.append(generic_plot)

    def add_inset(
        self,
        xlim: tuple[float, float],
        ylim: tuple[float, float] | None = None,
        plots: list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Queue an inset (zoomed sub-region) axes to be rendered when plot() runs.

        :param xlim: Data x-limits the inset should be clipped to.
        :param ylim: Optional data y-limits the inset should be clipped to.
        :param plots: Objects to replay in the inset; defaults to this
            plotter's own queued plots (same content, zoomed).
        :param kwargs: Forwarded to InsetPlot (width, height, loc, title,
            mark_region, mark_kwargs, tick_labelsize, title_fontsize, bbox_to_anchor).
        :return: None
        """
        if plots is None:
            plots = self._plots

        self._insets.append(InsetPlot(plots=plots, xlim=xlim, ylim=ylim, **kwargs))

    def plot(self, save: bool = False) -> plt.Axes:
        fig = plt.figure(figsize=self.figsize)
        ax = fig.add_subplot(1, 1, 1)

        for plot in self._plots:
            plot.ax = ax
            plot.plot()

        for inset in self._insets:
            inset.plot(parent_ax=ax)

        self._add_text_to_plot(ax=ax)
        self._add_legend(ax=ax)

        if self.xlog:
            ax.set_xscale("log")

        if self.log:
            ax.set_yscale("log")

        self._set_axislimits(ax=ax)
        self._add_axislabels(xax=ax, yax=ax)

        if save:
            plt.savefig(self._get_savestring())
            plt.clf()
            plt.close()

        else:
            plt.show()

        return ax
