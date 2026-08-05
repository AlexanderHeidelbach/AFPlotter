# tests/utilities/test_histogram.py
import json
import numpy as np
import pytest

from afplotter.utilities.histogram import SAVE_FORMAT_VERSION, Histogram, HistogramEntry


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


def test_save_load_round_trip(tmp_path):
    """Counts, errors, binning, signal split and styling must survive a save/load cycle.

    The errors here are deliberately not ``sqrt(counts)``, so a ``load`` that recomputes
    them instead of restoring them fails this test. They are passed straight into the
    ``HistogramEntry`` constructor -- ``add_entry`` preserves supplied errors (issue #37).
    """
    bkg_errors = np.array([1.5, 2.5, 3.5, 4.5, 5.5])
    hist = Histogram()
    hist.binning = np.linspace(0.0, 5.0, 6)
    hist.add_entry(
        HistogramEntry(
            name="bkg",
            latex_name="Background",
            counts=np.array([10.0, 20.0, 30.0, 40.0, 50.0]),
            errors=bkg_errors,
            color="#123456",
            hatch="//",
            weight=2.0,
            show_label=False,
        )
    )

    sig_errors = np.array([0.5, 0.5, 0.5, 0.5, 0.5])
    hist.add_entry(
        HistogramEntry(
            name="sig",
            latex_name="Signal",
            counts=np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
            errors=sig_errors,
            type="signal",
        )
    )

    hist.metadata["column_name"] = "pt"

    path = tmp_path / "h.json"
    hist.save(path)
    restored = Histogram.load(path)

    assert np.allclose(restored.get_bin_counts()[0], hist.get_bin_counts()[0])
    assert np.allclose(restored.get_bin_errors()[0], bkg_errors)
    assert np.allclose(restored.signal["sig"].errors, sig_errors)
    assert np.allclose(restored.binning, hist.binning)
    assert restored.get_names() == hist.get_names()
    assert restored.get_signal_names() == hist.get_signal_names()
    assert restored.get_colors() == hist.get_colors()
    assert restored.get_hatches() == hist.get_hatches()
    assert restored.metadata["column_name"] == "pt"
    # Fields most likely to be missed if HistogramEntry gains more of them.
    assert restored.entries["bkg"].show_label is False
    assert restored.entries["bkg"].type == "entry"
    assert restored.entries["bkg"].weight == 2.0


def test_save_does_not_mutate_the_source_histogram(tmp_path):
    """Saving must not clear the caller's raw arrays or per-event weights as a side effect."""
    hist = Histogram()
    hist.binning = np.linspace(0.0, 10.0, 6)
    raw = np.random.default_rng(0).normal(5.0, 2.0, 500)
    weight = np.random.default_rng(1).random(500)
    hist.add_entry(HistogramEntry(name="bkg", array=raw.copy(), weight=weight.copy()))

    hist.save(tmp_path / "h.json")

    assert hist.get_data()[0] is not None
    assert np.allclose(hist.get_data()[0], raw)
    assert isinstance(hist.entries["bkg"].weight, np.ndarray)
    assert np.allclose(hist.entries["bkg"].weight, weight)


def test_save_handles_per_event_weight_array(tmp_path):
    """The headline use case: an entry with a per-event weight array must save without error.

    A per-event ``weight`` is the same length as ``array`` and equally meaningless once
    ``array`` is dropped, so it must be nulled alongside ``array`` -- not serialized (which
    would crash, since ndarrays are not JSON-safe) and not silently kept (which would defeat
    the whole point of a binned-only, size-bounded save file).
    """
    hist = Histogram()
    hist.binning = np.linspace(0.0, 10.0, 6)
    rng = np.random.default_rng(0)
    array = rng.normal(5.0, 2.0, 10_000)
    weight = rng.random(10_000)
    hist.add_entry(HistogramEntry(name="bkg", array=array, weight=weight))
    counts_before = hist.get_bin_counts()[0].copy()
    errors_before = hist.get_bin_errors()[0].copy()

    path = tmp_path / "h.json"
    hist.save(path)  # must not raise TypeError: Object of type ndarray is not JSON serializable

    assert path.stat().st_size < 2_000  # binned-only; nowhere near 10k floats worth of JSON

    restored = Histogram.load(path)
    assert np.allclose(restored.get_bin_counts()[0], counts_before)
    assert np.allclose(restored.get_bin_errors()[0], errors_before)
    assert restored.entries["bkg"].weight == 1.0  # per-event weight cannot be restored; default


