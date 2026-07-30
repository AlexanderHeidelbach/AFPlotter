# README Iterative-Workflow Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new runnable example (`examples/workflow_demo.py`) that produces three
committed reference images showing AFPlotter's real usage pattern — three escalating prompts
(convenience layer → engine layer → palette switch) — and narrate that same sequence in the
README with the images embedded.

**Architecture:** One new example script writes three PNGs to a new committed
`docs/img/workflow/` directory (not gitignored, unlike `examples/output/`). The README gets a
new section between Quickstart and Docs that shows the three prompts as blockquotes, each
followed by its image and a one-line note on what changed. `examples/README.md` documents the
new script's non-standard output location, and the `verify-examples` skill is updated to check
that location instead of `examples/output/` for this one script.

**Tech Stack:** Python (afplotter, numpy), Markdown (README, skill file).

## Global Constraints

- Python 3.10+ typing: native `X | Y` unions and builtin generics — no `typing.Optional`/`List`/etc.
- reST docstrings (`:param:`/`:return:`) on public functions and classes.
- Line length 120 (ruff).
- No import-time side effects touching filesystem/env vars (`tests/test_packaging.py` guards this) — not at risk here since this script is only ever run standalone, never imported.
- `text_size=36` for all three plots (paper-ready per `set_matplotlibrc_params`'s own docstring default).
- Do **not** set `luminosity_value` on the `HistogramPlotter` in steps 2/3 — there is a known, unfixed watermark/luminosity overlap bug at large `text_size` (`docs/superpowers/specs/2026-07-30-watermark-text-spacing-design.md`); omitting `luminosity_value` sidesteps it. Fixing that bug is out of scope.
- Reuse `examples/_synthetic_data.py`'s `make_signal_background` — don't duplicate synthetic-data generation.
- `examples/README.md` is the source of truth `verify-examples` reads to know which `.py` files are runnable examples — any new example script must be listed there.

---

### Task 1: `examples/workflow_demo.py` + `examples/README.md` entry

**Files:**
- Create: `examples/workflow_demo.py`
- Modify: `examples/README.md`

**Interfaces:**
- Consumes: `examples._synthetic_data.make_signal_background(n_signal, n_background, seed) -> dict[str, np.ndarray]` (existing, `examples/_synthetic_data.py`); `afplotter.plot_histogram`, `afplotter.set_experiment`, `afplotter.set_palette`, `afplotter.get_palette`, `afplotter.Histogram`, `afplotter.HistogramEntry`, `afplotter.HistogramPlot`, `afplotter.HistogramPlotter`, `afplotter.HistogramVariable`, `afplotter.PetroffColors` (existing package API, already used by `examples/histogram_with_pull.py`); `afplotter.baseplotter.set_matplotlibrc_params` (module-level function, not re-exported from the package `__init__`, imported via its submodule path).
- Produces: `docs/img/workflow/01-histogram.png`, `docs/img/workflow/02-stacked-pull.png`, `docs/img/workflow/03-kit-colors.png` — filenames the README task (Task 3) embeds directly.

- [ ] **Step 1: Write `examples/workflow_demo.py`**

```python
# examples/workflow_demo.py
"""
Three-step version of the actual AFPlotter workflow: a user asks for a plot,
then asks for changes across follow-up turns. Mirrors the escalation path in
.claude/skills/afplotter/SKILL.md -- convenience layer first, engine once the
request needs a pull panel, then a palette switch.

Writes its output to docs/img/workflow/ (committed, unlike examples/output/)
since these images are embedded in the README.

Run: python examples/workflow_demo.py
"""

import os

import numpy as np

from afplotter import (
    Histogram,
    HistogramEntry,
    HistogramPlot,
    HistogramPlotter,
    HistogramVariable,
    PetroffColors,
    get_palette,
    plot_histogram,
    set_experiment,
    set_palette,
)
from afplotter.baseplotter import set_matplotlibrc_params
from _synthetic_data import make_signal_background

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(REPO_ROOT, "docs", "img", "workflow")

N_SIGNAL, N_BACKGROUND = 600, 1200
X_MIN, X_MAX = 0.0, 10.0


def step1_convenience(data: dict[str, np.ndarray]) -> None:
    """Prompt: "Plot signal vs background for pt" -- convenience layer."""
    plot_histogram(
        entries=data,
        bins=(X_MIN, X_MAX, 41),
        xlabel="$p_T$ [GeV]",
        stacked=False,
        save=os.path.join(OUTPUT_DIR, "01-histogram.png"),
    )


def _model(x: np.ndarray) -> np.ndarray:
    """dN/dx for the Gaussian signal plus flat background that generated the data."""
    signal = N_SIGNAL / (0.8 * np.sqrt(2 * np.pi)) * np.exp(-0.5 * ((x - 5.0) / 0.8) ** 2)
    background = N_BACKGROUND / (X_MAX - X_MIN)
    return signal + background


def _build_stacked_pull_plotter(data: dict[str, np.ndarray]) -> HistogramPlotter:
    """
    Shared by steps 2 and 3: builds the stacked+pull plot using whichever
    palette is active at call time, so switching the palette before calling
    this is the entire diff between "stack + pull panel" and "switch to KIT
    colors".
    """
    palette = get_palette()

    hist = Histogram()
    hist.binning = np.linspace(X_MIN, X_MAX, 41)
    hist.add_entry(HistogramEntry(name="signal", latex_name="Signal", array=data["signal"], color=palette.signal))
    hist.add_entry(
        HistogramEntry(name="background", latex_name="Background", array=data["background"], color=palette.background[1])
    )

    histplot = HistogramPlot(hist)
    histplot.stacked = True
    histplot.uncertainty = True

    variable = HistogramVariable("$p_T$", "GeV")
    plotter = HistogramPlotter(histplot, variable)
    plotter.watermark = "(Own Work)"

    plotter.add_function(_model, binwidth=True, label="Model", color=PetroffColors.purple, lw=2)
    plotter.add_pull(_model, binwidth=True, color=PetroffColors.purple, label="Model", lw=2, max_sigma=5.0)
    return plotter


def step2_engine_pull(data: dict[str, np.ndarray]) -> None:
    """Prompt: "Now stack them and add a pull panel comparing to the model"."""
    plotter = _build_stacked_pull_plotter(data)
    plotter.savepath = os.path.join(OUTPUT_DIR, "02-stacked-pull.png")
    plotter.plot(save=True)


def step3_kit_palette(data: dict[str, np.ndarray]) -> None:
    """Prompt: "Switch to KIT colors"."""
    set_palette("KIT")
    try:
        plotter = _build_stacked_pull_plotter(data)
        plotter.savepath = os.path.join(OUTPUT_DIR, "03-kit-colors.png")
        plotter.plot(save=True)
    finally:
        set_palette("Petroff")


def main() -> None:
    set_experiment("BelleII")
    set_matplotlibrc_params(36)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    data = make_signal_background(n_signal=N_SIGNAL, n_background=N_BACKGROUND, seed=3)

    step1_convenience(data)
    print("Saved to", os.path.join(OUTPUT_DIR, "01-histogram.png"))
    step2_engine_pull(data)
    print("Saved to", os.path.join(OUTPUT_DIR, "02-stacked-pull.png"))
    step3_kit_palette(data)
    print("Saved to", os.path.join(OUTPUT_DIR, "03-kit-colors.png"))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `uv run python examples/workflow_demo.py`
Expected: exit code 0, three "Saved to ..." lines printed.

- [ ] **Step 3: Verify the output files**

Run: `ls -la docs/img/workflow/`
Expected: `01-histogram.png`, `02-stacked-pull.png`, `03-kit-colors.png`, each with non-zero size.

Then open each PNG (e.g. via the Read tool, which can render images) and confirm:
- `01-histogram.png`: unstacked step-outline overlay of signal and background (no pull panel).
- `02-stacked-pull.png`: stacked filled histogram, a model curve overlay, and a pull panel below the main axes, in the default Petroff colors (signal in Petroff red).
- `03-kit-colors.png`: same layout as `02-stacked-pull.png` but signal in KIT red (`#a22223`) and background in KIT blue (`#4664aa`) instead of Petroff colors.

If any image doesn't match, fix the script and re-run Step 2 before proceeding — do not hand-edit the PNGs.

- [ ] **Step 4: Add `examples/workflow_demo.py` to `examples/README.md`**

Modify `examples/README.md` — add a bullet after the existing two, and a note about the
non-standard output directory:

```markdown
- `histogram_with_pull.py` — stacked histogram + model curve + pull panel,
  mirroring a typical fit-result plot.
- `exclusion_limit_with_inset.py` — expected-limit curve with an uncertainty
  band and a zoomed inset, mirroring a typical exclusion-limit plot.
- `workflow_demo.py` — three-step version of the actual AFPlotter workflow
  (convenience layer, then engine + pull panel, then a palette switch),
  mirroring the escalation path in `.claude/skills/afplotter/SKILL.md`. Writes
  to `docs/img/workflow/` instead of `examples/output/`, since its images are
  committed and embedded in the top-level README.

Run from the repo root with the package installed (`pip install -e .`):

    python examples/histogram_with_pull.py
    python examples/exclusion_limit_with_inset.py
    python examples/workflow_demo.py
```

(Insert the new bullet in the existing bullet list, and add the new `python examples/workflow_demo.py`
line to the existing "Run from the repo root" command block — don't duplicate that block.)

- [ ] **Step 5: Commit**

```bash
git add examples/workflow_demo.py examples/README.md docs/img/workflow/
git commit -m "$(cat <<'EOF'
Add workflow_demo.py example: convenience -> engine -> palette switch

Three-step script mirroring the real skill-driven usage pattern, with
committed reference images for the upcoming README section.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `verify-examples` skill exception for `workflow_demo.py`

**Files:**
- Modify: `.claude/skills/verify-examples/SKILL.md`

**Interfaces:**
- Consumes: nothing from Task 1 code — this is a documentation-only change to the skill's own
  instructions, but it references the exact filename and output directory Task 1 created
  (`examples/workflow_demo.py`, `docs/img/workflow/`).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Read the current file**

Read `.claude/skills/verify-examples/SKILL.md` in full (it's short — one "Steps" list, one
table, one "Common Mistakes" list).

- [ ] **Step 2: Edit step 3 of the "Steps" section**

Find:

```markdown
3. Confirm each run produced a new/updated file in `examples/output/`, non-zero size.
   An example that exits 0 but writes nothing didn't actually verify anything.
```

Replace with:

```markdown
3. Confirm each run produced a new/updated file, non-zero size. Every example
   writes to `examples/output/` **except** `workflow_demo.py`, which writes to
   `docs/img/workflow/` (its images are committed and embedded in the top-level
   README, so they can't live in the gitignored `examples/output/`). An
   example that exits 0 but writes nothing didn't actually verify anything.
```

(Match the exact current wording of step 3 first — read the file in Step 1 above and adjust
this replacement to the real surrounding text if it differs from what's quoted here.)

- [ ] **Step 3: Edit the "Quick Reference" table**

Find the row:

```markdown
| Each documented example produces output | new/updated file in `examples/output/`, non-zero size |
```

Replace with:

```markdown
| Each documented example produces output | new/updated file in `examples/output/` (or `docs/img/workflow/` for `workflow_demo.py`), non-zero size |
```

- [ ] **Step 4: Add a "Common Mistakes" entry**

Add a new bullet to the "Common Mistakes" list:

```markdown
- Checking `examples/output/` for `workflow_demo.py`'s output — it writes to
  `docs/img/workflow/` instead, on purpose (see step 3).
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/verify-examples/SKILL.md
git commit -m "$(cat <<'EOF'
Document workflow_demo.py's output-dir exception in verify-examples

It writes committed images to docs/img/workflow/ instead of the
gitignored examples/output/, so the skill's output-location check
needs a documented exception rather than a false failure.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: README "How you'd actually use this" section

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `docs/img/workflow/01-histogram.png`, `docs/img/workflow/02-stacked-pull.png`,
  `docs/img/workflow/03-kit-colors.png` (produced by Task 1) — referenced as README-relative
  image paths, which is how GitHub resolves README image links from the repo root.
- Produces: nothing consumed by later tasks (this is the last task).

- [ ] **Step 1: Insert the new section between Quickstart and Docs**

In `README.md`, after the existing Quickstart section (ends at the `set_palette(...)` paragraph,
line 59 in the current file) and before `## Docs`, insert:

```markdown
## How you'd actually use this

In practice you don't write the Quickstart snippet by hand — you install the
[Claude Code skill](#claude-code-skill-optional) above and just ask for what you want, in plain
English, across a few turns. Here's a real three-turn sequence, using the same synthetic
signal/background sample throughout:

> Plot signal vs background for pt

![Unstacked signal/background overlay](docs/img/workflow/01-histogram.png)

The convenience layer handles this in one call: `plot_histogram(entries, bins, stacked=False)`.

> Now stack them and add a pull panel comparing to the model

![Stacked histogram with model overlay and pull panel](docs/img/workflow/02-stacked-pull.png)

A pull panel needs the full engine, not the convenience layer, so this escalates to
`Histogram`/`HistogramEntry` → `HistogramPlot` → `HistogramPlotter`, with `add_function` and
`add_pull` for the model overlay and pull panel.

> Switch to KIT colors

![Same plot, KIT color palette](docs/img/workflow/03-kit-colors.png)

One line: `set_palette("KIT")`, called before the plot is rebuilt.

See `examples/workflow_demo.py` for the full runnable script behind these three images.
```

- [ ] **Step 2: Verify the README renders sensibly**

Run: `grep -n "^## " README.md`
Expected output shows section order: `# AFPlotter`, `## Install`, `## Claude Code skill (optional)`,
`## Quickstart`, `## How you'd actually use this`, `## Docs` — confirming the new section landed
between Quickstart and Docs, not appended at the end or misplaced.

Then confirm the three image paths resolve: `ls docs/img/workflow/01-histogram.png
docs/img/workflow/02-stacked-pull.png docs/img/workflow/03-kit-colors.png` — all three must exist
(from Task 1) for the README links to not be broken on GitHub.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
Add "How you'd actually use this" section to README

Narrates the real three-prompt skill-driven workflow (convenience ->
engine -> palette switch) with the workflow_demo.py output images
embedded, so the README shows the repo's actual usage pattern instead
of only a single static Quickstart snippet.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** scenario/three prompts → Task 1 steps 1-3; `examples/workflow_demo.py` →
  Task 1; `docs/img/workflow/` output dir → Task 1; README section → Task 3;
  `examples/README.md` bullet → Task 1 step 4; `verify-examples` skill update → Task 2;
  testing/verification → Task 1 steps 2-3 and Task 3 step 2; out-of-scope items (watermark bug,
  library code changes, CI regeneration) are not touched by any task, matching the spec.
- **Placeholder scan:** no TBD/TODO; all code blocks are complete, runnable content; the
  verify-examples task tells the implementer to re-read the file before matching exact wording
  (unavoidable since this plan can't inline a file it doesn't own the current byte-for-byte
  content of turning stale) rather than leaving a vague "update appropriately" instruction — the
  replacement text itself is fully specified either way.
- **Type consistency:** `_build_stacked_pull_plotter(data: dict[str, np.ndarray]) ->
  HistogramPlotter` is defined once in Task 1 and used identically by both `step2_engine_pull`
  and `step3_kit_palette` in the same task/file — no cross-task signature drift possible since
  it's all one file written in one task.
