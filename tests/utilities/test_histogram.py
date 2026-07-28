# tests/utilities/test_histogram.py
import numpy as np
import pytest

from afplotter.utilities.histogram import Histogram, HistogramEntry


def test_histogram_entry_add():
    e1 = HistogramEntry(name="a", counts=np.array([1.0, 2.0]), errors=np.array([1.0, 1.0]))
    e2 = HistogramEntry(name="b", counts=np.array([3.0, 4.0]), errors=np.array([1.0, 1.0]))
    combined = e1 + e2
    assert combined.counts.tolist() == [4.0, 6.0]
    assert combined.errors[0] == pytest.approx(np.sqrt(2))


def test_histogram_entry_add_mismatched_bins_raises():
    e1 = HistogramEntry(name="a", counts=np.array([1.0]))
    e2 = HistogramEntry(name="b", counts=np.array([1.0, 2.0]))
    with pytest.raises(ValueError):
        e1 + e2


def test_histogram_entry_iadd_accumulates():
    e1 = HistogramEntry(name="a", counts=np.array([]), errors=np.array([]))
    e2 = HistogramEntry(name="b", counts=np.array([2.0, 3.0]), errors=np.array([1.0, 1.0]))
    e1 += e2
    assert e1.counts.tolist() == [2.0, 3.0]
    e1 += e2
    assert e1.counts.tolist() == [4.0, 6.0]


def test_histogram_entry_as_dict_and_from_dict_roundtrip():
    e = HistogramEntry(name="a", array=np.array([1.0, 2.0]), counts=np.array([1.0]), errors=np.array([1.0]))
    data = e.as_dict
    restored = HistogramEntry.from_dict(data)
    assert restored.name == "a"
    assert restored.array.tolist() == [1.0, 2.0]


def test_histogram_add_entry_computes_counts_and_errors():
    hist = Histogram()
    hist.binning = np.array([0.0, 1.0, 2.0, 3.0])
    entry = HistogramEntry(name="a", array=np.array([0.5, 0.5, 1.5, 2.5]))
    hist.add_entry(entry)
    assert hist.get_entry("a").counts.tolist() == [2.0, 1.0, 1.0]
    assert hist.entries["a"].errors.tolist() == [pytest.approx(np.sqrt(2)), 1.0, 1.0]


def test_histogram_add_entry_without_binning_raises():
    hist = Histogram()
    with pytest.raises(ValueError, match="Binning not set"):
        hist.add_entry(HistogramEntry(name="a", array=np.array([1.0])))


def test_histogram_remove_entry():
    hist = Histogram()
    hist.binning = np.array([0.0, 1.0, 2.0])
    hist.add_entry(HistogramEntry(name="a", array=np.array([0.5])))
    hist.remove_entry("a")
    assert "a" not in hist.entries


def test_histogram_remove_missing_entry_raises():
    hist = Histogram()
    with pytest.raises(KeyError):
        hist.remove_entry("nonexistent")


def test_histogram_sum_entries():
    hist = Histogram()
    hist.binning = np.array([0.0, 1.0, 2.0])
    hist.add_entry(HistogramEntry(name="a", array=np.array([0.5])))
    hist.add_entry(HistogramEntry(name="b", array=np.array([0.5, 1.5])))
    hist.sum_entries(["a", "b"], name="combined")
    assert "a" not in hist.entries
    assert "b" not in hist.entries
    assert hist.entries["combined"].counts.tolist() == [2.0, 1.0]


def test_histogram_total_bin_count_and_scale():
    hist = Histogram()
    hist.binning = np.array([0.0, 1.0, 2.0])
    hist.add_entry(HistogramEntry(name="a", array=np.array([0.5, 0.5])))
    hist.add_entry(HistogramEntry(name="b", array=np.array([1.5])))
    assert hist.get_total_bin_count().tolist() == [2.0, 1.0]
    assert hist.get_total_scale() == pytest.approx(3.0)


def test_histogram_as_dict_and_from_dict_roundtrip():
    hist = Histogram()
    hist.binning = np.array([0.0, 1.0, 2.0])
    hist.add_entry(HistogramEntry(name="a", array=np.array([0.5])))
    data = hist.as_dict
    restored = Histogram.from_dict(data)
    assert restored.binning.tolist() == [0.0, 1.0, 2.0]
    assert restored.entries["a"].counts.tolist() == [1.0, 0.0]


def test_histogram_order_entries():
    hist = Histogram()
    hist.binning = np.array([0.0, 1.0, 2.0])
    hist.add_entry(HistogramEntry(name="a", array=np.array([0.5])))
    hist.add_entry(HistogramEntry(name="b", array=np.array([1.5])))
    hist.order_entries(["b", "a"])
    assert list(hist.entries.keys()) == ["b", "a"]


def test_histogram_order_entries_wrong_count_raises():
    hist = Histogram()
    hist.binning = np.array([0.0, 1.0, 2.0])
    hist.add_entry(HistogramEntry(name="a", array=np.array([0.5])))
    with pytest.raises(ValueError):
        hist.order_entries(["a", "b"])