def test_saved_file_size_does_not_scale_with_sample_size(tmp_path):
    """The saved payload must be binned-only; a 100x larger sample must not grow the file.

    This is the property that makes caching worthwhile, and it fails loudly if raw event
    arrays ever creep back into the payload.
    """
    rng = np.random.default_rng(0)
    sizes = []
    for n_events in (1_000, 100_000):
        hist = Histogram()
        hist.binning = np.linspace(0.0, 10.0, 11)
        hist.add_entry(HistogramEntry(name="bkg", array=rng.normal(5.0, 2.0, n_events)))
        path = tmp_path / f"h_{n_events}.json"
        hist.save(path)
        sizes.append(path.stat().st_size)

    small, large = sizes
    assert large < small * 1.1, f"file grew with sample size: {small} -> {large} bytes"


def test_load_rejects_an_unknown_format_version(tmp_path):
    """A future format must fail with a clear message, not a KeyError deep in from_dict."""
    hist = Histogram()
    hist.binning = np.linspace(0.0, 5.0, 6)
    hist.add_entry(HistogramEntry(name="bkg", counts=np.array([1.0, 2.0, 3.0, 4.0, 5.0])))
    path = tmp_path / "h.json"
    hist.save(path)

    payload = json.loads(path.read_text())
    payload["format_version"] = 99
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="format_version"):
        Histogram.load(path)


def test_load_rejects_a_non_object_top_level(tmp_path):
    """A JSON list at the top level must fail with a clear ValueError, not an AttributeError."""
    path = tmp_path / "h.json"
    path.write_text(json.dumps([1, 2, 3]))

    with pytest.raises(ValueError, match=str(path)):
        Histogram.load(path)


def test_load_rejects_a_payload_missing_entries(tmp_path):
    """A dict that passes the version check but lacks 'entries' must fail with a clear ValueError."""
    path = tmp_path / "h.json"
    path.write_text(json.dumps({"format_version": SAVE_FORMAT_VERSION}))

    with pytest.raises(ValueError, match="entries"):
        Histogram.load(path)


def test_add_entry_preserves_supplied_errors_on_a_prebinned_entry():
    """Issue #37: pre-binned errors are authoritative and must not be recomputed."""
    counts = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    errors = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
    # Guard the fixture: if these coincided with sqrt(counts) the test would pass
    # whether errors were preserved or overwritten.
    assert not np.allclose(errors, np.sqrt(counts))

    hist = Histogram()
    hist.binning = np.linspace(0.0, 5.0, 6)
    hist.add_entry(HistogramEntry(name="pre", counts=counts, errors=errors))

    assert np.allclose(hist.entries["pre"].errors, errors)


def test_add_entry_falls_back_to_poisson_when_no_errors_supplied():
    """The sqrt(counts) fallback is load-bearing for pre-binned entries without errors."""
    counts = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

    hist = Histogram()
    hist.binning = np.linspace(0.0, 5.0, 6)
    hist.add_entry(HistogramEntry(name="pre", counts=counts))

    assert np.allclose(hist.entries["pre"].errors, np.sqrt(counts))


def test_add_entry_computes_weighted_errors_from_a_raw_array():
    """With a raw array and no supplied errors, errors stay sqrt(sum w**2), not sqrt(counts)."""
    hist = Histogram()
    hist.binning = np.array([0.0, 1.0, 2.0])
    # Four events in bin 0, two in bin 1, each weighted 2.0.
    array = np.array([0.5, 0.5, 0.5, 0.5, 1.5, 1.5])
    hist.add_entry(HistogramEntry(name="w", array=array, weight=2.0))

    counts = hist.entries["w"].counts
    errors = hist.entries["w"].errors
    assert np.allclose(counts, [8.0, 4.0])
    assert np.allclose(errors, [4.0, np.sqrt(8.0)])  # sqrt(sum w**2) = sqrt(4*4), sqrt(2*4)
    # The whole point of the weighted path: it does not agree with Poisson.
    assert not np.allclose(errors, np.sqrt(counts))


