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
hist.add_entry(HistogramEntry(name="continuum", array=continuum_array))  # colour from the cycle
hist.add_entry(HistogramEntry(name="background", array=bkg_array, color="#377EB8"))  # or set one

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

## Colours

The default colour cycle is the **Petroff 10** sequence
([arXiv:2107.02270](https://arxiv.org/abs/2107.02270)), minus its red — nine colours,
exposed as `PETROFF_PALETTE.background` and installed as `axes.prop_cycle`. Entries
that do not set `color=` take colours from it in order, the same way for stacked and
step plots. Entries that *do* set `color=` keep it — only the missing ones are backfilled.

Switch palettes with `set_palette(name)`, mirroring `set_experiment(...)`:

```python
from afplotter import set_palette

set_palette("KIT")   # or "LMU", or "Petroff" (the default)
```

Each built-in palette (`Petroff`, `KIT`, `LMU`) holds its own red out of its own
background cycle and reserves it exclusively for signal — so switching palettes never
reintroduces a background/signal colour clash. Register a custom palette with
`afplotter.palettes.register_palette(Palette(name=..., background=[...], signal=...))`.

## Signal components

An entry with `type="signal"` is routed into `Histogram.signal` instead of
`Histogram.entries`. In a stacked plot it is **always drawn last, so it sits on top of
the stack**, filled in `get_palette().signal` at its true yield:

```python
from afplotter import Histogram, HistogramEntry, HistogramPlot

hist.add_entry(HistogramEntry(name="bkg", latex_name="Background", array=bkg_array))
hist.add_entry(HistogramEntry(name="signal", latex_name="Signal", array=sig_array, type="signal"))

histplot = HistogramPlot(hist)
histplot.stacked = True     # backgrounds stacked, signal closes the stack on top
histplot.uncertainty = True # the band covers the full S+B stack
```

Stack order among the backgrounds is `Histogram.order_entries(...)`; signal ignores it
and always ends up topmost.

Because signal is a stack layer, it counts toward the modelled total:
`get_total_bin_count()` and `get_total_bin_errors()` are **S+B**, so the `Stat. unc.`
band covers the whole stack and `add_pull(model)` compares your model against signal
plus background.

### The `sig_extra` outline overlay

`HistogramPlot.sig_extra = True` is for a signal too small to see at its true yield: it
draws the signal as an unfilled step outline, **peak-matched** to the background stack
(`get_signal_bin_counts()` rescales; `get_raw_signal_bin_counts()` does not), and
**excludes it from the stack entirely** — bars, legend entry, and the `Stat. unc.` band
all fall back to background-only. Signal never appears in both places at once; with
`sig_extra = True`, the peak-matched outline is its *only* representation.

Caveats worth knowing:

- When there is exactly **one** signal component it is always drawn in the active
  palette's reserved signal colour (`get_palette().signal`); an explicit `color=` on
  that entry is ignored.
- When there are **several** signal components, each one keeps its explicit `color=`
  if it has one, and is backfilled from the ordinary cycle otherwise. This applies both
  to signal stacked at true yield and to `sig_extra` outlines.
- Step mode (`stacked = False`) is unaffected: signals only appear there via `sig_extra`.
- `KITColors` and `LMUColors` are still exported and unchanged — they are just not
  the default; use them directly for one-off colours, or via `KIT_PALETTE`/`LMU_PALETTE`
  through `set_palette(...)`.

## 2D histograms

```python
from afplotter import plot_2d_histogram
plot_2d_histogram(xdata, ydata, xbins=(0, 10, 41), ybins=(-2, 2, 41), save="hist2d.png")
```

See `examples/histogram_with_pull.py` for a full runnable example.
