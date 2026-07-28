# AFPlotter examples

Runnable scripts using synthetic data (no real analysis data required).
Each writes a PNG to `examples/output/` (gitignored).

- `histogram_with_pull.py` — stacked histogram + model curve + pull panel,
  mirroring a typical fit-result plot.
- `exclusion_limit_with_inset.py` — expected-limit curve with an uncertainty
  band and a zoomed inset, mirroring a typical exclusion-limit plot.

Run from the repo root with the package installed (`pip install -e .`):

    python examples/histogram_with_pull.py
    python examples/exclusion_limit_with_inset.py
