# AFPlotter — Development Guide

A matplotlib-based plotting library for HEP analyses: histograms (stacked/step/pull/ratio),
2D histograms, composed "generic" plots, Polars-based lazy histogramming, and a
query-string selection parser. Built-in experiment styles (Belle II / Generic).

This file orients contributors and AI agents working in this repo. User-facing docs are in
`README.md` and `docs/`.

## Development workflow (required for AI agents)

This repo is developed AI-first: any non-trivial change (a new feature, a bugfix with more
than a one-line fix, a refactor, anything touching more than one file for a reason beyond
a mechanical rename) MUST go through the
[Superpowers](https://github.com/obra/superpowers) skill pipeline, in order:

1. **`superpowers:brainstorming`** — turn the request into a design, get it approved, write
   it to `docs/superpowers/specs/`.
2. **`superpowers:writing-plans`** — turn the approved design into a bite-sized, TDD-structured
   implementation plan, written to `docs/superpowers/plans/`.
3. **`superpowers:subagent-driven-development`** — execute the plan with a fresh implementer
   subagent per task, a task-scoped reviewer after each, and a final whole-branch review
   before merge.

**Exception**: trivial changes (typo fixes, doc-only corrections, a single-line mechanical
fix already fully specified by whoever asked for it) can be made directly — don't invoke the
full pipeline for those. When in doubt, use it; the pipeline overhead on a small task is much
cheaper than an unreviewed regression.

Concrete precedent: the `palettes.py`/`set_palette` work (PR #10) and the `pr-check` /
`verify-examples` skills (PR #12) were both built this way — see their commit history and
`docs/superpowers/{specs,plans}/` for the artifacts this pipeline produces.

Both artifacts are named `YYYY-MM-DD-<slug>.md`, with the plan reusing its spec's slug
(`2026-07-29-palette-switching-design.md` → `2026-07-29-palette-switching.md`).

### Run `/init` when starting fresh

At the start of a new session in this repo — before substantive work — run Claude Code's
`/init`. On a repo that already has a `CLAUDE.md` it doesn't overwrite anything; it
re-derives the guide from the code and reports where the two have diverged.

This matters more here than in most repos. This file is the single source of truth for
architecture, conventions, and testing philosophy, it is written largely by agents, and
nothing mechanically checks it against the code. It drifts silently: a `/init` pass found
a stale test count, a Status section describing a branch merged long ago, a documented
CI guarantee that was the *opposite* of what a contributor observes locally, and a
`.claude/skills/` skill justifying itself with technical debt that no longer existed.
None of that is visible from reading the code, and none of it fails a test.

Treat what `/init` reports as a finding to act on, not a formality — fixing drift is a
doc-only correction and falls under the exception above.

## Setup

```bash
uv sync --extra dev

uv run pytest tests/ -v                                  # full suite
uv run pytest tests/test_histogramplot.py -v             # one file
uv run pytest tests/test_baseplotter.py::test_default_properties -v   # one test
uv run pytest -k "palette" -v                            # by name substring

uv run python examples/histogram_with_pull.py            # examples are run, not inspected
```

`pre-commit run --all-files` runs ruff (lint + format) and mypy; CI runs the same three
checks, pinned to the same versions, alongside the test suite. Keep the two files in sync
— a version bump in `pyproject.toml`'s `dev` extra needs the matching `rev:` bump in
`.pre-commit-config.yaml`.

CI installs with `uv sync --locked`, so a dependency change in `pyproject.toml` without a
regenerated committed `uv.lock` fails CI before a single test runs.

**Expect local mypy to be red even on a clean tree.** CI pins `--python 3.10`; a local
`uv sync` picks whatever interpreter satisfies `>=3.10`, and because `uv.lock` carries
resolution markers, a newer interpreter legitimately resolves *newer* matplotlib/numpy.
The pinned `mypy==1.10.1` (June 2024) predates numpy 2.5's stubs and cannot resolve them,
so it reports ~11 errors — mostly `_HistogramResult?`/`NDArray?` false positives, where
the `?` is mypy's own unresolved-type marker — while CI stays green on the 3.10 set.
`ruff` is unaffected (pinned standalone binary, identical on both sets), and pytest passes
on both. Diff against the merge-base rather than reading raw counts; the `pr-check` skill
does this. A fix is in flight — see Status below.

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
| Signal is a stack layer, not just an overlay | `type="signal"` entries used to be drawn *only* as a `sig_extra` outline peak-matched to the background stack — never part of the stack, and excluded from every total. A stacked plot therefore could not show S+B at all. Now `plot_stacked` appends `Histogram.signal` after `Histogram.entries`, so signal always closes the stack on top in `get_palette().signal` at its true yield, and `get_total_bin_count`/`get_total_bin_errors` are S+B — which is what the `Stat. unc.` band and `add_pull` consume. `sig_extra` now means the opposite: it *excludes* signal from the stack entirely (bars, legend, uncertainty band all fall back to background-only), leaving the peak-matched outline as signal's sole representation — otherwise it would be both stacked and outlined, drawn and legended twice. |

## Conventions

- **Python 3.10+ typing**: native `X | Y` unions and builtin generics (`list[X]`, `dict[K, V]`,
  `tuple[X, Y]`) — no `typing.Optional`/`List`/`Dict`/`Tuple`/`Union` imports.
- A local green run doesn't guarantee CI will match, and a local red mypy doesn't mean the
  branch is broken — the interpreter and resolved dependency set differ. See Setup above;
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
- **`examples/workflow_demo.py` must stay deterministic, or `main` starts committing to itself.**
  `.github/workflows/update-workflow-images.yml` runs it on every push to `main` and commits
  any diff under `docs/img/workflow/` back to the branch. It stays quiet only because the
  script is fully reproducible (seeded RNG, no wall-clock, no timestamps) and because
  `[skip ci]` on the bot commit suppresses the re-trigger. Anything that makes its rendered
  output vary run-to-run — in the script itself or in the plotting code it exercises — turns
  that into a bot commit on every push. It is also the only example whose PNGs are committed
  (the README embeds them); the rest write to gitignored `examples/output/`.
- **Text-block rows are positioned from bboxes measured before layout settles.** `_add_text_to_plot` measures
  and positions the watermark/luminosity/`add_text()` rows before `_add_axislabels`/`_add_legend` run, and
  `figure.autolayout` can still shrink the axes box afterward — at very large `text_size` on a small `figsize`
  this can eat into the small cushion between rows. Harmless at normal figsizes; if you hit it, increase
  `figsize` or reduce `text_size`.

## Testing philosophy

Assertions must be **falsifiable** — they should fail if the behavior breaks. Repeatedly during
development, tests slipped through that couldn't distinguish pass from fail: `len(x) >= 0`
(always true), `assert x is not None` on a method that can't return `None`, or checking a line
count when both the correct and incorrect code paths produce one line. When adding a test, ask:
*what specific bug would make this fail?* If there isn't a clear answer, strengthen it — assert
on rendered data (`ax.lines[0].get_ydata()`), artist counts by type (`ax.containers` for
`errorbar`, `ax.patches` for `hist`), or computed values.

Examples in `examples/` are verified by **running them**, not by inspection — they must exit 0
and write a PNG to `examples/output/` (gitignored; `workflow_demo.py` is the exception, see
Gotchas). `examples/README.md`'s bullet list is the source of truth for which files are
runnable examples — the directory also holds helpers like `_synthetic_data.py` that are
imported, not run. The `verify-examples` skill automates this.

## Status

116 tests → **137** as of the palette/watermark/workflow-demo work; suite is green, `ruff check`
is clean, and CI (Python 3.10) is green on `main`.

In flight on `feature/ci-python-version-matrix` (issue #21): CI currently exercises only Python
3.10, so the newer dependency set a current interpreter resolves has never been tested. The design
(`docs/superpowers/specs/2026-08-03-ci-python-version-matrix-design.md`, on that branch) adds a
3.10/3.14 matrix,
bumps `mypy` 1.10.1 → 2.3.0, pins `.python-version` to 3.10, and fixes three real type defects —
two of which are latent on *both* dependency sets and invisible only because the pinned mypy is
too old to see them.

Open follow-ups:

- `Experiment.colors` and `labels["status"]` are defined but never read (only `labels["experiment"]`
  is wired, into the watermark name text). Their values now at least agree with `PetroffColors`,
  but nothing consumes them — signal red is deliberately experiment-independent.
- Only `BelleII` (real, Alex's own style) and `Generic` (neutral matplotlib-defaults fallback) ship
  built in. Register your own via `afplotter.experiments.registry.register(...)` rather than adding
  more built-ins for experiments this repo's maintainer isn't part of.
- A few tests in `tests/test_histogramplot.py` assert only "didn't crash" — see the testing
  philosophy above.
