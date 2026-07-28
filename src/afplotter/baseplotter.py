from typing import Any, Optional, Union, List, Tuple, Dict
import os
import numpy as np
from abc import ABC
from cycler import cycler
import matplotlib.pyplot as plt

from afplotter.experiments.context import get_experiment

PathType = Union[str, os.PathLike]


class KITColors:
    """
    KIT color scheme plus additional grey shades
    """

    kit_green = "#009682"  # type: str
    kit_blue = "#4664aa"  # type: str
    kit_maygreen = "#8cb63c"  # type: str
    kit_yellow = "#fce500"  # type: str
    kit_orange = "#df9b1b"  # type: str
    kit_brown = "#a7822e"  # type: str
    kit_red = "#a22223"  # type: str
    kit_purple = "#a3107c"  # type: str
    kit_cyan = "#23a1e0"  # type: str
    kit_black = "#000000"  # type: str
    white = "#ffffff"  # type: str
    light_grey = "#bdbdbd"  # type: str
    grey = "#797979"  # type: str
    dark_grey = "#4e4e4e"  # type: str

    lmu_green = "#00883A"  # R 0,   G 136, B 58
    lmu_blue = "#0F1987"  # R 15,  G 25,  B 135
    lmu_cyan = "#643BE3"  # R 100, G 59,  B 227
    lmu_violet = "#8C4091"  # R 140, G 64,  B 145
    lmu_red = "#D71919"  # R 215, G 25,  B 25
    lmu_orange = "#F18700"  # R 241, G 135, B 0

    default_colors = [
        kit_green,
        kit_blue,
        kit_red,
        kit_cyan,
        kit_orange,
        kit_maygreen,
        kit_yellow,
        kit_purple,
        kit_brown,
        dark_grey,
    ]  # type: List[str]


kit_color_cycler = cycler("color", KITColors.default_colors)


