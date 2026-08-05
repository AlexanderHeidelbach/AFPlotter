# Plotter Save/Load Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `HistogramPlotter`, `GenericPlotter` and `Histogram2DPlotter` a `save`/`load` pair that round-trips a plot *specification* to JSON.

**Architecture:** One new module, `src/afplotter/utilities/plotspec.py`, owns every value-level encode/decode rule and knows nothing about plotters. Each plotter gets a thin `save`/`load` pair that walks its own attributes through that core. Files are JSON; `HistogramPlotter` embeds its histogram via #9's `as_binned_dict`, `Histogram2DPlotter` saves spec only and takes its histograms back as `load` arguments.

**Tech Stack:** Python 3.10+, numpy, matplotlib, pytest. No new dependencies.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-05-plotter-save-load-design.md`. Issue: #38.
- **No plotter stores a callable.** `add_function`/`add_pull` evaluate `func` eagerly into sampled `GenericPlot` arrays. Do not add callable serialization, a model registry, or a qualname resolver — there is nothing to resolve.
- `PLOT_FORMAT_VERSION = 1`, defined in `plotspec.py`. Separate from `histogram.py`'s `SAVE_FORMAT_VERSION`; an embedded histogram payload keeps its own nested `format_version`.
- **Unserializable values: refuse by default.** `save(path)` raises `ValueError` naming the location, and **writes no file**. `save(path, skip_unserializable=True)` drops the entry, records it in the file under `"dropped"`, and `load` re-emits each as a `UserWarning`.
- **Positional args are never dropped**, even with `skip_unserializable=True` — removing one shifts every later argument and silently changes the matplotlib call. An unserializable positional arg always raises. Only kwargs are skippable.
- **Never save a live matplotlib object** (`_ax`, `Transform`, `Colormap`, `Figure`). These are exactly what `UnserializableValue` exists to catch.
- **The `BasePlotter` field list is hardcoded**, never scraped from `vars()`/`__dict__`.
- **Restore writes private attributes** (`_xlabel`, not `xlabel`): `HistogramPlotter` (`histogramplot.py:496,500`) and `Histogram2DPlotter` (`:885,889`) override `xlabel`/`ylabel` as read-only properties.
- Test fixtures must use **non-default** values for every field asserted. A fixture whose expected value a freshly-constructed plotter also produces proves nothing — that trap produced a false PASS during #9's spike.
- Every test must be verified by breaking the implementation and watching it fail. "It passes" is not evidence.
- Python 3.10+ typing: native `X | Y`, builtin generics. No `typing.Optional`/`List`/`Dict`/`Union`. reST docstrings (`:param:`/`:return:`/`:raises:`) on public functions and classes. Line length 120 (ruff).
- Tests run on the `Agg` backend (set in `tests/conftest.py`), which also provides the shared `synthetic_histogram` fixture.
- Commands: `uv run pytest tests/ -v`; `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/`. Only that mypy invocation is the project's real type gate.
- **`plot(save=True)` calls `plt.clf()` before returning** — never assert on axes content after a `save=True` call. Use `save=False` when you need the returned axes.

## File Structure

| File | Responsibility |
|---|---|
| `src/afplotter/utilities/plotspec.py` (new) | Value encode/decode, `UnserializableValue`, `GenericPlot`/`InsetPlot` encoding, the `BasePlotter` field block, `PLOT_FORMAT_VERSION`. Knows nothing about plotters. |
| `src/afplotter/genericplot.py` (modify) | `GenericPlotter.save`/`load` |
| `src/afplotter/histogramplot.py` (modify) | `HistogramPlotter.save`/`load`, `Histogram2DPlotter.save`/`load` |
| `tests/utilities/test_plotspec.py` (new) | Tasks 1-2 |
| `tests/test_genericplot.py` (modify) | Task 3 |
| `tests/test_histogramplot.py` (modify) | Tasks 4-5 |

---

### Task 1: The value codec

**Files:**
- Create: `src/afplotter/utilities/plotspec.py`
- Test: `tests/utilities/test_plotspec.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces, used by every later task:
  - `PLOT_FORMAT_VERSION: int` (value `1`)
  - `class UnserializableValue(ValueError)` with attributes `value_type: str`, `value_repr: str`, and `where: str | None` (a caller-set location fragment, e.g. `"kwarg 'transform'"`)
  - `encode_value(value: Any) -> Any`
  - `decode_value(data: Any) -> Any`

- [ ] **Step 1: Write the failing tests**

Create `tests/utilities/test_plotspec.py`:

```python
import json

import numpy as np
import pytest

from afplotter.utilities.plotspec import (
    PLOT_FORMAT_VERSION,
    UnserializableValue,
    decode_value,
    encode_value,
)


def test_plot_format_version_is_one():
    assert PLOT_FORMAT_VERSION == 1


@pytest.mark.parametrize("value", ["a", 1, 2.5, True, None, [1, 2], {"k": 1}])
def test_encode_value_passes_json_natives_through(value):
    assert encode_value(value) == value
    assert decode_value(encode_value(value)) == value


def test_encode_value_round_trips_an_ndarray_as_an_ndarray():
    """A list would render identically here but breaks callers that do arithmetic on args."""
    array = np.array([1.5, 2.5, 3.5])
    encoded = encode_value(array)
    json.dumps(encoded)  # must survive a real serialization, not just look serializable
    restored = decode_value(encoded)
    assert isinstance(restored, np.ndarray)
    assert np.allclose(restored, array)


def test_encode_value_round_trips_a_tuple_as_a_tuple():
    """JSON collapses tuples to lists; figsize/xlim/watermark_position must come back tuples."""
    encoded = encode_value((12, 8))
    json.dumps(encoded)
    restored = decode_value(encoded)
    assert isinstance(restored, tuple)
    assert restored == (12, 8)


def test_encode_value_recurses_into_containers():
    encoded = encode_value({"lims": (0.0, 1.0), "data": [np.array([1.0, 2.0])]})
    json.dumps(encoded)
    restored = decode_value(encoded)
    assert restored["lims"] == (0.0, 1.0)
    assert isinstance(restored["lims"], tuple)
    assert isinstance(restored["data"][0], np.ndarray)
    assert np.allclose(restored["data"][0], [1.0, 2.0])


def test_encode_value_rejects_a_live_matplotlib_object():
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    with pytest.raises(UnserializableValue) as excinfo:
        encode_value(ax.transAxes)
    plt.close("all")
    assert "Transform" in excinfo.value.value_type


def test_encode_value_rejects_an_unserializable_value_nested_in_a_container():
    """A container must not smuggle a live object past the check."""
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    with pytest.raises(UnserializableValue):
        encode_value({"transform": ax.transAxes})
    plt.close("all")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/utilities/test_plotspec.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'afplotter.utilities.plotspec'`.

- [ ] **Step 3: Write the module**

Create `src/afplotter/utilities/plotspec.py`:

