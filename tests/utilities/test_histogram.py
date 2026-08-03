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


def _signal_and_background() -> Histogram:
    """One background entry and one signal entry over two bins."""
    hist = Histogram()
    hist.binning = np.array([0.0, 1.0, 2.0])
    hist.add_entry(HistogramEntry(name="bkg", array=np.array([0.5, 0.5, 0.5, 1.5])))
    hist.add_entry(HistogramEntry(name="sig", array=np.array([0.5, 1.5]), type="signal"))
    return hist


def test_totals_include_the_signal():
    hist = _signal_and_background()
    # background is [3, 1], signal is [1, 1]
    assert hist.get_bin_counts()[0].tolist() == [3.0, 1.0]
    assert hist.get_raw_signal_bin_counts()[0].tolist() == [1.0, 1.0]
    assert hist.get_total_bin_count().tolist() == [4.0, 2.0]
    assert hist.get_total_scale() == pytest.approx(6.0)


def test_total_bin_errors_include_the_signal():
    hist = _signal_and_background()
    # Poisson errors are sqrt(N) per entry, added in quadrature over the stack,
    # so background [3, 1] plus signal [1, 1] gives sqrt(3 + 1) and sqrt(1 + 1).
    assert hist.get_total_bin_errors().tolist() == [
        pytest.approx(np.sqrt(4.0)),
        pytest.approx(np.sqrt(2.0)),
    ]


def test_stacked_accessors_put_signal_last():
    hist = _signal_and_background()
    counts = hist.get_stacked_bin_counts()
    assert len(counts) == 2
    assert counts[-1].tolist() == [1.0, 1.0]  # signal closes the stack
    assert len(hist.get_stacked_bin_centers()) == 2
    hist.entries["bkg"].latex_name = "Bkg"
    hist.signal["sig"].latex_name = "Sig"
    assert hist.get_stacked_latex_names() == ["Bkg", "Sig"]


def test_raw_signal_counts_are_not_peak_matched():
    """get_signal_bin_counts() rescales for the overlay; the stacked counts must not."""
    hist = _signal_and_background()
    assert hist.get_raw_signal_bin_counts()[0].tolist() == [1.0, 1.0]
    # the overlay version is scaled up to the background stack maximum (3)
    assert hist.get_signal_bin_counts()[0].tolist() == [3.0, 3.0]


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


def test_histogram_roundtrip_preserves_unset_binning():
    """A Histogram with no binning must survive as_dict -> from_dict with binning still None.

    Guards the binning=None path through as_dict/from_dict, which had zero coverage: a
    Histogram with unset binning must round-trip to unset binning, not be coerced into an
    array or an int.
    """
    hist = Histogram()
    data = hist.as_dict
    assert data["binning"] is None

    restored = Histogram.from_dict(data)
    assert restored.binning is None
    assert restored.entries == {}
    assert restored.signal == {}
