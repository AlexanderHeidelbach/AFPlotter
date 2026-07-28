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
- `legend_ncol`, `legend_title`, `legend_loc`
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