```python
"""Value-level encoding for plot specifications.

This module knows how to turn the values a plotter holds into JSON-safe data and back.
It knows nothing about plotters themselves -- each plotter's ``save``/``load`` walks its
own attributes through these helpers.
"""

from typing import Any

import numpy as np

PLOT_FORMAT_VERSION = 1
"""Version of the on-disk JSON format written by the plotters' ``save`` methods."""

_NDARRAY_KEY = "__ndarray__"
_TUPLE_KEY = "__tuple__"

_JSON_NATIVE = (str, bool, int, float, type(None))


class UnserializableValue(ValueError):
    """Raised when a value cannot be represented in a saved plot specification.

    :param value: The offending value.
    :param where: Optional location fragment set by the caller, e.g. ``"kwarg 'transform'"``.
    """

    def __init__(self, value: Any, where: str | None = None) -> None:
        self.value_type = type(value).__name__
        self.value_repr = repr(value)
        self.where = where
        super().__init__(f"Cannot save a value of type {self.value_type}: {self.value_repr}")


def encode_value(value: Any) -> Any:
    """Convert a value to JSON-safe data.

    ``np.ndarray`` and ``tuple`` are tagged so they survive the round trip as themselves;
    JSON natives pass through; lists and dicts are encoded element-wise.

    :param value: The value to encode.
    :return: JSON-safe data.
    :raises UnserializableValue: If the value (or anything nested inside it) has no
        representation -- a live matplotlib object, for instance.
    """
    if isinstance(value, np.ndarray):
        return {_NDARRAY_KEY: value.tolist()}
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, tuple):
        return {_TUPLE_KEY: [encode_value(item) for item in value]}
    if isinstance(value, list):
        return [encode_value(item) for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise UnserializableValue(value)
        return {key: encode_value(item) for key, item in value.items()}
    if isinstance(value, _JSON_NATIVE):
        return value
    raise UnserializableValue(value)


def decode_value(data: Any) -> Any:
    """Invert :func:`encode_value`.

    :param data: JSON data written by :func:`encode_value`.
    :return: The restored value.
    """
    if isinstance(data, dict):
        if _NDARRAY_KEY in data:
            return np.array(data[_NDARRAY_KEY])
        if _TUPLE_KEY in data:
            return tuple(decode_value(item) for item in data[_TUPLE_KEY])
        return {key: decode_value(item) for key, item in data.items()}
    if isinstance(data, list):
        return [decode_value(item) for item in data]
    return data
```

Note `np.generic` before the native check: numpy scalars (`np.float64`) are not `float` instances on every platform, and they reach here from computed values like `np.min(bin_centers)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/utilities/test_plotspec.py -v`
Expected: all pass.

- [ ] **Step 5: Verify the tests are falsifiable**

Temporarily change `encode_value` to return `value.tolist()` for ndarrays (dropping the `__ndarray__` tag) and re-run. Expected: `test_encode_value_round_trips_an_ndarray_as_an_ndarray` fails on `isinstance(restored, np.ndarray)`. Then temporarily delete the final `raise UnserializableValue(value)` and add `return value`; expected: both rejection tests fail. Restore both. Confirm with `git diff` that the file is back to the version above.

- [ ] **Step 6: Commit**

```bash
git add src/afplotter/utilities/plotspec.py tests/utilities/test_plotspec.py
git commit -m "Add the value codec for plot specifications

Issue #38. ndarrays and tuples are tagged so they survive JSON as
themselves; anything without a representation raises rather than
being silently dropped.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Encoding `GenericPlot` and `InsetPlot`

**Files:**
- Modify: `src/afplotter/utilities/plotspec.py` (append)
- Test: `tests/utilities/test_plotspec.py` (append)

**Interfaces:**
- Consumes: `encode_value`, `decode_value`, `UnserializableValue` from Task 1.
- Produces, used by Tasks 3-5:
  - `encode_generic_plot(plot: GenericPlot, *, skip_unserializable: bool = False) -> tuple[dict, list[str]]` — returns the payload and a list of dropped-kwarg descriptors (e.g. `["kwarg 'transform'"]`), which is empty unless something was skipped.
  - `decode_generic_plot(data: dict) -> GenericPlot`
  - `encode_inset(inset: InsetPlot, plot_refs: dict[str, Any]) -> dict` — `plot_refs` is the caller-built symbolic reference block, stored verbatim under `"plots"`.
  - `decode_inset(data: dict, resolved_plots: list[Any]) -> InsetPlot` — `resolved_plots` is what the caller resolved `"plots"` back to.

`InsetPlot`'s own settings are `xlim`, `ylim`, `width`, `height`, `loc`, `borderpad`, `title`, `mark_region`, `mark_kwargs`, `tick_labelsize`, `title_fontsize`, `bbox_to_anchor` (`genericplot.py:36-66`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/utilities/test_plotspec.py`:

```python
from afplotter.genericplot import GenericPlot, InsetPlot
from afplotter.utilities.plotspec import (
    decode_generic_plot,
    decode_inset,
    encode_generic_plot,
    encode_inset,
)


def test_encode_generic_plot_round_trips_method_args_and_kwargs():
    plot = GenericPlot("errorbar", np.array([1.0, 2.0]), np.array([3.0, 4.0]), color="red", ls="--")
    data, dropped = encode_generic_plot(plot)
    assert dropped == []
    json.dumps(data)

    restored = decode_generic_plot(data)
    assert restored.plotmethod == "errorbar"
    assert np.allclose(restored.args[0], [1.0, 2.0])
    assert np.allclose(restored.args[1], [3.0, 4.0])
    assert restored.kwargs == {"color": "red", "ls": "--"}


def test_encode_generic_plot_raises_on_an_unserializable_kwarg():
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    plot = GenericPlot("plot", np.array([1.0]), transform=ax.transAxes)
    with pytest.raises(UnserializableValue) as excinfo:
        encode_generic_plot(plot)
    plt.close("all")
    assert excinfo.value.where == "kwarg 'transform'"


def test_encode_generic_plot_skips_an_unserializable_kwarg_when_asked():
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    plot = GenericPlot("plot", np.array([1.0]), color="red", transform=ax.transAxes)
    data, dropped = encode_generic_plot(plot, skip_unserializable=True)
    plt.close("all")

    assert dropped == ["kwarg 'transform'"]
    restored = decode_generic_plot(data)
    assert restored.kwargs == {"color": "red"}  # the serializable kwarg survives


def test_encode_generic_plot_never_skips_a_positional_arg():
    """Dropping a positional would shift every later argument and change the call."""
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    plot = GenericPlot("plot", ax.transAxes, np.array([1.0]))
    with pytest.raises(UnserializableValue) as excinfo:
        encode_generic_plot(plot, skip_unserializable=True)
    plt.close("all")
    assert excinfo.value.where == "arg 0"


def test_encode_inset_round_trips_its_settings_and_reference_block():
    inset = InsetPlot(
        plots=[],
        xlim=(1.0, 2.0),
        ylim=(3.0, 4.0),
        width="50%",
        height="25%",
        loc="lower left",
        borderpad=2.0,
        title="zoom",
        mark_region=False,
        mark_kwargs={"ec": "red"},
        tick_labelsize=6,
        title_fontsize=11,
        bbox_to_anchor=(0.1, 0.2, 0.3, 0.4),
    )
    refs = {"histplot": True, "generic_plots": [0, 1]}
    data = encode_inset(inset, refs)
    json.dumps(data)
    assert data["plots"] == refs

    sentinel = [object(), object()]
    restored = decode_inset(data, sentinel)
    assert restored.plots is sentinel
    assert restored.xlim == (1.0, 2.0)
    assert isinstance(restored.xlim, tuple)
    assert restored.ylim == (3.0, 4.0)
    assert restored.width == "50%"
    assert restored.height == "25%"
    assert restored.loc == "lower left"
    assert restored.borderpad == 2.0
    assert restored.title == "zoom"
    assert restored.mark_region is False
    assert restored.mark_kwargs == {"ec": "red"}
    assert restored.tick_labelsize == 6
    assert restored.title_fontsize == 11
    assert restored.bbox_to_anchor == (0.1, 0.2, 0.3, 0.4)
```

