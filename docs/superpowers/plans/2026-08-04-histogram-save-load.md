# Histogram Save/Load Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `Histogram.save(path)` / `Histogram.load(path)` writing binned-only JSON, plus a clear error when a histogram without raw event data reaches the 2D plotter.

**Architecture:** `as_dict`/`from_dict` already round-trip everything through JSON, so this is file I/O over an existing serializer. `save` deep-copies the dict and nulls each entry's `array` before writing — never mutating the caller's histogram. A separate guard in `Histogram2DPlot.plot` converts an existing confusing failure into a named one.

**Tech Stack:** Python 3.10+, numpy, matplotlib, pytest, uv. No new dependencies.

Spec: `docs/superpowers/specs/2026-08-04-histogram-save-load-design.md`
Issue: #9
Branch: `feature/histogram-save-load`, already created off `main` at `9ac0030`. Spec committed at `2c50763`.

## Global Constraints

- **No new dependencies.** `json`, `copy`, and `pathlib` are stdlib. Runtime deps stay `matplotlib`, `numpy`, `polars`, `cycler`.
- **`save` must never mutate the caller's histogram.** Do not call `clear_array()` on live entries — that would destroy the user's data as a side effect of saving. Operate on a deep copy of the dict.
- **Python 3.10+ typing.** Native `X | Y` unions and builtin generics. No `typing.Optional`/`List`/`Dict`/`Tuple`/`Union`.
- **reST docstrings** (`:param:` / `:return:`) on public methods.
- **Line length 120** (ruff).
- **Falsifiable assertions only.** Every assertion needs an answer to "what specific bug makes this fail?" In particular, never build a fixture whose expected value would be produced by the broken code too.
- **Out of scope, from the spec:** wiring `save`/`load` into `LazyHistWrapper`'s caching; a 2D-capable format carrying raw arrays; any cross-tool interop or `hist` converter (settled by #8).
- Run commands from the repo root with `uv run`.

**Verified while writing this plan** — measured on the real classes, so a deviation means the surrounding code is wrong, not these facts:

- `copy.deepcopy(h.as_dict)` then setting `entry["array"] = None` for every entry in `"entries"` and `"signal"` produces a payload that `Histogram.from_dict` restores with counts, errors, binning, signal split and colors intact, and leaves the source histogram's arrays untouched.
- Payload sizes for a 1,200-event, 5-bin histogram: **655 bytes** binned-only versus **23,670 bytes** with arrays.
- `HistogramEntry.from_dict` already handles `array: None` correctly — it only converts keys that are not `None`.
- After loading, `get_data()` returns `[None]`, and `len([None]) > 0` is **true**, which is why `Histogram2DPlot.plot`'s existing length check does not catch this.

---

### Task 1: `save` and `load` on `Histogram`

**Files:**
- Modify: `src/afplotter/utilities/histogram.py` (imports at lines 1-4; add two methods to `Histogram`)
- Test: `tests/utilities/test_histogram.py` (append)

**Interfaces:**
- Consumes: the existing `Histogram.as_dict` property and `Histogram.from_dict` classmethod.
- Produces:
  - `Histogram.save(self, path: str | Path) -> None`
  - `Histogram.load(cls, path: str | Path) -> "Histogram"` (classmethod)
  - Module constant `SAVE_FORMAT_VERSION: int = 1`
  Task 2 does not consume these.

- [ ] **Step 1: Write the failing tests**

Append to `tests/utilities/test_histogram.py`:

```python
def test_save_load_round_trip(tmp_path):
    """Counts, errors, binning, signal split and styling must survive a save/load cycle.

    Fixture values are chosen so a broken round-trip cannot coincidentally pass: the errors
    are NOT sqrt(counts), so code that recomputes them instead of restoring them fails here.
    """
    hist = Histogram()
    hist.binning = np.linspace(0.0, 5.0, 6)
    hist.add_entry(
        HistogramEntry(
            name="bkg",
            latex_name="Background",
            counts=np.array([10.0, 20.0, 30.0, 40.0, 50.0]),
            errors=np.array([1.5, 2.5, 3.5, 4.5, 5.5]),
            color="#123456",
            hatch="//",
        )
    )
    hist.add_entry(
        HistogramEntry(
            name="sig",
            latex_name="Signal",
            counts=np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
            errors=np.array([0.5, 0.5, 0.5, 0.5, 0.5]),
            type="signal",
        )
    )
    hist.metadata["column_name"] = "pt"

    path = tmp_path / "h.json"
    hist.save(path)
    restored = Histogram.load(path)

    assert np.allclose(restored.get_bin_counts()[0], hist.get_bin_counts()[0])
    assert np.allclose(restored.get_bin_errors()[0], hist.get_bin_errors()[0])
    assert np.allclose(restored.binning, hist.binning)
    assert restored.get_names() == hist.get_names()
    assert restored.get_signal_names() == hist.get_signal_names()
    assert restored.get_colors() == hist.get_colors()
    assert restored.get_hatches() == hist.get_hatches()
    assert restored.get_latex_names() == hist.get_latex_names()
    assert restored.metadata["column_name"] == "pt"


def test_save_does_not_mutate_the_source_histogram(tmp_path):
    """Saving must not clear the caller's raw arrays as a side effect."""
    hist = Histogram()
    hist.binning = np.linspace(0.0, 10.0, 6)
    raw = np.random.default_rng(0).normal(5.0, 2.0, 500)
    hist.add_entry(HistogramEntry(name="bkg", array=raw.copy()))

    hist.save(tmp_path / "h.json")

    assert hist.get_data()[0] is not None
    assert np.allclose(hist.get_data()[0], raw)


def test_saved_file_size_does_not_scale_with_sample_size(tmp_path):
    """The saved payload must be binned-only; a 100x larger sample must not grow the file.

    This is the property that makes caching worthwhile, and it fails loudly if raw event
    arrays ever creep back into the payload.
    """
    rng = np.random.default_rng(0)
    sizes = []
    for n_events in (1_000, 100_000):
        hist = Histogram()
        hist.binning = np.linspace(0.0, 10.0, 11)
        hist.add_entry(HistogramEntry(name="bkg", array=rng.normal(5.0, 2.0, n_events)))
        path = tmp_path / f"h_{n_events}.json"
        hist.save(path)
        sizes.append(path.stat().st_size)

    small, large = sizes
    assert large < small * 1.1, f"file grew with sample size: {small} -> {large} bytes"


def test_load_rejects_an_unknown_format_version(tmp_path):
    """A future format must fail with a clear message, not a KeyError deep in from_dict."""
    hist = Histogram()
    hist.binning = np.linspace(0.0, 5.0, 6)
    hist.add_entry(HistogramEntry(name="bkg", counts=np.array([1.0, 2.0, 3.0, 4.0, 5.0])))
    path = tmp_path / "h.json"
    hist.save(path)

    payload = json.loads(path.read_text())
    payload["format_version"] = 99
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="format_version"):
        Histogram.load(path)
```

Add `import json` to the test file's imports, alongside the existing `import numpy as np` and `import pytest`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/utilities/test_histogram.py -k "save or load" -v`

Expected: all four FAIL with `AttributeError: 'Histogram' object has no attribute 'save'`.

- [ ] **Step 3: Add the imports and the version constant**

In `src/afplotter/utilities/histogram.py`, replace the import block at lines 1-4:

```python
from collections import defaultdict
import numpy as np  # type: ignore
from typing import Any
from dataclasses import dataclass, field, asdict
```

with:

```python
import copy
import json
from collections import defaultdict
from pathlib import Path
import numpy as np  # type: ignore
from typing import Any
from dataclasses import dataclass, field, asdict

SAVE_FORMAT_VERSION = 1
"""Version of the on-disk JSON format written by :meth:`Histogram.save`."""
```

- [ ] **Step 4: Implement `save` and `load`**

