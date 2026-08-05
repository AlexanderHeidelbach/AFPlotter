# Getting started

## Install

    pip install git+https://github.com/AlexanderHeidelbach/AFPlotter.git

## Experiment styles

Every plotter (`GenericPlotter`, `HistogramPlotter`, etc.) applies a
matplotlib style on first use. Pick one explicitly before plotting:

```python
from afplotter import set_experiment
set_experiment("BelleII")  # or "Generic"
```

If you never call `set_experiment`, the first plot falls back to `"Generic"`
and emits a `RuntimeWarning`.

## Common `BasePlotter` properties

Every plotter shares these (set as plain attributes):

- `figsize`, `xlabel`, `ylabel`, `xlim`, `ylim`, `log`, `xlog`
- `legend_max_rows`, `legend_title`, `legend_loc`
- `watermark`, `luminosity_value`, `luminosity_unit`
- `savedir`, `savename`, `saveformat` (or `savepath` for a full explicit path)

Rescale text sizes for a specific plot — the default (36) is tuned for print
figures; pass a smaller value for a more compact layout or a presentation
slide with limited space:

```python
plotter.set_matplotlibrc_params(text_size=24)
```

Add free-text annotations below the watermark:

```python
plotter.add_text("(Preliminary)")
```

## Saving and reloading a plot

Every plotter can write its specification to JSON and read it back:

```python
plotter.save("fit.json")
plotter = HistogramPlotter.load("fit.json")
plotter.ylim = (1, 5000)      # adjust anything, then re-render
plotter.plot(save=True)
```

`HistogramPlotter` embeds its binned data, so one file is enough. `Histogram2DPlotter` bins raw
events at plot time and cannot store them, so its `load` takes the histograms back:
`Histogram2DPlotter.load(path, xhistogram=xh, yhistogram=yh)`.

Overlays added with `add_function`/`add_pull` are saved as the sampled curve, not as the model —
a reloaded plot re-renders that curve but cannot re-evaluate the function at a different binning.

Saving refuses by default when a value cannot be represented in the file (a live matplotlib object,
for instance); pass `skip_unserializable=True` to drop such keyword arguments instead, and `load`
will warn naming what was dropped.
