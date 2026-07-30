# AFPlotter examples

Runnable scripts using synthetic data (no real analysis data required).
Each writes a PNG to `examples/output/` (gitignored).

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
