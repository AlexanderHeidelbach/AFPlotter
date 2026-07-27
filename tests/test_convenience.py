import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import pytest

from afplotter.convenience import plot_2d_histogram, plot_histogram, plot_histogram_from_files


@pytest.fixture
def two_entry_arrays():
    rng = np.random.default_rng(0)
    return {
        "signal": rng.normal(5, 1, 300),
        "background": rng.uniform(0, 10, 500),
    }


def test_plot_histogram_returns_axes_with_content(two_entry_arrays):
    ax = plot_histogram(two_entry_arrays, bins=(0, 10, 21), xlabel="pt", save=False)
    assert len(ax.patches) > 0 or len(ax.containers) > 0
    plt.close(ax.figure)


def test_plot_histogram_saves_to_explicit_path(two_entry_arrays, tmp_path):
    save_path = tmp_path / "out.png"
    plot_histogram(two_entry_arrays, bins=(0, 10, 21), save=str(save_path))
    assert save_path.exists()


def test_plot_histogram_stacked_option(two_entry_arrays, tmp_path):
    save_path = tmp_path / "stacked.png"
    plot_histogram(two_entry_arrays, bins=(0, 10, 21), stacked=True, save=str(save_path))
    assert save_path.exists()


def test_plot_histogram_from_files_with_selection(tmp_path):
    rng = np.random.default_rng(1)
    df = pl.DataFrame({"pt": rng.uniform(0, 10, 200), "weight": np.ones(200)})
    path = tmp_path / "data.parquet"
    df.write_parquet(path)

    save_path = tmp_path / "from_files.png"
    plot_histogram_from_files(
        files={"mc": path},
        column="pt",
        bins=(0, 10, 11),
        selection="pt > 5",
        save=str(save_path),
    )
    assert save_path.exists()


def test_plot_2d_histogram_saves(tmp_path):
    rng = np.random.default_rng(2)
    xdata = rng.uniform(0, 10, 300)
    ydata = rng.uniform(0, 10, 300)
    save_path = tmp_path / "hist2d.png"
    plot_2d_histogram(xdata, ydata, xbins=(0, 10, 11), ybins=(0, 10, 11), save=str(save_path))
    assert save_path.exists()
