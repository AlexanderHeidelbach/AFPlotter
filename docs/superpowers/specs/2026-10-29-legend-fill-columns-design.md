# Fill legend columns up to `legend_max_rows`

## Problem

`legend_max_rows` only decides the column count:

```python
# src/afplotter/baseplotter.py:445
ncol = ceil(len(labels) / legend_max_rows)
```

Matplotlib then distributes the entries over those columns with `np.array_split`, i.e. as evenly
as possible. The rendered row count is therefore `ceil(n / ncol)`, not `legend_max_rows`, and
raising the cap often changes nothing:

| entries | cap 3 | cap 4 (today) | cap 4 (wanted) |
|---|---|---|---|
| 5 | 3 + 2 | 3 + 2 | 4 + 1 |
| 6 | 3 + 3 | 3 + 3 | 4 + 2 |
| 9 | 3 + 3 + 3 | 3 + 3 + 3 | 4 + 4 + 1 |

The user sets `legend_max_rows = 4` with 6 entries and expects a 4-row legend; they get 3 rows.
This was equally true under the old name `legend_ncol` — the rename (`02e6e7f`) did not change
the math.

## Decision

`legend_max_rows` becomes an exact per-column fill target: columns fill top-down to the cap, and
only the last column is short.

- Column count is unchanged: `ncol = ceil(n / legend_max_rows)`.
- Entries keep their reading order (down the first column, then down the next).
- When everything fits in one column (`n <= legend_max_rows`) or `n` divides evenly by the cap,
  the layout is identical to today.

### Mechanism

Matplotlib has no "fill columns" option. `_add_legend` appends invisible, label-less placeholder
entries to the end of the handle/label lists so the total becomes `ncol * legend_max_rows`; with
every column then the same height, `np.array_split` puts exactly `legend_max_rows` entries in
each, and the placeholders land at the bottom of the last column, rendering as empty space.

Padding is applied only when `ncol > 1`. With a single column the padding would add empty rows
below the real entries, making the legend box taller for no reason.

Placeholders must draw nothing — no line, marker, or patch — and carry the empty string as label.
The choice of artist is left to the builder.

## Unchanged

- **Headroom.** `_set_axislimits` keeps reading `legend_max_rows` exactly as today (user's call).
  See `2026-08-04-legend-max-rows-rename-design.md` for why the headroom formula is its own
  problem.
- The default (4), the property name, and save/load (`utilities/plotspec.py` only stores the value).
- `examples/workflow_demo.py` uses 5 entries with `legend_max_rows = 5` → one column, so its
  committed images under `docs/img/workflow/` do not change and no bot commit results.

## Accepted side effect

Code that reads the legend back (`ax.get_legend().get_texts()`, `legend_handles`) sees the
placeholder entries as extra empty-string items. Nothing in the library does this. The existing
`test_add_legend_combines_multiple_axes` reads texts with 2 entries (single column, no padding)
and is unaffected.

## Docs

Update the `legend_max_rows` property docstring: it now states that each column is filled to the
cap and only the last column is short, instead of only describing the column-count derivation.

## Testing

Assert on rendered layout, not on internals: count real (non-empty) labels per column from text
x-positions (the approach `_legend_column_count` in `tests/test_baseplotter.py` already uses).

- 6 entries, cap 4 → real labels per column `[4, 2]` (fails on today's `[3, 3]`).
- 9 entries, cap 4 → `[4, 4, 1]`.
- 3 entries, cap 4 → one column, and the legend contains exactly 3 texts (no padding in the
  single-column case).
- Real labels keep their input order in column-major reading order.
- Existing `test_legend_max_rows_caps_rows_and_grows_columns` keeps passing.
