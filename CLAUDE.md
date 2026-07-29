# AFPlotter — Development Guide

A matplotlib-based plotting library for HEP analyses: histograms (stacked/step/pull/ratio),
2D histograms, composed "generic" plots, Polars-based lazy histogramming, and a
query-string selection parser. Built-in experiment styles (Belle II / Generic).

This file orients contributors and AI agents working in this repo. User-facing docs are in
`README.md` and `docs/`.

## Setup

```bash
uv sync --extra dev
uv run pytest tests/ -v   # full suite
```

`pre-commit run --all-files` runs ruff (lint + format) and mypy.

## Architecture

Three layers. Pick the lowest one that does the job.

| Layer | Entry points | Use for |
|---|---|---|
| **Convenience** (`convenience.py`) | `plot_histogram`, `plot_histogram_from_files`, `plot_2d_histogram` | One-call ad-hoc plots of a single variable |
| **Engine** | `HistogramPlotter`, `Histogram2DPlotter`, `GenericPlotter` | Real analysis plots — fit overlays, pull panels, exclusion bands, insets |
| **Data model** | `Histogram`/`HistogramEntry`, `LazyHistWrapper`/`LazyHistEntry`, `SelectionParser`/`SelectionOperator` | Building/filtering histogram inputs |

```
src/afplotter/
  baseplotter.py       BasePlotter (styling, legend, watermark, axis limits)
  palettes.py          KITColors/LMUColors/PetroffColors, Palette, palette registry + context (set_palette/get_palette)
  genericplot.py       GenericPlot, InsetPlot, GenericPlotter
  histogramplot.py     HistogramPlot, Histogram2DPlot, HistogramPlotter, Histogram2DPlotter
  convenience.py       high-level one-call functions
  experiments/         Experiment registry + bundled .mplstyle files
  selectionparser/     AST-based query-string -> Polars expression
  utilities/           Histogram data model, Polars lazy histogram builder
```

**Composed plots are multi-call by design.** Real analysis plots (exclusion limits, coupling
limits) chain `add_generic_plot(...)` / `add_generic_text(...)` / `add_inset(...)` on a
`GenericPlotter`. There is deliberately no one-shot `plot_generic()` — see decisions below.

## Key decisions

| Decision | Rationale |
|---|---|
| Experiment registry over one hardcoded style | The library used to `plt.style.use($ALPS_PATH/...)` **at import time**, so `import afplotter` crashed for anyone without that env var. Styles are now bundled package data, selected explicitly via `set_experiment("BelleII")`, applied lazily on first plotter construction. |
| Convenience layer *added*, engine internals *untouched* | Real usage (fit plots, limit plots) drives the engine classes directly and needs their full surface. The convenience functions serve the "just histogram this column" case without constraining the engine. |
| No one-shot `plot_generic()` | Composed plots are inherently multi-call compositions; a single-call wrapper would either be trivially thin or hide the API users actually need. |
| `add_inset` via `mpl_toolkits.axes_grid1.inset_locator` | Ported verbatim from production analysis code (percentage-string sizing, `loc`/`bbox_to_anchor`, `mark_inset` connectors) rather than reimplemented on `Axes.inset_axes`, so existing analysis scripts port over unchanged. |
| `InsetPlot` shared by both plotters via duck typing | Both `GenericPlot` and `HistogramPlot` already expose a settable `.ax` + no-arg `.plot()`. A shared base class would have been premature abstraction. |
| Selections take an explicit path | Was `$ALPS_PATH/configs/selections/<name>`; now `SelectionOperator(lf, selections_path=...)` or an inline dict. Same env-var-independence goal as the style fix. |
| Skill over MCP server | Ships as `.claude/skills/afplotter/SKILL.md` in-repo — no server process to run or configure, and it activates automatically for anyone who clones the repo and uses Claude Code. |
| Install from git, not PyPI | Personal/lab tool; `pip install git+https://github.com/AlexanderHeidelbach/AFPlotter.git`. |
| Petroff 10 as the default cycle, with its red held out | There used to be four uncoordinated palettes: `KITColors` (installed as `axes.prop_cycle`), the ggplot cycler in `belle2_modern.mplstyle` (dead — clobbered by `set_matplotlibrc_params`), seaborn cubehelix (`b2helix`, stacked plots only), and `Experiment.colors` (dead). A stacked and a step plot of the same data looked nothing alike. Now one cycle (`PETROFF_PALETTE.background`, 9 colours) feeds both paths, and `PETROFF_PALETTE.signal = "#bd1f01"` is excluded from it so red always means signal. `KITColors` stays exported, just not default. |
| Palettes are switchable (`set_palette`) | `KITColors` and `LMUColors` are separate classes now (previously mixed in one). `afplotter.palettes.Palette` pairs a background cycle with its own reserved signal color; `set_palette("KIT"\|"LMU"\|"Petroff")` mirrors `set_experiment(...)`. Default stays Petroff. Register a custom palette via `afplotter.palettes.register_palette(...)`. |

