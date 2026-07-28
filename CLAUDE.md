# AFPlotter — Development Guide

A matplotlib-based plotting library for HEP analyses: histograms (stacked/step/pull/ratio),
2D histograms, composed "generic" plots, Polars-based lazy histogramming, and a
query-string selection parser. Built-in experiment styles (Belle II / IceCube / Generic).

This file orients contributors and AI agents working in this repo. User-facing docs are in
`README.md` and `docs/`.

## Setup

```bash
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v          # full suite
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
  baseplotter.py       BasePlotter (styling, legend, watermark, axis limits), KITColors
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

## Conventions

- **Python 3.8 compatible typing**: `Optional[X]`, `List[X]`, `Dict[K, V]`, `Tuple[X, Y]` from
  `typing`. No bare `X | Y`, no builtin generics.
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
crash is fixed, all previously-empty test files have real coverage (87 tests), and README/docs/
examples/skill are in place.

Open follow-ups:

- Test isolation in `tests/experiments/` mutates module-global registry state without teardown —
  the suite passes in full-suite order but can fail under `pytest -k`, `--last-failed`, or
  parallel runs. Convert to an autouse fixture that cleans up before *and* after.
- `Experiment.colors` / `Experiment.labels` are defined but never read, and the `"Belle II"`
  watermark in `baseplotter.py` is hardcoded regardless of the selected experiment — so
  non-Belle II styles are currently placeholders. Wiring the watermark to
  `get_experiment().labels` would give those fields a purpose.
- `importlib_resources` is declared as a runtime dependency but never imported — drop it.
- `requires-python = ">=3.8"` is untested; modern polars/numpy/matplotlib no longer ship 3.8
  wheels. Either add a low-version CI job or raise the floor to what's actually supported.
- A few tests in `tests/test_histogramplot.py` assert only "didn't crash" — see the testing
  philosophy above.
