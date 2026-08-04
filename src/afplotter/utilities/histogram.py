import copy
import json
from collections import defaultdict
from pathlib import Path
import numpy as np  # type: ignore
from typing import Any
from dataclasses import dataclass, field, asdict

SAVE_FORMAT_VERSION = 1
"""Version of the on-disk JSON format written by :meth:`Histogram.save`."""


@dataclass
class HistogramEntry:
    name: str = ""
    latex_name: str = ""
    array: np.ndarray | None = None
    counts: np.ndarray = field(default_factory=lambda: np.array([]))
    errors: np.ndarray = field(default_factory=lambda: np.array([]))
    weight: float | np.ndarray = 1.0
    color: str | None = None
    hatch: str | None = None
    show_label: bool = True
    type: str = "entry"

    def __add__(self, other: "HistogramEntry") -> "HistogramEntry":
        if len(self.counts) != len(other.counts):
            raise ValueError(
                f"The two HistogramEntries {self.name} and {other.name}" "have different binns. They cannot be added."
            )
        return HistogramEntry(
            counts=self.counts + other.counts,
            errors=np.sqrt(self.errors**2 + other.errors**2),
        )

    def __iadd__(self, other: "HistogramEntry") -> "HistogramEntry":
        if len(self.counts) == 0:
            self.counts = other.counts
            self.errors = other.errors
        elif len(self.counts) == len(other.counts):
            self.counts += other.counts
            self.errors = np.sqrt(self.errors**2 + other.errors**2)
        else:
            raise ValueError(
                f"The two HistogramEntries {self.name} and {other.name}" "have different binns. They cannot be added."
            )
        self.clear_array()
        return self

    @property
    def as_dict(self) -> dict[str, Any]:
        """Converts the instance to a serializable dictionary."""
        data = asdict(self)  # Convert to dictionary
        # Convert numpy arrays to lists
        for key in ["array", "counts", "errors"]:
            if isinstance(data[key], np.ndarray):
                data[key] = data[key].tolist()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistogramEntry":
        """Creates an instance from a dictionary."""
        # Convert lists back to numpy arrays
        for key in ["array", "counts", "errors"]:
            if data.get(key) is not None:
                data[key] = np.array(data[key])
        return cls(**data)

    def get_weights(self, pot: float = 1.0) -> np.ndarray:
        return np.ones_like(self.array) * self.weight**pot

    def compute_counts(self, binning: np.ndarray | int) -> np.ndarray:
        assert self.array is not None, (
            f"The array for the HistogramEntry {self.name} is not set."
            + "Either this method was called too early or the array was already cleared."
        )
        self.counts, edges = np.histogram(self.array, bins=binning, weights=self.get_weights())
        return edges

    def compute_errors(self, binning: np.ndarray) -> None:
        if self.array is not None:
            bin_errors_squared, _ = np.histogram(
                self.array,
                bins=binning,
                weights=self.get_weights(pot=2.0),
            )
            self.errors = np.sqrt(bin_errors_squared)
        else:
            self.errors = np.sqrt(self.counts)

    def clear_array(self) -> None:
        self.array = None


