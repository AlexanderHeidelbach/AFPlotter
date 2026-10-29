from typing import Any
import numbers
import os
import numpy as np
from abc import ABC
from cycler import cycler
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from afplotter.experiments.context import get_experiment
from afplotter.palettes import get_palette

PathType = str | os.PathLike


def set_matplotlibrc_params(text_size: int = 36) -> None:
    """
    Sets default matplotlibrc parameters, scaled relative to a base text size.

    :param text_size: Base font size in points that tick/axis/legend sizes
        and geometry are derived from. Defaults to 36 (paper-ready — legible
        after a figure is shrunk to fit a paper column).
    :return: None
    """
    latex_text_size = text_size
    tick_label_size = 0.8 * latex_text_size

    major_tick_len = max(5, 0.25 * latex_text_size)
    minor_tick_len = max(3, 0.12 * latex_text_size)
    major_tick_w = max(1.0, 0.06 * latex_text_size)
    minor_tick_w = max(0.8, 0.04 * latex_text_size)

    xtick = {
        "top": True,
        "minor.visible": True,
        "direction": "in",
        "labelsize": tick_label_size,
        "major.pad": 10,
        "major.size": major_tick_len,
        "minor.size": minor_tick_len,
        "major.width": major_tick_w,
        "minor.width": minor_tick_w,
    }

    ytick = {
        "right": True,
        "minor.visible": True,
        "direction": "in",
        "labelsize": tick_label_size,
        "major.size": major_tick_len,
        "minor.size": minor_tick_len,
        "major.width": major_tick_w,
        "minor.width": minor_tick_w,
    }

    axes = {
        "labelsize": latex_text_size,
        "prop_cycle": cycler("color", get_palette().background),
        "formatter.limits": (-4, 4),
        "formatter.use_mathtext": True,
        "titlesize": latex_text_size,
        "labelpad": 4.0,
        "linewidth": max(1.0, 0.05 * latex_text_size),
    }

    lines = {"lw": 1.5}

    legend = {
        "frameon": False,
        "fontsize": latex_text_size * 0.6,
        "title_fontsize": latex_text_size * 0.5,
    }

    plt.rc("lines", **lines)
    plt.rc("axes", **axes)
    plt.rc("xtick", **xtick)
    plt.rc("ytick", **ytick)
    plt.rc("legend", **legend)

    plt.rcParams.update(
        {
            "font.size": latex_text_size,
            "figure.autolayout": True,
            "savefig.dpi": 300,
            "figure.dpi": 150,
        }
    )


