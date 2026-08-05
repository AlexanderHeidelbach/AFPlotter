import json

import numpy as np
import pytest

from afplotter.utilities.plotspec import (
    PLOT_FORMAT_VERSION,
    UnserializableValue,
    decode_value,
    encode_value,
)


def test_plot_format_version_is_one():
    assert PLOT_FORMAT_VERSION == 1


@pytest.mark.parametrize("value", ["a", 1, 2.5, True, None, [1, 2], {"k": 1}])
def test_encode_value_passes_json_natives_through(value):
    assert encode_value(value) == value
    assert decode_value(encode_value(value)) == value


def test_encode_value_round_trips_an_ndarray_as_an_ndarray():
    """A list would render identically here but breaks callers that do arithmetic on args."""
    array = np.array([1.5, 2.5, 3.5])
    encoded = encode_value(array)
    json.dumps(encoded)  # must survive a real serialization, not just look serializable
    restored = decode_value(encoded)
    assert isinstance(restored, np.ndarray)
    assert np.allclose(restored, array)


def test_encode_value_round_trips_a_tuple_as_a_tuple():
    """JSON collapses tuples to lists; figsize/xlim/watermark_position must come back tuples."""
    encoded = encode_value((12, 8))
    json.dumps(encoded)
    restored = decode_value(encoded)
    assert isinstance(restored, tuple)
    assert restored == (12, 8)


def test_encode_value_recurses_into_containers():
    encoded = encode_value({"lims": (0.0, 1.0), "data": [np.array([1.0, 2.0])]})
    json.dumps(encoded)
    restored = decode_value(encoded)
    assert restored["lims"] == (0.0, 1.0)
    assert isinstance(restored["lims"], tuple)
    assert isinstance(restored["data"][0], np.ndarray)
    assert np.allclose(restored["data"][0], [1.0, 2.0])


def test_encode_value_rejects_a_live_matplotlib_object():
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    with pytest.raises(UnserializableValue) as excinfo:
        encode_value(ax.transAxes)
    plt.close("all")
    assert "Transform" in excinfo.value.value_type


@pytest.mark.parametrize("marker_key", ["__ndarray__", "__tuple__"])
def test_encode_value_round_trips_a_plain_dict_with_a_marker_key_among_others(marker_key):
    """A real dict that happens to use a marker key alongside other keys must not be
    mistaken for a tagged ndarray/tuple -- both keys must survive the round trip."""
    value = {marker_key: 5, "other": "stuff"}
    encoded = encode_value(value)
    json.dumps(encoded)
    restored = decode_value(encoded)
    assert restored == value
    assert isinstance(restored, dict)


@pytest.mark.parametrize("marker_key", ["__ndarray__", "__tuple__"])
def test_encode_value_round_trips_a_plain_dict_whose_only_key_is_a_marker(marker_key):
    """A single-key dict literally named after a marker must decode back to a dict,
    not to an np.ndarray/tuple -- this is the exact collision the codec must refuse to drop."""
    value = {marker_key: 5}
    encoded = encode_value(value)
    json.dumps(encoded)
    restored = decode_value(encoded)
    assert restored == value
    assert isinstance(restored, dict)


def test_encode_value_rejects_an_unserializable_value_nested_in_a_container():
    """A container must not smuggle a live object past the check."""
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    with pytest.raises(UnserializableValue):
        encode_value({"transform": ax.transAxes})
    plt.close("all")