Add both methods to the `Histogram` class, immediately after the existing `from_dict` classmethod (which ends at line 120 with `return instance`):

```python
    def save(self, path: str | Path) -> None:
        """Write this histogram to a JSON file, without its raw event data.

        Only binned results are stored — counts, errors, binning, metadata and per-entry
        styling. Each entry's ``array`` is omitted, so the file size does not grow with the
        sample size. The histogram in memory is left untouched.

        A histogram loaded from such a file cannot be used for a 2D plot, because
        :class:`~afplotter.histogramplot.Histogram2DPlot` bins raw arrays at plot time.

        :param path: Destination file path. Any parent directory must already exist.
        """
        payload = copy.deepcopy(self.as_dict)
        for section in ("entries", "signal"):
            for entry in payload[section].values():
                entry["array"] = None
        payload["format_version"] = SAVE_FORMAT_VERSION
        Path(path).write_text(json.dumps(payload))

    @classmethod
    def load(cls, path: str | Path) -> "Histogram":
        """Read a histogram written by :meth:`save`.

        The returned histogram has no raw event data: ``get_data()`` yields ``None`` for
        every entry.

        :param path: Path to a JSON file written by :meth:`save`.
        :return: The reconstructed histogram.
        :raises ValueError: If the file's ``format_version`` is not supported.
        """
        payload = json.loads(Path(path).read_text())
        version = payload.get("format_version")
        if version != SAVE_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported format_version {version!r} in {path}; "
                f"this version of AFPlotter writes and reads format_version {SAVE_FORMAT_VERSION}."
            )
        return cls.from_dict(payload)
```

Note `copy.deepcopy` on the first line of `save`. A shallow copy would share the nested entry dicts with `as_dict`'s output, and while `as_dict` builds fresh dicts today, relying on that is fragile — the deep copy makes the no-mutation guarantee local and obvious.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/utilities/test_histogram.py -k "save or load" -v`

Expected: 4 passed.

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest tests/ -q`

Expected: PASS, four tests more than before this task.

- [ ] **Step 7: Commit**

```bash
git add src/afplotter/utilities/histogram.py tests/utilities/test_histogram.py
git commit -m "Add Histogram.save and Histogram.load

Writes binned results as JSON -- counts, errors, binning, metadata and
per-entry styling -- omitting each entry's raw array. A 1,200-event
histogram serialises to 655 bytes instead of 23,670, and the file size
does not grow with the sample size, which is what makes caching an
expensive LazyHistWrapper build worthwhile.

save() deep-copies the payload rather than calling clear_array(), so
saving never destroys the caller's event data as a side effect.

