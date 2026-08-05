# Saving and loading plotter objects

Issue: #38
Builds on: #9 (`Histogram.save`/`load`, binned-only JSON)

## The premise correction

The issue frames the central design question as "how are callables referenced?" — importable
qualname, re-attach after load, or a named-model registry. **No plotter ever stores a callable**,
so the question does not arise.

`HistogramPlotter.add_function` (`src/afplotter/histogramplot.py:512`) evaluates `func` eagerly:
it samples the model over 1000 points spanning the binning, applies the `density`/`binwidth`
scaling, and appends a `GenericPlot("plot", x, y, *args, **kwargs)` holding plain arrays.
`add_pull` (`:562`) does the same, then computes the pull values and appends `hlines`, `bar` and
`errorbar` `GenericPlot`s built from those numbers. By the time either method returns, `func` is
unreachable.

What a plotter actually holds is `GenericPlot(plotmethod: str, *args, **kwargs)` — a matplotlib
method name, positional args that are ndarrays or scalars, and styling kwargs. That is
serializable. The one hazard is that `*args`/`**kwargs` are arbitrary, so a caller *can* put a
live object in there (`transform=ax.transAxes`, a `Colormap`, a `Path`).

**Consequence, to be documented in the docstrings:** a loaded plot re-renders its overlays at the
resolution they were sampled at. Changing the binning after load does not recompute them — the
model is not there to re-evaluate.

## Decisions

**Scope: all three plotters.** `HistogramPlotter`, `GenericPlotter`, `Histogram2DPlotter`.
`GenericPlotter` is the simplest of the three (pure `GenericPlot`/`InsetPlot` composition, no
histogram) and shares the entire serialization core, so covering it costs little beyond
`HistogramPlotter` alone.

**2D saves the spec; data is re-attached at load.** `Histogram2DPlot` calls `ax.hist2d` on raw
event arrays (`histogramplot.py:463`) and stores no 2D counts, so there is nothing binned to save.
`Histogram2DPlotter.save` therefore writes styling, limits, `cmap`/`norm`/`cmin`/`cmax`, labels
and variables — everything except the events — and `load` requires `xhistogram=`/`yhistogram=`.
Embedding raw arrays was rejected: it reintroduces exactly the payload #9 removed (file size
scaling with sample size), and #9's size-independence test exists to stop that creeping back.
Refusing outright was rejected because a plot *specification* is what the issue asks for, and the
2D spec is worth saving even when its data is not.

**Unserializable values: refuse by default, explicit opt-out.** `save(path)` raises. Nothing is
written and the plotter is left untouched. `save(path, skip_unserializable=True)` drops the
offending entries, records them in the file, and `load` re-emits them as a `UserWarning`. Silent
best-effort was rejected: this library has just shipped two fixes for silent divergence (#26's
`legend_ncol`, #37's discarded errors), and a loaded plot that renders differently with no error
is the same failure in a new place. The opt-out exists because refusing outright would make one
stray `transform=` kwarg block saving an otherwise perfectly serializable plot.

**Only keyword arguments are skippable.** An unserializable *positional* argument always raises,
even under `skip_unserializable=True`: dropping one shifts every later argument by a position and
silently changes which matplotlib call gets made, which is a worse outcome than refusing.

**Format: JSON, one file per plotter.** `HistogramPlotter` embeds its histogram via #9's
`as_binned_dict`, so a single ~2 KB file holds spec plus data — the "hand a colleague one file"
case from the issue. `PLOT_FORMAT_VERSION = 1` is separate from #9's `SAVE_FORMAT_VERSION`: the
payloads have different shapes and will evolve independently, and the embedded histogram payload
keeps its own nested `format_version`, so each layer validates what it owns.

## The serialization core

A new module, `src/afplotter/utilities/plotspec.py`. It knows nothing about plotters — only how to
turn a small set of value kinds into JSON and back:

```python
encode_value(value) -> Any            # ndarray -> {"__ndarray__": [...]}
                                      # tuple   -> {"__tuple__": [...]}
                                      # str/int/float/bool/None/list/dict pass through
                                      # anything else -> raises UnserializableValue
decode_value(data) -> Any
encode_generic_plot(plot) -> dict     # {"plotmethod": ..., "args": [...], "kwargs": {...}}
decode_generic_plot(data) -> GenericPlot
encode_inset(inset, plot_refs) -> dict
decode_inset(data, resolved_plots) -> InsetPlot
```

Tuples need an explicit marker because JSON collapses them to lists, and `figsize`, `xlim`, `ylim`,
`watermark_position` and `bbox_to_anchor` are all tuples that matplotlib treats differently from
lists in places.

`UnserializableValue` carries the offending value's type and `repr`; the plotter layer catches it
and re-raises a `ValueError` that names the location, e.g.:

```
generic_plots[2] ("plot"): kwarg 'transform' holds a matplotlib Transform, which cannot be
saved. Remove it, pass skip_unserializable=True, or set it after load.
```

## What each plotter saves

**The `BasePlotter` block**, shared by all three: `figsize`, `label`, `xlabel`, `ylabel`,
`watermark`, `luminosity_value`, `luminosity_unit`, `log`, `xlog`, `legend_max_rows`,
`legend_title`, `legend_loc`, `xlim`, `ylim`, `savedir`, `saveformat`, `savename`, `savepath`,
`watermark_position`, `text`, `generic_text`.

This list is **hardcoded, not scraped from `vars()`/`__dict__`**. A hardcoded list fails loudly
when someone adds a property and forgets it; scraping would silently start persisting private
state and would break the moment an attribute holds a live object.

**Restoration writes the private attributes** (`_xlabel`, not `xlabel`). `HistogramPlotter`
(`histogramplot.py:496,500`) and `Histogram2DPlotter` (`:885,889`) override `xlabel`/`ylabel` as
read-only properties derived from their `HistogramVariable`, so assigning through the public name
raises `AttributeError`.

**`HistogramPlotter`:** the `BasePlotter` block, `variable` (a `HistogramVariable` dataclass —
`name`, `unit`), the `HistogramPlot` display flags (`stacked`, `sig_extra`, `uncertainty`,
`data_only`, `density`, `log`, `linewidth`, `edgecolor`), the embedded `Histogram` (and
`data_hist`, if set), `generic_plots`, `pull_plots`, `_insets`, `pull_ylim`, `pull_label`,
`color_map_kwargs`.

**`GenericPlotter`:** the `BasePlotter` block, `_plots`, `_insets`.

**`Histogram2DPlotter`:** the `BasePlotter` block, `xvariable`, `yvariable`, the `Histogram2DPlot`
settings (`density`, `log`, `cmap`, `norm`, `cmin`, `cmax`, `cbar_label`), `generic_plots`.

Never saved: `_ax` and any other live matplotlib object.

## The API

```python
HistogramPlotter.save(path, skip_unserializable=False) -> None
HistogramPlotter.load(path) -> HistogramPlotter

GenericPlotter.save(path, skip_unserializable=False) -> None
GenericPlotter.load(path) -> GenericPlotter

Histogram2DPlotter.save(path, skip_unserializable=False) -> None
Histogram2DPlotter.load(path, xhistogram, yhistogram) -> Histogram2DPlotter
```

`load` returns a fully editable plotter: adjust `ylim`, add overlays, call `plot()`.

`load` raises `ValueError` on an unrecognised `format_version`, on a non-object top level, and on a
missing required key — matching `Histogram.load`'s existing failure modes.

## Insets are references, not copies

`InsetPlot.plots` defaults to `[self.histplot] + self.generic_plots` (`histogramplot.py:559`) or
`self._plots` (`genericplot.py:148`) — the *same objects* the main axes replays. Encoding them
naively would duplicate every array and, worse, break that identity on load: an inset meaning "the
whole plot, zoomed" would silently become a frozen copy that no longer tracks the plot it zooms.

Each inset therefore stores symbolic references — `{"histplot": true, "generic_plots": [0, 1]}` —
resolved back to the live objects at load. An entry in `plots` that is not one of the plotter's own
objects always raises, on the same reasoning as an unserializable positional argument: dropping it
would remove a curve from the inset, not a style, so `skip_unserializable` does not apply to it.

The rest of `InsetPlot`'s configuration (`xlim`, `ylim`, `width`, `height`, `loc`, `borderpad`,
`title`, `mark_region`, `mark_kwargs`, `tick_labelsize`, `title_fontsize`, `bbox_to_anchor`) is
plain scalars and round-trips directly.