Every value above is deliberately non-default (`InsetPlot`'s defaults are `width="38%"`, `height="38%"`, `loc="upper center"`, `borderpad=1.0`, `title=None`, `mark_region=True`, `tick_labelsize=8`, `title_fontsize=15`, `bbox_to_anchor=None`), so an implementation that reconstructs a default `InsetPlot` fails every assertion.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/utilities/test_plotspec.py -k "generic_plot or inset" -v`
Expected: `ImportError: cannot import name 'encode_generic_plot'`.

- [ ] **Step 3: Append the implementation**

Add to `src/afplotter/utilities/plotspec.py`. Import `GenericPlot`/`InsetPlot` inside the functions, not at module top: `genericplot.py` imports `baseplotter`, and a top-level import here risks a cycle once the plotters import `plotspec`.

```python
_INSET_FIELDS = (
    "xlim",
    "ylim",
    "width",
    "height",
    "loc",
    "borderpad",
    "title",
    "mark_region",
    "mark_kwargs",
    "tick_labelsize",
    "title_fontsize",
    "bbox_to_anchor",
)


def encode_generic_plot(plot: Any, *, skip_unserializable: bool = False) -> tuple[dict[str, Any], list[str]]:
    """Encode one :class:`~afplotter.genericplot.GenericPlot`.

    :param plot: The plot to encode.
    :param skip_unserializable: Drop unserializable *keyword* arguments instead of raising.
        Positional arguments are never dropped -- removing one would shift every later
        argument and silently change the matplotlib call.
    :return: ``(payload, dropped)`` where ``dropped`` lists the descriptors of any skipped
        kwargs, e.g. ``["kwarg 'transform'"]``.
    :raises UnserializableValue: On an unserializable positional argument, or on an
        unserializable kwarg when ``skip_unserializable`` is false.
    """
    args = []
    for index, arg in enumerate(plot.args):
        try:
            args.append(encode_value(arg))
        except UnserializableValue as error:
            error.where = error.where or f"arg {index}"
            raise

    kwargs = {}
    dropped = []
    for key, value in plot.kwargs.items():
        try:
            kwargs[key] = encode_value(value)
        except UnserializableValue as error:
            where = error.where or f"kwarg {key!r}"
            if not skip_unserializable:
                error.where = where
                raise
            dropped.append(where)

    return {"plotmethod": plot.plotmethod, "args": args, "kwargs": kwargs}, dropped


def decode_generic_plot(data: dict[str, Any]) -> Any:
    """Invert :func:`encode_generic_plot`.

    :param data: One payload written by :func:`encode_generic_plot`.
    :return: The restored :class:`~afplotter.genericplot.GenericPlot`.
    """
    from afplotter.genericplot import GenericPlot

    args = [decode_value(arg) for arg in data["args"]]
    kwargs = {key: decode_value(value) for key, value in data["kwargs"].items()}
    return GenericPlot(data["plotmethod"], *args, **kwargs)


def encode_inset(inset: Any, plot_refs: dict[str, Any]) -> dict[str, Any]:
    """Encode one :class:`~afplotter.genericplot.InsetPlot`.

    The inset's ``plots`` are stored as the caller's symbolic reference block rather than
    by value: they are the *same objects* the main axes replays, and copying them would
    turn "the whole plot, zoomed" into a frozen duplicate on load.

    :param inset: The inset to encode.
    :param plot_refs: Symbolic references to the plotter's own objects, stored verbatim.
    :return: JSON-safe data.
    :raises UnserializableValue: If any of the inset's own settings cannot be encoded.
    """
    data = {field: encode_value(getattr(inset, field)) for field in _INSET_FIELDS}
    data["plots"] = plot_refs
    return data


def decode_inset(data: dict[str, Any], resolved_plots: list[Any]) -> Any:
    """Invert :func:`encode_inset`.

    :param data: One payload written by :func:`encode_inset`.
    :param resolved_plots: The live plot objects the caller resolved ``data["plots"]`` to.
    :return: The restored :class:`~afplotter.genericplot.InsetPlot`.
    """
    from afplotter.genericplot import InsetPlot

    settings = {field: decode_value(data[field]) for field in _INSET_FIELDS}
    return InsetPlot(plots=resolved_plots, **settings)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/utilities/test_plotspec.py -v`
Expected: all pass.

- [ ] **Step 5: Verify the tests are falsifiable**

Temporarily make `encode_generic_plot` treat positional args like kwargs (append to `dropped` and continue instead of re-raising) and re-run: `test_encode_generic_plot_never_skips_a_positional_arg` must fail. Then temporarily drop the `plots` key from `encode_inset`'s output: `test_encode_inset_round_trips_its_settings_and_reference_block` must fail on `data["plots"] == refs`. Restore both and confirm with `git diff`.

- [ ] **Step 6: Commit**

```bash
git add src/afplotter/utilities/plotspec.py tests/utilities/test_plotspec.py
git commit -m "Encode GenericPlot and InsetPlot for plot specifications

Issue #38. Insets store symbolic references to the plotter's own
objects rather than copies, so a loaded inset still zooms the live
plot instead of a frozen duplicate.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: The `BasePlotter` block and `GenericPlotter.save`/`load`

**Files:**
- Modify: `src/afplotter/utilities/plotspec.py` (append)
- Modify: `src/afplotter/genericplot.py` — add `save`/`load` to `GenericPlotter` (class starts at `:116`; `_plots`/`_insets` set in `__init__` at `:120-121`; `add_generic_plot` at `:123`)
- Test: `tests/test_genericplot.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 1-2.
- Produces:
  - `BASE_PLOTTER_FIELDS: tuple[str, ...]` in `plotspec.py`
  - `encode_base_plotter(plotter: Any) -> dict[str, Any]`
  - `decode_base_plotter(plotter: Any, data: dict[str, Any]) -> None` (mutates in place)
  - `warn_dropped(dropped: list[str]) -> None` — emits one `UserWarning` naming every dropped entry; used by all three `load` implementations
  - `GenericPlotter.save(path: str | Path, skip_unserializable: bool = False) -> None`
  - `GenericPlotter.load(path: str | Path) -> "GenericPlotter"` (classmethod)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_genericplot.py` (it already imports `numpy as np`, `pytest`, and from `afplotter.genericplot`; add `import json` and any missing names):

```python
def test_generic_plotter_save_load_round_trips_the_base_block(tmp_path):
    """Every asserted value is deliberately non-default: a freshly-constructed plotter fails."""
    plotter = GenericPlotter()
    plotter.figsize = (7, 3)
    plotter.label = "my label"
    plotter.xlabel = "mass"
    plotter.ylabel = "events"
    plotter.watermark = "internal"
    plotter.luminosity_value = 362.4
    plotter.luminosity_unit = "ab"
    plotter.log = True
    plotter.xlog = True
    plotter.legend_max_rows = 7
    plotter.legend_title = "samples"
    plotter.legend_loc = "upper right"
    plotter.xlim = (0.5, 9.5)
    plotter.ylim = (1.0, 1e4)
    plotter.savedir = "/tmp/plots"
    plotter.saveformat = "pdf"
    plotter.savename = "limit"
    plotter.savepath = "/tmp/plots/limit.pdf"
    plotter.watermark_position = (0.1, 0.8)
    plotter.add_text("a note")
    plotter.add_generic_text(s="x", x=0.1, y=0.2)

    path = tmp_path / "p.json"
    plotter.save(path)
    loaded = GenericPlotter.load(path)

    assert loaded.figsize == (7, 3)
    assert isinstance(loaded.figsize, tuple)
    assert loaded.label == "my label"
    assert loaded.xlabel == "mass"
    assert loaded.ylabel == "events"
    assert loaded.watermark == "internal"
    assert loaded.luminosity_value == 362.4
    assert loaded.luminosity_unit == "ab"
    assert loaded.log is True
    assert loaded.xlog is True
    assert loaded.legend_max_rows == 7
    assert loaded.legend_title == "samples"
    assert loaded.legend_loc == "upper right"
    assert loaded.xlim == (0.5, 9.5)
    assert isinstance(loaded.xlim, tuple)
    assert loaded.ylim == (1.0, 1e4)
    assert loaded.savedir == "/tmp/plots"
    assert loaded.saveformat == "pdf"
    assert loaded.savename == "limit"
    assert loaded.savepath == "/tmp/plots/limit.pdf"
    assert loaded.watermark_position == (0.1, 0.8)
    assert isinstance(loaded.watermark_position, tuple)
    assert loaded.text == ["a note"]
    assert loaded.generic_text == [{"s": "x", "x": 0.1, "y": 0.2}]


def test_generic_plotter_save_load_round_trips_plots_and_insets(tmp_path):
    plotter = GenericPlotter()
    plotter.add_generic_plot("plot", np.array([1.0, 2.0]), np.array([3.0, 4.0]), color="red")
    plotter.add_generic_plot("scatter", np.array([1.0]), np.array([2.0]), marker="x")
    plotter.add_inset(xlim=(1.0, 2.0), ylim=(3.0, 4.0), title="zoom")

    path = tmp_path / "p.json"
    plotter.save(path)
    loaded = GenericPlotter.load(path)

    assert [plot.plotmethod for plot in loaded._plots] == ["plot", "scatter"]
    assert np.allclose(loaded._plots[0].args[0], [1.0, 2.0])
    assert loaded._plots[0].kwargs == {"color": "red"}
    assert loaded._plots[1].kwargs == {"marker": "x"}

    assert len(loaded._insets) == 1
    assert loaded._insets[0].xlim == (1.0, 2.0)
    assert loaded._insets[0].title == "zoom"
    # The inset must reference the loaded plotter's own live plots, not copies of them.
    assert loaded._insets[0].plots[0] is loaded._plots[0]
    assert loaded._insets[0].plots[1] is loaded._plots[1]


def test_generic_plotter_save_refuses_an_unserializable_kwarg_and_writes_nothing(tmp_path):
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    plotter = GenericPlotter()
    plotter.add_generic_plot("plot", np.array([1.0]), color="red")
    plotter.add_generic_plot("plot", np.array([1.0]), transform=ax.transAxes)

    path = tmp_path / "p.json"
    with pytest.raises(ValueError, match=r"_plots\[1\].*transform"):
        plotter.save(path)
    plt.close("all")
    assert not path.exists()


def test_generic_plotter_save_can_skip_and_load_warns(tmp_path):
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    plotter = GenericPlotter()
    plotter.add_generic_plot("plot", np.array([1.0]), color="red", transform=ax.transAxes)

    path = tmp_path / "p.json"
    plotter.save(path, skip_unserializable=True)
    plt.close("all")

    with pytest.warns(UserWarning, match="transform"):
        loaded = GenericPlotter.load(path)
    assert loaded._plots[0].kwargs == {"color": "red"}


def test_generic_plotter_load_rejects_an_unknown_format_version(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"format_version": 99, "base": {}, "plots": [], "insets": []}))
    with pytest.raises(ValueError, match="99"):
        GenericPlotter.load(path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_genericplot.py -k "save or load" -v`
Expected: `AttributeError: 'GenericPlotter' object has no attribute 'save'`.

- [ ] **Step 3: Append the base-block helpers to `plotspec.py`**

```python
import warnings

BASE_PLOTTER_FIELDS = (
    "figsize",
    "label",
    "xlabel",
    "ylabel",
    "watermark",
    "luminosity_value",
    "luminosity_unit",
    "log",
    "xlog",
    "legend_max_rows",
    "legend_title",
    "legend_loc",
    "xlim",
    "ylim",
    "savedir",
    "saveformat",
    "savename",
    "savepath",
    "watermark_position",
    "text",
    "generic_text",
)
"""Every :class:`~afplotter.baseplotter.BasePlotter` attribute a saved plot carries.

Hardcoded rather than scraped from ``vars()``: a hardcoded list fails loudly when someone
adds a property and forgets it here, whereas scraping would silently start persisting
private state -- including live matplotlib objects.
"""


def _field_attribute(plotter: Any, field: str) -> str:
    """Return the attribute name backing ``field`` -- the private one where it exists."""
    private = f"_{field}"
    return private if hasattr(plotter, private) else field


def encode_base_plotter(plotter: Any) -> dict[str, Any]:
    """Encode the shared :class:`~afplotter.baseplotter.BasePlotter` attribute block.

    :param plotter: Any plotter deriving from ``BasePlotter``.
    :return: JSON-safe data.
    :raises UnserializableValue: If any field holds a value with no representation.
    """
    data = {}
    for field in BASE_PLOTTER_FIELDS:
        try:
            data[field] = encode_value(getattr(plotter, _field_attribute(plotter, field)))
        except UnserializableValue as error:
            error.where = error.where or f"{field}"
            raise
    return data


def decode_base_plotter(plotter: Any, data: dict[str, Any]) -> None:
    """Restore the shared attribute block onto ``plotter``, in place.

    Values are written to the *private* attributes: ``HistogramPlotter`` and
    ``Histogram2DPlotter`` override ``xlabel``/``ylabel`` as read-only properties, so
    assigning through the public name would raise.

    :param plotter: The plotter to populate.
    :param data: The block written by :func:`encode_base_plotter`.
    :return: None
    """
    for field in BASE_PLOTTER_FIELDS:
        if field in data:
            setattr(plotter, _field_attribute(plotter, field), decode_value(data[field]))


def warn_dropped(dropped: list[str]) -> None:
    """Emit one ``UserWarning`` naming everything a ``save`` dropped, if anything was.

    :param dropped: Descriptors recorded in the file's ``"dropped"`` list.
    :return: None
    """
    if dropped:
        warnings.warn(
            f"This plot was saved with skip_unserializable=True; {len(dropped)} element(s) "
            f"were dropped and are missing from the loaded plot: {', '.join(dropped)}",
            UserWarning,
            stacklevel=2,
        )
```

- [ ] **Step 4: Add `save`/`load` to `GenericPlotter`**

In `src/afplotter/genericplot.py`, add to the imports at the top:

```python
import json
from pathlib import Path

from afplotter.utilities.plotspec import (
    PLOT_FORMAT_VERSION,
    UnserializableValue,
    decode_base_plotter,
    decode_generic_plot,
    decode_inset,
    encode_base_plotter,
    encode_generic_plot,
    encode_inset,
    warn_dropped,
)
```

Then add these methods to `GenericPlotter`:

```python
    def save(self, path: str | Path, skip_unserializable: bool = False) -> None:
        """Write this plotter's specification to a JSON file.

        The saved file holds the plot's *specification*: styling, limits, text, and every
        queued overlay's method name, arguments and keyword arguments. Overlays added via
        a model function were already evaluated into sampled arrays when they were added,
        so a loaded plot re-renders them at that sampled resolution -- it cannot
        re-evaluate the model at a different binning.

        :param path: Destination file path. Any parent directory must already exist.
        :param skip_unserializable: Drop keyword arguments that cannot be saved, recording
            them in the file so :meth:`load` can warn. Positional arguments are never
            dropped.
        :raises ValueError: If any value cannot be saved and ``skip_unserializable`` is
            false. Nothing is written in that case.
        :return: None
        """
        dropped: list[str] = []
        try:
            base = encode_base_plotter(self)
            plots = []
            for index, plot in enumerate(self._plots):
                data, plot_dropped = encode_generic_plot(plot, skip_unserializable=skip_unserializable)
                plots.append(data)
                dropped.extend(f"_plots[{index}]: {item}" for item in plot_dropped)
            insets = [encode_inset(inset, self._inset_refs(inset)) for inset in self._insets]
        except UnserializableValue as error:
            raise ValueError(f"Cannot save this plotter: {error.where} holds {error.value_repr}") from error

        payload = {
            "format_version": PLOT_FORMAT_VERSION,
            "base": base,
            "plots": plots,
            "insets": insets,
            "dropped": dropped,
        }
        Path(path).write_text(json.dumps(payload))

    def _inset_refs(self, inset: InsetPlot) -> dict[str, Any]:
        """Describe an inset's plots as indices into ``self._plots``.

        :param inset: The inset to describe.
        :return: ``{"plots": [<index>, ...]}``
        :raises UnserializableValue: If the inset replays an object this plotter does not own.
        """
        indices = []
        for plot in inset.plots:
            for index, own in enumerate(self._plots):
                if plot is own:
                    indices.append(index)
                    break
            else:
                raise UnserializableValue(plot, where="an inset plot this plotter does not own")
        return {"plots": indices}

    @classmethod
    def load(cls, path: str | Path) -> "GenericPlotter":
        """Read a plotter written by :meth:`save`.

        :param path: Path to a JSON file written by :meth:`save`.
        :return: An editable plotter: adjust limits, add overlays, call ``plot()``.
        :raises ValueError: If the file's ``format_version`` is unsupported, its top-level
            JSON is not an object, or a required key is missing.
        """
        payload = json.loads(Path(path).read_text())
        if not isinstance(payload, dict):
            raise ValueError(f"Malformed plot file {path}: expected a JSON object at the top level.")
        version = payload.get("format_version")
        if version != PLOT_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported format_version {version!r} in {path}; "
                f"this version of AFPlotter writes and reads format_version {PLOT_FORMAT_VERSION}."
            )
        for key in ("base", "plots", "insets"):
            if key not in payload:
                raise ValueError(f"Malformed plot file {path}: missing required key {key!r}.")

        plotter = cls()
        decode_base_plotter(plotter, payload["base"])
        plotter._plots = [decode_generic_plot(data) for data in payload["plots"]]
        plotter._insets = [
            decode_inset(data, [plotter._plots[index] for index in data["plots"]["plots"]])
            for data in payload["insets"]
        ]
        warn_dropped(payload.get("dropped", []))
        return plotter
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_genericplot.py -v`
Expected: all pass, including the pre-existing tests.

- [ ] **Step 6: Verify the tests are falsifiable**

Temporarily change `decode_base_plotter` to skip the `figsize` field, and re-run: the base-block test must fail on `loaded.figsize == (7, 3)` — proving it asserts restored values, not defaults. Then temporarily make `save` write the file *before* encoding (move `Path(path).write_text` above the `try`): `test_generic_plotter_save_refuses_an_unserializable_kwarg_and_writes_nothing` must fail on `assert not path.exists()`. Restore both and confirm with `git diff`.

- [ ] **Step 7: Run the full suite and the gates**

```bash
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
uv run mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
```

Expected: all pass, ruff clean, mypy `Success`.

- [ ] **Step 8: Commit**

```bash
git add src/afplotter/utilities/plotspec.py src/afplotter/genericplot.py tests/test_genericplot.py
git commit -m "Add GenericPlotter.save and GenericPlotter.load