format_version is written and checked so a future format change fails
with a clear message instead of a KeyError inside from_dict."
```

---

### Task 2: Name the failure when a histogram has no raw event data

**Files:**
- Modify: `src/afplotter/histogramplot.py` (insert after line 452, before the `self.ax.hist2d(` call at line 454)
- Test: `tests/test_histogramplot.py` (append)

**Interfaces:**
- Consumes: `Histogram.save`/`Histogram.load` from Task 1, used only to construct the test fixture.
- Produces: nothing consumed by later tasks.

**Why this is not merely cosmetic.** `Histogram.get_data()` returns `[entry.array for entry in ...]`, so for an entry whose array is `None` it returns `[None]` — a list of length 1. `Histogram2DPlot.plot` tests `len(self.xhistogram.get_data()) > 0`, which is **true**, so the existing `"Unexpected data state encountered."` fallback never fires and execution reaches `hist2d(x=None)`. This is reachable **today** without save/load: `add_entry(clear=True)` produces the same state, and `LazyHistWrapper.lazy_execute` calls it.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_histogramplot.py`:

```python
def test_2d_plot_rejects_a_histogram_without_raw_data(tmp_path):
    """A loaded (binned-only) histogram must fail with a message naming the real cause.

    Without the guard this reaches hist2d(x=None) and raises from inside matplotlib, naming
    nothing useful. Matching on the message is the point of the test -- asserting merely that
    "something raised" would pass against the broken behaviour too.
    """
    hist = Histogram()
    hist.binning = np.linspace(0.0, 10.0, 6)
    hist.add_entry(HistogramEntry(name="x", array=np.random.default_rng(0).normal(5.0, 2.0, 200)))
    path = tmp_path / "h.json"
    hist.save(path)

    plot2d = Histogram2DPlot(Histogram.load(path), Histogram.load(path))
    fig, ax = plt.subplots()
    plot2d.ax = ax
    with pytest.raises(ValueError, match="raw event data"):
        plot2d.plot()
    plt.close(fig)
```

No new imports are needed: `Histogram2DPlot`, `Histogram`, `HistogramEntry`, `np`, `pytest` and
`plt` are all already imported in this file. The `Histogram2DPlot(x, y)` positional construction
and the `plot2d.ax = ax` assignment match the existing `test_histogram_2d_plot` at
`tests/test_histogramplot.py:76-79`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_histogramplot.py::test_2d_plot_rejects_a_histogram_without_raw_data -v`

Expected: FAIL. The error will come from matplotlib, not a `ValueError` matching `"raw event data"` — that is precisely the confusing failure this task replaces.

- [ ] **Step 3: Add the guard**

In `src/afplotter/histogramplot.py`, the branch selection currently ends at line 452 with
`raise ValueError("Unexpected data state encountered.")`, followed by a blank line and then
`heatmap = self.ax.hist2d(` at line 454.

Insert this between them:

```python
        for axis_name, axis_data in (("x", x_data), ("y", y_data)):
            if axis_data is None:
                raise ValueError(
                    f"The {axis_name} histogram has no raw event data (loaded from a binned-only "
                    "file, or cleared via add_entry(clear=True)). Histogram2DPlot bins raw arrays "
                    "at plot time, so it cannot plot binned-only input. Rebuild the histogram from "
                    "the source data to make a 2D plot."
                )
```

Do not change the branch-selection logic above it, and do not change the existing
`"Unexpected data state encountered."` raise — that guards a different condition.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_histogramplot.py::test_2d_plot_rejects_a_histogram_without_raw_data -v`

Expected: PASS.

- [ ] **Step 5: Confirm normal 2D plotting still works**

Run: `uv run pytest tests/test_histogramplot.py -q -k "2d or 2D"`

Expected: PASS. The guard must reject only `None` data — a real 2D plot with arrays present must be unaffected.

- [ ] **Step 6: Run the full suite and the lint gate**

```bash
uv run pytest tests/ -q
uv run ruff check .
uv run ruff format --check .
uv run mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
```

Expected: suite passes with five tests more than `main`; ruff clean; mypy `Success`. Those mypy flags are the ones `.github/workflows/ci.yml:43` uses — a bare `uv run mypy src/` is a different check.

- [ ] **Step 7: Verify no committed image changed**

```bash
uv run python examples/workflow_demo.py && git status --short docs/img/workflow/
```

Expected: exits 0, **no output** from `git status`. This change adds a guard on a path that previously crashed; it must not alter any rendering. If a PNG shows as modified, revert it with `git checkout docs/img/workflow/` and investigate before committing.

- [ ] **Step 8: Commit**

```bash
git add src/afplotter/histogramplot.py tests/test_histogramplot.py
git commit -m "Name the failure when a 2D plot gets no raw event data

Histogram.get_data() returns [None] for an entry whose array was
cleared, so the existing len(...) > 0 check in Histogram2DPlot.plot
passes and execution reaches hist2d(x=None), raising from inside
matplotlib with nothing to point at.

Reachable today without save/load: add_entry(clear=True) produces the
same state and LazyHistWrapper.lazy_execute calls it. Checking the
selected data for None covers both causes.

Closes #9"
```

---

## Outcome

<!-- Fill this in when the plan has been executed: final commit SHA, test count, what was
     verified, and anything that deviated from the plan. The SDD ledger under .superpowers/
     is gitignored and vanishes with the working copy. -->

Not yet executed.