## Conventions

- **Python 3.10+ typing**: native `X | Y` unions and builtin generics (`list[X]`, `dict[K, V]`,
  `tuple[X, Y]`) — no `typing.Optional`/`List`/`Dict`/`Tuple`/`Union` imports.
- Local `uv sync` picks whatever interpreter satisfies `>=3.10` (may be newer than 3.10); CI
  pins exactly 3.10 via `--python 3.10`. A local green run doesn't guarantee CI will match —
  check the CI run itself for anything version-sensitive.
- **reST docstrings** (`:param:` / `:return:`) on public functions and classes.
- **No import-time side effects** that touch the filesystem or env vars. `import afplotter` must
  succeed in a bare environment — `tests/test_packaging.py` guards this as a regression test.
- Line length 120 (ruff).
- Tests use the matplotlib `Agg` backend (set in `tests/conftest.py`); `tests/conftest.py` also
  provides the shared `synthetic_histogram` fixture.

## Gotchas learned the hard way

These bit us during development and are easy to repeat:

- **`plot(save=True)` calls `plt.clf()` before returning.** Any assertion about axes content
  after a `save=True` call is meaningless. Check the written file instead, or use `save=False`
  when you need to inspect the returned axes.
- **`add_function`/`add_pull` with `density=True` (the default) compare against raw bin counts.**
  A model function must return an absolute `dN/dx` scaled to the real sample size, not a unit-norm
  PDF, or the overlay is invisible and the pull panel clips off-screen.
- **`bbox_to_anchor` on `add_inset` does not imply the inset fills that box.** `width`/`height`
  are percentages *of the bbox* and still default to `"38%"`. Pass `width="100%", height="100%"`
  alongside `bbox_to_anchor` for precise placement.
- **`SelectionParser` doesn't accept arbitrary Python.** No function calls (`abs(eta) < 2` raises).
  See `docs/selections.md` for the supported grammar and current null/NaN semantics.
- **`figure.autolayout` conflicts with `mpl_toolkits` insets**, producing a `tight_layout`
  warning on save. Harmless but noisy.

## Testing philosophy

Assertions must be **falsifiable** — they should fail if the behavior breaks. Repeatedly during
development, tests slipped through that couldn't distinguish pass from fail: `len(x) >= 0`
(always true), `assert x is not None` on a method that can't return `None`, or checking a line
count when both the correct and incorrect code paths produce one line. When adding a test, ask:
*what specific bug would make this fail?* If there isn't a clear answer, strengthen it — assert
on rendered data (`ax.lines[0].get_ydata()`), artist counts by type (`ax.containers` for
`errorbar`, `ax.patches` for `hist`), or computed values.

Examples in `examples/` are verified by **running them**, not by inspection — they must exit 0
and write a PNG to `examples/output/` (gitignored).

## Status

Standalone-packaging work is complete on `feature/standalone-package-and-skill`: the import-time
crash is fixed, all previously-empty test files have real coverage (116 tests), and README/docs/
examples/skill are in place.

Open follow-ups:

- `Experiment.colors` and `labels["status"]` are defined but never read (only `labels["experiment"]`
  is wired, into the watermark name text). Their values now at least agree with `PetroffColors`,
  but nothing consumes them — signal red is deliberately experiment-independent.
- Only `BelleII` (real, Alex's own style) and `Generic` (neutral matplotlib-defaults fallback) ship
  built in. Register your own via `afplotter.experiments.registry.register(...)` rather than adding
  more built-ins for experiments this repo's maintainer isn't part of.
- `importlib_resources` is declared as a runtime dependency but never imported — drop it.
- A few tests in `tests/test_histogramplot.py` assert only "didn't crash" — see the testing
  philosophy above.
