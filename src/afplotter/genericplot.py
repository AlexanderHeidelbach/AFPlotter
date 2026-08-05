import json
from pathlib import Path
from typing import Any

from matplotlib import pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import inset_axes, mark_inset

from afplotter.baseplotter import BasePlotter
from afplotter.utilities.plotspec import (
    PLOT_FORMAT_VERSION,
    UnserializableValue,
    decode_base_plotter,
    decode_generic_plot,
    decode_inset,
    encode_base_plotter,
    encode_generic_plot,
    encode_inset,
    warn_dropped,
)


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
        ax = self.ax
        if ax is None:
            ax = plt.subplots()[1]
            self.ax = ax
        plotmethod = getattr(ax, self.plotmethod)
        plotmethod(*self.args, **self.kwargs)

        return ax


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

    def save(self, path: str | Path, skip_unserializable: bool = False) -> None:
        """Write this plotter's specification to a JSON file.

        The saved file holds the plot's *specification*: styling, limits, text, and every
        queued overlay's method name, arguments and keyword arguments. Overlays added via
        a model function were already evaluated into sampled arrays when they were added,
        so a loaded plot re-renders them at that sampled resolution -- it cannot
        re-evaluate the model at a different binning.

        :param path: Destination file path. Any parent directory must already exist.
        :param skip_unserializable: Drop keyword arguments that cannot be saved, recording
            them in the file so :meth:`load` can warn. Positional arguments are never
            dropped.
        :raises ValueError: If any value cannot be saved and ``skip_unserializable`` is
            false. Nothing is written in that case.
        :return: None
        """
        dropped: list[str] = []
        try:
            base = encode_base_plotter(self)
            plots = []
            for index, plot in enumerate(self._plots):
                try:
                    data, plot_dropped = encode_generic_plot(plot, skip_unserializable=skip_unserializable)
                except UnserializableValue as error:
                    error.where = f"_plots[{index}]: {error.where}"
                    raise
                plots.append(data)
                dropped.extend(f"_plots[{index}]: {item}" for item in plot_dropped)
            insets = [encode_inset(inset, self._inset_refs(inset)) for inset in self._insets]
        except UnserializableValue as error:
            raise ValueError(f"Cannot save this plotter: {error.where} holds {error.value_repr}") from error

        payload = {
            "format_version": PLOT_FORMAT_VERSION,
            "base": base,
            "plots": plots,
            "insets": insets,
            "dropped": dropped,
        }
        Path(path).write_text(json.dumps(payload))

    def _inset_refs(self, inset: InsetPlot) -> dict[str, Any]:
        """Describe an inset's plots as indices into ``self._plots``.

        :param inset: The inset to describe.
        :return: ``{"plots": [<index>, ...]}``
        :raises UnserializableValue: If the inset replays an object this plotter does not own.
        """
        indices = []
        for plot in inset.plots:
            for index, own in enumerate(self._plots):
                if plot is own:
                    indices.append(index)
                    break
            else:
                raise UnserializableValue(plot, where="an inset plot this plotter does not own")
        return {"plots": indices}

    @classmethod
    def load(cls, path: str | Path) -> "GenericPlotter":
        """Read a plotter written by :meth:`save`.

        :param path: Path to a JSON file written by :meth:`save`.
        :return: An editable plotter: adjust limits, add overlays, call ``plot()``.
        :raises ValueError: If the file's ``format_version`` is unsupported, its top-level
            JSON is not an object, or a required key is missing.
        """
        payload = json.loads(Path(path).read_text())
        if not isinstance(payload, dict):
            raise ValueError(f"Malformed plot file {path}: expected a JSON object at the top level.")
        version = payload.get("format_version")
        if version != PLOT_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported format_version {version!r} in {path}; "
                f"this version of AFPlotter writes and reads format_version {PLOT_FORMAT_VERSION}."
            )
        for key in ("base", "plots", "insets"):
            if key not in payload:
                raise ValueError(f"Malformed plot file {path}: missing required key {key!r}.")

        plotter = cls()
        decode_base_plotter(plotter, payload["base"])
        plotter._plots = [decode_generic_plot(data) for data in payload["plots"]]
        plotter._insets = [
            decode_inset(data, [plotter._plots[index] for index in data["plots"]["plots"]])
            for data in payload["insets"]
        ]
        warn_dropped(payload.get("dropped", []))
        return plotter
