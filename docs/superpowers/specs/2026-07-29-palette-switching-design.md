# Palette switching and color-class cleanup

## Context

PR #10 consolidated four uncoordinated color sources into one Petroff-10-based
cycle and reserved its red for signal. It left three follow-ups, noted in
`CLAUDE.md`:

- `KITColors` mixes `kit_*` hexes, `lmu_*` hexes, and neutral greys in one class.
- There is no supported way to switch the active color cycle — a user wanting
  KIT or LMU colors instead of Petroff has no equivalent of `set_experiment(...)`.
- `plot_stacked`/`plot_step` discard *every* user-set `HistogramEntry.color` if
  even one entry lacks one (all-or-nothing fallback to the cycle).
- `HistogramPlot.b2helix` (seaborn cubehelix) is dead code and the only reason
  `seaborn` is a runtime dependency.

This design addresses all four together, since the palette-switching work
touches the same color-handling code paths as the other three.

## 1. Color storage classes

Split the current mixed `KITColors` (in `src/afplotter/baseplotter.py`):

- **`KITColors`** — unchanged except `lmu_*` constants removed. Keeps `kit_*`
  hexes plus the neutral greys/black/white (nothing in the codebase currently
  reads the greys; they stay as user-facing convenience constants).
- **`LMUColors`** (new, same file) — the six `lmu_*` hexes, same plain-namespace
  style as `KITColors`.
- **`PetroffColors`** — unchanged.

None of the three classes build cycles or reserve a signal color themselves —
that responsibility moves to `Palette` (below). The current module-level
`kit_color_cycler`, `petroff_color_cycler`, and `KITColors.default_colors` /
`PetroffColors.default_colors` are removed; palettes are the single source of
truth for cycles going forward.

## 2. Palette abstraction and switching API

A new frozen dataclass in `baseplotter.py`:

```python
@dataclass(frozen=True)
class Palette:
    name: str
    background: list[str]   # cycle colors; signal color already excluded
    signal: str              # reserved; never appears in background
```