Issue #38. Adds the shared BasePlotter attribute block -- hardcoded,
never scraped -- and the first plotter to use it. A save that cannot
represent a value raises and writes nothing.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: `HistogramPlotter.save`/`load`

**Files:**
- Modify: `src/afplotter/histogramplot.py` — add `save`/`load` to `HistogramPlotter` (class at `:481`; `__init__` at `:482-493` sets `histplot`, `variable`, `generic_plots`, `_insets`, `pull_plots`, `pull_ylim`, `color_map_kwargs`, `pull_label`)
- Test: `tests/test_histogramplot.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 1-3, plus `Histogram.as_binned_dict`-based payloads. `Histogram` already provides `as_dict`, `from_dict`, and per-entry `as_binned_dict()` (`utilities/histogram.py:77`); build the embedded payload the same way `Histogram.save` does (`histogram.py:173-187`) and restore it with `Histogram.from_dict`.
- Produces:
  - `HistogramPlotter.save(path: str | Path, skip_unserializable: bool = False) -> None`
  - `HistogramPlotter.load(path: str | Path) -> "HistogramPlotter"` (classmethod)

`HistogramPlot` display flags to carry: `stacked`, `sig_extra`, `uncertainty`, `data_only`, `density`, `log`, `linewidth`, `edgecolor` (all plain properties on `HistogramPlot`, `histogramplot.py:95-165`). `data_hist` is an optional second `Histogram`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_histogramplot.py` (it already imports `numpy as np` and `pytest`; add `import json` if absent, and the names used below):

