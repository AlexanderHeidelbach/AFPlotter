# Histograms

## Quick single-histogram plots

For a simple "just plot this column" request, use the convenience functions:

```python
from afplotter import plot_histogram, plot_histogram_from_files

plot_histogram({"signal": signal_array, "background": bkg_array}, bins=(0, 10, 41), stacked=True, save="out.png")

plot_histogram_from_files(
    files={"signal": "sig.parquet", "background": "bkg.parquet"},
    column="pt",
    bins=(0, 10, 41),
    selection="pt > 0 and eta > -2 and eta < 2",
    save="out.png",
)
```

## Full control: stacked/step/pull plots

For anything beyond a single histogram (fit overlays, pull panels, data
comparison), build the objects directly:

```python
from afplotter import Histogram, HistogramEntry, HistogramPlot, HistogramPlotter, HistogramVariable
import numpy as np

hist = Histogram()
hist.binning = np.linspace(0, 10, 41)
hist.add_entry(HistogramEntry(name="signal", array=signal_array, color="#E41A1C"))
hist.add_entry(HistogramEntry(name="background", array=bkg_array, color="#377EB8"))

histplot = HistogramPlot(hist)
histplot.stacked = True
histplot.uncertainty = True

plotter = HistogramPlotter(histplot, HistogramVariable("$M$", "GeV"))
plotter.add_function(model_pdf, binwidth=True, label="Model", color="black")
plotter.add_pull(model_pdf, binwidth=True, color="black", label="Model", max_sigma=5.0)
plotter.plot(save=True)
```

`HistogramPlot.data_hist` + `HistogramPlot.data_only = True` overlays a
data-only errorbar plot instead of (or alongside) the modeled entries.

## 2D histograms

```python
from afplotter import plot_2d_histogram
plot_2d_histogram(xdata, ydata, xbins=(0, 10, 41), ybins=(-2, 2, 41), save="hist2d.png")
```

See `examples/histogram_with_pull.py` for a full runnable example.
