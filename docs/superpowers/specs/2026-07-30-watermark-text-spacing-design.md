# Adaptive watermark/luminosity text spacing

## Context

`BasePlotter._add_text_to_plot` (`src/afplotter/baseplotter.py`) draws the
top-left text block on every plot: the experiment name, the watermark string
next to it, an optional luminosity line below (`$\int\,L\,\mathrm{d}t\;=\;$...`),
and any `add_text()` lines below that. The vertical gaps between these rows
are hardcoded axes-fraction offsets (`y - 0.06` for the luminosity row,
`y - 0.076 - (i+1)*0.05` for each `add_text()` row), independent of the
`text_size` passed to `set_matplotlibrc_params(text_size)`.

At large `text_size` (e.g. 36+, used for paper-ready figures), the rendered
text grows but the fixed gaps don't, so the luminosity row's `\int` glyph —
whose mathtext rendering has an unusually tall ascender/descender — overlaps
the watermark row above it. This was observed while producing a demo plot at
`text_size=36`.

Two independent fixes address this:

1. Make the vertical spacing between rows adapt to the actual rendered text
   size, not just `text_size` in the abstract.
2. Shrink the luminosity row's worst offender — the `\int` glyph — by moving
   it out of mathtext.

## 1. Measured-bbox row spacing

`_add_text_to_plot` already solves an analogous problem for the watermark's
*x*-position: it draws the experiment-name text, forces a canvas draw, then
measures that text's rendered bbox via
`experiment_text.get_window_extent(renderer).transformed(ax.transAxes.inverted())`
to know exactly where to start the watermark text horizontally. This design
applies the same technique vertically.

Replace the hardcoded row offsets with a running cursor:

- Get one renderer at the top of the function (as today:
  `ax.figure.canvas.draw()` then `ax.figure.canvas.get_renderer()`).
- Track `y_cursor`, starting at `self.watermark_position[1]`.
- For the first row (experiment name + watermark, drawn side by side at the
  same y): after both `ax.text(...)` calls, measure both artists' bboxes in
  axes-fraction coordinates and take the smaller (lower) `y0` of the two as
  the row's bottom.
- Set `y_cursor = row_bottom - margin` for the next row, where `margin` is a
  small constant (e.g. `0.01`) axes-fraction gap for visual breathing room.
  Because `row_bottom` comes from the actual measured glyph extent (including
  descenders and unusually tall glyphs like `\int`), the effective gap between
  rows grows with `text_size` automatically — `margin` only adds a constant
  baseline cushion, it does not need to scale itself.
- Repeat for the luminosity row (if `luminosity_value` is set) and then for
  each `add_text()` row, each becoming its own measured row and updating
  `y_cursor` in turn.
- `generic_text` entries (`add_generic_text`) are unaffected — they already
  take fully explicit positions from the caller.

No new public API: `watermark_position` keeps its current meaning (the anchor
for the first row only); everything below it is now derived.

## 2. Luminosity glyph

Change the `luminosity` property (`baseplotter.py:174-175`) to move `\int`
out of the mathtext span and use the plain unicode `∫` character instead,
rendered in the regular (non-math) font:

```python
@property
def luminosity(self) -> str:
    return f"∫ $L\\,\\mathrm{{d}}t\\;=\\;${self.luminosity_value:.0f}$\\;\\mathrm{{{self.luminosity_unit}}}^{{-1}}$"
```

Matplotlib renders the portion of a text string outside `$...$` delimiters
with the normal (non-italic, non-math) font, so `∫` no longer carries the
oversized ascender/descender that LaTeX's `\int` renders with. The rest of
the expression (`L dt = value unit⁻¹`) stays as mathtext, unchanged.

## Testing

Both fixes get falsifiable regression tests in the existing baseplotter test
file:

- **Glyph**: assert `plotter.luminosity` does not contain `"\\int"` and does
  contain `"∫"`.
- **Spacing**: render the text block at a small `text_size` (e.g. 14) and a
  large one (e.g. 48). After each render, collect the watermark row's texts
  and the luminosity row's text from `ax.texts`, measure their bboxes via
  `get_window_extent`, and assert the luminosity row's top edge (`bbox.y1`)
  stays at or below the watermark row's bottom edge (`bbox.y0`) — i.e. no
  overlap — at both sizes. This is the check that fails against the current
  fixed-offset code at `text_size=48` and passes after the fix, so it
  actually distinguishes correct from incorrect behavior (per this repo's
  testing philosophy in `CLAUDE.md`).

No changes to `HistogramPlotter`/`GenericPlotter`/`Histogram2DPlotter` or any
other call site are needed — all consumers go through
`BasePlotter._add_text_to_plot`.

## Out of scope

- `generic_text`/`add_generic_text` positioning (caller-supplied, unaffected).
- The legend/watermark horizontal collision fixed manually in the earlier
  demo session (font size, `legend_loc`, `ylim`) — that was a per-plot layout
  choice, not a library bug.
