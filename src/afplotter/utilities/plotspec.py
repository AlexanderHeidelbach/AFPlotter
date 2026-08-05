"""Value-level encoding for plot specifications.

This module knows how to turn the values a plotter holds into JSON-safe data and back.
It knows nothing about plotters themselves -- each plotter's ``save``/``load`` walks its
own attributes through these helpers.
"""

from typing import Any

import numpy as np

PLOT_FORMAT_VERSION = 1
"""Version of the on-disk JSON format written by the plotters' ``save`` methods."""

_NDARRAY_KEY = "__ndarray__"
_TUPLE_KEY = "__tuple__"
_DICT_KEY = "__dict__"
_MARKER_KEYS = frozenset({_NDARRAY_KEY, _TUPLE_KEY, _DICT_KEY})

_JSON_NATIVE = (str, bool, int, float, type(None))


class UnserializableValue(ValueError):
    """Raised when a value cannot be represented in a saved plot specification.

    :param value: The offending value.
    :param where: Optional location fragment set by the caller, e.g. ``"kwarg 'transform'"``.
    """

    def __init__(self, value: Any, where: str | None = None) -> None:
        self.value_type = type(value).__name__
        self.value_repr = repr(value)
        self.where = where
        super().__init__(f"Cannot save a value of type {self.value_type}: {self.value_repr}")


def encode_value(value: Any) -> Any:
    """Convert a value to JSON-safe data.

    ``np.ndarray`` and ``tuple`` are tagged so they survive the round trip as themselves;
    JSON natives pass through; lists and dicts are encoded element-wise. A plain dict whose
    encoded form would collide with one of these markers -- i.e. it has exactly one key equal
    to ``"__ndarray__"``, ``"__tuple__"`` or ``"__dict__"`` -- is itself wrapped in a
    ``"__dict__"`` marker, so :func:`decode_value` can tell it apart from an actual tagged value.

    :param value: The value to encode.
    :return: JSON-safe data.
    :raises UnserializableValue: If the value (or anything nested inside it) has no
        representation -- a live matplotlib object, for instance.
    """
    if isinstance(value, np.ndarray):
        return {_NDARRAY_KEY: value.tolist()}
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, tuple):
        return {_TUPLE_KEY: [encode_value(item) for item in value]}
    if isinstance(value, list):
        return [encode_value(item) for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise UnserializableValue(value)
        encoded = {key: encode_value(item) for key, item in value.items()}
        if len(encoded) == 1 and next(iter(encoded)) in _MARKER_KEYS:
            return {_DICT_KEY: encoded}
        return encoded
    if isinstance(value, _JSON_NATIVE):
        return value
    raise UnserializableValue(value)


def decode_value(data: Any) -> Any:
    """Invert :func:`encode_value`.

    :param data: JSON data written by :func:`encode_value`.
    :return: The restored value.
    """
    if isinstance(data, dict):
        if len(data) == 1:
            (key,) = data
            if key == _NDARRAY_KEY:
                return np.array(data[_NDARRAY_KEY])
            if key == _TUPLE_KEY:
                return tuple(decode_value(item) for item in data[_TUPLE_KEY])
            if key == _DICT_KEY:
                return {inner_key: decode_value(item) for inner_key, item in data[_DICT_KEY].items()}
        return {key: decode_value(item) for key, item in data.items()}
    if isinstance(data, list):
        return [decode_value(item) for item in data]
    return data


_INSET_FIELDS = (
    "xlim",
    "ylim",
    "width",
    "height",
    "loc",
    "borderpad",
    "title",
    "mark_region",
    "mark_kwargs",
    "tick_labelsize",
    "title_fontsize",
    "bbox_to_anchor",
)


def encode_generic_plot(plot: Any, *, skip_unserializable: bool = False) -> tuple[dict[str, Any], list[str]]:
    """Encode one :class:`~afplotter.genericplot.GenericPlot`.

    :param plot: The plot to encode.
    :param skip_unserializable: Drop unserializable *keyword* arguments instead of raising.
        Positional arguments are never dropped -- removing one would shift every later
        argument and silently change the matplotlib call.
    :return: ``(payload, dropped)`` where ``dropped`` lists the descriptors of any skipped
        kwargs, e.g. ``["kwarg 'transform'"]``.
    :raises UnserializableValue: On an unserializable positional argument, or on an
        unserializable kwarg when ``skip_unserializable`` is false.
    """
    args = []
    for index, arg in enumerate(plot.args):
        try:
            args.append(encode_value(arg))
        except UnserializableValue as error:
            error.where = error.where or f"arg {index}"
            raise

    kwargs = {}
    dropped = []
    for key, value in plot.kwargs.items():
        try:
            kwargs[key] = encode_value(value)
        except UnserializableValue as error:
            where = error.where or f"kwarg {key!r}"
            if not skip_unserializable:
                error.where = where
                raise
            dropped.append(where)

    return {"plotmethod": plot.plotmethod, "args": args, "kwargs": kwargs}, dropped


def decode_generic_plot(data: dict[str, Any]) -> Any:
    """Invert :func:`encode_generic_plot`.

    :param data: One payload written by :func:`encode_generic_plot`.
    :return: The restored :class:`~afplotter.genericplot.GenericPlot`.
    """
    from afplotter.genericplot import GenericPlot

    args = [decode_value(arg) for arg in data["args"]]
    kwargs = {key: decode_value(value) for key, value in data["kwargs"].items()}
    return GenericPlot(data["plotmethod"], *args, **kwargs)


def encode_inset(inset: Any, plot_refs: dict[str, Any]) -> dict[str, Any]:
    """Encode one :class:`~afplotter.genericplot.InsetPlot`.

    The inset's ``plots`` are stored as the caller's symbolic reference block rather than
    by value: they are the *same objects* the main axes replays, and copying them would
    turn "the whole plot, zoomed" into a frozen duplicate on load.

    :param inset: The inset to encode.
    :param plot_refs: Symbolic references to the plotter's own objects, stored verbatim.
    :return: JSON-safe data.
    :raises UnserializableValue: If any of the inset's own settings cannot be encoded.
    """
    data = {field: encode_value(getattr(inset, field)) for field in _INSET_FIELDS}
    data["plots"] = plot_refs
    return data


def decode_inset(data: dict[str, Any], resolved_plots: list[Any]) -> Any:
    """Invert :func:`encode_inset`.

    :param data: One payload written by :func:`encode_inset`.
    :param resolved_plots: The live plot objects the caller resolved ``data["plots"]`` to.
    :return: The restored :class:`~afplotter.genericplot.InsetPlot`.
    """
    from afplotter.genericplot import InsetPlot

    settings = {field: decode_value(data[field]) for field in _INSET_FIELDS}
    return InsetPlot(plots=resolved_plots, **settings)
