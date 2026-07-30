# Adaptive Watermark/Luminosity Text Spacing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the `∫` glyph in the luminosity row overlapping the watermark row above it at large `text_size` (e.g. 36+, used for paper-ready figures), by making row spacing adapt to actually-rendered text and shrinking the glyph that triggers it.

**Architecture:** Two independent, additive changes to `src/afplotter/baseplotter.py`, both confined to `BasePlotter`. (1) `luminosity` (a `@property`) drops `\int` from its mathtext span in favor of the plain unicode `∫` rendered in the regular font. (2) `_add_text_to_plot` replaces its three hardcoded axes-fraction row offsets with a measured-bbox cursor: after drawing each row of text, its rendered bbox (via the existing `get_window_extent(renderer).transformed(ax.transAxes.inverted())` pattern already used for the watermark's x-position) determines where the next row starts.

**Tech Stack:** Python 3.10+, matplotlib (`Text.get_window_extent`, `Axes.transAxes`), pytest.

## Global Constraints

- Python 3.10+ typing: no `typing.Optional`/`List`/`Dict` imports (native `|`, builtin generics only).
- reST docstrings (`:param:`/`:return:`) on public functions/classes — `_add_text_to_plot` is private (leading underscore), existing one-line docstring style is fine, no reST needed there.
- No import-time filesystem/env side effects (unaffected by this change — no new imports).
- Line length 120 (ruff).
- Tests must be falsifiable: assert on rendered bbox geometry, not "didn't crash" (per `CLAUDE.md` testing philosophy). Every new test in this plan was verified against the *current* code first to confirm it fails for the right reason.
- `pre-commit run --all-files` (ruff + mypy) must pass before each commit.

---

## File Structure

- **Modify:** `src/afplotter/baseplotter.py`
  - `luminosity` property (currently lines 173-175): glyph change.
  - `_add_text_to_plot` (currently lines 294-347): row-spacing rewrite.
- **Modify:** `tests/test_baseplotter.py` — new regression tests appended near the existing `_add_text_to_plot`/`luminosity` tests (after line 144, before `test_set_axislimits_linear_expands_ylim_for_legend`).

No new files. No changes to any other plotter class — every caller goes through `BasePlotter._add_text_to_plot`.

---

## Task 1: Plain unicode `∫` in the luminosity label

**Files:**
- Modify: `src/afplotter/baseplotter.py:173-175`
- Test: `tests/test_baseplotter.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `BasePlotter.luminosity` (`@property`, returns `str`) — same signature, new content (no `\int`, contains `∫` outside `$...$`). Read by `_add_text_to_plot` in Task 2 exactly as today (`self.luminosity`).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_baseplotter.py`, directly after `test_luminosity_formats_with_zero_decimals` (line 76):

```python
def test_luminosity_uses_plain_integral_sign_not_mathtext_int():
    """The \\int mathtext glyph has a tall ascender/descender that overlaps
    the watermark row at large text_size; the plain unicode character avoids
    that by rendering in the regular (non-math) font instead."""
    plotter = ConcretePlotter()
    plotter.luminosity_value = 408.0
    assert "\\int" not in plotter.luminosity
    assert "∫" in plotter.luminosity
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_baseplotter.py::test_luminosity_uses_plain_integral_sign_not_mathtext_int -v`
Expected: FAIL — `assert '\\int' not in plotter.luminosity` fails because the current property still contains `\int`.

- [ ] **Step 3: Change the property**

In `src/afplotter/baseplotter.py`, replace:

```python
    @property
    def luminosity(self) -> str:
        return f"$\\int\\,L\\,\\mathrm{{d}}t\\;=\\;${self.luminosity_value:.0f}$\\; \\mathrm{{{self.luminosity_unit}}}^{{-1}}$"
```

with:

```python
    @property
    def luminosity(self) -> str:
        return f"∫ $L\\,\\mathrm{{d}}t\\;=\\;${self.luminosity_value:.0f}$\\;\\mathrm{{{self.luminosity_unit}}}^{{-1}}$"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_baseplotter.py::test_luminosity_uses_plain_integral_sign_not_mathtext_int -v`
Expected: PASS

- [ ] **Step 5: Run the full existing baseplotter test suite to confirm no other test depended on the old string**

Run: `uv run pytest tests/test_baseplotter.py -v`
Expected: All PASS, including `test_luminosity_formats_with_zero_decimals` and `test_add_text_to_plot_renders_watermark_and_luminosity` (both key off `plotter.luminosity` dynamically, not a hardcoded string, so they adapt automatically).

- [ ] **Step 6: Commit**

```bash
git add src/afplotter/baseplotter.py tests/test_baseplotter.py
git commit -m "fix: render luminosity's integral sign as plain unicode, not mathtext \\int"
```

---

## Task 2: Measured-bbox row spacing in `_add_text_to_plot`

**Files:**
- Modify: `src/afplotter/baseplotter.py:294-347` (the `_add_text_to_plot` method)
- Test: `tests/test_baseplotter.py`

**Interfaces:**
- Consumes: `self.watermark_position: tuple[float, float]` (existing property, unchanged meaning: anchors the first row only). `self.luminosity: str` (from Task 1). `self.text: list[str]` (existing, via `add_text`). `self.generic_text: list[dict]` (existing, untouched by this task).
- Produces: `_add_text_to_plot(ax: plt.Axes) -> None` — same signature and same set of rendered strings as before (experiment name, watermark, optional luminosity, each `add_text()` line, each `generic_text` entry); only the y-positions of the luminosity row and `add_text()` rows change from fixed offsets to measured ones.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_baseplotter.py`, directly after `test_add_text_to_plot_watermark_spacing_holds_at_reduced_font_size` (line 144, right before `test_set_axislimits_linear_expands_ylim_for_legend`):

```python
def _bbox(ax, renderer, label):
    text = {t.get_text(): t for t in ax.texts}[label]
    return text.get_window_extent(renderer=renderer).transformed(ax.transAxes.inverted())


def test_add_text_to_plot_luminosity_does_not_overlap_watermark_row_at_large_font_size():
    """Regression test for the \\int glyph in the luminosity row growing tall
    enough at large text_size to overlap the watermark row above it — this is
    the root cause behind the reported "integral sign overlaps the watermark"
    bug. Confirmed against the pre-fix code: gap was -0.236 (a large overlap)
    at text_size=48 before this fix."""
    set_experiment("BelleII")
    plotter = ConcretePlotter()
    plotter.set_matplotlibrc_params(48)
    plotter.luminosity_value = 408.0
    fig, ax = plt.subplots()
    plotter._add_text_to_plot(ax=ax)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    watermark_bbox = _bbox(ax, renderer, plotter.watermark)
    luminosity_bbox = _bbox(ax, renderer, plotter.luminosity)
    assert watermark_bbox.y0 >= luminosity_bbox.y1
    plt.close(fig)


def test_add_text_to_plot_luminosity_spacing_holds_at_reduced_font_size():
    """Regression check: the fix must not break spacing at the smaller font
    size used by the bundled examples (examples/histogram_with_pull.py etc.)."""
    set_experiment("BelleII")
    plotter = ConcretePlotter()
    plotter.set_matplotlibrc_params(16)
    plotter.luminosity_value = 408.0
    fig, ax = plt.subplots()
    plotter._add_text_to_plot(ax=ax)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    watermark_bbox = _bbox(ax, renderer, plotter.watermark)
    luminosity_bbox = _bbox(ax, renderer, plotter.luminosity)
    assert watermark_bbox.y0 >= luminosity_bbox.y1
    plt.close(fig)


def test_add_text_to_plot_extra_text_rows_do_not_overlap_luminosity_at_large_font_size():
    """add_text() rows must stack below the luminosity row without overlap
    too — the fix applies to every row, not just the luminosity one."""
    set_experiment("BelleII")
    plotter = ConcretePlotter()
    plotter.set_matplotlibrc_params(48)
    plotter.luminosity_value = 408.0
    plotter.add_text("(Preliminary)")
    fig, ax = plt.subplots()
    plotter._add_text_to_plot(ax=ax)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    luminosity_bbox = _bbox(ax, renderer, plotter.luminosity)
    extra_bbox = _bbox(ax, renderer, "(Preliminary)")
    assert luminosity_bbox.y0 >= extra_bbox.y1
    plt.close(fig)


def test_add_text_to_plot_multiple_extra_text_rows_stack_without_overlap():
    """Two add_text() rows must not overlap each other either."""
    set_experiment("BelleII")
    plotter = ConcretePlotter()
    plotter.set_matplotlibrc_params(48)
    plotter.add_text("(Preliminary)")
    plotter.add_text("Signal region")
    fig, ax = plt.subplots()
    plotter._add_text_to_plot(ax=ax)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    first_bbox = _bbox(ax, renderer, "(Preliminary)")
    second_bbox = _bbox(ax, renderer, "Signal region")
    assert first_bbox.y0 >= second_bbox.y1
    plt.close(fig)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_baseplotter.py -k "does_not_overlap_watermark_row_at_large or extra_text_rows_do_not_overlap or multiple_extra_text_rows_stack" -v`
Expected: FAIL for `test_add_text_to_plot_luminosity_does_not_overlap_watermark_row_at_large_font_size` (assertion `watermark_bbox.y0 >= luminosity_bbox.y1` fails, matching the confirmed -0.236 gap) and for `test_add_text_to_plot_extra_text_rows_do_not_overlap_luminosity_at_large_font_size` (`self.text` row is at `y - 0.076 - 0.05`, also too close at large font). `test_add_text_to_plot_luminosity_spacing_holds_at_reduced_font_size` may already PASS at the small size — that's fine, it's a regression guard, not required to fail first.

- [ ] **Step 3: Rewrite `_add_text_to_plot`**

Replace the full method body in `src/afplotter/baseplotter.py` (currently lines 294-347):

```python
    def _add_text_to_plot(self, ax: plt.Axes) -> None:
        """Handling of different texts in the plot."""
        x = self.watermark_position[0]
        y = self.watermark_position[1]
        row_margin = 0.01
        experiment_text = ax.text(
            x,
            y,
            get_experiment().labels.get("experiment", ""),
            ha="left",
            transform=ax.transAxes,
            style="italic",
            alpha=0.95,
            weight="bold",
            fontsize=plt.rcParams["xtick.labelsize"],
        )
        # The watermark's x-position depends on the rendered width of the
        # experiment-name text above, which varies with font size and the
        # experiment's name itself — a fixed offset only holds for one font size.
        ax.figure.canvas.draw()
        renderer = ax.figure.canvas.get_renderer()  # type: ignore
        experiment_bbox = experiment_text.get_window_extent(renderer=renderer).transformed(ax.transAxes.inverted())
        watermark_text = ax.text(
            experiment_bbox.x1 + 0.02,
            y,
            self.watermark,
            ha="left",
            transform=ax.transAxes,
            alpha=0.8,
            fontsize=plt.rcParams["xtick.labelsize"],
        )
        # Rows below this one start from the lower of the two texts sharing
        # it, so spacing tracks whichever glyph actually descends furthest
        # (e.g. italics, descenders, or — for the luminosity row below — the
        # tall integral sign) instead of a fixed fraction tuned for one font
        # size only.
        watermark_bbox = watermark_text.get_window_extent(renderer=renderer).transformed(ax.transAxes.inverted())
        y_cursor = min(experiment_bbox.y0, watermark_bbox.y0) - row_margin

        if self.luminosity_value:
            luminosity_text = ax.text(
                x,
                y_cursor,
                self.luminosity,
                ha="left",
                va="top",
                transform=ax.transAxes,
                alpha=0.8,
                fontsize=plt.rcParams["xtick.labelsize"],
            )
            luminosity_bbox = luminosity_text.get_window_extent(renderer=renderer).transformed(ax.transAxes.inverted())
            y_cursor = luminosity_bbox.y0 - row_margin

        for text in self.text:
            extra_text = ax.text(
                x,
                y_cursor,
                text,
                ha="left",
                va="top",
                transform=ax.transAxes,
                alpha=0.8,
                fontsize=plt.rcParams["legend.fontsize"],
            )
            extra_bbox = extra_text.get_window_extent(renderer=renderer).transformed(ax.transAxes.inverted())
            y_cursor = extra_bbox.y0 - row_margin

        for text_wargs in self.generic_text:
            text_wargs["transform"] = ax.transAxes
            ax.text(**text_wargs)
```

Notes for the implementer:
- The experiment/watermark row keeps its original `va="baseline"` (matplotlib default, unspecified) so `watermark_position` still means exactly what it did before for that row.
- The luminosity row and each `add_text()` row switch to `va="top"`, anchoring `y_cursor` at each row's *top* — this makes `y_cursor` a literal "next available top" cursor, consistent with `y_cursor = <previous row bottom> - row_margin`.
- `row_margin` is a small constant cushion, not a scaling factor — the actual scaling comes from `get_window_extent` reflecting the real rendered size at whatever `text_size` is active.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_baseplotter.py -v`
Expected: All PASS, including the 4 new tests from Step 1 and every pre-existing test in the file (in particular `test_add_text_to_plot_renders_watermark_and_luminosity`, `test_add_text_to_plot_watermark_does_not_overlap_experiment_name_at_default_size`, and `test_add_text_to_plot_watermark_spacing_holds_at_reduced_font_size`, none of which this task should change the behavior of — they only test the experiment/watermark row, which keeps its original positioning).

- [ ] **Step 5: Run the full project test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS. This catches any other test that happens to render text via `_add_text_to_plot` indirectly (e.g. through `HistogramPlotter.plot()`).

- [ ] **Step 6: Lint and type-check**

Run: `uv run pre-commit run --all-files`
Expected: ruff (lint + format) and mypy both pass. If ruff reformats anything, re-stage before committing.

- [ ] **Step 7: Commit**

```bash
git add src/afplotter/baseplotter.py tests/test_baseplotter.py
git commit -m "fix: make watermark/luminosity/extra-text row spacing track actual rendered text size"
```

---

## Task 3: Regenerate the bundled examples and verify visually

**Files:**
- None modified (verification only) — runs the existing `examples/histogram_with_pull.py`, which sets `luminosity_value = 62.8` and calls `set_matplotlibrc_params(18)`, giving a real (if modest) exercise of both changed code paths.

**Interfaces:**
- Consumes: `HistogramPlotter.plot(save=True)` (existing, unchanged signature) — indirectly exercises `_add_text_to_plot` and `luminosity` via `BasePlotter`.
- Produces: nothing new; this task is a manual visual gate, not code.

- [ ] **Step 1: Run the example**

Run: `uv run python examples/histogram_with_pull.py`
Expected: exits 0, writes `examples/output/histogram_with_pull.png`.

- [ ] **Step 2: Inspect the output**

Open `examples/output/histogram_with_pull.png` and confirm the `∫L dt = 63 fb⁻¹` line renders cleanly below the `Belle II (Own Work)` line with no visible overlap, and that the `∫` glyph looks reasonably sized (not a stray tiny or misaligned character next to the rest of the mathtext expression).

- [ ] **Step 3: Spot-check a large text_size manually**

Run this one-off script (no need to save it) to confirm the fix at the exact font size that motivated this plan:

```bash
uv run python -c "
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from afplotter.baseplotter import BasePlotter
from afplotter.experiments.context import set_experiment

class ConcretePlotter(BasePlotter):
    pass

set_experiment('BelleII')
plotter = ConcretePlotter()
plotter.set_matplotlibrc_params(36)
plotter.luminosity_value = 62.8
fig, ax = plt.subplots(figsize=(12, 8))
plotter._add_text_to_plot(ax=ax)
fig.savefig('/tmp/watermark_check.png', dpi=150)
print('saved /tmp/watermark_check.png')
"
```

Open `/tmp/watermark_check.png` and confirm no overlap at `text_size=36`.

- [ ] **Step 4: No commit needed**

This task only verifies; nothing changes. If Step 2 or Step 3 reveal a visible problem despite passing tests, stop and re-open Task 2 rather than proceeding — the bbox-based tests are a proxy for "looks right," not a replacement for looking.

---

## Self-Review Notes

- **Spec coverage:** Both spec sections ("1. Measured-bbox row spacing" and "2. Luminosity glyph") map to Task 2 and Task 1 respectively. The spec's "Testing" section maps to the tests in both tasks (glyph assertion in Task 1 Step 1; overlap assertions at small/large `text_size` in Task 2 Step 1). The spec's "Out of scope" items (generic_text positioning, the earlier demo's legend/watermark horizontal fix) are untouched by this plan, as intended.
- **Placeholder scan:** No TBD/TODO; every step has literal code or an exact command.
- **Type consistency:** `_add_text_to_plot(self, ax: plt.Axes) -> None` signature unchanged across both tasks. `luminosity` stays `-> str`. Test helper `_bbox(ax, renderer, label)` is defined once in Task 2 Step 1 and reused within that same task's tests only (Task 1's test doesn't need it).