class BasePlotter(ABC):
    """Abstract plotter class to set basic properties for specific plots"""

    def __init__(self) -> None:
        get_experiment()
        set_matplotlibrc_params()
        self._figsize: tuple[int, int] = (12, 8)
        self._label: str | list[str | None] | None = "label"
        self._xlabel: str = "x"
        self._ylabel: str = "y"
        self._watermark: str = "(own work)"
        self._luminosity_value: float = 0.0
        self._luminosity_unit: str = "fb"
        self._log: bool = False
        self._xlog: bool = False
        self._legend_max_rows: int = 4
        self._legend_short_column: str = "last"
        self._legend_column_sizes: list[int] | None = None
        self._legend_title: str | None = None
        self._legend_loc: str = "best"
        self._xlim: tuple[float, float] | None = None
        self._ylim: tuple[float, float] | None = None
        self._savedir: PathType = "./"
        self._saveformat: str = "png"
        self._savename: str = "plot"
        self._savepath: str = ""
        self._watermark_position: tuple = (0.033, 0.915)

        self.text: list[str] = []
        self.generic_text: list[dict] = []

    @property
    def figsize(self) -> tuple[int, int]:
        return self._figsize

    @figsize.setter
    def figsize(self, figsize: tuple[int, int]) -> None:
        self._figsize = figsize

    @property
    def label(self) -> str | list[str | None] | None:
        return self._label

    @label.setter
    def label(self, label: str | list[str | None] | None) -> None:
        self._label = label

    @property
    def xlabel(self) -> str:
        return self._xlabel

    @xlabel.setter
    def xlabel(self, xlabel: str) -> None:
        self._xlabel = xlabel

    @property
    def ylabel(self) -> str:
        return self._ylabel

    @ylabel.setter
    def ylabel(self, ylabel: str) -> None:
        self._ylabel = ylabel

    @property
    def watermark(self) -> str:
        return self._watermark

    @watermark.setter
    def watermark(self, watermark: str) -> None:
        self._watermark = watermark

    @property
    def luminosity_value(self) -> float:
        return self._luminosity_value

    @luminosity_value.setter
    def luminosity_value(self, luminosity_value: float) -> None:
        self._luminosity_value = luminosity_value

    @property
    def luminosity_unit(self) -> str:
        return self._luminosity_unit

    @luminosity_unit.setter
    def luminosity_unit(self, luminosity_unit: str) -> None:
        self._luminosity_unit = luminosity_unit

    @property
    def luminosity(self) -> str:
        return f"∫$L\\,\\mathrm{{d}}t\\;=\\;${self.luminosity_value:.0f}$\\;\\mathrm{{{self.luminosity_unit}}}^{{-1}}$"

    @property
    def legend_max_rows(self) -> int:
        """Maximum number of entries stacked in one legend column.

        The legend's column count is derived from this, not set by it:
        ``ncol = ceil(len(labels) / legend_max_rows)``. Raising this value
        therefore produces *fewer*, taller columns; lowering it produces more,
        shorter ones. To force a single column, set it to at least the number
        of legend entries. Columns are filled top-down to this cap; only the
        last column is shorter (matplotlib alone would spread entries evenly);
        see ``legend_short_column`` to move or spread the short column and
        ``legend_column_sizes`` to set every column's size explicitly.

        :return: The per-column row cap. Defaults to 4.
        """
        return self._legend_max_rows

    @legend_max_rows.setter
    def legend_max_rows(self, legend_max_rows: int) -> None:
        """Set the maximum number of entries stacked in one legend column.

        :param legend_max_rows: The per-column row cap. Values below 1 are not
            validated here; 0 raises ZeroDivisionError when the legend is drawn.
        """
        self._legend_max_rows = legend_max_rows

    @property
    def legend_short_column(self) -> str:
        """Where the short column goes when entries do not fill the legend grid.

        ``"last"`` fills columns to ``legend_max_rows`` and leaves the last one short,
        ``"first"`` leaves the first one short, ``"balanced"`` lets matplotlib spread
        entries as evenly as possible (no placeholders). Ignored when
        ``legend_column_sizes`` is set.

        :return: One of ``"last"``, ``"first"``, ``"balanced"``. Defaults to ``"last"``.
        """
        return self._legend_short_column

    @legend_short_column.setter
    def legend_short_column(self, legend_short_column: str) -> None:
        """Set the short-column mode.

        :param legend_short_column: One of ``"last"``, ``"first"``, ``"balanced"``.
        :raises ValueError: If the value is not an allowed mode.
        """
        allowed = ("last", "first", "balanced")
        if legend_short_column not in allowed:
            raise ValueError(f"legend_short_column must be one of {allowed}, got {legend_short_column!r}")
        self._legend_short_column = legend_short_column

    @property
    def legend_column_sizes(self) -> list[int] | None:
        """Explicit number of entries in each legend column, left to right.

        When set, it wins over ``legend_max_rows`` and ``legend_short_column``: the column
        count is ``len(sizes)`` and entries are assigned in order. The sizes must sum to
        the number of legend entries, otherwise drawing the legend raises ``ValueError``.

        :return: A copy of the column sizes (mutating it does not affect the plotter), or None for automatic layout.
        """
        return None if self._legend_column_sizes is None else list(self._legend_column_sizes)

    @legend_column_sizes.setter
    def legend_column_sizes(self, legend_column_sizes: list[int] | None) -> None:
        """Set the explicit column sizes.

        :param legend_column_sizes: Positive column sizes, or None for automatic layout. Stored as a copy.
        :raises ValueError: If the list is empty or any size is not an integer >= 1.
        """
        if legend_column_sizes is None:
            self._legend_column_sizes = None
            return
        sizes = list(legend_column_sizes)
        if (
            not sizes
            or not all(isinstance(size, numbers.Integral) and not isinstance(size, bool) for size in sizes)
            or any(size < 1 for size in sizes)
        ):
            raise ValueError(f"legend_column_sizes must be a non-empty list of integers >= 1, got {sizes!r}")
        self._legend_column_sizes = [int(size) for size in sizes]

    @property
    def legend_title(self) -> str | None:
        return self._legend_title

    @legend_title.setter
    def legend_title(self, legend_title: str) -> None:
        self._legend_title = legend_title

    @property
    def legend_loc(self) -> str:
        return self._legend_loc

    @legend_loc.setter
    def legend_loc(self, legend_loc: str) -> None:
        self._legend_loc = legend_loc

    @property
    def log(self) -> bool:
        return self._log

    @log.setter
    def log(self, log: bool) -> None:
        self._log = log

    @property
    def xlog(self) -> bool:
        return self._xlog

    @xlog.setter
    def xlog(self, log: bool) -> None:
        self._xlog = log

    @property
    def xlim(self) -> tuple[float, float] | None:
        return self._xlim

    @xlim.setter
    def xlim(self, xlim: tuple[float, float]) -> None:
        self._xlim = xlim

    @property
    def ylim(self) -> tuple[float, float] | None:
        return self._ylim

    @ylim.setter
    def ylim(self, ylim: tuple[float, float]) -> None:
        self._ylim = ylim

    @property
    def savedir(self) -> PathType:
        return self._savedir

    @savedir.setter
    def savedir(self, savedir: PathType) -> None:
        if not os.path.exists(savedir):
            os.makedirs(savedir)
        self._savedir = savedir

    @property
    def saveformat(self) -> str:
        return self._saveformat

    @saveformat.setter
    def saveformat(self, saveformat: str) -> None:
        self._saveformat = saveformat

    @property
    def savename(self) -> str:
        return self._savename

    @savename.setter
    def savename(self, savename: str) -> None:
        self._savename = savename

    @property
    def savepath(self) -> str:
        return self._savepath

    @savepath.setter
    def savepath(self, savepath: str) -> None:
        self._savepath = savepath

    @property
    def watermark_position(self) -> tuple:
        return self._watermark_position

    @watermark_position.setter
    def watermark_position(self, watermark_position: tuple) -> None:
        self._watermark_position = watermark_position

    def set_matplotlibrc_params(self, text_size: int = 36) -> None:
        """
        Rescale matplotlib rcParams for this plot (e.g. for a presentation-sized figure).

        :param text_size: Base font size in points. Defaults to 36 (paper-ready).
        :return: None
        """
        set_matplotlibrc_params(text_size)

    def add_text(self, text: str) -> None:
        self.text.append(text)

    def add_generic_text(self, **text_kwargs: dict[Any, Any]) -> None:
        self.generic_text.append(text_kwargs)

    def _get_savestring(self) -> PathType:
        """Concatinates savedir, savename and saveformat to full savepath"""
        return os.path.join(self.savedir, f"{self.savename}.{self.saveformat}") if not self.savepath else self.savepath

    def _add_text_to_plot(self, ax: plt.Axes) -> None:
        """Handling of different texts in the plot."""
        x = self.watermark_position[0]
        y = self.watermark_position[1]
        row_margin = 0.01
        experiment_text = ax.text(
            x,
            y,
            get_experiment().labels.get("experiment", ""),
            ha="left",
            transform=ax.transAxes,
            style="italic",
            alpha=0.95,
            weight="bold",
            fontsize=plt.rcParams["xtick.labelsize"],
        )
        # The watermark's x-position depends on the rendered width of the
        # experiment-name text above, which varies with font size and the
        # experiment's name itself — a fixed offset only holds for one font size.
        ax.figure.canvas.draw()
        renderer = ax.figure.canvas.get_renderer()  # type: ignore
        experiment_bbox = experiment_text.get_window_extent(renderer=renderer).transformed(ax.transAxes.inverted())
        watermark_text = ax.text(
            experiment_bbox.x1 + 0.02,
            y,
            self.watermark,
            ha="left",
            transform=ax.transAxes,
            alpha=0.8,
            fontsize=plt.rcParams["xtick.labelsize"],
        )
        # Rows below this one start from the lower of the two texts sharing
        # it, so spacing tracks whichever glyph actually descends furthest
        # (e.g. italics, descenders, or — for the luminosity row below — the
        # tall integral sign) instead of a fixed fraction tuned for one font
        # size only.
        watermark_bbox = watermark_text.get_window_extent(renderer=renderer).transformed(ax.transAxes.inverted())
        y_cursor = min(experiment_bbox.y0, watermark_bbox.y0) - row_margin

        if self.luminosity_value:
            luminosity_text = ax.text(
                x,
                y_cursor,
                self.luminosity,
                ha="left",
                va="top",
                transform=ax.transAxes,
                alpha=0.8,
                fontsize=plt.rcParams["xtick.labelsize"],
            )
            luminosity_bbox = luminosity_text.get_window_extent(renderer=renderer).transformed(ax.transAxes.inverted())
            y_cursor = luminosity_bbox.y0 - row_margin

        for text in self.text:
            extra_text = ax.text(
                x,
                y_cursor,
                text,
                ha="left",
                va="top",
                transform=ax.transAxes,
                alpha=0.8,
                fontsize=plt.rcParams["legend.fontsize"],
            )
            extra_bbox = extra_text.get_window_extent(renderer=renderer).transformed(ax.transAxes.inverted())
            y_cursor = extra_bbox.y0 - row_margin

        for text_wargs in self.generic_text:
            text_wargs["transform"] = ax.transAxes
            ax.text(**text_wargs)

    def _add_axislabels(
        self,
        xax: plt.Axes | None = None,
        yax: plt.Axes | None = None,
        xlabel: str | None = None,
        ylabel: str | None = None,
    ) -> None:
        """Set axis labels for histogram plots

        Args:
            xax (plt.Axes): x-ax to plot on
            yax (plt.Axes): y-ax to plot on
        """

        if xax is not None:
            label = self.xlabel if xlabel is None else xlabel

            off_set = xax.xaxis.get_offset_text().get_text()
            if off_set:
                xax.xaxis.offsetText.set_visible(False)
                label += off_set

            xax.set_xlabel(label)

        if yax is not None:
            label = self.ylabel if ylabel is None else ylabel

            off_set = yax.yaxis.get_offset_text().get_text()
            if off_set:
                yax.yaxis.offsetText.set_visible(False)
                label += off_set

            yax.set_ylabel(label)

    def _set_axislimits(self, ax: plt.Axes, ylim: tuple[float, float] | None = None) -> None:
        """Set axis limits depending on number of legend and text lines"""
        xlim = self.xlim
        ylim = self.ylim if ylim is None else ylim
        lines_legend = self.legend_max_rows
        lines_text = len(self.text) + 1
        if xlim is not None:
            ax.set_xlim(left=xlim[0], right=xlim[1])
        if ylim is None:
            ax.set_ylim(
                bottom=ax.get_ylim()[0],
                top=(
                    ax.get_ylim()[1] * (1 + 0.1 * lines_legend * np.sign(ax.get_ylim()[1]))
                    if not self.log
                    else ax.get_ylim()[1] * (1 + 10 ** (max([lines_legend, lines_text]) / 2))
                ),
            )
        else:
            ax.set_ylim(bottom=ylim[0], top=ylim[1])

    def _add_legend(self, ax: list[plt.Axes] | plt.Axes, *, use_column_sizes: bool = True) -> None:
        """Addition of legend with respect to number of labels.

        :param ax: Axes (or list of axes) whose labelled artists form the legend.
        :param use_column_sizes: If False, ignore ``legend_column_sizes`` and lay out automatically.
        """
        if not isinstance(ax, list):
            ax = [ax]
        lines, labels = [], []
        for axis in ax:
            line, label = axis.get_legend_handles_labels()
            lines.extend(line)
            labels.extend(label)

        if labels:
            n = len(labels)
            cap = self.legend_max_rows
            sizes = self.legend_column_sizes if use_column_sizes else None
            counts: list[int] | None
            if sizes is not None:
                if sum(sizes) != n:
                    raise ValueError(
                        f"legend_column_sizes {sizes} sum to {sum(sizes)}, but there are {n} legend entries on this axes"
                    )
                counts = list(sizes)
                ncol = len(counts)
            else:
                ncol = n // cap + (1 if n % cap != 0 else 0)
                counts = None
                if self.legend_short_column != "balanced":
                    counts = [cap] * (ncol - 1) + [n - cap * (ncol - 1)]
                    if self.legend_short_column == "first":
                        counts.reverse()
            if counts is not None and len(set(counts)) > 1:
                # matplotlib splits entries evenly across columns; pad each column with invisible
                # placeholders to a full rectangular grid so the columns come out as requested.
                height = max(counts)
                padded_lines, padded_labels = [], []
                start = 0
                for count in counts:
                    padded_lines.extend(lines[start : start + count])
                    padded_labels.extend(labels[start : start + count])
                    for _ in range(height - count):
                        padded_lines.append(Line2D([], [], linestyle="none", marker=""))
                        padded_labels.append("")
                    start += count
                lines, labels = padded_lines, padded_labels
            legend_kwargs: dict[str, Any] = {
                "ncol": ncol,
                "title": self.legend_title,
                "loc": self.legend_loc,
            }
            ax[0].legend(lines, labels, **legend_kwargs)
