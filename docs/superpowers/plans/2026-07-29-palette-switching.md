# Palette Switching and Color-Class Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `KITColors`/`LMUColors` apart, introduce a switchable `Palette` abstraction with `set_palette()`/`get_palette()` (default Petroff), and fix the two follow-ups PR #10 left behind (all-or-nothing entry-color fallback, dead `b2helix`/seaborn).

**Architecture:** A new `src/afplotter/palettes.py` module owns all raw color-swatch classes (`KITColors`, `LMUColors`, `PetroffColors`) plus a `Palette` dataclass (background cycle + reserved signal color) and a registry/context pair (`register_palette`/`get`/`set_palette`/`get_palette`) mirroring the existing `afplotter.experiments.registry`/`context` pattern exactly. `baseplotter.py` and `histogramplot.py` read the active palette through `get_palette()` instead of hardcoded constants.

**Tech Stack:** Python 3.10+, matplotlib, `cycler`, pytest.

## Global Constraints

- Python 3.10+ typing: native `X | Y` unions, builtin generics — no `typing.Optional`/`List`/`Dict`.
- reST docstrings (`:param:`/`:return:`) on public functions and classes.
- No import-time side effects touching filesystem or env vars (`tests/test_packaging.py` guards this).
- Line length 120 (ruff).
- Tests use the matplotlib `Agg` backend (set in `tests/conftest.py`).
- `PETROFF_PALETTE` is the default palette: `get_palette()` returns it when nothing has been explicitly set, and `set_palette()` with no argument selects it.
- `set_palette()` is global and live (mirrors `set_experiment()`): it updates `plt.rcParams["axes.prop_cycle"]` immediately, and any `BasePlotter` constructed afterward picks up the new cycle via `set_matplotlibrc_params()`.
- All three built-in palettes hold their own red out of their own background cycle and reserve it as `signal` (Petroff/KIT/LMU each).
- This work continues directly on branch `feature/petroff-colors` (PR #10, not yet merged) — do **not** branch off `main`, since `main` lacks `PetroffColors`/`SIGNAL_COLOR` entirely.
- Assertions must be falsifiable: assert on rendered hex colors (`to_hex(...)`) or artist properties, never "didn't crash."

---

### Task 1: `palettes.py` — color classes, `Palette`, registry, context, and wiring

**Files:**
- Create: `src/afplotter/palettes.py`
- Create: `tests/palettes/__init__.py`
- Create: `tests/palettes/conftest.py`
- Create: `tests/palettes/test_registry.py`
- Create: `tests/palettes/test_context.py`
- Modify: `src/afplotter/baseplotter.py` (remove `KITColors`/`PetroffColors`/cyclers/`SIGNAL_COLOR`, wire `set_matplotlibrc_params`)
- Modify: `src/afplotter/histogramplot.py` (swap `SIGNAL_COLOR` import for `get_palette`)
- Modify: `src/afplotter/__init__.py` (export new symbols)
- Modify: `tests/test_baseplotter.py` (fix references to removed/moved symbols)
- Modify: `tests/test_histogramplot.py` (fix references to removed/moved symbols)
- Modify: `examples/histogram_with_pull.py` (fix `SIGNAL_COLOR`/`PetroffColors` import)

**Interfaces:**
- Produces: `afplotter.palettes.KITColors`, `LMUColors`, `PetroffColors` (plain hex-constant classes); `afplotter.palettes.Palette` (frozen dataclass: `name: str`, `background: list[str]`, `signal: str`); `PETROFF_PALETTE`, `KIT_PALETTE`, `LMU_PALETTE` (module-level `Palette` instances); `register_palette(palette: Palette) -> None`; `get(name: str) -> Palette`; `set_palette(name: str = "Petroff") -> Palette`; `get_palette() -> Palette`.

- [ ] **Step 1: Write failing tests for the color classes and `Palette` instances**

Create `tests/palettes/__init__.py` (empty file, mirrors `tests/experiments/__init__.py`).

Create `tests/palettes/conftest.py`:

```python
import pytest

from afplotter import palettes


def _reset_palette_state():
    palettes._PALETTES = {
        palettes.PETROFF_PALETTE.name: palettes.PETROFF_PALETTE,
        palettes.KIT_PALETTE.name: palettes.KIT_PALETTE,
        palettes.LMU_PALETTE.name: palettes.LMU_PALETTE,
    }
    palettes._CURRENT_PALETTE = None


@pytest.fixture(autouse=True)
def clean_palette_registry():
    """Reset the module-global palette registry/context before and after each test.

    Without this, tests that register or select palettes leak state into
    whichever test runs next, so results depend on run order.
    """
    _reset_palette_state()
    yield
    _reset_palette_state()
```

Create `tests/palettes/test_registry.py`:

```python
import pytest

from afplotter import palettes


def _dummy_palette(name: str) -> "palettes.Palette":
    return palettes.Palette(name=name, background=["#000000"], signal="#ffffff")


def test_register_and_get():
    p = _dummy_palette("TestPalette")
    palettes.register_palette(p)
    assert palettes.get("TestPalette") is p


def test_register_duplicate_raises():
    p = _dummy_palette("TestPalette")
    palettes.register_palette(p)
    with pytest.raises(ValueError, match="already registered"):
        palettes.register_palette(p)


def test_get_unknown_raises():
    with pytest.raises(ValueError, match="Unknown palette"):
        palettes.get("NoSuchPalette")


def test_builtin_palettes_are_registered():
    assert palettes.get("Petroff").name == "Petroff"
    assert palettes.get("KIT").name == "KIT"
    assert palettes.get("LMU").name == "LMU"
```

Create `tests/palettes/test_context.py`:

```python
import matplotlib.pyplot as plt

from afplotter import palettes


def test_set_palette_by_name():
    p = palettes.set_palette("KIT")
    assert p.name == "KIT"
    assert palettes.get_palette().name == "KIT"


def test_set_palette_defaults_to_petroff():
    p = palettes.set_palette()
    assert p.name == "Petroff"


def test_get_palette_without_set_defaults_to_petroff():
    assert palettes.get_palette().name == "Petroff"


def test_set_palette_updates_rcparams_immediately():
    plt.rcParams["axes.prop_cycle"] = plt.cycler("color", ["#123456"])
    palettes.set_palette("KIT")
    assert plt.rcParams["axes.prop_cycle"].by_key()["color"] == palettes.KIT_PALETTE.background


def test_kit_palette_excludes_kit_red_and_reserves_it_as_signal():
    assert palettes.KITColors.kit_red not in palettes.KIT_PALETTE.background
    assert palettes.KIT_PALETTE.signal == palettes.KITColors.kit_red


def test_lmu_palette_excludes_lmu_red_and_reserves_it_as_signal():
    assert palettes.LMUColors.lmu_red not in palettes.LMU_PALETTE.background
    assert palettes.LMU_PALETTE.signal == palettes.LMUColors.lmu_red


def test_petroff_palette_excludes_red_and_reserves_it_as_signal():
    assert palettes.PetroffColors.red not in palettes.PETROFF_PALETTE.background
    assert palettes.PETROFF_PALETTE.signal == palettes.PetroffColors.red
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/palettes/ -v`
Expected: FAIL / ERROR — `afplotter.palettes` module does not exist yet (`ModuleNotFoundError`).

- [ ] **Step 3: Create `src/afplotter/palettes.py`**

```python
from dataclasses import dataclass

import matplotlib.pyplot as plt
from cycler import cycler


class KITColors:
    """
    KIT color scheme plus additional grey shades
    """

    kit_green = "#009682"  # type: str
    kit_blue = "#4664aa"  # type: str
    kit_maygreen = "#8cb63c"  # type: str
    kit_yellow = "#fce500"  # type: str
    kit_orange = "#df9b1b"  # type: str
    kit_brown = "#a7822e"  # type: str
    kit_red = "#a22223"  # type: str
    kit_purple = "#a3107c"  # type: str
    kit_cyan = "#23a1e0"  # type: str
    kit_black = "#000000"  # type: str
    white = "#ffffff"  # type: str
    light_grey = "#bdbdbd"  # type: str
    grey = "#797979"  # type: str
    dark_grey = "#4e4e4e"  # type: str


class LMUColors:
    """LMU corporate color scheme."""

    lmu_green = "#00883A"  # R 0,   G 136, B 58
    lmu_blue = "#0F1987"  # R 15,  G 25,  B 135
    lmu_cyan = "#643BE3"  # R 100, G 59,  B 227
    lmu_violet = "#8C4091"  # R 140, G 64,  B 145
    lmu_red = "#D71919"  # R 215, G 25,  B 25
    lmu_orange = "#F18700"  # R 241, G 135, B 0


class PetroffColors:
    """
    Petroff 10 colour sequence, as shipped in matplotlib's ``petroff10`` style.

    See M. A. Petroff, "Accessible Color Sequences for Data Visualization",
    arXiv:2107.02270.
    """

    blue = "#3f90da"  # type: str
    amber = "#ffa90e"  # type: str
    red = "#bd1f01"  # type: str
    grey_green = "#94a4a2"  # type: str
    purple = "#832db6"  # type: str
    brown = "#a96b59"  # type: str
    orange = "#e76300"  # type: str
    khaki = "#b9ac70"  # type: str
    slate = "#717581"  # type: str
    pale_cyan = "#92dadd"  # type: str


@dataclass(frozen=True)
class Palette:
    """
    A named background color cycle plus a color reserved exclusively for signal.

    :param name: Unique palette identifier, e.g. "Petroff".
    :param background: Cycle colors for non-signal components. Must not
        contain ``signal``.
    :param signal: Color reserved for signal components; never appears in
        ``background``.
    """

    name: str
    background: list[str]
    signal: str


#: Petroff 10 (arXiv:2107.02270) minus its red, which is reserved for signal.
PETROFF_PALETTE = Palette(
    name="Petroff",
    background=[
        PetroffColors.blue,
        PetroffColors.amber,
        PetroffColors.grey_green,
        PetroffColors.purple,
        PetroffColors.brown,
        PetroffColors.orange,
        PetroffColors.khaki,
        PetroffColors.slate,
        PetroffColors.pale_cyan,
    ],
    signal=PetroffColors.red,
)

#: KIT color scheme minus kit_red, which is reserved for signal.
KIT_PALETTE = Palette(
    name="KIT",
    background=[
        KITColors.kit_green,
        KITColors.kit_blue,
        KITColors.kit_cyan,
        KITColors.kit_orange,
        KITColors.kit_maygreen,
        KITColors.kit_yellow,
        KITColors.kit_purple,
        KITColors.kit_brown,
        KITColors.dark_grey,
    ],
    signal=KITColors.kit_red,
)

#: LMU color scheme minus lmu_red, which is reserved for signal.
LMU_PALETTE = Palette(
    name="LMU",
    background=[
        LMUColors.lmu_green,
        LMUColors.lmu_blue,
        LMUColors.lmu_cyan,
        LMUColors.lmu_violet,
        LMUColors.lmu_orange,
    ],
    signal=LMUColors.lmu_red,
)

_PALETTES: dict[str, Palette] = {
    PETROFF_PALETTE.name: PETROFF_PALETTE,
    KIT_PALETTE.name: KIT_PALETTE,
    LMU_PALETTE.name: LMU_PALETTE,
}

_CURRENT_PALETTE: Palette | None = None


def register_palette(palette: Palette) -> None:
    """
    Register a new palette.

    :param palette: The palette to register.
    :raises ValueError: If a palette with the same name is already registered.
    :return: None
    """
    if palette.name in _PALETTES:
        raise ValueError(f"Palette {palette.name} already registered")
    _PALETTES[palette.name] = palette


def get(name: str) -> Palette:
    """
    Look up a registered palette by name.

    :param name: Palette name, e.g. "Petroff".
    :raises ValueError: If no palette with that name is registered.
    :return: The matching Palette.
    """
    try:
        return _PALETTES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown palette '{name}'. Available: {', '.join(_PALETTES)}") from exc


def set_palette(name: str = "Petroff") -> Palette:
    """
    Select the active color palette and apply it immediately.

    :param name: Palette name, e.g. "KIT". Defaults to "Petroff".
    :return: The now-current Palette.
    """
    global _CURRENT_PALETTE
    _CURRENT_PALETTE = get(name)
    plt.rcParams["axes.prop_cycle"] = cycler("color", _CURRENT_PALETTE.background)
    return _CURRENT_PALETTE


def get_palette() -> Palette:
    """
    Get the current palette, defaulting to "Petroff" if none has been set.

    :return: The current Palette.
    """
    global _CURRENT_PALETTE
    if _CURRENT_PALETTE is None:
        _CURRENT_PALETTE = PETROFF_PALETTE
    return _CURRENT_PALETTE
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `uv run pytest tests/palettes/ -v`
Expected: PASS (all tests in `tests/palettes/`).

- [ ] **Step 5: Remove the old color classes and cyclers from `baseplotter.py`, wire `set_matplotlibrc_params`**

In `src/afplotter/baseplotter.py`:

Delete the `KITColors` class, `PetroffColors` class, the `#: Colour used for signal components...` comment, the `SIGNAL_COLOR = PetroffColors.signal_red` line, and the `kit_color_cycler`/`petroff_color_cycler` lines (everything between the `PathType = str | os.PathLike` line and the `def set_matplotlibrc_params` line).

Add an import alongside the existing ones:

```python
from afplotter.palettes import get_palette
```

In `set_matplotlibrc_params`, change:

```python
    axes = {
        "labelsize": latex_text_size,
        "prop_cycle": petroff_color_cycler,
```

to:

```python
    axes = {
        "labelsize": latex_text_size,
        "prop_cycle": cycler("color", get_palette().background),
```

(`cycler` is already imported at the top of the file.)

- [ ] **Step 6: Update `histogramplot.py`'s `SIGNAL_COLOR` usage**

In `src/afplotter/histogramplot.py`, change the import:

```python
from afplotter.baseplotter import SIGNAL_COLOR, BasePlotter
```

to:

```python
from afplotter.baseplotter import BasePlotter
from afplotter.palettes import get_palette
```

Replace the single usage of `SIGNAL_COLOR` (in `plot_step`, the lone-signal branch):

```python
                colors = [SIGNAL_COLOR]
```

with:

```python
                colors = [get_palette().signal]
```

- [ ] **Step 7: Update `src/afplotter/__init__.py` exports**

Change:

```python
from afplotter.baseplotter import SIGNAL_COLOR, BasePlotter, KITColors, PetroffColors
```

to:

```python
from afplotter.baseplotter import BasePlotter
from afplotter.palettes import (
    KIT_PALETTE,
    LMU_PALETTE,
    PETROFF_PALETTE,
    KITColors,
    LMUColors,
    Palette,
    PetroffColors,
    get_palette,
    register_palette,
    set_palette,
)
```

- [ ] **Step 8: Fix `tests/test_baseplotter.py` references to removed/moved symbols**

Change the import line:

```python
from afplotter.baseplotter import SIGNAL_COLOR, BasePlotter, KITColors, PetroffColors
```

to:

```python
from afplotter.baseplotter import BasePlotter
from afplotter.palettes import PETROFF_PALETTE, KITColors, LMUColors, PetroffColors, get_palette
```

Replace these five tests:

```python
def test_kit_colors_defines_default_colors():
    assert len(KITColors.default_colors) == 10
    assert KITColors.kit_green == "#009682"


def test_kit_colors_defines_lmu_colors():
    assert KITColors.lmu_green == "#00883A"
    assert KITColors.lmu_blue == "#0F1987"
    assert KITColors.lmu_orange == "#F18700"


def test_petroff_colors_hold_red_out_of_the_cycle():
    # The full Petroff 10 sequence, minus its red, is what may be handed to
    # background components. Red must be reachable only as the signal colour.
    assert PetroffColors.default_colors == [
        "#3f90da",
        "#ffa90e",
        "#94a4a2",
        "#832db6",
        "#a96b59",
        "#e76300",
        "#b9ac70",
        "#717581",
        "#92dadd",
    ]
    assert PetroffColors.red == "#bd1f01"
    assert PetroffColors.red not in PetroffColors.default_colors


def test_signal_color_is_the_reserved_petroff_red():
    assert SIGNAL_COLOR == "#bd1f01"
    assert SIGNAL_COLOR == PetroffColors.signal_red


def test_constructing_a_plotter_installs_the_petroff_cycle():
    # Regression guard: BasePlotter.__init__ applies the experiment .mplstyle and
    # *then* set_matplotlibrc_params(). The Petroff cycle must be what survives.
    plt.rcParams["axes.prop_cycle"] = plt.cycler("color", ["#123456"])
    ConcretePlotter()
    assert plt.rcParams["axes.prop_cycle"].by_key()["color"] == PetroffColors.default_colors
```

with:

```python
def test_kit_colors_defines_kit_hexes():
    assert KITColors.kit_green == "#009682"
    assert KITColors.kit_red == "#a22223"


def test_lmu_colors_defines_lmu_hexes():
    assert LMUColors.lmu_green == "#00883A"
    assert LMUColors.lmu_blue == "#0F1987"
    assert LMUColors.lmu_orange == "#F18700"


def test_petroff_palette_holds_red_out_of_the_cycle():
    # The full Petroff 10 sequence, minus its red, is what may be handed to
    # background components. Red must be reachable only as the signal colour.
    assert PETROFF_PALETTE.background == [
        "#3f90da",
        "#ffa90e",
        "#94a4a2",
        "#832db6",
        "#a96b59",
        "#e76300",
        "#b9ac70",
        "#717581",
        "#92dadd",
    ]
    assert PetroffColors.red == "#bd1f01"
    assert PetroffColors.red not in PETROFF_PALETTE.background


def test_signal_color_defaults_to_the_reserved_petroff_red():
    assert get_palette().signal == "#bd1f01"
    assert get_palette().signal == PetroffColors.red


def test_constructing_a_plotter_installs_the_petroff_cycle():
    # Regression guard: BasePlotter.__init__ applies the experiment .mplstyle and
    # *then* set_matplotlibrc_params(). The active palette's cycle must survive.
    plt.rcParams["axes.prop_cycle"] = plt.cycler("color", ["#123456"])
    ConcretePlotter()
    assert plt.rcParams["axes.prop_cycle"].by_key()["color"] == PETROFF_PALETTE.background
```

- [ ] **Step 9: Fix `tests/test_histogramplot.py` references to removed/moved symbols**

Change the import line:

```python
from afplotter.baseplotter import SIGNAL_COLOR, PetroffColors
```

to:

```python
from afplotter.palettes import PETROFF_PALETTE, PetroffColors, get_palette
```

Then replace every use of `PetroffColors.default_colors` with `PETROFF_PALETTE.background`, and every use of `SIGNAL_COLOR` with `get_palette().signal`, across:
`test_stacked_entries_use_the_petroff_cycle`, `test_no_stacked_entry_is_ever_signal_red`,
`test_single_signal_is_drawn_in_signal_red`, `test_single_signal_red_overrides_an_explicit_entry_color`,
`test_multiple_signals_fall_back_to_the_cycle`. For example:

```python
def test_stacked_entries_use_the_petroff_cycle():
    colors = _rendered_colors(_uncolored_histogram(n_entries=3))
    assert [colors[f"B{i}"][0] for i in range(3)] == PETROFF_PALETTE.background[:3]


def test_no_stacked_entry_is_ever_signal_red():
    # 12 entries wraps past the end of the 9-colour cycle; red must still never appear.
    colors = _rendered_colors(_uncolored_histogram(n_entries=12))
    assert get_palette().signal not in [face for face, _ in colors.values()]


def test_single_signal_is_drawn_in_signal_red():
    colors = _rendered_colors(_uncolored_histogram(n_entries=2, n_signals=1), sig_extra=True)
    assert colors["S0"][1] == get_palette().signal
    assert [colors[f"B{i}"][0] for i in range(2)] == PETROFF_PALETTE.background[:2]


def test_single_signal_red_overrides_an_explicit_entry_color():
    hist = _uncolored_histogram(n_entries=2)
    hist.add_entry(
        HistogramEntry(
            name="sig0",
            latex_name="S0",
            array=np.random.default_rng(8).normal(5, 1, 300),
            type="signal",
            color="#00ff00",
        )
    )
    colors = _rendered_colors(hist, sig_extra=True)
    assert colors["S0"][1] == get_palette().signal


def test_multiple_signals_fall_back_to_the_cycle():
    colors = _rendered_colors(_uncolored_histogram(n_entries=2, n_signals=2), sig_extra=True)
    signal_edges = [colors["S0"][1], colors["S1"][1]]
    assert signal_edges == PETROFF_PALETTE.background[:2]
    assert get_palette().signal not in signal_edges
```

- [ ] **Step 10: Fix `examples/histogram_with_pull.py`'s import**

Change:

```python
from afplotter import (
    Histogram,
    HistogramEntry,
    HistogramPlot,
    HistogramPlotter,
    HistogramVariable,
    SIGNAL_COLOR,
    PetroffColors,
    set_experiment,
)
```

to:

```python
from afplotter import (
    Histogram,
    HistogramEntry,
    HistogramPlot,
    HistogramPlotter,
    HistogramVariable,
    PETROFF_PALETTE,
    PetroffColors,
    set_experiment,
)
```

And change:

```python
    hist.add_entry(HistogramEntry(name="signal", latex_name="Signal", array=data["signal"], color=SIGNAL_COLOR))
```

to:

```python
    hist.add_entry(HistogramEntry(name="signal", latex_name="Signal", array=data["signal"], color=PETROFF_PALETTE.signal))
```

- [ ] **Step 11: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: PASS — all tests, including the new `tests/palettes/` ones.

- [ ] **Step 12: Run the fixed example**

Run: `uv run python examples/histogram_with_pull.py`
Expected: exits 0, writes `examples/output/histogram_with_pull.png`.

- [ ] **Step 13: Commit**

```bash
git add src/afplotter/palettes.py src/afplotter/baseplotter.py src/afplotter/histogramplot.py \
        src/afplotter/__init__.py tests/palettes/ tests/test_baseplotter.py \
        tests/test_histogramplot.py examples/histogram_with_pull.py
git commit -m "Introduce switchable Palette abstraction, split KITColors/LMUColors"
```

---

### Task 2: Bundled `.mplstyle` files stop hardcoding the color cycle

**Files:**
- Modify: `src/afplotter/experiments/belle2_modern.mplstyle`
- Modify: `src/afplotter/experiments/generic.mplstyle`
- Modify: `tests/experiments/test_registry.py` or wherever the `.mplstyle` files are asserted against (verify no existing test asserts the hardcoded hex list from the style file directly — see Step 1).

**Interfaces:**
- Consumes: `afplotter.palettes.get_palette()` (Task 1) — applied via `BasePlotter.__init__` → `set_matplotlibrc_params()`, not by the style file itself.

- [ ] **Step 1: Check for any test asserting the `.mplstyle` files' hardcoded `axes.prop_cycle`**

Run: `grep -rn "axes.prop_cycle\|petroff10\|3f90da" tests/`
Expected: no hits inside `tests/` (the existing cycle-related assertions target `plt.rcParams` after constructing a plotter, i.e. the *effective* cycle installed by `set_matplotlibrc_params`, not the raw style file). If a hit is found, read that test and confirm it survives this change (it should, since `set_matplotlibrc_params()` still installs the correct cycle after `plt.style.use(...)` — the order documented in `BasePlotter.__init__` is unchanged, only the *source* of the color list changes from a literal in the style file to `get_palette().background`).

- [ ] **Step 2: Remove the hardcoded cycle from `generic.mplstyle`**

In `src/afplotter/experiments/generic.mplstyle`, remove this line:

```
# Petroff 10 (arXiv:2107.02270) minus its red 'bd1f01', which is reserved for signal.
axes.prop_cycle: cycler('color', ['3f90da', 'ffa90e', '94a4a2', '832db6', 'a96b59', 'e76300', 'b9ac70', '717581', '92dadd'])
```

Replace with:

```
# Color cycle is supplied at runtime by afplotter.set_palette(...) (default: Petroff),
# applied by BasePlotter via set_matplotlibrc_params() after this style loads.
```

- [ ] **Step 3: Remove the hardcoded cycle from `belle2_modern.mplstyle`**

In `src/afplotter/experiments/belle2_modern.mplstyle`, remove this line:

```
# Petroff 10 (arXiv:2107.02270) minus its red 'bd1f01', which is reserved for signal.
axes.prop_cycle: cycler('color', ['3f90da', 'ffa90e', '94a4a2', '832db6', 'a96b59', 'e76300', 'b9ac70', '717581', '92dadd'])
```

Replace with:

```
# Color cycle is supplied at runtime by afplotter.set_palette(...) (default: Petroff),
# applied by BasePlotter via set_matplotlibrc_params() after this style loads.
```

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: PASS — `test_constructing_a_plotter_installs_the_petroff_cycle` (Task 1, Step 8) still passes because `set_matplotlibrc_params()` installs the cycle regardless of what the style file does.

- [ ] **Step 5: Commit**

```bash
git add src/afplotter/experiments/belle2_modern.mplstyle src/afplotter/experiments/generic.mplstyle
git commit -m "Stop hardcoding the color cycle in bundled .mplstyle files"
```

---

### Task 3: Remove dead `b2helix`/seaborn code

**Files:**
- Modify: `src/afplotter/histogramplot.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: nothing from prior tasks.
- Produces: nothing consumed by later tasks (pure removal).

- [ ] **Step 1: Confirm nothing else calls `b2helix`**

Run: `grep -rn "b2helix" src/ tests/ examples/ docs/`
Expected: only the definition in `src/afplotter/histogramplot.py` (no callers).

- [ ] **Step 2: Remove `b2helix` and the `seaborn` import from `histogramplot.py`**

Remove this import line:

```python
import seaborn as sns  # type: ignore
```

Remove this method:

```python
    @staticmethod
    def b2helix(n: int) -> list:
        rgb_colors = sns.cubehelix_palette(
            n, start=1.5, rot=1.5, dark=0.3, light=0.8, reverse=True
        )
        hex_colors = [to_hex(rgb) for rgb in rgb_colors]
        return hex_colors
```

(`to_hex` is still used by `plot_stacked`'s statistical-uncertainty band via `matplotlib.colors`; check remaining usages with `grep -n "to_hex" src/afplotter/histogramplot.py` — if this import becomes unused after removal, drop `from matplotlib.colors import to_hex` too.)

- [ ] **Step 3: Remove `seaborn` from `pyproject.toml`**

In `pyproject.toml`'s dependencies list, remove the line:

```
    "seaborn",
```

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: PASS.

- [ ] **Step 5: Re-sync the environment and verify seaborn is no longer installed as a dependency of afplotter**

Run: `uv sync --extra dev`
Run: `uv run python -c "import afplotter"`
Expected: succeeds (afplotter itself never imported seaborn beyond the removed line).

- [ ] **Step 6: Commit**

```bash
git add src/afplotter/histogramplot.py pyproject.toml uv.lock
git commit -m "Drop dead b2helix method and the seaborn dependency"
```

---

### Task 4: Per-entry color fill-in for `plot_stacked`/`plot_step`

**Files:**
- Modify: `src/afplotter/histogramplot.py`
- Modify: `tests/test_histogramplot.py`
- Modify: `examples/histogram_with_pull.py` (stale comment)

**Interfaces:**
- Consumes: `afplotter.palettes.get_palette()` (Task 1); `HistogramPlot.std_colors(n: int) -> list[str]` (existing).
- Produces: `HistogramPlot._fill_missing_colors(colors: list[str | None]) -> list[str]` (static method) — used by `plot_stacked`, `plot_step`.

- [ ] **Step 1: Write a failing test for per-entry fill-in on `plot_stacked`**

In `tests/test_histogramplot.py`, add:

```python
def test_stacked_backfills_only_missing_entry_colors():
    hist = _uncolored_histogram(n_entries=0)
    hist.add_entry(HistogramEntry(name="bkg0", latex_name="B0", array=np.random.default_rng(1).uniform(0, 10, 400), color="#00ff00"))
    hist.add_entry(HistogramEntry(name="bkg1", latex_name="B1", array=np.random.default_rng(2).uniform(0, 10, 400)))
    colors = _rendered_colors(hist)
    assert colors["B0"][0] == "#00ff00"
    assert colors["B1"][0] == PETROFF_PALETTE.background[1]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_histogramplot.py::test_stacked_backfills_only_missing_entry_colors -v`
Expected: FAIL — currently `plot_stacked` discards `B0`'s explicit `"#00ff00"` and assigns `PETROFF_PALETTE.background[0]` to it instead, because the all-or-nothing guard triggers as soon as any entry (`B1`) lacks a color.

- [ ] **Step 3: Add `_fill_missing_colors` and use it in `plot_stacked`**

In `src/afplotter/histogramplot.py`, add a new static method next to `std_colors`:

```python
    @staticmethod
    def _fill_missing_colors(colors: list[str | None]) -> list[str]:
        cycle = HistogramPlot.std_colors(len(colors))
        return [color if color is not None else cycle[i] for i, color in enumerate(colors)]
```

Change `plot_stacked`'s color resolution from:

```python
    def plot_stacked(self) -> None:
        colors = self.histogram.get_colors()
        if not all((color is not None) for color in colors):
            colors = self.std_colors(len(self.histogram.entries))
```

to:

```python
    def plot_stacked(self) -> None:
        colors = self._fill_missing_colors(self.histogram.get_colors())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_histogramplot.py::test_stacked_backfills_only_missing_entry_colors -v`
Expected: PASS.

- [ ] **Step 5: Write a failing test for per-entry fill-in on `plot_step`, including hatches**

In `tests/test_histogramplot.py`, add:

```python
def _rendered_step_colors_and_hatches(hist: Histogram) -> dict[str, tuple[str, str | None]]:
    histplot = HistogramPlot(hist)
    histplot.stacked = False
    plotter = HistogramPlotter(histplot, HistogramVariable("$M$", "GeV"))
    ax, _ = plotter.plot(save=False)
    result = {
        patch.get_label(): (to_hex(patch.get_edgecolor()), patch.get_hatch())
        for patch in ax.patches
    }
    plt.close(ax.figure)
    return result


def test_step_backfills_only_missing_entry_colors_and_keeps_hatches():
    hist = _uncolored_histogram(n_entries=0)
    hist.add_entry(
        HistogramEntry(
            name="bkg0", latex_name="B0", array=np.random.default_rng(1).uniform(0, 10, 400),
            color="#00ff00", hatch="///",
        )
    )
    hist.add_entry(
        HistogramEntry(name="bkg1", latex_name="B1", array=np.random.default_rng(2).uniform(0, 10, 400))
    )
    result = _rendered_step_colors_and_hatches(hist)
    assert result["B0"] == ("#00ff00", "///")
    assert result["B1"][0] == PETROFF_PALETTE.background[1]
```

- [ ] **Step 6: Run it to verify it fails**

Run: `uv run pytest tests/test_histogramplot.py::test_step_backfills_only_missing_entry_colors_and_keeps_hatches -v`
Expected: FAIL — currently `plot_step` discards `B0`'s explicit color and hatch entirely, falling back to `std_colors` for both entries with no hatches, because `B1` lacks a color.

- [ ] **Step 7: Simplify `plot_step`'s non-`sig_extra` branch to always fill in and always keep hatches**

Change:

```python
        if not sig_extra:
            centers = self.histogram.get_bin_centers()
            weights = self.histogram.get_bin_counts()
            errors = self.histogram.get_bin_errors()
            labels = self.histogram.get_latex_names()
            if any(color is None for color in self.histogram.get_colors()):
                colors = self.std_colors(len(self.histogram.entries))
                hatches = [None] * len(self.histogram.entries)
            else:
                colors = self.histogram.get_colors()
                hatches = self.histogram.get_hatches()
```

to:

```python
        if not sig_extra:
            centers = self.histogram.get_bin_centers()
            weights = self.histogram.get_bin_counts()
            errors = self.histogram.get_bin_errors()
            labels = self.histogram.get_latex_names()
            colors = self._fill_missing_colors(self.histogram.get_colors())
            hatches = self.histogram.get_hatches()
```

- [ ] **Step 8: Simplify the `sig_extra` multi-signal branch the same way**

Task 1, Step 6 already replaced `SIGNAL_COLOR` with `get_palette().signal` in the lone-signal
`else` branch below, so the code at this point reads:

```python
            if len(self.histogram.signal) != 1:
                if any(color is None for color in self.histogram.get_signal_colors()):
                    colors = self.std_colors(len(self.histogram.signal))
                else:
                    colors = self.histogram.get_signal_colors()

            else:
                # A lone signal component is always drawn in the reserved signal
                # colour, overriding any explicitly set HistogramEntry.color.
                colors = [get_palette().signal]
```

Change the multi-signal `if` branch only, to:

```python
            if len(self.histogram.signal) != 1:
                colors = self._fill_missing_colors(self.histogram.get_signal_colors())
            else:
                # A lone signal component is always drawn in the reserved signal
                # colour, overriding any explicitly set HistogramEntry.color.
                colors = [get_palette().signal]
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `uv run pytest tests/test_histogramplot.py -v`
Expected: PASS — including the two new tests and all pre-existing color/signal tests from Task 1.

- [ ] **Step 10: Update the now-stale comment in `examples/histogram_with_pull.py`**

Change:

```python
    # Colors are all-or-nothing per stack: set every entry or none of them (in
    # which case the Petroff cycle supplies them in order).
```

to:

```python
    # Any entry without an explicit color is backfilled from the active cycle;
    # entries that do set one (like these) keep it.
```

- [ ] **Step 11: Run the full test suite and the example**

Run: `uv run pytest tests/ -v`
Expected: PASS.

Run: `uv run python examples/histogram_with_pull.py`
Expected: exits 0.

- [ ] **Step 12: Commit**

```bash
git add src/afplotter/histogramplot.py tests/test_histogramplot.py examples/histogram_with_pull.py
git commit -m "Backfill only missing HistogramEntry colors instead of discarding all of them"
```

---

### Task 5: Documentation updates

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/histograms.md`
- Modify: `.claude/skills/afplotter/SKILL.md`

**Interfaces:**
- Consumes: nothing (docs only — no code interfaces).

- [ ] **Step 1: Update `CLAUDE.md`'s decisions table and open follow-ups**

In `CLAUDE.md`, find the follow-up bullet list under "Open follow-ups" (the one added by PR #10 mentioning `Experiment.colors`/`labels["status"]`, the all-or-nothing entry colors, and `b2helix`). Remove the two now-resolved bullets:

```
- **Entry colors are all-or-nothing.** `plot_stacked` and `plot_step` both discard *every*
  user-set `HistogramEntry.color` if *any* entry lacks one, and fall back to the whole cycle
  (`histogramplot.py`, the `if not all((color is not None) ...)` guards). `plot_step` also
  drops the hatches on that path. A per-entry "fill in only the missing ones" path would be
  the right fix.
- `HistogramPlot.b2helix` (seaborn cubehelix) is no longer called by anything — it is the only
  reason `seaborn` is a runtime dependency. Drop both together if nobody is using it.
```

Add a row to the decisions table (after the Petroff row from PR #10):

```
| Palettes are switchable (`set_palette`) | `KITColors` and `LMUColors` are separate classes now (previously mixed in one). `afplotter.palettes.Palette` pairs a background cycle with its own reserved signal color; `set_palette("KIT"\|"LMU"\|"Petroff")` mirrors `set_experiment(...)`. Default stays Petroff. Register a custom palette via `afplotter.palettes.register_palette(...)`. |
```

- [ ] **Step 2: Update `README.md`**

Change:

```
Colors come from the [Petroff 10](https://arxiv.org/abs/2107.02270) sequence by default,
with its red held out of the cycle and reserved for signal components — see
[Histograms → Colours](docs/histograms.md#colours).
```

to:

```
Colors come from the [Petroff 10](https://arxiv.org/abs/2107.02270) sequence by default,
with its red held out of the cycle and reserved for signal components. Switch to KIT or LMU
colors (or register your own) with `set_palette(...)` — see
[Histograms → Colours](docs/histograms.md#colours).
```

- [ ] **Step 3: Update `docs/histograms.md`'s Colours section**

Replace the whole `## Colours` section:

```
## Colours

The default colour cycle is the **Petroff 10** sequence
([arXiv:2107.02270](https://arxiv.org/abs/2107.02270)), minus its red — nine colours,
exposed as `PetroffColors.default_colors` and installed as `axes.prop_cycle`. Entries
that do not set `color=` take colours from it in order, the same way for stacked and
step plots.

The held-out red `#bd1f01` is `SIGNAL_COLOR` (`PetroffColors.signal_red`). Because it
is not in the cycle, no background component can ever be drawn in it.

An entry with `type="signal"` is routed into `Histogram.signal` and drawn as an
outlined step overlay when `HistogramPlot.sig_extra = True`:

```python
from afplotter import Histogram, HistogramEntry, HistogramPlot, SIGNAL_COLOR

hist.add_entry(HistogramEntry(name="signal", latex_name="Signal", array=sig_array, type="signal"))

histplot = HistogramPlot(hist)
histplot.stacked = True    # `entries` form the stack
histplot.sig_extra = True  # `signal` is overlaid on top, in SIGNAL_COLOR
```

Caveats worth knowing:

- When there is exactly **one** signal component it is always `SIGNAL_COLOR`; an
  explicit `color=` on that entry is ignored.
- When there are **several** signal components they fall back to the ordinary cycle,
  or to their explicit `color=` values if all of them set one.
- `KITColors` is still exported and unchanged — it is just no longer the default.
```

with:

```
## Colours

The default colour cycle is the **Petroff 10** sequence
([arXiv:2107.02270](https://arxiv.org/abs/2107.02270)), minus its red — nine colours,
exposed as `PETROFF_PALETTE.background` and installed as `axes.prop_cycle`. Entries
that do not set `color=` take colours from it in order, the same way for stacked and
step plots. Entries that *do* set `color=` keep it — only the missing ones are backfilled.

Switch palettes with `set_palette(name)`, mirroring `set_experiment(...)`:

```python
from afplotter import set_palette

set_palette("KIT")   # or "LMU", or "Petroff" (the default)
```

Each built-in palette (`Petroff`, `KIT`, `LMU`) holds its own red out of its own
background cycle and reserves it exclusively for signal — so switching palettes never
reintroduces a background/signal colour clash. Register a custom palette with
`afplotter.palettes.register_palette(Palette(name=..., background=[...], signal=...))`.

An entry with `type="signal"` is routed into `Histogram.signal` and drawn as an
outlined step overlay when `HistogramPlot.sig_extra = True`:

```python
from afplotter import Histogram, HistogramEntry, HistogramPlot, get_palette

hist.add_entry(HistogramEntry(name="signal", latex_name="Signal", array=sig_array, type="signal"))

histplot = HistogramPlot(hist)
histplot.stacked = True    # `entries` form the stack
histplot.sig_extra = True  # `signal` is overlaid on top, in get_palette().signal
```

Caveats worth knowing:

- When there is exactly **one** signal component it is always drawn in the active
  palette's reserved signal colour; an explicit `color=` on that entry is ignored.
- When there are **several** signal components, each one keeps its explicit `color=`
  if it has one, and is backfilled from the ordinary cycle otherwise.
- `KITColors` and `LMUColors` are still exported and unchanged — they are just not
  the default; use them directly for one-off colours, or via `KIT_PALETTE`/`LMU_PALETTE`
  through `set_palette(...)`.
```

- [ ] **Step 4: Update `.claude/skills/afplotter/SKILL.md`'s Colors bullet**

Change:

```
- Colors: the default cycle is Petroff 10 minus its red — `PetroffColors`
  (imported from `afplotter`). Leave `color=` unset on `HistogramEntry` and the
  cycle supplies it. The held-out red is `SIGNAL_COLOR` (`#bd1f01`), used
  automatically for entries with `type="signal"`; never hand that red to a
  background component. `KITColors` (`kit_green`, `kit_blue`, `kit_red`, …,
  plus an `lmu_*` set) is still exported for explicit one-off colors.
```

to:

```
- Colors: the default cycle is Petroff 10 minus its red — `PETROFF_PALETTE`
  (imported from `afplotter.palettes`). Leave `color=` unset on `HistogramEntry`
  and the cycle supplies it; entries that do set one keep it. The held-out red
  is `get_palette().signal`, used automatically for entries with `type="signal"`;
  never hand that red to a background component. Switch the whole cycle with
  `set_palette("KIT" | "LMU" | "Petroff")`. `KITColors` (`kit_green`, `kit_blue`,
  `kit_red`, …) and `LMUColors` (`lmu_green`, `lmu_blue`, …) are still exported
  separately for explicit one-off colors.
```

- [ ] **Step 5: Run the full test suite one more time**

Run: `uv run pytest tests/ -v`
Expected: PASS.

- [ ] **Step 6: Run `ruff` and `mypy`**

Run: `uv run ruff check . && uv run ruff format --check .`
Run: `uv run mypy src/`
Expected: no new errors beyond what already existed on `feature/petroff-colors` before this plan (per PR #10's verification notes: 1 pre-existing lint error, 6 pre-existing `convenience.py` mypy errors).

- [ ] **Step 7: Commit**

```bash
git add CLAUDE.md README.md docs/histograms.md .claude/skills/afplotter/SKILL.md
git commit -m "Document palette switching and the KITColors/LMUColors split"
```
