# Legend Column Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `legend_short_column` ("last"/"first"/"balanced") and `legend_column_sizes` (explicit per-column counts) to `BasePlotter`, rendered via placeholder padding, and persist both through save/load.

**Architecture:** `_add_legend` turns the active layout into a list of real-entry counts per column, then pads each column with the existing invisible `Line2D` placeholder up to the tallest column (skipped for `"balanced"` and for one column), so matplotlib's even split of the rectangular grid reproduces the intended columns.

**Tech Stack:** Python 3.10+, matplotlib, pytest (Agg).

**Spec:** `docs/superpowers/specs/2026-10-29-legend-column-layout-design.md`

## Global Constraints

- `legend_short_column` default `"last"`; allowed exactly `"last"`, `"first"`, `"balanced"`; setter raises `ValueError` otherwise, naming the allowed values.
- `legend_column_sizes` default `None`; type `list[int] | None`; setter raises `ValueError` on `[]` or any size < 1.
- When `legend_column_sizes` is set it wins: `ncol = len(sizes)`, entries assigned in order, `legend_short_column` and (for layout) `legend_max_rows` ignored.
- `sum(sizes) != len(labels)` → `ValueError` from `_add_legend` stating both numbers. No labels → no legend, no error.
- Otherwise `ncol = ceil(n / legend_max_rows)` in every mode.
- `"last"` output must be identical to the current branch behaviour (existing tests stay green unchanged).
- `"balanced"` adds no placeholders.
- Placeholder: the existing `Line2D([], [], linestyle="none", marker="")` with label `""`. Short columns keep real entries at the top.
- `_set_axislimits` is not touched.
- Conventions: native `X | Y` typing, reST docstrings, line length 120.

## Review Focus

- `"first"` when `n` divides evenly by the cap (8, cap 4) must be `[4, 4]` with no placeholders — test `test_legend_short_column_first_even_split_has_no_padding`.
- `"first"` / `"balanced"` with a single column (3 entries, cap 4) → 3 texts, no padding — covered by the same parametrised single-column test.
- `legend_column_sizes` with one column (`[6]`, 6 entries) → one column, no padding — `test_legend_column_sizes_single_column`.
- Setting `legend_column_sizes = None` after a list restores automatic layout — `test_legend_column_sizes_none_restores_auto`.
- A size list stored and later mutated by the caller must not silently change the plotter's layout — the setter stores a copy (`list(sizes)`); `test_legend_column_sizes_setter_copies`.

---

### Task 1: Short-column modes and explicit column sizes

**Files:**
- Modify: `src/afplotter/baseplotter.py` (`__init__` attribute block ~line 103; new properties next to `legend_max_rows` ~178-200; `_add_legend` ~434-460)
- Modify: `docs/getting-started.md:25`
- Test: `tests/test_baseplotter.py`

**Interfaces:**
- Produces: `BasePlotter.legend_short_column` (property, `str`, private attr `_legend_short_column`), `BasePlotter.legend_column_sizes` (property, `list[int] | None`, private attr `_legend_column_sizes`). Task 2 relies on these exact private names (save/load writes private attributes).

- [ ] **Step 1: Write failing tests** in `tests/test_baseplotter.py`, reusing `_legend_columns` (extend it with optional `short_column` / `column_sizes` kwargs that are set on the plotter before `_add_legend`):