def test_add_entry_supplied_errors_win_over_a_raw_array():
    """Precedence: supplied binned values are never recomputed, exactly as counts behave.

    This entry carries both a raw ``array`` and explicit ``errors``. The supplied errors
    win. Pinning this is the point of the test -- it is what fails if someone later
    switches to the 'recompute whenever array exists' reading.
    """
    array = np.array([0.5, 0.5, 0.5, 0.5, 1.5, 1.5])
    counts = np.array([4.0, 2.0])
    errors = np.array([0.25, 0.75])
    assert not np.allclose(errors, np.sqrt(counts))

    hist = Histogram()
    hist.binning = np.array([0.0, 1.0, 2.0])
    hist.add_entry(HistogramEntry(name="both", array=array, counts=counts, errors=errors))

    assert np.allclose(hist.entries["both"].errors, errors)


def test_add_entry_rejects_errors_of_the_wrong_length():
    """A mismatched errors array is a caller bug; fail here, not deep inside plotting."""
    hist = Histogram()
    hist.binning = np.linspace(0.0, 5.0, 6)
    entry = HistogramEntry(
        name="pre",
        counts=np.array([10.0, 20.0, 30.0, 40.0, 50.0]),
        errors=np.array([1.0, 1.0, 1.0]),
    )

    with pytest.raises(ValueError, match=r"'pre'.*3 errors.*5 counts"):
        hist.add_entry(entry)


def test_sum_entries_keeps_the_propagated_errors():
    """Issue #37: __iadd__ quadrature-sums errors; add_entry must not replace them.

    Both inputs are pre-binned with errors that are not sqrt(counts), so the correct
    result -- sqrt(a**2 + b**2) -- differs from the sqrt(total counts) the broken code
    produced.
    """
    hist = Histogram()
    hist.binning = np.array([0.0, 1.0, 2.0])
    hist.add_entry(HistogramEntry(name="a", counts=np.array([4.0, 9.0]), errors=np.array([3.0, 4.0])))
    hist.add_entry(HistogramEntry(name="b", counts=np.array([12.0, 7.0]), errors=np.array([4.0, 3.0])))

    hist.sum_entries(["a", "b"], name="combined")

    combined = hist.entries["combined"]
    expected = np.array([5.0, 5.0])  # sqrt(3**2 + 4**2), sqrt(4**2 + 3**2)
    assert np.allclose(combined.counts, [16.0, 16.0])
    # The broken behaviour returned sqrt(16) == 4.0 per bin; the correct answer is 5.0.
    assert not np.allclose(expected, np.sqrt(combined.counts))
    assert np.allclose(combined.errors, expected)


def test_loaded_entries_survive_being_re_added(tmp_path):
    """Issue #37: Histogram.load restores authoritative errors; re-adding must not corrupt them."""
    counts = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    errors = np.array([1.5, 2.5, 3.5, 4.5, 5.5])
    assert not np.allclose(errors, np.sqrt(counts))

    hist = Histogram()
    hist.binning = np.linspace(0.0, 5.0, 6)
    hist.add_entry(HistogramEntry(name="bkg", counts=counts, errors=errors))

    path = tmp_path / "h.json"
    hist.save(path)
    restored = Histogram.load(path)

    rebuilt = Histogram()
    rebuilt.binning = restored.binning
    rebuilt.add_entry(restored.entries["bkg"])

    assert np.allclose(rebuilt.entries["bkg"].errors, errors)


def test_add_entry_coerces_list_valued_errors_to_an_ndarray(tmp_path):
    """A list-valued errors must be coerced to an ndarray, not stored verbatim.

    Before add_entry normalized this, a plain list survived into the stored entry:
    len() passed the guard, the non-empty check skipped compute_errors, and downstream
    consumers (as_binned_dict's .tolist(), get_total_bin_errors' / __iadd__'s **2) crashed
    far from the cause. Errors here are deliberately not sqrt(counts) -- a fixture whose
    expected value the broken code also produces would prove nothing.
    """
    counts = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    errors = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert not np.allclose(errors, np.sqrt(counts))

    hist = Histogram()
    hist.binning = np.linspace(0.0, 5.0, 6)
    hist.add_entry(HistogramEntry(name="pre", counts=counts, errors=errors))

    stored = hist.entries["pre"].errors
    assert isinstance(stored, np.ndarray)
    assert np.allclose(stored, errors)

    path = tmp_path / "h.json"
    hist.save(path)
    restored = Histogram.load(path)
    assert np.allclose(restored.entries["pre"].errors, errors)
