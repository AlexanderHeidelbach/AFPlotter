# Legend column layout: short column choice and explicit column sizes

Follows `2026-10-29-legend-fill-columns-design.md`, which made legend columns fill to
`legend_max_rows` with only the last column short, by padding with invisible placeholders.

## Why

A student wants maximal control over the legend layout. Their reference plot has 6 entries with
a cap of 4 laid out as 2 + 4 — the short column *first* — which today's fill-to-cap (4 + 2)
cannot produce. Beyond that, they want to set column sizes by hand.

## Decision

Two new `BasePlotter` properties, both persisted by save/load.

### `legend_short_column: str = "last"`

Chooses which column takes the remainder when `legend_max_rows` drives the layout.
`ncol = ceil(n / legend_max_rows)` in every mode.

| value | 6 entries, cap 4 | 9 entries, cap 4 | mechanism |
|---|---|---|---|
| `"last"` (default) | 4 + 2 | 4 + 4 + 1 | today's behaviour, unchanged |
| `"first"` | 2 + 4 | 1 + 4 + 4 | remainder in column 1, all others full |
| `"balanced"` | 3 + 3 | 3 + 3 + 3 | no padding: matplotlib's own even split (behaviour before the fill-columns change) |

The setter raises `ValueError` for any other value, naming the allowed ones.

### `legend_column_sizes: list[int] | None = None`

Explicit entry count per column, left to right, e.g. `[2, 4]` or `[3, 1, 5]`.

- When set, it takes precedence: entries are assigned in order (first `sizes[0]` entries to
  column 1, the next `sizes[1]` to column 2, …), and `ncol = len(sizes)`.
  `legend_short_column` is ignored, and `legend_max_rows` is ignored *for layout*.
- If `sum(sizes) != number of legend entries`, `_add_legend` raises `ValueError` stating both
  numbers (user's call: fail, never silently add a column). This check can only happen at draw
  time, when the entries are known. A plot with no legend entries draws no legend and raises
  nothing.
- The setter rejects (my call) an empty list and any size < 1 with `ValueError`; `None` resets
  to the automatic layout.

### Rendering rule shared by all modes

Every mode reduces to a list of real-entry counts per column. When the counts are not all equal,
each column is padded with invisible, label-`""` placeholders (the existing `Line2D` placeholder)
up to the tallest column, so short columns keep their entries at the top and the grid is
rectangular — matplotlib's even split of a rectangular grid then reproduces the intended columns
exactly. Entries keep their reading order: down column 1, then column 2.

`"balanced"` is the one exception: it passes the entries through unpadded, exactly as before the
fill-columns change. A single column is never padded.

(Builder's choice how to structure this; a single helper that turns a layout into per-column
counts, followed by one padding routine, is the natural shape.)

## Unchanged

- Headroom: `_set_axislimits` keeps reading `legend_max_rows` in every mode, including when
  `legend_column_sizes` is set (user's call from the previous spec).
- `legend_max_rows` name, default 4, and meaning.
- `examples/workflow_demo.py` output (single column, default mode).

## Save/load

Add `legend_short_column` and `legend_column_sizes` to `BASE_PLOTTER_FIELDS` in
`utilities/plotspec.py`. Files saved before this change lack the keys; `decode_base_plotter`
already skips missing keys, so they load with the defaults. A round-trip test must cover a
non-default value of each.

## Docs

reST docstrings on both properties. Add both to the legend property list in
`docs/getting-started.md` (`legend_max_rows`, `legend_title`, `legend_loc` line).

## Testing

Rendered layout, via real labels grouped by text x-position (helper `_legend_columns` in
`tests/test_baseplotter.py`):

- `"first"`, 6 entries, cap 4 → `[["entry 0", "entry 1"], ["entry 2", …, "entry 5"]]`.
- `"first"`, 9 entries, cap 4 → sizes `[1, 4, 4]`.
- `"balanced"`, 6 entries, cap 4 → `[3, 3]`, and no placeholder texts at all.
- `legend_column_sizes = [3, 1, 2]`, 6 entries → `[3, 1, 2]` in order, regardless of cap.
- `legend_column_sizes` sum mismatch (`[2, 4]`, 7 entries) → `ValueError` from `_add_legend`.
- Setter rejections: `legend_short_column = "middle"`, `legend_column_sizes = []`, `[2, 0]`.
- `"first"` with the short column's entries at the top: its real labels sit above the
  placeholders (y-position check), so the column is not bottom-aligned.
- Save/load round trip preserves `"first"` and `[2, 4]`.