```python
def test_legend_short_column_defaults_to_last():
    assert ConcretePlotter().legend_short_column == "last"
    assert ConcretePlotter().legend_column_sizes is None

def test_legend_short_column_first():
    cols = _legend_columns(max_rows=4, n_labels=6, short_column="first")
    assert cols == [["entry 0", "entry 1"], [f"entry {i}" for i in range(2, 6)]]
    assert [len(c) for c in _legend_columns(max_rows=4, n_labels=9, short_column="first")] == [1, 4, 4]

def test_legend_short_column_first_keeps_entries_at_top():
    # 6 entries, cap 4, "first": in column 1 the two real labels' y (window extent y0) are both
    # greater than every placeholder's y in that column (matplotlib y grows upward).

def test_legend_short_column_first_even_split_has_no_padding():
    # 8 entries, cap 4, "first" -> [4, 4] and exactly 8 legend texts

@pytest.mark.parametrize("mode", ["first", "balanced"])
def test_legend_short_column_single_column_not_padded(mode):
    # 3 entries, cap 4 -> exactly 3 legend texts

def test_legend_short_column_balanced():
    # 6 entries, cap 4 -> column sizes [3, 3] and exactly 6 legend texts (no placeholders)

def test_legend_short_column_rejects_unknown():
    with pytest.raises(ValueError, match="first"):
        ConcretePlotter().legend_short_column = "middle"

def test_legend_column_sizes_explicit():
    cols = _legend_columns(max_rows=4, n_labels=6, column_sizes=[3, 1, 2])
    assert cols == [["entry 0", "entry 1", "entry 2"], ["entry 3"], ["entry 4", "entry 5"]]

def test_legend_column_sizes_override_short_column():
    # column_sizes=[2, 4] with short_column="balanced" -> [2, 4]

def test_legend_column_sizes_single_column():
    # [6] with 6 entries -> one column, exactly 6 texts

def test_legend_column_sizes_mismatch_raises():
    # [2, 4] with 7 labelled lines -> pytest.raises(ValueError, match="7") around _add_legend

@pytest.mark.parametrize("bad", [[], [2, 0], [3, -1]])
def test_legend_column_sizes_rejects_invalid(bad):
    with pytest.raises(ValueError):
        ConcretePlotter().legend_column_sizes = bad

def test_legend_column_sizes_none_restores_auto():
    # set [3, 3] then None; 6 entries cap 4 -> [4, 2]

def test_legend_column_sizes_setter_copies():
    # sizes = [2, 4]; plotter.legend_column_sizes = sizes; sizes.append(1)
    # -> plotter.legend_column_sizes == [2, 4]
```

Fill the comment-only tests in with concrete assertions as described.

- [ ] **Step 2: Run to verify RED**

Run: `uv run pytest tests/test_baseplotter.py -k legend -v`
Expected: new tests FAIL (`AttributeError`/layout mismatches); all pre-existing legend tests PASS.

- [ ] **Step 3: Implement**

In `BasePlotter.__init__`: `self._legend_short_column: str = "last"`, `self._legend_column_sizes: list[int] | None = None`. Properties with reST docstrings and the validating setters described in Global Constraints (`legend_column_sizes` setter stores `list(value)`). In `_add_legend`, derive per-column counts:
- sizes set → validate sum against `len(labels)` (raise), counts = sizes;
- `"last"` → `[cap]*(ncol-1) + [n - cap*(ncol-1)]`; `"first"` → reversed of that; `"balanced"` → no padding, pass `ncol` through.
Then, when there is more than one column and counts are unequal, rebuild `lines`/`labels` column by column, appending `max(counts) - count` placeholders after each column's real entries. `ncol` passed to matplotlib is `len(counts)`. Update the `legend_max_rows` docstring sentence about filling to mention `legend_short_column` / `legend_column_sizes`. Add both property names to the legend line in `docs/getting-started.md:25`.

- [ ] **Step 4: Run to verify GREEN**

Run: `uv run pytest tests/ -q`
Expected: all pass, including the unchanged `test_legend_fills_columns_to_max_rows` etc.

- [ ] **Step 5: Lint/type**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/`
Expected: clean.

- [ ] **Step 6: Commit** — `feat: add legend_short_column and legend_column_sizes` + `Assisted-by:` trailer.

### Task 2: Persist the new legend settings through save/load

**Files:**
- Modify: `src/afplotter/utilities/plotspec.py` (`BASE_PLOTTER_FIELDS`, after `"legend_loc"`)
- Test: `tests/test_genericplot.py` (`test_generic_plotter_save_load_round_trips_the_base_block`)

**Interfaces:**
- Consumes: private attributes `_legend_short_column`, `_legend_column_sizes` from Task 1.

- [ ] **Step 1: Extend the round-trip test** — set `plotter.legend_short_column = "first"` and `plotter.legend_column_sizes = [2, 4]` alongside the other non-default values; assert `loaded.legend_short_column == "first"` and `loaded.legend_column_sizes == [2, 4]` (and `isinstance(..., list)`, mirroring the `xlim` tuple check).
- [ ] **Step 2: Add a backward-compat test** `test_save_load_without_legend_layout_keys_uses_defaults` in `tests/test_genericplot.py`: save a plotter, delete the two keys from the written JSON's base block, load → `"last"` and `None`. (Inspect the saved file format to locate the base block.)
- [ ] **Step 3: RED** — `uv run pytest tests/test_genericplot.py -k save_load -v`: round-trip test fails (values not persisted).
- [ ] **Step 4: Add both names to `BASE_PLOTTER_FIELDS`.** If `decode_value` returns the sizes as a non-list, normalise in the decode path so the type assertion holds.
- [ ] **Step 5: GREEN + full suite + lint/type** (commands as Task 1 Steps 4-5).
- [ ] **Step 6: Commit** — `feat: persist legend layout settings in save/load` + trailer.
