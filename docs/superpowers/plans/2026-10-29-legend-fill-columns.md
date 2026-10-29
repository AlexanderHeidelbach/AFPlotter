# Fill Legend Columns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each legend column hold exactly `legend_max_rows` entries (only the last column short) instead of matplotlib's balanced split.

**Architecture:** `BasePlotter._add_legend` pads the handle/label lists with invisible, empty-label placeholders up to `ncol * legend_max_rows` when `ncol > 1`; matplotlib's `np.array_split` then yields full columns and the placeholders sit at the bottom of the last one.

**Tech Stack:** Python 3.10+, matplotlib, pytest (Agg backend).

**Spec:** `docs/superpowers/specs/2026-10-29-legend-fill-columns-design.md`

## Global Constraints

- `ncol = ceil(n / legend_max_rows)` is unchanged.
- Pad only when `ncol > 1`; pad count is `ncol * legend_max_rows - n`.
- Placeholders draw nothing and have label `""`.
- `_set_axislimits` (headroom) is not touched.
- Default `legend_max_rows` stays 4; property name unchanged.
- Repo conventions: native `X | Y` typing, reST docstrings, line length 120.

## Review Focus

- Legend combined from several axes (`_add_legend(ax=[ax1, ax2])`) with `n > legend_max_rows` must pad the combined list, not per axis — covered by `test_legend_fills_columns_across_multiple_axes`.
- `n` an exact multiple of the cap (8 entries, cap 4) must add zero placeholders — covered by `test_legend_no_padding_when_columns_divide_evenly`.
- Placeholders must be invisible: no visible line/marker in the legend — covered by `test_legend_placeholders_are_invisible`.
- Real label order must be column-major reading order — covered in `test_legend_fills_columns_to_max_rows`.
- Single column (`n <= cap`) gets no padding — covered by `test_legend_single_column_is_not_padded`.

---

### Task 1: Fill legend columns to `legend_max_rows`

**Files:**
- Modify: `src/afplotter/baseplotter.py` (`legend_max_rows` property docstring ~178-189; `_add_legend` ~434-451)
- Test: `tests/test_baseplotter.py` (next to `test_legend_max_rows_caps_rows_and_grows_columns`)

**Interfaces:**
- Consumes: existing `BasePlotter._add_legend(self, ax: list[plt.Axes] | plt.Axes) -> None`, `ConcretePlotter` test helper.
- Produces: no new public API.

- [ ] **Step 1: Write the failing tests**

Add a helper and tests to `tests/test_baseplotter.py`:

```python
def _legend_columns(max_rows, n_labels):
    """Return the real (non-empty) legend labels grouped by column, left to right."""
    plotter = ConcretePlotter()
    plotter.legend_max_rows = max_rows
    fig, ax = plt.subplots()
    for i in range(n_labels):
        ax.plot([0, 1], [i, i], label=f"entry {i}")
    plotter._add_legend(ax=ax)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    columns: dict[int, list[str]] = {}
    for text in ax.get_legend().get_texts():
        if text.get_text():
            # Same 5px bucketing as _legend_column_count.
            columns.setdefault(round(text.get_window_extent(renderer).x0 / 5), []).append(text.get_text())
    plt.close(fig)
    return [columns[x] for x in sorted(columns)]


def test_legend_fills_columns_to_max_rows():
    cols = _legend_columns(max_rows=4, n_labels=6)
    assert [len(c) for c in cols] == [4, 2]  # matplotlib alone gives [3, 3]
    assert cols == [[f"entry {i}" for i in range(4)], ["entry 4", "entry 5"]]
    assert [len(c) for c in _legend_columns(max_rows=4, n_labels=9)] == [4, 4, 1]


def test_legend_single_column_is_not_padded():
    plotter = ConcretePlotter()
    plotter.legend_max_rows = 4
    fig, ax = plt.subplots()
    for i in range(3):
        ax.plot([0, 1], [i, i], label=f"entry {i}")
    plotter._add_legend(ax=ax)
    assert len(ax.get_legend().get_texts()) == 3
    plt.close(fig)


def test_legend_no_padding_when_columns_divide_evenly():
    # 8 entries, cap 4 -> two full columns, zero placeholders
    ...build as above with 8 labels...
    assert len(ax.get_legend().get_texts()) == 8


def test_legend_placeholders_are_invisible():
    # 6 entries, cap 4 -> 2 placeholders; every legend handle whose label is "" draws nothing
    ...build as above...
    legend = ax.get_legend()
    for handle, text in zip(legend.legend_handles, legend.get_texts()):
        if not text.get_text():
            assert not handle.get_visible() or <handle draws no line and no marker>


def test_legend_fills_columns_across_multiple_axes():
    # 3 labelled lines on ax1 + 3 on ax2, cap 4, _add_legend(ax=[ax1, ax2])
    # -> real labels per column [4, 2], in ax1-then-ax2 order
```

The invisibility assertion depends on the placeholder artist the implementer picks (e.g. `Line2D([], [], linestyle="none", marker="")` → assert `get_linestyle() == "None"` and `get_marker() in ("", "None", None)`; or `visible=False` → assert `not get_visible()`). Make it concrete for that choice — it must fail if the placeholder were a default visible `Line2D`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_baseplotter.py -k "legend" -v`
Expected: `test_legend_fills_columns_to_max_rows` and `test_legend_fills_columns_across_multiple_axes` FAIL (`[3, 3] != [4, 2]`); the single-column / divide-evenly / existing legend tests PASS (they pin current behaviour that must survive). `test_legend_placeholders_are_invisible` fails or is vacuous until padding exists — confirm it fails, e.g. by asserting first that exactly 2 empty-label entries exist.

- [ ] **Step 3: Implement padding in `_add_legend`**

After computing `ncol`, if `ncol > 1` append `ncol * self.legend_max_rows - len(labels)` placeholder handles and `""` labels to `lines`/`labels` before calling `ax[0].legend(...)`. Update the `legend_max_rows` docstring: columns are filled top-down to the cap, only the last column is short; drop nothing else from it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ -v`
Expected: all PASS, including `test_legend_max_rows_caps_rows_and_grows_columns` and `test_add_legend_combines_multiple_axes`.

- [ ] **Step 5: Lint, type-check, examples**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/`
Expected: clean.
Run: `uv run python examples/workflow_demo.py && git status --short docs/img/workflow/`
Expected: exit 0 and no diff under `docs/img/workflow/` (5 entries, cap 5 → single column, untouched).

- [ ] **Step 6: Commit**

```bash
git add src/afplotter/baseplotter.py tests/test_baseplotter.py
git commit -m "feat: fill legend columns up to legend_max_rows"
```
(with the repo's `Assisted-by:` trailer)