```python
def _histogram_plotter(histogram):
    """A plotter whose every saved field differs from its constructed default."""
    histplot = HistogramPlot(histogram)
    histplot.stacked = True
    histplot.sig_extra = True
    histplot.uncertainty = True
    histplot.density = True
    histplot.linewidth = 2.5
    histplot.edgecolor = "navy"
    plotter = HistogramPlotter(histplot, HistogramVariable(name="mass", unit="GeV"))
    plotter.figsize = (7, 3)
    plotter.ylim = (1.0, 500.0)
    plotter.pull_ylim = (-2.5, 2.5)
    plotter.pull_label = "residual"
    plotter.color_map_kwargs = {"min_val": 0.0, "max_val": 1.0, "cmap": "plasma", "label": "score"}
    return plotter


def test_histogram_plotter_save_load_round_trips_spec_and_data(tmp_path, synthetic_histogram):
    plotter = _histogram_plotter(synthetic_histogram)
    plotter.add_function(lambda x: 30.0 * np.exp(-((x - 5.0) ** 2) / 2.0), density=False, color="red")

    path = tmp_path / "p.json"
    plotter.save(path)
    loaded = HistogramPlotter.load(path)

    assert loaded.figsize == (7, 3)
    assert isinstance(loaded.figsize, tuple)
    assert loaded.ylim == (1.0, 500.0)
    assert loaded.pull_ylim == (-2.5, 2.5)
    assert loaded.pull_label == "residual"
    assert loaded.color_map_kwargs == {"min_val": 0.0, "max_val": 1.0, "cmap": "plasma", "label": "score"}

    assert loaded.variable.name == "mass"
    assert loaded.variable.unit == "GeV"
    # Proves restoration wrote _xlabel: xlabel is a read-only property on this class.
    assert loaded.xlabel == "mass (GeV)"

    assert loaded.histplot.stacked is True
    assert loaded.histplot.sig_extra is True
    assert loaded.histplot.uncertainty is True
    assert loaded.histplot.density is True
    assert loaded.histplot.linewidth == 2.5
    assert loaded.histplot.edgecolor == "navy"

    assert np.allclose(loaded.histplot.histogram.binning, synthetic_histogram.binning)
    assert np.allclose(
        loaded.histplot.histogram.get_bin_counts()[0],
        synthetic_histogram.get_bin_counts()[0],
    )
    assert np.allclose(
        loaded.histplot.histogram.get_bin_errors()[0],
        synthetic_histogram.get_bin_errors()[0],
    )
    assert loaded.histplot.histogram.get_names() == synthetic_histogram.get_names()

    # The overlay add_function sampled is preserved as data, not as a callable.
    assert len(loaded.generic_plots) == 1
    assert loaded.generic_plots[0].plotmethod == "plot"
    assert np.allclose(loaded.generic_plots[0].args[1], plotter.generic_plots[0].args[1])
    assert loaded.generic_plots[0].kwargs == {"color": "red"}


def test_histogram_plotter_save_load_round_trips_pull_plots(tmp_path, synthetic_histogram):
    plotter = _histogram_plotter(synthetic_histogram)
    plotter.add_pull(lambda x: 30.0 * np.exp(-((x - 5.0) ** 2) / 2.0), density=False, color="red")

    path = tmp_path / "p.json"
    plotter.save(path)
    loaded = HistogramPlotter.load(path)

    assert [plot.plotmethod for plot in loaded.pull_plots] == [
        plot.plotmethod for plot in plotter.pull_plots
    ]
    assert np.allclose(loaded.pull_plots[-1].args[1], plotter.pull_plots[-1].args[1])
    assert loaded.pull_ylim == plotter.pull_ylim


def test_histogram_plotter_inset_references_the_loaded_objects(tmp_path, synthetic_histogram):
    plotter = _histogram_plotter(synthetic_histogram)
    plotter.add_generic_plot(GenericPlot("plot", np.array([1.0, 2.0]), np.array([3.0, 4.0])))
    plotter.add_inset(xlim=(2.0, 4.0), title="zoom")

    path = tmp_path / "p.json"
    plotter.save(path)
    loaded = HistogramPlotter.load(path)

    assert len(loaded._insets) == 1
    assert loaded._insets[0].title == "zoom"
    # Default inset content is [histplot] + generic_plots; both must be the LIVE objects.
    assert loaded._insets[0].plots[0] is loaded.histplot
    assert loaded._insets[0].plots[1] is loaded.generic_plots[0]


def test_histogram_plotter_file_size_does_not_scale_with_sample_size(tmp_path):
    """The point of embedding binned-only data: caching stays viable at any sample size."""
    rng = np.random.default_rng(seed=7)
    sizes = []
    for n_events, name in ((1_000, "small.json"), (100_000, "large.json")):
        histogram = Histogram()
        histogram.binning = np.linspace(0, 10, 21)
        histogram.add_entry(HistogramEntry(name="bkg", array=rng.uniform(0, 10, size=n_events)))
        plotter = HistogramPlotter(HistogramPlot(histogram), HistogramVariable(name="mass"))
        path = tmp_path / name
        plotter.save(path)
        sizes.append(path.stat().st_size)

    assert abs(sizes[1] - sizes[0]) / sizes[0] < 0.10


def test_loaded_histogram_plotter_renders_the_same_overlay(tmp_path, synthetic_histogram):
    """Round-tripping a dict is not the same as re-rendering a plot."""
    plotter = _histogram_plotter(synthetic_histogram)
    plotter.add_function(lambda x: 30.0 * np.exp(-((x - 5.0) ** 2) / 2.0), density=False, color="red")

    path = tmp_path / "p.json"
    plotter.save(path)
    loaded = HistogramPlotter.load(path)

    original_ax, _ = plotter.plot(save=False)
    original_curves = [line.get_ydata() for line in original_ax.lines]
    plt.close("all")

    loaded_ax, _ = loaded.plot(save=False)
    loaded_curves = [line.get_ydata() for line in loaded_ax.lines]
    plt.close("all")

    assert len(loaded_curves) == len(original_curves) > 0
    for restored, original in zip(loaded_curves, original_curves):
        assert np.allclose(restored, original)
```

