# examples/_synthetic_data.py
"""Synthetic data generators shared by the example scripts."""

import numpy as np


def make_signal_background(n_signal: int = 500, n_background: int = 1000, seed: int = 0) -> dict[str, np.ndarray]:
    """
    Generate a Gaussian "signal" and a uniform "background" sample over [0, 10).

    :param n_signal: Number of signal points.
    :param n_background: Number of background points.
    :param seed: RNG seed for reproducibility.
    :return: {"signal": array, "background": array}
    """
    rng = np.random.default_rng(seed)
    return {
        "signal": rng.normal(loc=5.0, scale=0.8, size=n_signal),
        "background": rng.uniform(0.0, 10.0, size=n_background),
    }


def make_exclusion_curve(seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate a synthetic expected upper-limit curve with a +/-1 sigma band.

    :param seed: RNG seed for reproducibility.
    :return: (masses, expected, band_lower, band_upper)
    """
    rng = np.random.default_rng(seed)
    masses = np.linspace(0.2, 9.5, 60)
    expected = 5.0 / masses + rng.normal(0, 0.05, size=masses.size)
    band = 0.4 / masses
    return masses, expected, expected - band, expected + band