## Testing

Fixtures use values a broken implementation would not reproduce by accident — every scalar
asserted is a *non-default* value, so an implementation that silently constructs a fresh plotter
fails. (#9's spike produced a false PASS from exactly this trap: five metadata checks hardcoded to
the value the broken code also returned.)

- **Scalar round-trip.** Every field in the `BasePlotter` block set to a non-default value
  (`figsize=(7, 3)`, not the default `(12, 8)`), asserted individually after load.
- **Tuple fidelity.** `figsize` and `watermark_position` come back as `tuple`, not `list` —
  `assert isinstance(loaded.figsize, tuple)`, which a marker-less JSON round-trip fails.
- **Read-only property restore.** A loaded `HistogramPlotter` has the right `variable` and derives
  the right `xlabel`, proving restoration went through `_xlabel` rather than raising.
- **Overlay round-trip.** A `GenericPlot` with ndarray args and styling kwargs: `plotmethod`,
  `np.allclose` on each arg, and the kwargs dict all match.
- **Inset identity.** After load, `loaded._insets[0].plots[0] is loaded.histplot` — the reference
  is live, not a copy.
- **Refusal.** `save` with a `transform=` kwarg raises `ValueError` naming `generic_plots[2]` and
  `transform`, and **writes no file** (`assert not path.exists()`).
- **Opt-out.** The same plotter with `skip_unserializable=True` writes; `load` emits a
  `UserWarning` naming the dropped entry (`pytest.warns(UserWarning, match="transform")`).
- **2D contract.** `Histogram2DPlotter.load` without histograms raises `TypeError`; with them, the
  spec fields are restored and `plot()` runs.
- **Size independence.** A `HistogramPlotter` built from 1,000 vs 100,000 events saves to files
  within 10% of each other — #9's guard, re-applied at this layer.
- **Render equivalence.** `load(...).plot(save=True)` writes a PNG, and a separate `save=False`
  render is compared against the original plotter's axes (line count and `get_ydata()` on the
  overlay). Round-tripping a dict is not the same as re-rendering a plot; only this test covers
  the gap between them.

## Out of scope

- **Re-evaluating models at a new binning.** Impossible by construction — the callable is gone
  before `save` is ever reachable. Documented in the docstrings so nobody expects it.
- **A raw-array format for `Histogram2DPlot`.** Rejected above.
- **Saving figures rather than specs.** matplotlib already has `savefig` and pickle; the point of
  this issue is an editable specification.
- **`add_pull_data`'s data-vs-MC pull.** Needs no special handling — it produces `GenericPlot`s
  like everything else and round-trips free.
