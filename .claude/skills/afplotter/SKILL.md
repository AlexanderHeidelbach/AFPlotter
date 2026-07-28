---
name: afplotter
description: Use when the user asks to plot HEP-style data or results (histograms, exclusion limits, fit results) using AFPlotter. Trigger on "plot this", "make a histogram of X", "plot the exclusion limit", or similar requests referencing data files, arrays, or analysis results in a physics context.
---

# AFPlotter plotting skill

Drive the `afplotter` package (installed in this environment) to produce the
requested plot. Write a short throwaway Python script, run it via Bash, then
report the saved plot path back and send the image with `SendUserFile`.

## Step 1: Pick a style

Always start the script with:

```python
from afplotter import set_experiment
set_experiment("BelleII")  # ask the user if unclear whether BelleII/Generic
```

## Step 2: Pick the right interface

**Simple single-histogram request** ("plot column X", "histogram this array",
"plot signal vs background for pt") → use the convenience functions:

```python
from afplotter import plot_histogram, plot_histogram_from_files, plot_2d_histogram

plot_histogram({"signal": sig_array, "background": bkg_array}, bins=(0, 10, 41), stacked=True, save="/tmp/out.png")

plot_histogram_from_files(
    files={"signal": "sig.parquet", "background": "bkg.parquet"},
    column="pt", bins=(0, 10, 41), selection="pt > 0 and eta > -2 and eta < 2", save="/tmp/out.png",
)

plot_2d_histogram(xdata, ydata, xbins=(0, 10, 41), ybins=(-2, 2, 41), save="/tmp/out.png")
```

**Composed/analysis plot** (fit result with pull panel, exclusion/coupling
limit with fills or insets, multiple overlaid curves) → drive the full
engine directly. See `docs/histograms.md` and `docs/composed-plots.md` in
this repo for the exact patterns, and `examples/histogram_with_pull.py` /
`examples/exclusion_limit_with_inset.py` for complete runnable references.
Key building blocks:

- `Histogram`/`HistogramEntry` → `HistogramPlot` → `HistogramPlotter` for
  histogram-based plots; `add_function`/`add_pull` for fit overlays.
- `GenericPlotter` + `add_generic_plot(plotmethod, *args, **kwargs)` for
  arbitrary composed plots (any `Axes` method: `"plot"`, `"fill_between"`,
  `"fill"`, `"errorbar"`, `"scatter"`); `add_generic_text` for annotations.
- `plotter.add_inset(xlim=..., ylim=..., title=..., bbox_to_anchor=...)` for a
  zoomed sub-region, available on both `GenericPlotter` and `HistogramPlotter`
  — defaults to replaying the same content as the main plot; see
  `docs/composed-plots.md` for `width`/`height`/`loc`/`bbox_to_anchor`/
  `mark_region` details.
- `KITColors` (imported from `afplotter`) for the standard color palette
  (`kit_green`, `kit_blue`, `kit_orange`, `kit_red`, `kit_purple`, etc., plus
  an `lmu_*` set).

## Step 3: Save and report

Always pass an explicit `save=` path (or set `.savedir`/`.savename`/
`.saveformat` on the plotter directly for the full-engine path). Run the
script with Bash, then send the resulting PNG back with `SendUserFile`
(`status: "normal"`, since this is a direct reply to the user's request).

## Step 4: Data location

If the user references a file (parquet, CSV, etc.) without a full path, ask
where it lives rather than guessing. Don't fabricate data — only use
synthetic data if the user explicitly says they don't have real data yet.
