import numpy as np
import polars as pl
import pytest

from afplotter.utilities.lazyhistogram import LazyHistEntry, LazyHistWrapper, WrapperState


@pytest.fixture
def sample_parquet(tmp_path):
    path = tmp_path / "sample.parquet"
    rng = np.random.default_rng(seed=7)
    df = pl.DataFrame(
        {
            "pt": rng.uniform(0, 10, 200),
            "eta": rng.uniform(-2, 2, 200),
            "weight": np.ones(200),
        }
    )
    df.write_parquet(path)
    return path


def test_lazy_hist_entry_loads_from_path(sample_parquet):
    entry = LazyHistEntry(name="mc", input=sample_parquet)
    assert entry.data.collect().height == 200


def test_lazy_hist_entry_applies_prefilter(sample_parquet):
    entry = LazyHistEntry(name="mc", input=sample_parquet, prefilter="pt > 5")
    result = entry.data.collect()
    assert (result["pt"] > 5).all()


def test_lazy_hist_entry_rejects_invalid_input():
    with pytest.raises(ValueError, match="Data must be a LazyFrame"):
        LazyHistEntry(name="mc", input=42)  # type: ignore[arg-type]


def test_wrapper_state_transitions(sample_parquet):
    wrapper = LazyHistWrapper()
    assert wrapper.state.get_state() == WrapperState.INIT

    wrapper.add_lazy_entry(LazyHistEntry(name="mc", input=sample_parquet))
    assert wrapper.state.get_state() == WrapperState.DATA

    wrapper.add_hist(column="pt", bins=(0, 10, 11), identifier="pt_hist")
    assert wrapper.state.get_state() == WrapperState.HIST

    wrapper.lazy_execute()
    assert wrapper.state.get_state() == WrapperState.EXECUTED


def test_add_hist_before_data_raises(sample_parquet):
    wrapper = LazyHistWrapper()
    with pytest.raises(Exception, match="Can only add histograms"):
        wrapper.add_hist(column="pt", bins=(0, 10, 11))


def test_get_hist_before_execute_raises(sample_parquet):
    wrapper = LazyHistWrapper()
    wrapper.add_lazy_entry(LazyHistEntry(name="mc", input=sample_parquet))
    wrapper.add_hist(column="pt", bins=(0, 10, 11), identifier="pt_hist")
    with pytest.raises(Exception, match="Can only get histograms after execution"):
        wrapper.get_hist("pt_hist")


def test_full_1d_flow_produces_populated_histogram(sample_parquet):
    wrapper = LazyHistWrapper()
    wrapper.add_lazy_entry(LazyHistEntry(name="mc", input=sample_parquet))
    wrapper.add_hist(column="pt", bins=(0, 10, 11), identifier="pt_hist", weight=True)
    wrapper.lazy_execute()

    hist = wrapper.get_hist("pt_hist")
    assert hist.get_names() == ["mc"]
    assert hist.get_total_bin_count().sum() == pytest.approx(200)


def test_full_2d_flow_produces_populated_histograms(sample_parquet):
    wrapper = LazyHistWrapper()
    wrapper.add_lazy_entry(LazyHistEntry(name="mc", input=sample_parquet))
    wrapper.add_hist2d(
        xcolumn="pt",
        ycolumn="eta",
        xbins=(0, 10, 11),
        ybins=(-2, 2, 11),
        entries_to_hist="mc",
        identifier="pt_eta",
    )
    wrapper.lazy_execute()

    hist2d = wrapper.get_2Dhist("pt_eta")
    assert hist2d["x"].get_total_bin_count().sum() == pytest.approx(200)
    assert hist2d["y"].get_total_bin_count().sum() == pytest.approx(200)


def test_unknown_identifier_raises_keyerror(sample_parquet):
    wrapper = LazyHistWrapper()
    wrapper.add_lazy_entry(LazyHistEntry(name="mc", input=sample_parquet))
    wrapper.add_hist(column="pt", bins=(0, 10, 11), identifier="pt_hist")
    wrapper.lazy_execute()
    with pytest.raises(KeyError):
        wrapper.get_hist("nonexistent")


def test_get_bins_rejects_int():
    with pytest.raises(ValueError, match="Integers are not allowed"):
        LazyHistWrapper.get_bins(50)