If `tests/test_histogramplot.py` does not already import `matplotlib.pyplot as plt`, `Histogram`, `HistogramEntry` or `GenericPlot`, add those imports.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_histogramplot.py -k "save_load or inset_references or file_size or renders_the_same" -v`
Expected: `AttributeError: 'HistogramPlotter' object has no attribute 'save'`.

- [ ] **Step 3: Implement `save`/`load`**

Add to `src/afplotter/histogramplot.py` the same `plotspec` imports Task 3 added to `genericplot.py` (plus `json` and `Path` if absent), then these methods on `HistogramPlotter`:

```python
    def save(self, path: str | Path, skip_unserializable: bool = False) -> None:
        """Write this plotter's specification and its binned data to a JSON file.

        The histogram is embedded without its raw event arrays, so the file stays small
        regardless of sample size. Overlays added through :meth:`add_function` or
        :meth:`add_pull` were evaluated into sampled arrays when they were added, so a
        loaded plot re-renders them at that resolution; it cannot re-evaluate the model
        at a different binning.

        :param path: Destination file path. Any parent directory must already exist.
        :param skip_unserializable: Drop keyword arguments that cannot be saved, recording
            them in the file so :meth:`load` can warn. Positional arguments are never
            dropped.
        :raises ValueError: If any value cannot be saved and ``skip_unserializable`` is
            false. Nothing is written in that case.
        :return: None
        """
        dropped: list[str] = []

        def encode_plots(plots: list[GenericPlot], label: str) -> list[dict[str, Any]]:
            encoded = []
            for index, plot in enumerate(plots):
                data, plot_dropped = encode_generic_plot(plot, skip_unserializable=skip_unserializable)
                encoded.append(data)
                dropped.extend(f"{label}[{index}]: {item}" for item in plot_dropped)
            return encoded

        try:
            base = encode_base_plotter(self)
            generic_plots = encode_plots(self.generic_plots, "generic_plots")
            pull_plots = encode_plots(self.pull_plots, "pull_plots")
            insets = [encode_inset(inset, self._inset_refs(inset)) for inset in self._insets]
            histplot = {
                "stacked": self.histplot.stacked,
                "sig_extra": self.histplot.sig_extra,
                "uncertainty": self.histplot.uncertainty,
                "data_only": self.histplot.data_only,
                "density": self.histplot.density,
                "log": self.histplot.log,
                "linewidth": self.histplot.linewidth,
                "edgecolor": self.histplot.edgecolor,
            }
            spec = {
                "variable": {"name": self.variable.name, "unit": self.variable.unit},
                "pull_ylim": encode_value(self.pull_ylim),
                "pull_label": self.pull_label,
                "color_map_kwargs": encode_value(self.color_map_kwargs),
            }
        except UnserializableValue as error:
            raise ValueError(f"Cannot save this plotter: {error.where} holds {error.value_repr}") from error

        payload = {
            "format_version": PLOT_FORMAT_VERSION,
            "base": base,
            "spec": spec,
            "histplot": histplot,
            "histogram": _binned_histogram_payload(self.histplot.histogram),
            "data_histogram": (
                _binned_histogram_payload(self.histplot.data_hist)
                if self.histplot.data_hist is not None
                else None
            ),
            "generic_plots": generic_plots,
            "pull_plots": pull_plots,
            "insets": insets,
            "dropped": dropped,
        }
        Path(path).write_text(json.dumps(payload))

    def _inset_refs(self, inset: InsetPlot) -> dict[str, Any]:
        """Describe an inset's plots symbolically: this plotter's histplot and/or its overlays.

        :param inset: The inset to describe.
        :return: ``{"histplot": bool, "generic_plots": [<index>, ...]}`` in replay order.
        :raises UnserializableValue: If the inset replays an object this plotter does not own.
        """
        refs: dict[str, Any] = {"order": []}
        for plot in inset.plots:
            if plot is self.histplot:
                refs["order"].append(["histplot", 0])
                continue
            for index, own in enumerate(self.generic_plots):
                if plot is own:
                    refs["order"].append(["generic_plots", index])
                    break
            else:
                raise UnserializableValue(plot, where="an inset plot this plotter does not own")
        return refs

    @classmethod
    def load(cls, path: str | Path) -> "HistogramPlotter":
        """Read a plotter written by :meth:`save`.

        The restored histogram carries no raw event data, so the plotter cannot be used to
        build a 2D plot -- see :class:`Histogram2DPlot`.

        :param path: Path to a JSON file written by :meth:`save`.
        :return: An editable plotter: adjust limits, add overlays, call ``plot()``.
        :raises ValueError: If the file's ``format_version`` is unsupported, its top-level
            JSON is not an object, or a required key is missing.
        """
        payload = json.loads(Path(path).read_text())
        if not isinstance(payload, dict):
            raise ValueError(f"Malformed plot file {path}: expected a JSON object at the top level.")
        version = payload.get("format_version")
        if version != PLOT_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported format_version {version!r} in {path}; "
                f"this version of AFPlotter writes and reads format_version {PLOT_FORMAT_VERSION}."
            )
        for key in ("base", "spec", "histplot", "histogram"):
            if key not in payload:
                raise ValueError(f"Malformed plot file {path}: missing required key {key!r}.")

        histplot = HistogramPlot(Histogram.from_dict(payload["histogram"]))
        for flag, value in payload["histplot"].items():
            setattr(histplot, flag, value)
        if payload.get("data_histogram") is not None:
            histplot.data_hist = Histogram.from_dict(payload["data_histogram"])

        spec = payload["spec"]
        plotter = cls(histplot, HistogramVariable(**spec["variable"]))
        decode_base_plotter(plotter, payload["base"])
        plotter.pull_ylim = decode_value(spec["pull_ylim"])
        plotter.pull_label = spec["pull_label"]
        plotter.color_map_kwargs = decode_value(spec["color_map_kwargs"])
        plotter.generic_plots = [decode_generic_plot(data) for data in payload.get("generic_plots", [])]
        plotter.pull_plots = [decode_generic_plot(data) for data in payload.get("pull_plots", [])]
        plotter._insets = [
            decode_inset(data, plotter._resolve_inset_refs(data["plots"])) for data in payload.get("insets", [])
        ]
        warn_dropped(payload.get("dropped", []))
        return plotter

    def _resolve_inset_refs(self, refs: dict[str, Any]) -> list[Any]:
        """Turn the symbolic references written by :meth:`_inset_refs` back into live objects.

        :param refs: One inset's reference block.
        :return: The plot objects, in replay order.
        """
        resolved: list[Any] = []
        for kind, index in refs["order"]:
            resolved.append(self.histplot if kind == "histplot" else self.generic_plots[index])
        return resolved
