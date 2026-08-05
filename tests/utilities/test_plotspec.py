import json

import numpy as np
import pytest

from afplotter.genericplot import GenericPlot, InsetPlot
from afplotter.utilities.plotspec import (
    PLOT_FORMAT_VERSION,
    UnserializableValue,
    decode_generic_plot,
    decode_inset,
    decode_value,
    encode_generic_plot,
    encode_inset,
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


def test_encode_value_rejects_an_unserializable_numpy_scalar():
    """np.generic.item() is not validated before finding #38's fix -- np.complex128.item()
    returns a Python complex, which is not JSON-native and previously reached json.dumps
    unchecked, raising a bare TypeError there instead of UnserializableValue here."""
    with pytest.raises(UnserializableValue) as excinfo:
        encode_value(np.complex128(1 + 2j))
    assert "complex128" in excinfo.value.value_type


def test_encode_value_rejects_an_unserializable_numpy_datetime_scalar():
    with pytest.raises(UnserializableValue):
        encode_value(np.datetime64("2024-01-01"))


def test_encode_value_encodes_a_pathlike_savedir_as_a_string():
    from pathlib import Path

    encoded = encode_value(Path("/tmp/out"))
    json.dumps(encoded)
    assert encoded == "/tmp/out"
    assert decode_value(encoded) == "/tmp/out"


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


def test_encode_generic_plot_round_trips_method_args_and_kwargs():
    plot = GenericPlot("errorbar", np.array([1.0, 2.0]), np.array([3.0, 4.0]), color="red", ls="--")
    data, dropped = encode_generic_plot(plot)
    assert dropped == []
    json.dumps(data)

    restored = decode_generic_plot(data)
    assert restored.plotmethod == "errorbar"
    assert np.allclose(restored.args[0], [1.0, 2.0])
    assert np.allclose(restored.args[1], [3.0, 4.0])
    assert restored.kwargs == {"color": "red", "ls": "--"}


def test_encode_generic_plot_raises_on_an_unserializable_kwarg():
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    plot = GenericPlot("plot", np.array([1.0]), transform=ax.transAxes)
    with pytest.raises(UnserializableValue) as excinfo:
        encode_generic_plot(plot)
    plt.close("all")
    assert excinfo.value.where == "kwarg 'transform'"


def test_encode_generic_plot_skips_an_unserializable_kwarg_when_asked():
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    plot = GenericPlot("plot", np.array([1.0]), color="red", transform=ax.transAxes)
    data, dropped = encode_generic_plot(plot, skip_unserializable=True)
    plt.close("all")

    assert dropped == ["kwarg 'transform'"]
    restored = decode_generic_plot(data)
    assert restored.kwargs == {"color": "red"}  # the serializable kwarg survives


def test_encode_generic_plot_never_skips_a_positional_arg():
    """Dropping a positional would shift every later argument and change the call."""
    from matplotlib import pyplot as plt

    ax = plt.subplots()[1]
    plot = GenericPlot("plot", ax.transAxes, np.array([1.0]))
    with pytest.raises(UnserializableValue) as excinfo:
        encode_generic_plot(plot, skip_unserializable=True)
    plt.close("all")
    assert excinfo.value.where == "arg 0"


def test_encode_inset_round_trips_its_settings_and_reference_block():
    inset = InsetPlot(
        plots=[],
        xlim=(1.0, 2.0),
        ylim=(3.0, 4.0),
        width="50%",
        height="25%",
        loc="lower left",
        borderpad=2.0,
        title="zoom",
        mark_region=False,
        mark_kwargs={"ec": "red"},
        tick_labelsize=6,
        title_fontsize=11,
        bbox_to_anchor=(0.1, 0.2, 0.3, 0.4),
    )
    refs = {"histplot": True, "generic_plots": [0, 1]}
    data = encode_inset(inset, refs)
    json.dumps(data)
    assert data["plots"] == refs

    sentinel = [object(), object()]
    restored = decode_inset(data, sentinel)
    assert restored.plots is sentinel
    assert restored.xlim == (1.0, 2.0)
    assert isinstance(restored.xlim, tuple)
    assert restored.ylim == (3.0, 4.0)
    assert restored.width == "50%"
    assert restored.height == "25%"
    assert restored.loc == "lower left"
    assert restored.borderpad == 2.0
    assert restored.title == "zoom"
    assert restored.mark_region is False
    assert restored.mark_kwargs == {"ec": "red"}
    assert restored.tick_labelsize == 6
    assert restored.title_fontsize == 11
    assert restored.bbox_to_anchor == (0.1, 0.2, 0.3, 0.4)