class Histogram:
    def __init__(self) -> None:
        self._binning: np.ndarray | int | None = None
        self.entries: dict[str, HistogramEntry] = defaultdict(lambda: HistogramEntry())
        self.signal: dict[str, HistogramEntry] = defaultdict(lambda: HistogramEntry())
        self.metadata: dict[Any, Any] = {}

    @property
    def as_dict(self) -> dict[str, Any]:
        binning = (
            self.binning
            if isinstance(self.binning, int)
            else self.binning.tolist()
            if self.binning is not None
            else None
        )
        data = {
            "binning": binning,
            "metadata": self.metadata,
            "entries": {name: entry.as_dict for name, entry in self.entries.items()},
            "signal": {name: entry.as_dict for name, entry in self.signal.items()},
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Histogram":
        instance = cls()
        instance.binning = np.array(data["binning"]) if data["binning"] is not None else None
        instance.metadata = data["metadata"]
        instance.entries = {name: HistogramEntry.from_dict(entry_data) for name, entry_data in data["entries"].items()}
        instance.signal = {name: HistogramEntry.from_dict(entry_data) for name, entry_data in data["signal"].items()}
        return instance

    def save(self, path: str | Path) -> None:
        """Write this histogram to a JSON file, without its raw event data.

        Only binned results are stored — counts, errors, binning, metadata and per-entry
        styling. Each entry's ``array`` is omitted, so the file size does not grow with the
        sample size. The histogram in memory is left untouched.

        A histogram loaded from such a file cannot be used for a 2D plot, because
        :class:`~afplotter.histogramplot.Histogram2DPlot` bins raw arrays at plot time.

        :param path: Destination file path. Any parent directory must already exist.
        """
        payload = copy.deepcopy(self.as_dict)
        for section in ("entries", "signal"):
            for entry in payload[section].values():
                entry["array"] = None
        payload["format_version"] = SAVE_FORMAT_VERSION
        Path(path).write_text(json.dumps(payload))

    @classmethod
    def load(cls, path: str | Path) -> "Histogram":
        """Read a histogram written by :meth:`save`.

        The returned histogram has no raw event data: ``get_data()`` yields ``None`` for
        every entry.

        :param path: Path to a JSON file written by :meth:`save`.
        :return: The reconstructed histogram.
        :raises ValueError: If the file's ``format_version`` is not supported.
        """
        payload = json.loads(Path(path).read_text())
        version = payload.get("format_version")
        if version != SAVE_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported format_version {version!r} in {path}; "
                f"this version of AFPlotter writes and reads format_version {SAVE_FORMAT_VERSION}."
            )
        return cls.from_dict(payload)

    @property
    def binning(self) -> np.ndarray | int | None:
        return self._binning

    @binning.setter
    def binning(self, bins: np.ndarray | int | None) -> None:
        self._binning = bins

    @property
    def column_name(self) -> str:
        return self.metadata.get("column_name", "")

    @property
    def filters(self) -> list[Any]:
        return self.metadata.get("filters", [])

    def add_entry(self, entry: HistogramEntry, clear: bool = False) -> None:
        if self.binning is None:
            raise ValueError("Binning not set")

        if len(entry.counts) == 0:
            edges = entry.compute_counts(binning=self.binning)
            if isinstance(self.binning, int):
                self.binning = edges

        binning = self.binning
        if isinstance(binning, int):
            raise ValueError("Binning was not resolved to an array before computing entry errors")
        entry.compute_errors(binning=binning)

        if clear:
            entry.clear_array()

        if entry.type == "entry":
            self.entries[entry.name] = entry
        elif entry.type == "signal":
            self.signal[entry.name] = entry
        else:
            raise ValueError("Entry type not recognized")

    def get_entry(self, name: str) -> HistogramEntry:
        return self.entries[name]

    def remove_entry(self, name: str) -> None:
        if name in self.entries:
            del self.entries[name]
        else:
            raise KeyError(f"Entry '{name}' not found in histogram.")

    def sum_entries(
        self,
        entries: list[str],
        name: str = "",
        latex_name: str = "",
        color: str | None = None,
        hatch: str | None = None,
        type: str = "entry",
    ) -> None:
        new_entry = HistogramEntry(name=name, latex_name=latex_name, color=color, hatch=hatch, type=type)
        try:
            for entry_name in entries:
                new_entry += self.get_entry(entry_name)

            self.add_entry(new_entry)
        finally:
            for entry_name in entries:
                self.remove_entry(entry_name)

    def get_data(self) -> list[np.ndarray | None]:
        return list(entry.array for entry in self.entries.values())

    def get_signal_data(self) -> list[np.ndarray | None]:
        return list(entry.array for entry in self.signal.values())

    def get_names(self) -> list[str]:
        return list(entry.name for entry in self.entries.values())

    def get_latex_names(self) -> list[str] | None:
        if any(not entry.show_label for entry in self.entries.values()):
            return None
        else:
            return list(entry.latex_name if entry.latex_name else entry.name for entry in self.entries.values())

    def get_stacked_latex_names(self) -> list[str] | None:
        """Legend labels for every stack layer, bottom first — entries, then signal."""
        names = self.get_latex_names()
        if names is None:
            return None
        return names + self.get_signal_latex_names()

    def get_signal_names(self) -> list[str]:
        return list(entry.name for entry in self.signal.values())

    def get_signal_latex_names(self) -> list[str]:
        return list(entry.latex_name if entry.latex_name else entry.name for entry in self.signal.values())

    def get_colors(self) -> list[str | None]:
        return list(entry.color for entry in self.entries.values())

    def get_signal_colors(self) -> list[str | None]:
        return list(entry.color for entry in self.signal.values())

    def get_hatches(self) -> list[str | None]:
        return list(entry.hatch for entry in self.entries.values())

    def get_bin_centers(self) -> list[np.ndarray]:
        assert not isinstance(self.binning, int)
        assert self.binning is not None

        bin_mids = [(self.binning[i] + self.binning[i + 1]) / 2 for i in range(0, len(self.binning) - 1)]
        entries = self.entries if self.entries else self.signal
        return [np.array(bin_mids) for _ in entries]

    def get_stacked_bin_centers(self) -> list[np.ndarray]:
        """Bin centers repeated once per stack layer (entries, then signal)."""
        assert not isinstance(self.binning, int)
        assert self.binning is not None

        bin_mids = np.array([(self.binning[i] + self.binning[i + 1]) / 2 for i in range(0, len(self.binning) - 1)])
        return [bin_mids for _ in range(len(self.entries) + len(self.signal))]

    def get_bin_width(self) -> float:
        assert not isinstance(self.binning, int)
        assert self.binning is not None

        return self.binning[1] - self.binning[0]

    def get_bin_count_for_entry(self, entry: HistogramEntry) -> np.ndarray:
        return entry.counts

    def get_bin_counts(self) -> list[np.ndarray]:
        return [self.get_bin_count_for_entry(entry) for entry in self.entries.values()]

    def get_raw_signal_bin_counts(self) -> list[np.ndarray]:
        """Signal counts at their true yield, i.e. what is stacked and summed.

        Contrast :meth:`get_signal_bin_counts`, which peak-matches the signal to the
        background stack for the ``sig_extra`` outline overlay.
        """
        return [self.get_bin_count_for_entry(entry) for entry in self.signal.values()]

    def get_raw_signal_bin_errors(self) -> list[np.ndarray]:
        """Signal errors at their true yield. See :meth:`get_raw_signal_bin_counts`."""
        return [self.get_bin_error_for_entry(entry=entry) for entry in self.signal.values()]

    def get_stacked_bin_counts(self) -> list[np.ndarray]:
        """Bin counts of every stack layer, bottom first — entries, then signal on top."""
        return self.get_bin_counts() + self.get_raw_signal_bin_counts()

    def get_total_bin_count(self) -> np.ndarray:
        # The modelled total is signal + background: both entries and signal are
        # model components, and signal is a layer of the stack.
        return np.sum(self.get_stacked_bin_counts(), axis=0)

    def get_total_scale(self) -> float:
        return float(np.sum(self.get_total_bin_count() * self.get_bin_width()))

    def get_bin_error_for_entry(self, entry: HistogramEntry) -> np.ndarray:
        return entry.errors

    def get_bin_errors(self) -> list[np.ndarray]:
        return [self.get_bin_error_for_entry(entry=entry) for entry in self.entries.values()]

    def get_stacked_bin_errors(self) -> list[np.ndarray]:
        """Bin errors of every stack layer, bottom first — entries, then signal on top."""
        return self.get_bin_errors() + self.get_raw_signal_bin_errors()

    def get_total_bin_errors(self) -> np.ndarray:
        return np.sqrt(np.sum([errors**2 for errors in self.get_stacked_bin_errors()], axis=0))

    def get_signal_bin_count_for_component(self, entry: HistogramEntry) -> tuple[np.ndarray, float]:
        bin_count = self.get_bin_count_for_entry(entry=entry).astype(float)
        scaling = 1
        if self.entries:
            max_bin_count = np.max(bin_count)
            max_bin_counts = np.max(np.sum(self.get_bin_counts(), axis=0))
            scaling = max_bin_counts / max_bin_count if max_bin_count != 0 else 1

        bin_count *= scaling

        return bin_count, scaling

    def get_signal_bin_counts(self) -> list[np.ndarray]:
        signal_bin_counts = []  # type: list[np.ndarray]
        for entry in self.signal.values():
            bin_count, _ = self.get_signal_bin_count_for_component(entry=entry)
            signal_bin_counts.append(bin_count)
        return signal_bin_counts

    def get_total_signal_bin_count(self) -> np.ndarray:
        return np.sum(self.get_signal_bin_counts(), axis=0)

    def get_total_signal_scale(self) -> float:
        return float(np.sum(self.get_total_signal_bin_count() * self.get_bin_width()))

    def get_signal_bin_error_for_entry(self, entry: HistogramEntry) -> np.ndarray:
        _, scaling = self.get_signal_bin_count_for_component(entry=entry)
        return scaling * self.get_bin_error_for_entry(entry=entry)

    def get_signal_bin_errors(self) -> list[np.ndarray]:
        return [self.get_signal_bin_error_for_entry(entry=entry) for entry in self.signal.values()]

    def get_scale(self) -> float:
        return np.max([self.get_total_scale(), self.get_total_signal_scale()])

    def order_entries(self, entry_name: list[str]) -> None:
        if len(entry_name) != len(self.entries):
            raise ValueError("The number of entries to order does not match the number of entries.")
        self.entries = {name: self.entries[name] for name in entry_name}
