import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest

from afplotter.utilities.histogram import Histogram, HistogramEntry


@pytest.fixture
def synthetic_histogram():
    """A 2-entry Histogram (signal + background) with 20 bins over [0, 10)."""
    rng = np.random.default_rng(seed=42)
    hist = Histogram()
    hist.binning = np.linspace(0, 10, 21)
    hist.add_entry(
        HistogramEntry(
            name="signal",
            latex_name="Signal",
            array=rng.normal(loc=5, scale=1, size=500),
            color="#E41A1C",
        )
    )
    hist.add_entry(
        HistogramEntry(
            name="background",
            latex_name="Background",
            array=rng.uniform(0, 10, size=1000),
            color="#377EB8",
        )
    )
    return hist
