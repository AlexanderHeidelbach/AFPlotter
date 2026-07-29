from dataclasses import dataclass
from typing import Any, Callable
from matplotlib import pyplot as plt  # type: ignore
import numpy as np  # type: ignore

from afplotter.baseplotter import BasePlotter
from afplotter.palettes import get_palette
from afplotter.genericplot import GenericPlot, InsetPlot
from afplotter.utilities.histogram import Histogram


def poisson_ratio(b: np.ndarray, a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute ratio b/a with propagated Poisson errors for arrays.

    Rules:
      - a == 0 and b == 0 → ratio = 1, err = 0
      - a == 0 xor b == 0 → ratio = 0, err = 0
      - a > 0 and b > 0  → ratio = b/a with propagated error
    """
    b = np.asarray(b, dtype=float)
    a = np.asarray(a, dtype=float)

    ratio = np.full_like(b, 0.0, dtype=float)
    err = np.full_like(b, 0.0, dtype=float)

    # Case 1: both zero → ratio = 1
    mask_both_zero = (a == 0) & (b == 0)
    ratio[mask_both_zero] = 1.0
    err[mask_both_zero] = 0.0

    # Case 2: a > 0 and b > 0 → normal Poisson ratio
    mask_valid = (a > 0) & (b > 0)
    ratio[mask_valid] = b[mask_valid] / a[mask_valid]

    with np.errstate(divide="ignore", invalid="ignore"):
        err[mask_valid] = ratio[mask_valid] * np.sqrt(
            (1.0 / b[mask_valid]) + (1.0 / a[mask_valid])
        )

    return ratio, err


def weighted_mean_and_error(x, sigma):
    """
    Compute weighted mean and its uncertainty.

    Parameters:
        x (array-like): data points
        sigma (array-like): uncertainties of data points

    Returns:
        (x_mean, sigma_mean): weighted mean and its uncertainty
    """
    x = np.asarray(x, dtype=float)
    sigma = np.asarray(sigma, dtype=float)

    # weights = 1.0 / sigma**2
    weights = np.where(sigma == 0, 1e-12, 1 / sigma**2)
    x_mean = np.sum(x * weights) / np.sum(weights)
    sigma_mean = 1.0 / np.sqrt(np.sum(weights))

    return x_mean, sigma_mean


@dataclass
class HistogramVariable:
    name: str
    unit: str = ""


class HistogramPlot:
    def __init__(self, histogram: Histogram) -> None:
        self.histogram = histogram
        self._ax: plt.Axes | None = None
        self._stacked: bool = False
        self._sig_extra: bool = False
        self._uncertainty: bool = False
        self._data_only: bool = False
        self._data_hist: Histogram | None = None
        self._linewidth: float = 1.0
        self._edgecolor: str | None = "black"

        self._density: bool = False
        self._log: bool = False

    @property
    def ax(self) -> plt.Axes:
        assert self._ax is not None
        return self._ax

    @ax.setter
    def ax(self, ax: plt.Axes) -> None:
        self._ax = ax

    @property
    def stacked(self) -> bool:
        return self._stacked

    @stacked.setter
    def stacked(self, stack: bool) -> None:
        self._stacked = stack

    @property
    def sig_extra(self) -> bool:
        return self._sig_extra

    @sig_extra.setter
    def sig_extra(self, sig: bool) -> None:
        self._sig_extra = sig

    @property
    def uncertainty(self) -> bool:
        return self._uncertainty

    @uncertainty.setter
    def uncertainty(self, uncert: bool) -> None:
        self._uncertainty = uncert

    @property
    def density(self) -> bool:
        return self._density

    @density.setter
    def density(self, dens: bool) -> None:
        self._density = dens

    @property
    def log(self) -> bool:
        return self._log

    @log.setter
    def log(self, log: bool) -> None:
        self._log = log

    @property
    def data_only(self) -> bool:
        return self._data_only

    @data_only.setter
    def data_only(self, data: bool) -> None:
        self._data_only = data

    @property
    def data_hist(self) -> Histogram | None:
        return self._data_hist

    @data_hist.setter
    def data_hist(self, entry: Histogram) -> None:
        self._data_hist = entry

    @property
    def linewidth(self) -> float:
        return self._linewidth

    @linewidth.setter
    def linewidth(self, width: float) -> None:
        self._linewidth = width

    @property
    def edgecolor(self) -> str | None:
        return self._edgecolor

    @edgecolor.setter
    def edgecolor(self, color: str | None) -> None:
        self._edgecolor = color

    @staticmethod
    def hatches(n: int) -> list[str]:
        hatches_list = [
            "///",
            r"\\\ ",
            "xxx",
            "--",
            "++",
            "o",
            ".+",
            "xx",
            "//",
            "*",
            "O",
            ".",
        ]
        return [hatches_list[i % len(hatches_list)] for i in range(n)]


    @staticmethod
    def std_colors(n: int) -> list[str]:
        colormap = dict(plt.rcParams)["axes.prop_cycle"].by_key()["color"]
        return [colormap[i % len(colormap)] for i in range(n)]

    def _prepare_data(self) -> None:
        assert self.data_hist is not None


    def plot_stacked(self) -> None:
        colors = self.histogram.get_colors()
        if not all((color is not None) for color in colors):
            colors = self.std_colors(len(self.histogram.entries))

        self.ax.hist(
            self.histogram.get_bin_centers(),
            bins=self.histogram.binning,  # type: ignore
            weights=self.histogram.get_bin_counts(),
            label=self.histogram.get_latex_names(),  # type: ignore
            color=colors,  # type: ignore
            histtype="stepfilled",
            stacked=True,
            density=self.density,
            lw=0.3,
            edgecolor=self.edgecolor,
            log=self.log,
        )  # noqa

        if self.uncertainty:
            scalefactor = self.histogram.get_total_scale() if self.density else 1
            self.ax.bar(
                self.histogram.get_bin_centers()[0],
                height=2 * self.histogram.get_total_bin_errors() / scalefactor,
                width=self.histogram.get_bin_width(),
                bottom=(
                    self.histogram.get_total_bin_count()
                    - self.histogram.get_total_bin_errors()
                )
                / scalefactor,
                color="black",
                hatch="///////",
                fill=False,
                lw=0,
                label="Stat. unc.",
            )

    def plot_step(self, sig_extra: bool = False) -> None:
        hatches: list[str] | list[None] | list[str | None] = [None]
        if not sig_extra:
            centers = self.histogram.get_bin_centers()
            weights = self.histogram.get_bin_counts()
            errors = self.histogram.get_bin_errors()
            labels = self.histogram.get_latex_names()
            if any(color is None for color in self.histogram.get_colors()):
                colors = self.std_colors(len(self.histogram.entries))
                hatches = [None] * len(self.histogram.entries)
            else:
                colors = self.histogram.get_colors()
                hatches = self.histogram.get_hatches()
        else:
            centers = [self.histogram.get_bin_centers()[0]] * len(self.histogram.signal)
            weights = self.histogram.get_signal_bin_counts()
            errors = self.histogram.get_signal_bin_errors()
            labels = self.histogram.get_signal_latex_names()
            if len(self.histogram.signal) != 1:
                if any(color is None for color in self.histogram.get_signal_colors()):
                    colors = self.std_colors(len(self.histogram.signal))
                else:
                    colors = self.histogram.get_signal_colors()

            else:
                # A lone signal component is always drawn in the reserved signal
                # colour, overriding any explicitly set HistogramEntry.color.
                colors = [get_palette().signal]
            hatches = [None] * len(self.histogram.signal)

        if labels is None:
            labels = [None] * len(centers)
        for center, weight, error, label, color, hatch in zip(
            centers, weights, errors, labels, colors, hatches
        ):
            self.ax.hist(
                center,
                bins=self.histogram.binning,  # type: ignore
                weights=weight,
                label=label,
                color=color,
                histtype="step",
                stacked=False,
                hatch=hatch,
                density=self.density,
                lw=self.linewidth,
                log=self.log,
            )

            if self.uncertainty:
                scalefactor = (
                    np.sum(weight * self.histogram.get_bin_width())
                    if self.density
                    else 1
                )
                self.ax.bar(
                    center,
                    height=2 * error / scalefactor,
                    width=self.histogram.get_bin_width(),
                    bottom=(weight - error) / scalefactor,
                    edgecolor=color,
                    hatch="///////",
                    fill=False,
                    lw=0,
                )

    def plot_data(self) -> None:
        self._prepare_data()
        assert self.data_hist is not None

        scalefactor = 1
        if self.density:
            if self.histogram.entries:
                scalefactor = self.histogram.get_total_scale()
            elif self.histogram.signal:
                scalefactor = self.histogram.get_total_signal_scale()
            else:
                scalefactor = self.data_hist.get_total_scale()

        data_labels = self.data_hist.get_latex_names()
        if data_labels is None:
            label = "Data"
        else:
            label = data_labels[0]

        self.ax.errorbar(
            self.data_hist.get_bin_centers()[0],
            self.data_hist.get_bin_counts()[0] / scalefactor,
            yerr=self.data_hist.get_bin_errors()[0] / scalefactor,
            ls="",
            marker=".",
            color="black",
            label=label,
        )

    def plot(self) -> plt.Axes:
        if not self.data_only:
            if self.stacked:
                self.plot_stacked()

            else:
                self.plot_step()

        if self.sig_extra and not self.data_only:
            self.plot_step(True)

        if self.data_hist:
            self.plot_data()

        return self.ax


class Histogram2DPlot:
    def __init__(self, xhistogram: Histogram, yhistogram: Histogram) -> None:
        self.xhistogram = xhistogram
        self.yhistogram = yhistogram
        self._ax: plt.Axes | None = None

        self._density: bool = False
        self._log: bool = False

        self._cmap: str = "viridis"
        self._cmin: float | None = None
        self._cmax: float | None = None
        self._cbar_label: str = "Entries"
        self._norm = "linear"

    @property
    def ax(self) -> plt.Axes:
        assert self._ax is not None
        return self._ax

    @ax.setter
    def ax(self, ax: plt.Axes) -> None:
        self._ax = ax

    @property
    def density(self) -> bool:
        return self._density

    @density.setter
    def density(self, dens: bool) -> None:
        self._density = dens

    @property
    def log(self) -> bool:
        return self._log

    @log.setter
    def log(self, log: bool) -> None:
        self._log = log

    @property
    def cmap(self) -> str:
        return self._cmap

    @cmap.setter
    def cmap(self, cmap: str) -> None:
        self._cmap = cmap

    @property
    def norm(self) -> str:
        return self._norm

    @norm.setter
    def norm(self, norm: str) -> None:
        self._norm = norm

    @property
    def cmin(self) -> float | None:
        return self._cmin

    @cmin.setter
    def cmin(self, cmin: float | None) -> None:
        self._cmin = cmin

    @property
    def cmax(self) -> float | None:
        return self._cmax

    @cmax.setter
    def cmax(self, cmax: float | None) -> None:
        self._cmax = cmax

    @property
    def cbar_label(self) -> str:
        return self._cbar_label

    @cbar_label.setter
    def cbar_label(self, label: str) -> None:
        self._cbar_label = label

    def plot(self) -> plt.Axes:
        x_is_signal = len(self.xhistogram.get_signal_data()) > 0
        x_is_entry = len(self.xhistogram.get_data()) > 0

        # Determine the type of data for yhistogram
        y_is_signal = len(self.yhistogram.get_signal_data()) > 0
        y_is_entry = len(self.yhistogram.get_data()) > 0

        # Validate consistency
        if (x_is_signal and not y_is_signal) or (y_is_signal and not x_is_signal):
            raise ValueError(
                "Mismatch in data types: one histogram is signal and the other is default."
            )
        if (x_is_entry and not y_is_entry) or (y_is_entry and not x_is_entry):
            raise ValueError(
                "Mismatch in data types: one histogram is default and the other is signal."
            )

        # Use signal data if both are signal
        if x_is_signal and y_is_signal:
            x_data = self.xhistogram.get_signal_data()[0]
            y_data = self.yhistogram.get_signal_data()[0]
        # Use normal data if both are normal
        elif x_is_entry and y_is_entry:
            x_data = self.xhistogram.get_data()[0]
            y_data = self.yhistogram.get_data()[0]
        else:
            # Should not reach here due to checks above, but a fallback just in case
            raise ValueError("Unexpected data state encountered.")

        heatmap = self.ax.hist2d(
            x=x_data,
            y=y_data,
            bins=(self.xhistogram.binning, self.yhistogram.binning),
            density=self.density,
            cmap=self.cmap,
            cmin=self.cmin,
            cmax=self.cmax,
            norm=self.norm,
        )

        cbar = plt.colorbar(heatmap[3])
        cbar.set_label(self.cbar_label)
        heatmap[3].set_rasterized(True)  # type: ignore

        return self.ax


class HistogramPlotter(BasePlotter):
    def __init__(self, histplot: HistogramPlot, variable: HistogramVariable) -> None:
        super().__init__()
        self.histplot = histplot
        self.variable = variable
        self.generic_plots: list[GenericPlot] = []
        self._insets: list[InsetPlot] = []
        self.pull_plots: list[GenericPlot] = []
        self.pull_ylim: tuple[float, float] | None = None
        self.color_map_kwargs: dict[str, Any] = {}
        self.pull_label: str = "Pull"

        self.log = self.histplot.log

    @property
    def xlabel(self) -> str:
        return self.variable.name + (
            " (" + self.variable.unit + ")" if self.variable.unit else ""
        )

    @property
    def ylabel(self) -> str:
        bindiff = self.histplot.histogram.get_bin_width()
        ylabel = (
            "Entries / ({bindiff:.3{c}}".format(
                bindiff=bindiff,
                c="e" if (abs(bindiff) > 1e3 or abs(bindiff) < 1e-3) else "f",
            )
            + (f" {self.variable.unit}" if self.variable.unit is not None else "")
            + ")"
        )
        return ylabel

    def add_function(
        self,
        func: Callable,
        density: bool = True,
        binwidth: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        x = np.linspace(
            np.min(self.histplot.histogram.binning),
            np.max(self.histplot.histogram.binning),
            1000,
        )
        y = func(x)

        if not density:
            y *= self.histplot.histogram.get_scale()
        if binwidth:
            y *= self.histplot.histogram.get_bin_width()

        self.generic_plots.append(GenericPlot("plot", x, y, *args, **kwargs))

    def add_generic_plot(self, generic_plot: GenericPlot) -> None:
        self.generic_plots.append(generic_plot)

    def add_inset(
        self,
        xlim: tuple[float, float],
        ylim: tuple[float, float] | None = None,
        plots: list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Queue an inset axes replaying this plotter's histogram (and any
        generic overlays) zoomed to xlim/ylim.

        :param xlim: Data x-limits for the inset.
        :param ylim: Optional data y-limits for the inset.
        :param plots: Objects to replay in the inset (must expose an `ax`
            setter and a no-argument `plot()`, as both HistogramPlot and
            GenericPlot do); defaults to this plotter's histogram plus any
            generic overlays.
        :param kwargs: Forwarded to InsetPlot (width, height, loc, title,
            mark_region, mark_kwargs, tick_labelsize, title_fontsize, bbox_to_anchor).
        :return: None
        """
        if plots is None:
            plots = [self.histplot] + list(self.generic_plots)
        self._insets.append(InsetPlot(plots=plots, xlim=xlim, ylim=ylim, **kwargs))

    def add_pull(
        self,
        func: Callable,
        density: bool = True,
        binwidth: bool = False,
        show_sigmas: bool = True,
        max_sigma: float = 3.0,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        x = np.linspace(
            np.min(self.histplot.histogram.binning),
            np.max(self.histplot.histogram.binning),
            1000,
        )
        y = func(x)

        if not density:
            y *= self.histplot.histogram.get_scale()
        if binwidth:
            y *= self.histplot.histogram.get_bin_width()

        generic_plot = GenericPlot("plot", x, y, *args, **kwargs)
        color = generic_plot.kwargs.get("color", "black")
        self.generic_plots.append(generic_plot)

        bin_centers = self.histplot.histogram.get_bin_centers()[0]
        bin_width = self.histplot.histogram.get_bin_width()
        y_hist = self.histplot.histogram.get_total_bin_count()
        y_err = self.histplot.histogram.get_total_bin_errors()
        y_func = func(bin_centers)
        if not density:
            y_func *= self.histplot.histogram.get_scale()
        if binwidth:
            y_func *= self.histplot.histogram.get_bin_width()
        if not density:
            y_func *= self.histplot.histogram.get_scale()

        y_pull = np.divide(
            (y_func - y_hist),
            y_err,
            out=np.zeros_like(y_err),
            where=y_err != 0,
            dtype=float,
        )

        if show_sigmas:
            self.pull_plots.append(
                GenericPlot(
                    "hlines",
                    y=[0],
                    xmin=np.min(bin_centers),
                    xmax=np.max(bin_centers),
                    color="grey",
                    ls="-",
                    alpha=0.5,
                )
            )
            self.pull_plots.append(
                GenericPlot(
                    "hlines",
                    y=[-1, 1],
                    xmin=np.min(bin_centers),
                    xmax=np.max(bin_centers),
                    color="grey",
                    ls="--",
                    alpha=0.5,
                )
            )
            self.pull_plots.append(
                GenericPlot(
                    "hlines",
                    y=[-2, 2],
                    xmin=np.min(bin_centers),
                    xmax=np.max(bin_centers),
                    color="grey",
                    ls="-.",
                    alpha=0.5,
                )
            )
            ylim = (-max_sigma, max_sigma)
        else:
            ylim = (np.min(y_pull) * 1.1, np.max(y_pull) * 1.1)

        self.pull_plots.append(
            GenericPlot(
                "bar",
                x=bin_centers,
                height=y_pull,
                width=bin_width,
                color="lightgray",
                alpha=0.5,
            )
        )
        self.pull_plots.append(
            GenericPlot(
                "errorbar",
                bin_centers,
                y_pull,
                xerr=bin_width / 2,
                color=color,
                marker=".",
                ls="",
            )
        )

        self.pull_ylim = ylim
        self.pull_label = "($y-$bin)/$\\sigma_{\\rm bin}$"

    def add_pull_data(
        self,
        show_sigmas: bool = True,
        max_sigma: float = 3.0,
        ratio: bool = False,
        ylim: tuple[float, float] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        assert self.histplot.data_hist is not None

        bin_centers = self.histplot.histogram.get_bin_centers()[0]
        bin_centers_data = self.histplot.data_hist.get_bin_centers()[0]
        assert np.all(
            bin_centers == bin_centers_data
        ), "Bin centers of data and model do not match!"
        bin_width = self.histplot.histogram.get_bin_width()
        y_hist = self.histplot.histogram.get_total_bin_count()
        y_err = self.histplot.histogram.get_total_bin_errors()
        y_data = self.histplot.data_hist.get_total_bin_count()
        y_data_err = self.histplot.data_hist.get_total_bin_errors()
        y_err_total = np.sqrt(y_err**2 + y_data_err**2)

        if not ratio:
            y_pull = np.divide(
                (y_data - y_hist),
                y_err_total,
                out=np.zeros_like(y_err_total),
                where=y_err_total != 0,
                dtype=float,
            )
            y_err = 0 * y_err_total
        else:
            y_pull, y_err = poisson_ratio(y_data, y_hist)

        if show_sigmas:
            self.pull_plots.append(
                GenericPlot(
                    "hlines",
                    y=[0],
                    xmin=np.min(bin_centers),
                    xmax=np.max(bin_centers),
                    color="grey",
                    ls="-",
                    alpha=0.5,
                )
            )
            self.pull_plots.append(
                GenericPlot(
                    "hlines",
                    y=[-1, 1],
                    xmin=np.min(bin_centers),
                    xmax=np.max(bin_centers),
                    color="grey",
                    ls="--",
                    alpha=0.5,
                )
            )
            self.pull_plots.append(
                GenericPlot(
                    "hlines",
                    y=[-2, 2],
                    xmin=np.min(bin_centers),
                    xmax=np.max(bin_centers),
                    color="grey",
                    ls="-.",
                    alpha=0.5,
                )
            )
            ylim_auto = (-max_sigma, max_sigma)
        else:
            ylim_auto = (
                np.min(y_pull) * 1.1 if np.min(y_pull) < 0 else np.min(y_pull) * 0.9,
                np.max(y_pull) * 1.1,
            )

        if not ratio:
            self.pull_plots.append(
                GenericPlot(
                    "bar",
                    x=bin_centers,
                    height=y_pull,
                    width=bin_width,
                    color="lightgray",
                    alpha=0.5,
                )
            )
        if ratio:
            self.pull_plots.append(
                GenericPlot(
                    "hlines",
                    y=1,
                    xmin=np.min(bin_centers) - bin_width / 2,
                    xmax=np.max(bin_centers) + bin_width / 2,
                    color="lightgray",
                    alpha=0.5,
                )
            )

        wmean, _ = weighted_mean_and_error(y_pull, y_err)
        self.pull_plots.append(
            GenericPlot(
                "errorbar",
                bin_centers,
                y_pull,
                yerr=y_err,
                xerr=bin_width / 2,
                color="black",
                marker=".",
                label=f"Mean: {wmean:.2f}",
                ls="",
            )
        )

        self.pull_ylim = ylim_auto if ylim is None else ylim
        if ratio:
            self.pull_label = "$\\frac{N_{\\rm data}}{N_{\\rm MC}}$"
        else:
            self.pull_label = "$\\frac{N_{\\rm data}-N_{\\rm MC}}{\\sqrt{\\sigma_{\\rm data}^2 + \\sigma_{\\rm MC}^2}}$"

    def add_colormap(
        self, min_val: float, max_val: float, cmap: str = "viridis", label: str = ""
    ) -> None:
        self.color_map_kwargs = {
            "min_val": min_val,
            "max_val": max_val,
            "cmap": cmap,
            "label": label,
        }

    def _add_colormap(self, ax: plt.Axes) -> None:
        sm = plt.cm.ScalarMappable(  # type: ignore
            cmap=self.color_map_kwargs["cmap"],
            norm=plt.Normalize(  # type: ignore
                vmin=self.color_map_kwargs["min_val"],
                vmax=self.color_map_kwargs["max_val"],
            ),
        )
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax)
        cbar.set_label(self.color_map_kwargs["label"])

    def plot(self, save: bool = False) -> tuple[plt.Axes, plt.Axes | None]:
        if self.pull_plots:
            fig = plt.figure(figsize=(self.figsize[0], 1.5 * self.figsize[1]))
            ax = fig.add_subplot(4, 1, (1, 3), xticklabels=[])
            ax_diff = fig.add_subplot(4, 1, 4)

        else:
            fig = plt.figure(figsize=self.figsize)
            ax = fig.add_subplot(1, 1, 1)
            ax_diff = None

        self.histplot.ax = ax
        ax = self.histplot.plot()

        for generic_plot in self.generic_plots:
            generic_plot.ax = ax
            ax = generic_plot.plot()

        for inset in self._insets:
            inset.plot(parent_ax=ax)

        self.xlim = (
            np.min(self.histplot.histogram.binning),
            np.max(self.histplot.histogram.binning),
        )
        self._add_text_to_plot(ax=ax)

        if self.color_map_kwargs:
            self._add_colormap(ax=ax)

        self._set_axislimits(ax=ax)

        self._add_legend(ax=ax)

        if self.xlog:
            ax.set_xscale("log")

        if self.log:
            ax.set_yscale("log")

        if ax_diff is not None:
            self._add_axislabels(yax=ax_diff, ylabel=self.pull_label)
            self._set_axislimits(ax=ax_diff, ylim=self.pull_ylim)
            for generic_plot in self.pull_plots:
                generic_plot.ax = ax_diff
                _ = generic_plot.plot()
            self._add_legend(ax=ax_diff)

        self._add_axislabels(xax=(ax if ax_diff is None else ax_diff), yax=ax)

        if save:
            plt.savefig(self._get_savestring())
            plt.clf()
            plt.close()

        else:
            plt.show()

        return ax, ax_diff


class Histogram2DPlotter(BasePlotter):
    def __init__(
        self,
        histplot: Histogram2DPlot,
        xvariable: HistogramVariable,
        yvariable: HistogramVariable,
    ) -> None:
        super().__init__()
        self.histplot = histplot
        self.xvariable = xvariable
        self.yvariable = yvariable
        self.generic_plots: list[GenericPlot] = []
        self.log = self.histplot.log

    @property
    def xlabel(self) -> str:
        return self.xvariable.name + (
            " (" + self.xvariable.unit + ")" if self.xvariable.unit else ""
        )

    @property
    def ylabel(self) -> str:
        return self.yvariable.name + (
            " (" + self.yvariable.unit + ")" if self.yvariable.unit else ""
        )

    def add_generic_plot(self, generic_plot: GenericPlot) -> None:
        self.generic_plots.append(generic_plot)

    def plot(self, save: bool = False) -> plt.Axes:
        fig = plt.figure(figsize=self.figsize)
        ax = fig.add_subplot(1, 1, 1)

        self.histplot.ax = ax
        ax = self.histplot.plot()

        for generic_plot in self.generic_plots:
            generic_plot.ax = ax
            ax = generic_plot.plot()
        self._add_text_to_plot(ax=ax)

        self.xlim = (
            np.min(self.histplot.xhistogram.binning),
            np.max(self.histplot.xhistogram.binning),
        )

        self.ylim = (
            np.min(self.histplot.yhistogram.binning),
            np.max(self.histplot.yhistogram.binning),
        )

        if self.xlog:
            ax.set_xscale("log")

        if self.log:
            ax.set_yscale("log")

        self._add_axislabels(xax=ax, yax=ax)
        self._set_axislimits(ax=ax)

        if save:
            plt.savefig(
                self._get_savestring(),
                bbox_inches="tight",
                pad_inches=0.0,
            )
            plt.clf()
            plt.close()

        else:
            plt.show()

        return ax
