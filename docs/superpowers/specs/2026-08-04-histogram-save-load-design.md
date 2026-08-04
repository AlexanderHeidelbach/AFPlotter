# Saving and loading `Histogram` objects

Issue: #9
Depends on: #8 (closed — verdict: build a purpose-built format, do not depend on `hist`)

## What already works

`as_dict` / `from_dict` exist on both `Histogram` and `HistogramEntry`, and they already
round-trip everything that matters. Verified: counts, errors, binning, the entries/signal split,
`latex_name`, `color`, `hatch`, and `metadata` all survive `json.loads(json.dumps(h.as_dict))`
intact.

So #9 is not a serialization layer. It is file I/O plus a format contract.

## Decisions

**Payload: binned results only.** `save` drops each entry's raw `array`. Files then stay roughly
2 KB regardless of sample size, which is what makes the issue's caching motivation work — the
expensive part being cached is the binning, not the events.

Keeping raw arrays was rejected: `as_dict` embeds them, producing ~12 KB of JSON for 600 events
and therefore ~200 MB for 10M — which defeats the purpose entirely.

**Format: JSON.** `as_dict` is already JSON-safe, so this adds no dependency and no encoding
logic. With arrays dropped there is no large numeric payload left, so binary compactness buys
nothing, and a file a student can open in a text editor is worth more than a few saved bytes.

`.npz` + JSON header (suggested by #8's outcome), HDF5, and ROOT/`uproot` were all rejected on
the same ground: each solves a large-data problem that the binned-only payload has already
removed, while adding a dependency or an opaque format.

**Failure mode: loud, at plot time.** See below.

## API

Two additions to `Histogram`:

```python
def save(self, path: str | Path) -> None
@classmethod
def load(cls, path: str | Path) -> "Histogram"
```

`save` writes JSON containing the existing `as_dict` payload plus one key:

- `"format_version"` — an integer, starting at `1`, so a future format change is detected rather
  than crashing on a mysterious `KeyError`.

`load` rejects a file whose `format_version` it does not recognise, with an error naming the
version found and the version supported.

No `"binned_only"` marker: `format_version` already distinguishes a future raw-data format, and a
second flag saying the same thing is one more field to keep consistent for no gain.

## The 2D guard

`Histogram2DPlot` bins raw arrays at plot time — `self.ax.hist2d(...)` at
`src/afplotter/histogramplot.py:454`. It never stores 2D counts. A binned-only histogram
therefore cannot produce a 2D plot.

The failure today is bad. `get_data()` returns `[entry.array for entry in ...]`, so for cleared
entries it returns `[None]` — a list of length 1. `Histogram2DPlot.plot`'s guard tests
`len(self.xhistogram.get_data()) > 0`, which is **true**, so the existing `"Unexpected data state
encountered."` fallback does not fire. Execution reaches `hist2d(x=None)` and raises somewhere
inside matplotlib, naming nothing useful.

`Histogram2DPlot.plot` checks the selected `x_data` / `y_data` for `None` immediately after the
existing branch selection, and raises:

```
ValueError: Histogram 'ttbar' has no raw event data (loaded from a binned-only
file, or cleared via add_entry(clear=True)). Histogram2DPlot bins raw arrays at
plot time. Rebuild it from the source data to make a 2D plot.
```

Checking the data for `None` — rather than tagging loaded histograms with a flag — is deliberate.
**`add_entry(clear=True)` already produces exactly this state today**, and
`LazyHistWrapper.lazy_execute` calls it, so the confusing failure is reachable without ever
touching save/load. One `None` check covers both causes; a load-only flag would fix the new path
and leave the existing one broken.

## Testing

- **Round-trip.** Save and load a histogram with a background entry and a signal entry; assert
  counts, errors, binning, `get_signal_names()`, `get_colors()`, `get_latex_names()`, and
  `metadata` all match. Use values that are *not* self-consistent by coincidence — a fixture
  where a broken round-trip would reproduce the right answer anyway proves nothing. (This exact
  trap produced a false PASS during #8's spike: an error check whose fixture had errors equal to
  `sqrt(counts)`, so it passed whether errors were preserved or overwritten.)
- **Size independence.** Build the same binning from 1,000 and from 100,000 events, save both,
  and assert the two file sizes differ by less than 10%. (Counts grow by a few digits per bin, so
  the files are not byte-identical; a 100× data increase must not produce a 100× file.) This is
  the property that makes caching viable, and it fails loudly if raw arrays creep back in.
- **2D guard.** Assert that plotting a loaded histogram in 2D raises `ValueError` and that the
  message mentions raw event data — not merely that *something* raised, which a matplotlib
  `TypeError` would also satisfy.
- **Version rejection.** A file with `format_version: 99` raises an error naming both versions.

## Out of scope

- **`LazyHistWrapper` caching integration.** Saving is a `Histogram` capability. Wiring it into
  the lazy builder so expensive builds are cached automatically is worth doing, but it is a
  separate issue that depends on this one existing.
- **A 2D-capable format.** Would require the raw-array payload this design deliberately rejects.
- **Cross-tool interop.** #8 settled that; converters to `hist` are tracked separately.