Three built-in instances, each holding its own red out of its own background
cycle (generalizing the KIT/signal-clash fix PR #10 made for Petroff):

```python
PETROFF_PALETTE = Palette(
    "Petroff",
    background=[
        PetroffColors.blue, PetroffColors.amber, PetroffColors.grey_green,
        PetroffColors.purple, PetroffColors.brown, PetroffColors.orange,
        PetroffColors.khaki, PetroffColors.slate, PetroffColors.pale_cyan,
    ],
    signal=PetroffColors.red,
)
KIT_PALETTE = Palette(
    "KIT",
    background=[
        KITColors.kit_green, KITColors.kit_blue, KITColors.kit_cyan,
        KITColors.kit_orange, KITColors.kit_maygreen, KITColors.kit_yellow,
        KITColors.kit_purple, KITColors.kit_brown, KITColors.dark_grey,
    ],
    signal=KITColors.kit_red,
)
LMU_PALETTE = Palette(
    "LMU",
    background=[
        LMUColors.lmu_green, LMUColors.lmu_blue, LMUColors.lmu_cyan,
        LMUColors.lmu_violet, LMUColors.lmu_orange,
    ],
    signal=LMUColors.lmu_red,
)
```

(KIT background/order preserves PR #10's pre-existing `KITColors.default_colors`
ordering with `kit_red` removed; LMU background is the remaining five `lmu_*`
constants in declaration order.)

A new module `src/afplotter/palettes.py`, mirroring the existing
`experiments/registry.py` + `experiments/context.py` pattern:

```python
def register_palette(palette: Palette) -> None: ...   # raises on duplicate name, like experiments.registry.register
def get(name: str) -> Palette: ...                      # lookup by name, like experiments.registry.get
def set_palette(name: str = "Petroff") -> Palette: ...  # sets current palette, re-applies rcParams; defaults to Petroff
def get_palette() -> Palette: ...                        # current palette; defaults to Petroff if never set
```

`PETROFF_PALETTE` is the default: `get_palette()` returns it when no palette has
been explicitly set, and `set_palette()` with no argument selects it — matching
how `set_experiment(None)` already defaults to `"Generic"`.

`set_matplotlibrc_params()` (in `baseplotter.py`) reads `get_palette().background`
for `axes.prop_cycle` instead of the hardcoded `petroff_color_cycler`. This
keeps it the single source of truth regardless of call order, and makes
`set_palette()` live: calling it re-applies rcParams immediately, and any
`BasePlotter` constructed afterward (which calls `set_matplotlibrc_params()` in
`__init__`) picks up the new cycle — the same behavior `set_experiment()`
already has.

Signal color lookup changes from the fixed module constant `SIGNAL_COLOR` to
`get_palette().signal`, read dynamically wherever `histogramplot.py` currently
uses `SIGNAL_COLOR`. The `SIGNAL_COLOR` module-level constant is removed.

Both bundled `.mplstyle` files (`belle2_modern.mplstyle`, `generic.mplstyle`)
drop their hardcoded `axes.prop_cycle` line — that hardcoding is exactly the
"another source of truth" duplication PR #10 was fixing, and it would leave a
direct `plt.style.use(...)` user's cycle un-switchable. Their comment about
"Petroff 10 ... reserved for signal" is replaced with a note that the cycle is
supplied by `afplotter.set_palette(...)` at runtime.

Users can register a custom palette the same way they register a custom
experiment: `afplotter.palettes.register_palette(Palette(...))`.

## 3. Follow-up fixes

**Per-entry color fill-in** (`histogramplot.py`, `plot_stacked` and
`plot_step`): replace the current all-or-nothing guards —

```python
if not all((color is not None) for color in colors):
    colors = self.std_colors(len(self.histogram.entries))
```

— with logic that backfills only the entries whose `color` is `None` from the
active cycle, preserving any explicitly-set `HistogramEntry.color` values.
`plot_step` no longer needs to drop hatches on this path, since hatches don't
need resetting just because one color was missing.

**Drop `b2helix`/seaborn**: remove `HistogramPlot.b2helix`, the `seaborn`
import in `histogramplot.py`, and the `seaborn` runtime dependency from
`pyproject.toml`. Nothing calls it after PR #10 switched `plot_stacked` to
`std_colors`.

## 4. Testing

- `LMUColors` constants (moved from `KITColors`).
- `Palette`, `register_palette`, `set_palette`, `get_palette` — mirroring the
  existing experiment-context tests (`tests/test_experiments.py` or wherever
  those live).
- `set_palette("KIT")` excludes `kit_red` from `axes.prop_cycle` and reserves
  it as signal — parallel to the existing Petroff assertions in
  `tests/test_baseplotter.py`.
- `get_palette()` / `set_matplotlibrc_params()` default to Petroff when no
  palette has been set.
- Per-entry color fill-in: an entry with `color=None` gets backfilled from the
  cycle while other entries keep their explicit colors, on both `plot_stacked`
  and `plot_step`.
- Remove/adjust any test exercising `b2helix`.
- All assertions on rendered hex colors (`to_hex(...)`) or artist properties,
  per this repo's testing philosophy in `CLAUDE.md` — not "didn't crash."

## 5. Docs

Update wherever `KITColors`, the Petroff cycle, or `SIGNAL_COLOR` are currently
described: `CLAUDE.md` (decisions table + gotchas — including marking the two
follow-ups as resolved), `README.md`, `docs/histograms.md`, and
`.claude/skills/afplotter/SKILL.md`. Document `set_palette(...)`, the three
built-in palettes, and how to register a custom one, following the same
pattern already used to document `set_experiment(...)`.

## Out of scope

- Wiring `Experiment.colors` to anything — still unread, still deliberately
  independent of the active palette (an experiment's style is about fonts/tick
  geometry; palette is a separate, orthogonal choice per this design).
- `ruff-format` drift on `main` noted in PR #10 — unrelated, tracked separately.
