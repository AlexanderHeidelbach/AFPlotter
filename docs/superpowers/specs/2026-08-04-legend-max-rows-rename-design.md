# Rename `legend_ncol` to `legend_max_rows`

Issue: #26

## Problem

`BasePlotter.legend_ncol` does not set the legend's column count. It is a divisor:

```python
# src/afplotter/baseplotter.py:430
ncol = len(labels) // self.legend_ncol + (1 if len(labels) % self.legend_ncol != 0 else 0)
```

That is `ncol = ceil(len(labels) / legend_ncol)`. The property caps **rows** and lets columns
grow to fit. With the default of 4:

| labels | matplotlib receives | layout |
|---|---|---|
| 4 | `ncol=1` | 1 column × 4 rows |
| 8 | `ncol=2` | 2 columns × 4 rows |
| 12 | `ncol=3` | 3 columns × 4 rows |

Anyone setting `legend_ncol = 2` expecting two columns gets two *rows* per column, and the
column count moves the other way. The runtime behaviour is coherent; the name is wrong.

## Decision

Rename the property to `legend_max_rows`. Behaviour is unchanged — this is a naming fix and
nothing else.

The name states the cap and implies the growth direction, and it sits naturally beside
`legend_title` / `legend_loc`. `legend_max_rows_per_column` was rejected as unwieldy at every
use site; `legend_rows` was rejected because dropping "max" reads as an exact row count, which
it is not when the label count does not divide evenly — a milder version of the original
confusion.

## Scope

Behaviour is byte-identical. Both read sites are updated mechanically:

- `_add_legend` (`baseplotter.py:430`) keeps `ceil(len(labels) / max_rows)`.
- `_set_axislimits` (`baseplotter.py:403`) keeps passing the cap into the headroom formula.

Nothing under `docs/img/workflow/` re-renders, so `update-workflow-images.yml` does not produce
a bot commit on merge.

### Deliberately out of scope

Issue #26 floated fixing the headroom calculation in the same pass, on the grounds that
headroom is constant in the number of labels. Investigation showed that change is far larger
than the issue assumed, so it is excluded here and filed separately.

Three findings, all at `baseplotter.py:399-417`:

1. **Linear headroom is constant.** `ylim_top * (1 + 0.1 * lines_legend)` uses the *cap*, not
   the realised row count, so a 1-entry legend reserves the same 40% as a 4-entry one.
2. **Log headroom is violently sensitive.** `ylim_top * (1 + 10 ** (max(lines_legend, lines_text) / 2))`
   with the default 4 is `1 + 10**2` — **101× the data maximum** on every log-scale plot.
   Switching to a realised row count of 1 makes it ≈4.2×. That re-ranges every log plot in the
   library, and #26 never asked what the log formula *should* be.
3. **Headroom is reserved even when no legend is drawn.** `_add_legend` returns early when
   there are no labels, but `_set_axislimits` adds headroom unconditionally.

Any fix is further constrained by call order, which **differs between the two plotters**:

| Plotter | Order |
|---|---|
| `genericplot.py:164,172` | `_add_legend` → `_set_axislimits` |
| `histogramplot.py:830,832` | `_set_axislimits` → `_add_legend` |

So a realised-row-count headroom cannot read the drawn legend; it must gather labels itself via
`get_legend_handles_labels()`. (`Histogram2DPlotter` is unaffected — it sets `self.ylim`
explicitly before calling `_set_axislimits`, so the headroom branch never runs.)

This is filed as its own issue, linking back to this spec.

## Breaking change

`legend_ncol` is removed outright. No deprecation shim, no raising tombstone — consistent with
the project's pre-1.0 status, installation from a moving `main`, and the absence of any release
cadence that could retire a shim.

**Known consequence, accepted deliberately.** `BasePlotter` defines no `__slots__` and no
`__setattr__` guard, so stale caller code fails *silently*:

```python
plotter.legend_ncol = 5   # creates a dead attribute, no error
plotter.plot()            # renders with legend_max_rows = 4, the default
```

No `AttributeError`, no warning — the legend simply lays out differently. A raising tombstone
(a property whose getter and setter both raise, preserving no behaviour) was considered and
rejected in favour of a clean source tree. The break should therefore be called out in whatever
release-notes mechanism comes out of #6.

## Call sites

Seven references across four files:

| File | Reference |
|---|---|
| `src/afplotter/baseplotter.py:103` | `self._legend_ncol: int = 4` initialiser |
| `src/afplotter/baseplotter.py:178-183` | property getter + setter |
| `src/afplotter/baseplotter.py:403` | `lines_legend = self.legend_ncol` |
| `src/afplotter/baseplotter.py:430` | the `ncol` divisor |
| `examples/workflow_demo.py:93-97` | assignment **plus** an explanatory comment naming the property twice |
| `docs/getting-started.md:25` | property list |
| `tests/test_baseplotter.py:29,270` | default assertion, setter usage |

The `workflow_demo.py` comment explains *why* the value is raised to 5 ("force a single narrow
column") and needs rewording under the new name, not a find-and-replace.

The property currently has no docstring. It gains a reST one stating the semantics explicitly —
the name alone is what failed here, so the contract is written down this time.

## Testing

The two existing test references update mechanically. One new test is added, because **nothing
currently asserts the `ncol` mapping at all** — the rename's real risk is a later contributor
reading `legend_max_rows` and "fixing" the divisor into a straight pass-through to
`Axes.legend(ncol=...)`.

```
6 labels, legend_max_rows=3  ->  legend renders 2 columns
6 labels, legend_max_rows=6  ->  legend renders 1 column
```

Both cases are required: the first alone passes under a pass-through implementation for some
inputs, the second discriminates it.

Assert on **rendered geometry** — the count of distinct x-positions among the legend's text
artists — not on `Legend._ncols`. CI spans two matplotlib versions across the 3.10 and 3.14
matrix legs, and a private attribute is exactly what differs between them.

## Success criteria

- `grep -rn legend_ncol` returns nothing outside `docs/superpowers/` and `CC-Session-Logs/`
  (historical artifacts, left intact).
- The new column-count test passes, and fails if the divisor is replaced by a pass-through.
- Full suite, `ruff check`, and `mypy` green on both matrix legs.
- `examples/workflow_demo.py` exits 0, and running it leaves `git status` clean for
  `docs/img/workflow/` on the same interpreter that produced the committed PNGs. (Across
  matplotlib versions the bytes may legitimately differ; the check is that *this* change
  introduces no diff, not that the PNGs are version-independent.)
- A follow-up issue exists for the headroom findings.