```

Add this module-level helper next to the imports in `histogramplot.py`, so `save` never materializes raw arrays:

```python
def _binned_histogram_payload(histogram: Histogram) -> dict[str, Any]:
    """Build the embedded, binned-only payload for a histogram.

    Mirrors :meth:`Histogram.save`'s payload without writing a file, and without
    materializing any entry's raw ``array``.

    :param histogram: The histogram to encode.
    :return: JSON-safe data accepted by :meth:`Histogram.from_dict`.
    """
    binning = (
        histogram.binning
        if isinstance(histogram.binning, int)
        else histogram.binning.tolist()
        if histogram.binning is not None
        else None
    )
    return {
        "binning": binning,
        "metadata": histogram.metadata,
        "entries": {name: entry.as_binned_dict() for name, entry in histogram.entries.items()},
        "signal": {name: entry.as_binned_dict() for name, entry in histogram.signal.items()},
    }
```

Note the `_inset_refs` reference block here uses an ordered `"order"` list rather than `GenericPlotter`'s flat index list, because a `HistogramPlotter` inset can replay two kinds of object. `GenericPlotter`'s simpler block stays as Task 3 wrote it — the two are read only by their own class.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_histogramplot.py -v`
Expected: all pass, including the pre-existing tests.

- [ ] **Step 5: Verify the tests are falsifiable**

Temporarily make `load` build `HistogramVariable(name="x")` instead of reading `spec["variable"]`, and re-run: the spec round-trip test must fail on `loaded.xlabel == "mass (GeV)"`. Then temporarily make `_binned_histogram_payload` use `entry.as_dict` instead of `entry.as_binned_dict()`: `test_histogram_plotter_file_size_does_not_scale_with_sample_size` must fail, because raw arrays return to the payload. Restore both and confirm with `git diff`.

- [ ] **Step 6: Run the full suite and the gates**

```bash
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
uv run mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
```

Expected: all pass, ruff clean, mypy `Success`.

- [ ] **Step 7: Commit**

```bash
git add src/afplotter/histogramplot.py tests/test_histogramplot.py
git commit -m "Add HistogramPlotter.save and HistogramPlotter.load

Issue #38. The histogram is embedded binned-only, so file size does
not scale with sample size. Insets keep referencing the loaded
plotter's own live objects rather than copies.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: `Histogram2DPlotter.save`/`load`

**Files:**
- Modify: `src/afplotter/histogramplot.py` — add `save`/`load` to `Histogram2DPlotter` (class at `:870`; `__init__` at `:871-882` sets `histplot`, `xvariable`, `yvariable`, `generic_plots`)
- Test: `tests/test_histogramplot.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 1-4.
- Produces:
  - `Histogram2DPlotter.save(path: str | Path, skip_unserializable: bool = False) -> None`
  - `Histogram2DPlotter.load(path: str | Path, xhistogram: Histogram, yhistogram: Histogram) -> "Histogram2DPlotter"` (classmethod; both histograms are required positional-or-keyword parameters)

`Histogram2DPlot` settings to carry: `density`, `log`, `cmap`, `norm`, `cmin`, `cmax`, `cbar_label` (properties at `histogramplot.py:373-426`). `Histogram2DPlot.__init__` takes `(xhistogram, yhistogram)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_histogramplot.py`:

```python
def _2d_histograms():
    rng = np.random.default_rng(seed=11)
    xhist = Histogram()
    xhist.binning = np.linspace(0, 10, 11)
    xhist.add_entry(HistogramEntry(name="x", array=rng.uniform(0, 10, size=400)))
    yhist = Histogram()
    yhist.binning = np.linspace(0, 5, 6)
    yhist.add_entry(HistogramEntry(name="y", array=rng.uniform(0, 5, size=400)))
    return xhist, yhist


def test_histogram_2d_plotter_save_load_round_trips_the_spec(tmp_path):
    """Every asserted value is non-default: cmap defaults to 'viridis', norm to 'linear'."""
    xhist, yhist = _2d_histograms()
    histplot = Histogram2DPlot(xhist, yhist)
    histplot.cmap = "plasma"
    histplot.norm = "log"
    histplot.cmin = 0.5
    histplot.cmax = 42.0
    histplot.cbar_label = "events / bin"
    histplot.density = True
    plotter = Histogram2DPlotter(histplot, HistogramVariable("mass", "GeV"), HistogramVariable("time", "ns"))
    plotter.figsize = (7, 3)
    plotter.add_generic_plot(GenericPlot("plot", np.array([1.0, 2.0]), np.array([3.0, 4.0]), color="red"))

    path = tmp_path / "p2d.json"
    plotter.save(path)

    fresh_x, fresh_y = _2d_histograms()
    loaded = Histogram2DPlotter.load(path, xhistogram=fresh_x, yhistogram=fresh_y)

    assert loaded.figsize == (7, 3)
    assert loaded.xvariable.name == "mass"
    assert loaded.yvariable.unit == "ns"
    assert loaded.xlabel == "mass (GeV)"
    assert loaded.histplot.cmap == "plasma"
    assert loaded.histplot.norm == "log"
    assert loaded.histplot.cmin == 0.5
    assert loaded.histplot.cmax == 42.0
    assert loaded.histplot.cbar_label == "events / bin"
    assert loaded.histplot.density is True
    assert loaded.generic_plots[0].kwargs == {"color": "red"}
    # The data came from the caller, not the file.
    assert loaded.histplot.xhistogram is fresh_x
    assert loaded.histplot.yhistogram is fresh_y


def test_histogram_2d_plotter_save_does_not_embed_event_data(tmp_path):
    """Raw arrays in the payload are exactly what this design rejects."""
    xhist, yhist = _2d_histograms()
    plotter = Histogram2DPlotter(
        Histogram2DPlot(xhist, yhist), HistogramVariable("mass"), HistogramVariable("time")
    )
    path = tmp_path / "p2d.json"
    plotter.save(path)

    payload = json.loads(path.read_text())
    assert "histogram" not in payload
    assert path.stat().st_size < 2_000


def test_histogram_2d_plotter_load_requires_both_histograms(tmp_path):
    xhist, yhist = _2d_histograms()
    plotter = Histogram2DPlotter(
        Histogram2DPlot(xhist, yhist), HistogramVariable("mass"), HistogramVariable("time")
    )
    path = tmp_path / "p2d.json"
    plotter.save(path)

    with pytest.raises(TypeError):
        Histogram2DPlotter.load(path)


def test_loaded_histogram_2d_plotter_renders(tmp_path):
    xhist, yhist = _2d_histograms()
    plotter = Histogram2DPlotter(
        Histogram2DPlot(xhist, yhist), HistogramVariable("mass"), HistogramVariable("time")
    )
    path = tmp_path / "p2d.json"
    plotter.save(path)

    fresh_x, fresh_y = _2d_histograms()
    loaded = Histogram2DPlotter.load(path, xhistogram=fresh_x, yhistogram=fresh_y)
    ax = loaded.plot(save=False)
    assert ax.get_xlabel() == "mass"
    plt.close("all")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_histogramplot.py -k "2d_plotter" -v`
