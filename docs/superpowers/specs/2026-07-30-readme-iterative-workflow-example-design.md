# README iterative-workflow example

## Context

AFPlotter's actual intended usage — per `.claude/skills/afplotter/SKILL.md` and the
"AI-first" framing in `CLAUDE.md` — is conversational: a user asks Claude for a plot in
plain English, then asks for changes across follow-up turns, with Claude picking the right
layer (convenience vs. engine) and API each time. Nothing in the README currently shows this;
the Quickstart is a single static code block. This adds a worked example of the real workflow:
three prompts, each producing a plot, narrated in the README with the actual output images
embedded.

## Scenario

Three prompts, escalating through the repo's own architecture (convenience → engine →
palette-switching), using the same synthetic signal/background sample throughout:

1. **"Plot signal vs background for pt"** → convenience layer (`plot_histogram`), unstacked
   step overlay.
2. **"Now stack them and add a pull panel comparing to the model"** → escalates to the engine
   (`Histogram`/`HistogramEntry`/`HistogramPlot`/`HistogramPlotter`, `add_function`/`add_pull`),
   same data.
3. **"Switch to KIT colors"** → `set_palette("KIT")`, same stacked+pull plot rebuilt.

This mirrors the SKILL.md decision tree (simple request → convenience; composed/analysis
request → engine) and the palette-switching feature, rather than an arbitrary demo sequence.

All three plots render at `text_size=36` (`set_matplotlibrc_params`'s own default, documented
as "paper-ready") so the embedded images look presentation-quality, not like a quick test
script. `luminosity_value` is deliberately left unset on the `HistogramPlotter` in steps 2/3:
there is a known, not-yet-fixed overlap bug between the watermark and luminosity text rows at
large `text_size` (see `docs/superpowers/specs/2026-07-30-watermark-text-spacing-design.md`),
and setting it here would surface that bug in a checked-in image. Fixing it is out of scope for
this change.

## `examples/workflow_demo.py`

New script, following the existing example scripts' shape (`_synthetic_data` import,
`main()`, docstring header) but writing to a different, non-gitignored output directory.

```python
# examples/workflow_demo.py
"""
Three-step version of the actual AFPlotter workflow: a user asks for a plot,
then asks for changes across follow-up turns. Mirrors the escalation path in
.claude/skills/afplotter/SKILL.md — convenience layer first, engine once the
request needs a pull panel, then a palette switch.

Run: python examples/workflow_demo.py
"""
```

- `OUTPUT_DIR = docs/img/workflow/` (relative to repo root) — committed, unlike
  `examples/output/`, since these images are embedded in the README.
- Shared setup: `set_experiment("BelleII")`, `from afplotter.baseplotter import
  set_matplotlibrc_params; set_matplotlibrc_params(36)` called once in `main()` before all
  three steps (it mutates global rcParams, so one call covers all three plots).
- `step1_convenience()`: `make_signal_background(n_signal=600, n_background=1200, seed=3)`
  (same seed/counts as `histogram_with_pull.py`, for visual continuity across the docs), calls
  `plot_histogram(entries=..., bins=(0, 10, 41), xlabel="$p_T$ [GeV]", stacked=False,
  save=OUTPUT_DIR/"01-histogram.png")`.
- `step2_engine_pull()`: rebuilds the same data via `Histogram`/`HistogramEntry` (signal in
  `PETROFF_PALETTE.signal`, background in `PetroffColors.blue`, matching
  `histogram_with_pull.py`'s pattern), `HistogramPlot(stacked=True, uncertainty=True)`,
  `HistogramPlotter`, the same closed-form `model(x)` function as `histogram_with_pull.py`
  (Gaussian signal + flat background matched to the generating parameters), `add_function` +
  `add_pull`. Saves to `OUTPUT_DIR/"02-stacked-pull.png"`.
- `step3_kit_palette()`: calls `set_palette("KIT")`, then repeats `step2`'s plot construction
  verbatim (factored into a shared helper so the two steps can't drift apart), saving to
  `OUTPUT_DIR/"03-kit-colors.png"`. Resets the palette back to `"Petroff"` afterward so running
  the script twice, or running it before other examples in the same process, is idempotent.
- `main()` creates `OUTPUT_DIR` if missing and calls all three steps in order, printing each
  saved path (matching the existing examples' `print("Saved to", ...)` convention).

## README changes

New section titled **"How you'd actually use this"**, placed after Quickstart and before Docs.
Structure: one short lead-in sentence explaining this is the real skill-driven workflow (not a
single API call), then for each of the three prompts:

```markdown
> Plot signal vs background for pt

![...](docs/img/workflow/01-histogram.png)

Convenience layer: one `plot_histogram()` call.
```

...repeated for prompts 2 and 3, with their one-line notes ("escalates to the engine for the
pull panel", "same plot, `set_palette(\"KIT\")`"). Each note names the specific function/call
that changed, staying consistent with the Quickstart's existing level of code-mindedness. Close
the section with a one-sentence pointer to the skill install instructions already earlier in
the README ("This is what the Claude Code skill (above) does automatically.").

## Supporting doc/skill updates

- `examples/README.md`: add a bullet for `workflow_demo.py`, explicitly noting it writes to
  `docs/img/workflow/` instead of `examples/output/` (so `verify-examples` and future readers
  aren't confused by the exception).
- `.claude/skills/verify-examples/SKILL.md`: step 3 ("confirm each run produced a new/updated
  file in `examples/output/`") needs a documented exception for `workflow_demo.py` — check
  `docs/img/workflow/` instead for that one script. Update the "Common Mistakes" / steps text
  accordingly rather than silently special-casing it.

## Testing

This is a docs/example artifact, not library behavior, so there's no new unit test. Verification
is procedural, matching this repo's "run it, don't read it" examples philosophy:

- `uv run python examples/workflow_demo.py` exits 0 and writes all three PNGs to
  `docs/img/workflow/`, each non-zero size.
- Visual check of all three images: step 1 shows an unstacked overlay, step 2 shows a stacked
  histogram with a pull panel and model curve, step 3 shows the same as step 2 but with KIT
  colors instead of Petroff.
- `tests/test_packaging.py`'s import-time-side-effect guard is unaffected (the new script is
  never imported by the package, only run standalone, same as the other example scripts).
- README renders correctly on GitHub (image paths are relative to repo root, matching how
  GitHub resolves README-relative image links).

## Out of scope

- Fixing the watermark/luminosity spacing bug at large `text_size` (tracked separately in
  `docs/superpowers/specs/2026-07-30-watermark-text-spacing-design.md`) — sidestepped here by
  not setting `luminosity_value`.
- Any change to `plot_histogram`, `HistogramPlotter`, or other library code — this is docs +
  one new example script only.
- Automating image regeneration in CI (e.g. failing a PR if committed images are stale relative
  to the script) — regeneration stays a manual `python examples/workflow_demo.py` step for
  whoever touches this script next.
