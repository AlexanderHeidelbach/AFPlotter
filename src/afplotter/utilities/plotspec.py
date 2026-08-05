"""Value-level encoding for plot specifications.

This module knows how to turn the values a plotter holds into JSON-safe data and back.
It knows nothing about plotters themselves -- each plotter's ``save``/``load`` walks its
own attributes through these helpers.
"""

import os
import warnings
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
        item = value.item()
        if isinstance(item, _JSON_NATIVE):
            return item
        raise UnserializableValue(value)
    if isinstance(value, os.PathLike):
        path = os.fspath(value)
        if isinstance(path, str):
            return path
        raise UnserializableValue(value)
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
    data = {}
    for field in _INSET_FIELDS:
        try:
            data[field] = encode_value(getattr(inset, field))
        except UnserializableValue as error:
            error.where = error.where or field
            raise
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


BASE_PLOTTER_FIELDS = (
    "figsize",
    "label",
    "xlabel",
    "ylabel",
    "watermark",
    "luminosity_value",
    "luminosity_unit",
    "log",
    "xlog",
    "legend_max_rows",
    "legend_title",
    "legend_loc",
    "xlim",
    "ylim",
    "savedir",
    "saveformat",
    "savename",
    "savepath",
    "watermark_position",
    "text",
    "generic_text",
)
"""Every :class:`~afplotter.baseplotter.BasePlotter` attribute a saved plot carries.

Hardcoded rather than scraped from ``vars()``: a hardcoded list fails loudly when someone
adds a property and forgets it here, whereas scraping would silently start persisting
private state -- including live matplotlib objects.
"""


def _field_attribute(plotter: Any, field: str) -> str:
    """Return the attribute name backing ``field`` -- the private one where it exists."""
    private = f"_{field}"
    return private if hasattr(plotter, private) else field


def encode_base_plotter(plotter: Any) -> dict[str, Any]:
    """Encode the shared :class:`~afplotter.baseplotter.BasePlotter` attribute block.

    :param plotter: Any plotter deriving from ``BasePlotter``.
    :return: JSON-safe data.
    :raises UnserializableValue: If any field holds a value with no representation.
    """
    data = {}
    for field in BASE_PLOTTER_FIELDS:
        try:
            data[field] = encode_value(getattr(plotter, _field_attribute(plotter, field)))
        except UnserializableValue as error:
            error.where = error.where or f"{field}"
            raise
    return data


def decode_base_plotter(plotter: Any, data: dict[str, Any]) -> None:
    """Restore the shared attribute block onto ``plotter``, in place.

    Values are written to the *private* attributes: ``HistogramPlotter`` and
    ``Histogram2DPlotter`` override ``xlabel``/``ylabel`` as read-only properties, so
    assigning through the public name would raise.

    :param plotter: The plotter to populate.
    :param data: The block written by :func:`encode_base_plotter`.
    :return: None
    """
    for field in BASE_PLOTTER_FIELDS:
        if field in data:
            setattr(plotter, _field_attribute(plotter, field), decode_value(data[field]))


def warn_dropped(dropped: list[str]) -> None:
    """Emit one ``UserWarning`` naming everything a ``save`` dropped, if anything was.

    :param dropped: Descriptors recorded in the file's ``"dropped"`` list.
    :return: None
    """
    if dropped:
        warnings.warn(
            f"This plot was saved with skip_unserializable=True; {len(dropped)} element(s) "
            f"were dropped and are missing from the loaded plot: {', '.join(dropped)}",
            UserWarning,
            stacklevel=2,
        )