Expected: `AttributeError: 'Histogram2DPlotter' object has no attribute 'save'`.

- [ ] **Step 3: Implement `save`/`load`**

Add to `Histogram2DPlotter` in `src/afplotter/histogramplot.py`:

```python
    def save(self, path: str | Path, skip_unserializable: bool = False) -> None:
        """Write this plotter's specification to a JSON file, without its event data.

        :class:`Histogram2DPlot` bins raw event arrays at plot time and stores no 2D
        counts, so there is nothing binned to embed. The file holds styling, limits,
        colour-map settings, variables and overlays; :meth:`load` takes the histograms
        back as arguments.

        :param path: Destination file path. Any parent directory must already exist.
        :param skip_unserializable: Drop keyword arguments that cannot be saved, recording
            them in the file so :meth:`load` can warn. Positional arguments are never
            dropped.
        :raises ValueError: If any value cannot be saved and ``skip_unserializable`` is
            false. Nothing is written in that case.
        :return: None
        """
        dropped: list[str] = []
        try:
            base = encode_base_plotter(self)
            generic_plots = []
            for index, plot in enumerate(self.generic_plots):
                data, plot_dropped = encode_generic_plot(plot, skip_unserializable=skip_unserializable)
                generic_plots.append(data)
                dropped.extend(f"generic_plots[{index}]: {item}" for item in plot_dropped)
            spec = {
                "xvariable": {"name": self.xvariable.name, "unit": self.xvariable.unit},
                "yvariable": {"name": self.yvariable.name, "unit": self.yvariable.unit},
            }
            histplot = {
                "density": self.histplot.density,
                "log": self.histplot.log,
                "cmap": self.histplot.cmap,
                "norm": self.histplot.norm,
                "cmin": self.histplot.cmin,
                "cmax": self.histplot.cmax,
                "cbar_label": self.histplot.cbar_label,
            }
        except UnserializableValue as error:
            raise ValueError(f"Cannot save this plotter: {error.where} holds {error.value_repr}") from error

        payload = {
            "format_version": PLOT_FORMAT_VERSION,
            "base": base,
            "spec": spec,
            "histplot": histplot,
            "generic_plots": generic_plots,
            "dropped": dropped,
        }
        Path(path).write_text(json.dumps(payload))

    @classmethod
    def load(cls, path: str | Path, xhistogram: Histogram, yhistogram: Histogram) -> "Histogram2DPlotter":
        """Read a plotter written by :meth:`save`, re-attaching its event data.

        :param path: Path to a JSON file written by :meth:`save`.
        :param xhistogram: The x-axis histogram, carrying raw event arrays.
        :param yhistogram: The y-axis histogram, carrying raw event arrays.
        :return: An editable plotter: adjust limits, add overlays, call ``plot()``.
        :raises ValueError: If the file's ``format_version`` is unsupported, its top-level
            JSON is not an object, or a required key is missing.
        """
        payload = json.loads(Path(path).read_text())
        if not isinstance(payload, dict):
            raise ValueError(f"Malformed plot file {path}: expected a JSON object at the top level.")
        version = payload.get("format_version")
        if version != PLOT_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported format_version {version!r} in {path}; "
                f"this version of AFPlotter writes and reads format_version {PLOT_FORMAT_VERSION}."
            )
        for key in ("base", "spec", "histplot"):
            if key not in payload:
                raise ValueError(f"Malformed plot file {path}: missing required key {key!r}.")

        histplot = Histogram2DPlot(xhistogram, yhistogram)
        for setting, value in payload["histplot"].items():
            setattr(histplot, setting, value)

        spec = payload["spec"]
        plotter = cls(
            histplot,
            HistogramVariable(**spec["xvariable"]),
            HistogramVariable(**spec["yvariable"]),
        )
        decode_base_plotter(plotter, payload["base"])
        plotter.generic_plots = [decode_generic_plot(data) for data in payload.get("generic_plots", [])]
        warn_dropped(payload.get("dropped", []))
        return plotter
```

`Histogram2DPlot.__init__` (`histogramplot.py:349-351`) stores its inputs as `self.xhistogram` / `self.yhistogram`, which is what the test's `loaded.histplot.xhistogram is fresh_x` assertion reads.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_histogramplot.py -v`
Expected: all pass.

- [ ] **Step 5: Verify the tests are falsifiable**

Temporarily make `load` skip the `histplot` settings loop and re-run: the 2D spec round-trip must fail on `loaded.histplot.cmap == "plasma"`. Then temporarily give `load` defaults (`xhistogram=None, yhistogram=None`): `test_histogram_2d_plotter_load_requires_both_histograms` must fail. Restore both and confirm with `git diff`.

- [ ] **Step 6: Update the docs**

`docs/getting-started.md` documents the plotters' workflow. Add a short subsection under the existing histogram-plotting material, matching the file's tone and heading depth:

```markdown
### Saving and reloading a plot

Every plotter can write its specification to JSON and read it back:

```python
plotter.save("fit.json")
plotter = HistogramPlotter.load("fit.json")
plotter.ylim = (1, 5000)      # adjust anything, then re-render
plotter.plot(save=True)
```

`HistogramPlotter` embeds its binned data, so one file is enough. `Histogram2DPlotter` bins raw
events at plot time and cannot store them, so its `load` takes the histograms back:
`Histogram2DPlotter.load(path, xhistogram=xh, yhistogram=yh)`.

Overlays added with `add_function`/`add_pull` are saved as the sampled curve, not as the model —
a reloaded plot re-renders that curve but cannot re-evaluate the function at a different binning.
```

- [ ] **Step 7: Run the full suite and the gates**

```bash
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
uv run mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
```

Expected: all pass, ruff clean, mypy `Success`.

- [ ] **Step 8: Commit**

```bash
git add src/afplotter/histogramplot.py tests/test_histogramplot.py docs/getting-started.md
git commit -m "Add Histogram2DPlotter.save and Histogram2DPlotter.load

Issue #38. Histogram2DPlot bins raw arrays at plot time and stores no
2D counts, so the file holds the specification only and load takes the
histograms back as arguments.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Notes for the final review

- The spec's `save`/`load` docstrings must all state that overlays are stored as sampled curves and cannot be re-evaluated at a new binning. That is the one user-visible consequence of `add_function`'s eager evaluation, and it is invisible from the API otherwise.
- `plotspec.py` is the only new file; if it has grown past roughly 300 lines by Task 5, say so in the review rather than splitting it mid-plan.
- No public API is removed or renamed by this work, so nothing here is owed to #6's release notes.
