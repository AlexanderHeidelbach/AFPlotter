import hashlib
from collections import defaultdict
from copy import deepcopy
from enum import Enum
from typing import Any
from pathlib import Path

import polars as pl
import numpy as np

from afplotter.utilities.histogram import Histogram, HistogramEntry
from afplotter.selectionparser.polars import SelectionParser


class LazyHistEntry(HistogramEntry):
    def __init__(
        self,
        name: str,
        input: pl.LazyFrame | Path | str | list[pl.LazyFrame] | list[Path] | list[str],
        prefilter: str | None = None,  # Assume prefilter is a query string
        *args,
        **kwargs,
    ) -> None:
        super().__init__(name, *args, **kwargs)
        self.input = input
        self.prefilter = prefilter
        self.data = self._get_data()

    def _get_data(self) -> pl.LazyFrame:
        data = pl.LazyFrame()
        if isinstance(self.input, (Path, str)):
            data = pl.scan_parquet(str(self.input))
        elif isinstance(self.input, list):
            if all(isinstance(d, (Path, str)) for d in self.input):
                data = pl.concat([pl.scan_parquet(str(d)) for d in self.input])
            elif all(isinstance(d, pl.LazyFrame) for d in self.input):
                data = pl.concat(self.input)  # type: ignore
            else:
                raise ValueError("All elements in the data list must be of the same type (Path/str or LazyFrame).")
        elif isinstance(self.input, pl.LazyFrame):
            data = self.input
        else:
            raise ValueError("Data must be a LazyFrame, a path/str, or a list of LazyFrames/paths/str.")

        # Apply query-string-based prefilter if provided
        if self.prefilter:
            try:
                expr = SelectionParser(self.prefilter).parse()
                data = data.filter(expr)
            except Exception as e:
                raise ValueError(f"Failed to parse selection query: {e}")

        return data


class WrapperState(Enum):
    INIT = "init"
    DATA = "data"
    HIST = "hist"
    EXECUTED = "executed"
    DONE = "done"


class LazyState:
    def __init__(self) -> None:
        self.state = WrapperState.INIT

    def set_state(self, new_state):
        if isinstance(new_state, WrapperState):
            self.state: WrapperState = new_state
        else:
            raise ValueError(f"Invalid state: {new_state}")

    def get_state(self) -> WrapperState:
        return self.state

    def is_state(self, check_state: WrapperState) -> bool:
        return self.state.value == check_state.value

    @property
    def is_preparation(self) -> bool:
        return self.is_state(WrapperState.INIT) or self.is_state(WrapperState.DATA)

    @property
    def is_production(self) -> bool:
        return self.is_state(WrapperState.HIST) or self.is_state(WrapperState.DATA)

    @property
    def name(self) -> str:
        return self.state.value


