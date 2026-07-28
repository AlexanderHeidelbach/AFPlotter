# AFPlotter

A standalone matplotlib-based plotting library for HEP analyses (histograms,
2D histograms, composed/generic plots, Polars-based lazy histogramming, and
an AST-based selection-query parser), with built-in Belle II / Generic
experiment styles. Register your own via `afplotter.experiments.registry`.

## Install

    pip install git+https://github.com/AlexanderHeidelbach/AFPlotter.git

Or for local development:

    git clone https://github.com/AlexanderHeidelbach/AFPlotter.git
    cd AFPlotter
    uv sync --extra dev

## Quickstart

```python
from afplotter import plot_histogram, set_experiment
import numpy as np

set_experiment("BelleII")  # or "Generic"

rng = np.random.default_rng(0)
plot_histogram(
    entries={"signal": rng.normal(5, 1, 500), "background": rng.uniform(0, 10, 1000)},
    bins=(0, 10, 41),
    xlabel="p_T (GeV)",
    stacked=True,
    save="pt.png",
)
```

## Docs

- [Getting started](docs/getting-started.md) — experiment styles, `BasePlotter` properties
- [Histograms](docs/histograms.md) — stacked/step/pull plots, 2D histograms, the convenience layer
- [Composed plots](docs/composed-plots.md) — `GenericPlotter`, fills/exclusion bands, `add_inset`
- [Selections](docs/selections.md) — the query-string filter parser

See `examples/` for runnable scripts.
