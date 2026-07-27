# Composed plots

Real analysis plots (exclusion limits, coupling limits, anything with
multiple overlays) are built by composing `GenericPlotter` directly — there
is no one-shot convenience function for this, since real plots are always
multi-call compositions.

```python
from afplotter import GenericPlotter, KITColors

plotter = GenericPlotter()
plotter.xlabel = "$m_a$ (GeV/c$^2$)"
plotter.ylabel = "$\\sigma$ (fb)"
plotter.xlim = (0.2, 9.5)

plotter.add_generic_plot("plot", masses, expected, label="Expected", color="black", ls="--")
plotter.add_generic_plot("fill_between", x=masses, y1=lower, y2=upper, color=KITColors.kit_yellow, label="$\\pm 1\\sigma$")
plotter.add_generic_text(x=0.5, y=0.9, s="Belle II\n(this work)", ha="center", color=KITColors.kit_green)

plotter.plot(save=True)
```

`add_generic_plot(plotmethod, *args, **kwargs)` calls any `matplotlib.axes.Axes`
method (`"plot"`, `"fill"`, `"fill_between"`, `"errorbar"`, `"scatter"`, ...)
with the given arguments. `add_generic_plot_object(GenericPlot(...))` lets you
build and reuse a plot command before adding it.

## Insets

Available on both `GenericPlotter` and `HistogramPlotter`. By default, an
inset replays exactly the same content as the main plot, just zoomed and
placed in a corner:

```python
plotter.add_inset(xlim=(0.2, 2.0), ylim=(0, 9), title="Low-mass region")
```

This uses `mpl_toolkits.axes_grid1.inset_locator` under the hood, so sizing
follows its conventions: `width`/`height` are percentage strings of the
parent axes (default `"38%"`/`"38%"`), placed via a legend-style `loc`
string (default `"upper center"`). For precise placement, pass
`bbox_to_anchor=(x0, y0, w, h)` (axes-fraction coordinates) instead of
relying on `loc`:

```python
plotter.add_inset(
    xlim=(0.17, 1.0),
    ylim=(0, 9),
    bbox_to_anchor=(-0.35, 0.04, 0.8, 0.8),
    title="$0.16 < m_a < 1.0$ GeV/$c^2$",
    tick_labelsize=20,
    title_fontsize=20,
    mark_region=False,
)
```

Set `mark_region=False` to skip drawing the connector lines/box indicating
the zoomed region on the parent axes (drawn via `mark_inset`); pass
`mark_kwargs={...}` to customize their style (`loc1`/`loc2`/`fc`/`ec`/`lw`).
Pass `plots=[...]` to show different content in the inset than on the main
axes (any object with a settable `.ax` and a no-argument `.plot()` — e.g. a
standalone `GenericPlot`).

See `examples/exclusion_limit_with_inset.py` for a full runnable example.