class LazyHistWrapper:
    def __init__(self) -> None:
        self.entries: dict[str, LazyHistEntry] = {}
        self.hist_configs: dict[str, dict[str, Any]] = {}
        self.state: LazyState = LazyState()
        self.histograms: dict[str, Histogram] = defaultdict(lambda: Histogram())

        self.histograms2D: dict[str, dict[str, Histogram]] = defaultdict(
            lambda: {
                "x": Histogram(),
                "y": Histogram(),
            }
        )

    @staticmethod
    def get_uid(
        column: str,
        bins: np.ndarray,
        filters: str | None = None,
        entries_to_hist: list[str] | str | None = None,
    ) -> str:
        """
        Generate a unique identifier for a histogram configuration
        based on the column, bins, filters, and entries_to_hist parameters.
        """
        # Convert parameters into a string and hash them
        config_string = f"{column}_{bins}_{filters}_{entries_to_hist}"
        return hashlib.sha256(config_string.encode()).hexdigest()

    @staticmethod
    def get_bins(
        bins: np.ndarray | list[float] | tuple[float, float, int],
    ) -> np.ndarray:
        array_bins = np.array([])
        if isinstance(bins, tuple):
            array_bins = np.linspace(bins[0], bins[1], bins[2] if len(bins) == 3 else 50)
        elif isinstance(bins, list):
            array_bins = np.array(bins)
        elif isinstance(bins, int):
            raise ValueError(
                "Bins must be a list-like object or a 2-/3-tuple (start, stop, num). Integers are not allowed."
            )
        else:
            array_bins = bins

        return array_bins

    def add_lazy_entry(self, entries: LazyHistEntry | list[LazyHistEntry]) -> None:
        if not self.state.is_preparation:
            raise Exception("Can only add lazy entries before querying histograms")

        entries = [entries] if isinstance(entries, LazyHistEntry) else entries
        self.entries.update({entry.name: entry for entry in entries})
        self.state.set_state(WrapperState.DATA)

    def add_hist(
        self,
        column: str,
        bins: np.ndarray | list | tuple,
        identifier: str = "",
        filters: str | None = None,
        entries_to_hist: list[str] | None = None,
        weight: bool = True,
        factor: float | None = 1.0,
    ) -> None:
        if not self.state.is_production:
            raise Exception(
                f"Can only add histograms after data and before execution, but found state: {self.state.name}"
            )

        if identifier in self.hist_configs.keys():
            raise ValueError(f"Identifier '{identifier}' already exists.")

        array_bins = self.get_bins(bins)

        uid = identifier if identifier else self.get_uid(column, array_bins, filters, entries_to_hist)

        # Store histogram configuration and metadata
        self.hist_configs[uid] = {
            "type": "1D",
            "column": column,
            "bins": array_bins,
            "filters": filters,
            "entries_to_hist": entries_to_hist,
            "factor": factor,
            "uid": uid,
            "weight": weight,
        }

        self.state.set_state(WrapperState.HIST)

    def add_hist2d(
        self,
        xcolumn: str,  # Column name for the x-axis of the 2D histogram
        ycolumn: str,  # Column name for the y-axis of the 2D histogram
        xbins: np.ndarray | list[float] | tuple[float, float, int],  # Binning for the x-axis
        ybins: np.ndarray | list[float] | tuple[float, float, int],  # Binning for the y-axis
        entries_to_hist: str | list[str],  # Single or multiple entries to consider for the histogram
        identifier: str = "",
        filters: str | None = None,
        xfactor: float | None = 1.0,
        yfactor: float | None = 1.0,
    ):
        if not self.state.is_production:
            raise Exception(
                f"Can only add histograms after data and before execution, but found state: {self.state.name}"
            )
        if identifier in self.hist_configs.keys():
            raise ValueError(f"Identifier '{identifier}' already exists.")

        array_xbins = self.get_bins(xbins)
        array_ybins = self.get_bins(ybins)

        uid = (
            identifier
            if identifier
            else self.get_uid(
                xcolumn + ycolumn,
                np.append(array_xbins, array_ybins),
                filters,
                entries_to_hist,
            )
        )

        self.hist_configs[uid] = {
            "type": "2D",
            "xcolumn": xcolumn,
            "ycolumn": ycolumn,
            "xbins": xbins,
            "ybins": ybins,
            "filters": filters,
            "entries_to_hist": entries_to_hist,
            "xfactor": xfactor,
            "yfactor": yfactor,
            "uid": uid,
        }
        self.state.set_state(WrapperState.HIST)

    def lazy_execute(self) -> None:
        if not self.state.is_state(WrapperState.HIST):
            raise Exception(f"Can only execute after adding hists, but found state: {self.state.name}")

        # Iterate over all entries to handle their histograms
        for entry_name, entry in self.entries.items():
            relevant_hists = [
                config
                for config in self.hist_configs.values()
                if (
                    config["entries_to_hist"] is None  # Applies to all entries
                    or (isinstance(config["entries_to_hist"], list) and entry_name in config["entries_to_hist"])
                    or entry_name == config["entries_to_hist"]
                )
            ]

            if not relevant_hists:
                continue

            lf = entry.data
            lf_list: list[pl.LazyFrame] = []
            uid_list: list[str] = []

            for hist in relevant_hists:
                filtered_lf = lf
                # Apply string-based filter using SelectionParser
                if hist["filters"]:
                    try:
                        expr = SelectionParser(hist["filters"]).parse()
                        filtered_lf = lf.filter(expr)
                    except Exception as e:
                        raise ValueError(f"Failed to parse filter for histogram {hist['uid']}: {e}")

                interessted_columns = []
                if hist["type"] == "1D":
                    interessted_columns.append(hist["column"])
                    if "weight" in lf.collect_schema().names() and hist["weight"]:
                        interessted_columns.append("weight")

                elif hist["type"] == "2D":
                    interessted_columns.append(hist["xcolumn"])
                    interessted_columns.append(hist["ycolumn"])

                else:
                    raise ValueError(f"Unsupported histogram type: {hist['type']}")
                lf_list.append(filtered_lf.select(interessted_columns))
                uid_list.append(hist["uid"])

            for uid, batch in zip(
                uid_list,
                pl.collect_all(lf_list, predicate_pushdown=False),
            ):
                config = self.hist_configs[uid]

                if config["type"] == "1D":
                    data = batch.to_numpy()
                    hist_entry = deepcopy(entry)
                    try:
                        hist_entry.array = data[:, 0] * config["factor"]
                        hist_entry.weight = data[:, 1]
                    except IndexError:
                        hist_entry.array = data[:, 0] * config["factor"]

                    self.histograms[uid].binning = config["bins"]
                    self.histograms[uid].add_entry(hist_entry, clear=True)
                    self.histograms[uid].metadata.update({"column_name": config["column"]})
                    self.histograms[uid].metadata.update({"filters": config["filters"]})

                elif config["type"] == "2D":
                    data = batch.to_numpy()
                    hist_xentry = deepcopy(entry)
                    hist_xentry.array = data[:, 0] * config["xfactor"]
                    hist_yentry = deepcopy(entry)
                    hist_yentry.array = data[:, 1] * config["yfactor"]
                    self.histograms2D[uid]["x"].binning = config["xbins"]
                    self.histograms2D[uid]["x"].add_entry(hist_xentry)
                    self.histograms2D[uid]["x"].metadata.update({"column_name": config["xcolumn"]})
                    self.histograms2D[uid]["x"].metadata.update({"filters": config["filters"]})

                    self.histograms2D[uid]["y"].binning = config["ybins"]
                    self.histograms2D[uid]["y"].add_entry(hist_yentry)
                    self.histograms2D[uid]["y"].metadata.update({"column_name": config["ycolumn"]})
                    self.histograms2D[uid]["y"].metadata.update({"filters": config["filters"]})

        self.state.set_state(WrapperState.EXECUTED)

    def get_hist(self, identifier: str) -> Histogram:
        if not self.state.is_state(WrapperState.EXECUTED):
            raise Exception(f"Can only get histograms after execution, but found state: {self.state.name}")
        if identifier not in self.histograms.keys():
            raise KeyError(f"Identifier '{identifier}' not found for 1D Hists.")
        else:
            return self.histograms[identifier]

    def get_2Dhist(self, identifier: str) -> dict[str, Histogram]:
        if not self.state.is_state(WrapperState.EXECUTED):
            raise Exception(f"Can only get histograms after execution, but found state: {self.state.name}")
        if identifier not in self.histograms2D.keys():
            raise KeyError(f"Identifier '{identifier}' not found for 2D Hists.")
        else:
            return self.histograms2D[identifier]

    def get_all_hists(self) -> dict[str, Histogram]:
        if not self.state.is_state(WrapperState.EXECUTED):
            raise Exception(f"Can only get histograms after execution, but found state: {self.state.name}")
        return self.histograms

    def get_all_2Dhists(self) -> dict[str, dict[str, Histogram]]:
        if not self.state.is_state(WrapperState.EXECUTED):
            raise Exception(f"Can only get histograms after execution, but found state: {self.state.name}")
        return self.histograms2D
