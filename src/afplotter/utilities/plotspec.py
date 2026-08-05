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
    JSON natives pass through; lists and dicts are encoded element-wise.

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
        return {key: encode_value(item) for key, item in value.items()}
    if isinstance(value, _JSON_NATIVE):
        return value
    raise UnserializableValue(value)


def decode_value(data: Any) -> Any:
    """Invert :func:`encode_value`.

    :param data: JSON data written by :func:`encode_value`.
    :return: The restored value.
    """
    if isinstance(data, dict):
        if _NDARRAY_KEY in data:
            return np.array(data[_NDARRAY_KEY])
        if _TUPLE_KEY in data:
            return tuple(decode_value(item) for item in data[_TUPLE_KEY])
        return {key: decode_value(item) for key, item in data.items()}
    if isinstance(data, list):
        return [decode_value(item) for item in data]
    return data