def set_matplotlibrc_params(text_size: int = 25) -> None:
    """
    Sets default matplotlibrc parameters, scaled relative to a base text size.

    :param text_size: Base font size in points that tick/axis/legend sizes
        and geometry are derived from. Defaults to 25.
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
        "prop_cycle": kit_color_cycler,
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
        self._figsize: Tuple[int, int] = (12, 8)
        self._label: Optional[Union[str, List[Optional[str]]]] = "label"
        self._xlabel: str = "x"
        self._ylabel: str = "y"
        self._watermark: str = "(own work)"
        self._luminosity_value: float = 0.0
        self._luminosity_unit: str = "fb"
        self._log: bool = False
        self._xlog: bool = False
        self._legend_ncol: int = 4
        self._legend_title: Optional[str] = None
        self._legend_loc: str = "best"
        self._xlim: Optional[Tuple[float, float]] = None
        self._ylim: Optional[Tuple[float, float]] = None
        self._savedir: PathType = "./"
        self._saveformat: str = "png"
        self._savename: str = "plot"
        self._savepath: str = ""
        self._watermark_position: tuple = (0.033, 0.915)

        self.text: List[str] = []
        self.generic_text: List[dict] = []

    @property
    def figsize(self) -> Tuple[int, int]:
        return self._figsize

    @figsize.setter
    def figsize(self, figsize: Tuple[int, int]) -> None:
        self._figsize = figsize

    @property
    def label(self) -> Optional[Union[str, List[Optional[str]]]]:
        return self._label

    @label.setter
    def label(self, label: Optional[Union[str, List[Optional[str]]]]) -> None:
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
        return f"$\\int\\,L\\,\\mathrm{{d}}t\\;=\\;${self.luminosity_value:.0f}$\\; \\mathrm{{{self.luminosity_unit}}}^{{-1}}$"

    @property
    def legend_ncol(self) -> int:
        return self._legend_ncol

    @legend_ncol.setter
    def legend_ncol(self, legend_ncol: int) -> None:
        self._legend_ncol = legend_ncol

    @property
    def legend_title(self) -> Optional[str]:
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
    def xlim(self) -> Optional[Tuple[float, float]]:
        return self._xlim

    @xlim.setter
    def xlim(self, xlim: Tuple[float, float]) -> None:
        self._xlim = xlim

    @property
    def ylim(self) -> Optional[Tuple[float, float]]:
        return self._ylim

    @ylim.setter
    def ylim(self, ylim: Tuple[float, float]) -> None:
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

    def set_matplotlibrc_params(self, text_size: int = 25) -> None:
        """
        Rescale matplotlib rcParams for this plot (e.g. for a presentation-sized figure).

        :param text_size: Base font size in points. Defaults to 25.
        :return: None
        """
        set_matplotlibrc_params(text_size)

    def add_text(self, text: str) -> None:
        self.text.append(text)

    def add_generic_text(self, **text_kwargs: Dict[Any, Any]) -> None:
        self.generic_text.append(text_kwargs)

    def _get_savestring(self) -> PathType:
        """Concatinates savedir, savename and saveformat to full savepath"""
        return (
            os.path.join(self.savedir, f"{self.savename}.{self.saveformat}")
            if not self.savepath
            else self.savepath
        )

    def _add_text_to_plot(self, ax: plt.Axes) -> None:
        """Handling of different texts in the plot."""
        x = self.watermark_position[0]
        y = self.watermark_position[1]
        ax.text(
            x,
            y,
            get_experiment().labels.get("experiment", ""),
            ha="left",
            transform=ax.transAxes,
            style="italic",
            alpha=0.95,
            weight="bold",
            fontsize=20,
        )
        ax.text(
            x + 0.130,
            y,
            self.watermark,
            ha="left",
            transform=ax.transAxes,
            alpha=0.8,
            fontsize=20,
        )
        if self.luminosity_value:
            ax.text(
                x,
                y - 0.06,
                self.luminosity,
                ha="left",
                transform=ax.transAxes,
                alpha=0.8,
                fontsize=20,
            )
        if self.text:
            [
                ax.text(
                    x,
                    y - 0.076 - (i + 1) * 0.05,
                    text,
                    ha="left",
                    transform=ax.transAxes,
                    alpha=0.8,
                    fontsize=15,
                )
                for i, text in enumerate(self.text)
            ]

        for text_wargs in self.generic_text:
            text_wargs["transform"] = ax.transAxes
            ax.text(**text_wargs)

    def _add_axislabels(
        self,
        xax: Optional[plt.Axes] = None,
        yax: Optional[plt.Axes] = None,
        xlabel: Optional[str] = None,
        ylabel: Optional[str] = None,
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

    def _set_axislimits(
        self, ax: plt.Axes, ylim: Optional[Tuple[float, float]] = None
    ) -> None:
        """Set axis limits depending on number of legend and text lines"""
        xlim = self.xlim
        ylim = self.ylim if ylim is None else ylim
        lines_legend = self.legend_ncol
        lines_text = len(self.text) + 1
        if xlim is not None:
            ax.set_xlim(left=xlim[0], right=xlim[1])
        if ylim is None:
            ax.set_ylim(
                bottom=ax.get_ylim()[0],
                top=(
                    ax.get_ylim()[1]
                    * (1 + 0.1 * lines_legend * np.sign(ax.get_ylim()[1]))
                    if not self.log
                    else ax.get_ylim()[1]
                    * (1 + 10 ** (max([lines_legend, lines_text]) / 2))
                ),
            )
        else:
            ax.set_ylim(bottom=ylim[0], top=ylim[1])

    def _add_legend(self, ax: Union[List[plt.Axes], plt.Axes]) -> None:
        """Addition of legend with respect to number of labels."""
        if not isinstance(ax, list):
            ax = [ax]
        lines, labels = [], []
        for axis in ax:
            line, label = axis.get_legend_handles_labels()
            lines.extend(line)
            labels.extend(label)

        if labels:
            ncol = len(labels) // self.legend_ncol + (
                1 if len(labels) % self.legend_ncol != 0 else 0
            )
            ax[0].legend(
                lines, labels, ncol=ncol, title=self.legend_title, loc=self.legend_loc
            )
