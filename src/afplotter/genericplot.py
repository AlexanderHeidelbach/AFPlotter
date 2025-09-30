from typing import Any, Optional, List

from matplotlib import pyplot as plt

from afplotter.baseplotter import BasePlotter


class GenericPlot:
    def __init__(self, plotmethod: str, *args: Any, **kwargs: Any) -> None:
        self.plotmethod = plotmethod
        self.args = args
        self.kwargs = kwargs
        self._ax: Optional[plt.Axes] = None

    @property
    def ax(self) -> Optional[plt.Axes]:
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


class GenericPlotter(BasePlotter):
    def __init__(self) -> None:
        super().__init__()

        self._plots: List[GenericPlot] = []

    def add_generic_plot(self, plotmethod: str, *args: Any, **kwargs: Any) -> None:
        self._plots.append(GenericPlot(plotmethod, *args, **kwargs))

    def add_generic_plot_object(self, generic_plot: GenericPlot) -> None:
        self._plots.append(generic_plot)

    def plot(self, save: bool = False) -> plt.Axes:
        fig = plt.figure(figsize=self.figsize)
        ax = fig.add_subplot(1, 1, 1)

        for plot in self._plots:
            plot.ax = ax
            plot.plot()

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
