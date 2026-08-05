# Preserving explicitly supplied bin errors

Issue: #37

## The bug

`Histogram.add_entry` (`src/afplotter/utilities/histogram.py:249`) calls `entry.compute_errors()`
unconditionally. With `array is None` — a pre-binned entry — `compute_errors` sets
`errors = sqrt(counts)`, discarding whatever the caller supplied:

```python
h.add_entry(HistogramEntry(name="pre",
                           counts=np.array([10., 20., 30., 40., 50.]),
                           errors=np.array([1., 1., 1., 1., 1.])))
h.get_bin_errors()[0]
# [3.16 4.47 5.48 6.32 7.07]  <- sqrt(counts), not the supplied ones
```

Pre-binned input is therefore half-supported: `counts` survive, uncertainties do not. Any sample
whose errors are not Poisson — a weighted MC sample, or anything arriving from `uproot`/`hist`
with a real variance array — loses them silently.

**This has two in-repo instances beyond inbound interop**, which the issue does not mention:

- `Histogram.load` restores authoritative binned errors, and re-adding a loaded entry corrupts
  them. `load`'s docstring already documents this, pointing at #37.
- `sum_entries` (`histogram.py:270`) builds its combined entry with `+=`, which correctly
  quadrature-sums errors and clears `array`, then hands it to `add_entry` — which replaces the
  propagated result with `sqrt(counts)`. Summing weighted entries loses errors today, entirely
  within AFPlotter.

One fix repairs all three.

## Decisions

**The rule: binned values a caller supplies explicitly are authoritative and never recomputed.**

`add_entry` already behaves this way for `counts` — `compute_counts` runs only when
`len(entry.counts) == 0`, so raw `array` does not override supplied counts. Errors now match. The
alternative (recompute from `array` whenever it exists, preserve errors only when `array is None`)
is the issue's literal Direction and fixes the reported case equally well, but leaves `counts` and
`errors` following different precedence rules on the same entry. One rule is worth more than the
marginal case it costs.

Consequence, accepted deliberately: an entry carrying *both* raw `array` and supplied `errors`
keeps the supplied errors even if they disagree with the array. That combination has no in-repo
producer; the rule's clarity is the payoff.

**`compute_errors` is not touched.** Both its branches stay reachable and correct: raw `array` →
`sqrt(sum w**2)`; pre-binned with no errors → Poisson. The Poisson fallback is load-bearing for
entries supplied with `counts` but no `errors`, and stays.

**Length mismatches raise.** Supplied errors of a length other than the entry's bin count are a
caller error that currently flows through to plotting and fails far from its cause, or broadcasts
silently. `counts` itself remains unvalidated against `binning`; this design does not address that.

## The change

In `Histogram.add_entry`, replacing the unconditional `entry.compute_errors(...)`:

```python
if len(entry.errors) not in (0, len(entry.counts)):
    raise ValueError(...)          # names the entry and both lengths
if len(entry.errors) == 0:
    entry.compute_errors(binning=binning)
```

Order matters: counts are resolved earlier in the method, so when the guard runs
`len(entry.counts)` is the real bin count whether it was supplied or just computed.

`load`'s `.. warning::` block (`histogram.py:196-201`), which documents this bug as known and
unfixed, is deleted.

## Blast radius

No in-repo caller supplies errors into `add_entry` except `sum_entries`, which wants the new
behaviour. `LazyHistWrapper` builds entries from a template whose `counts`/`errors` are empty and
sets only `array`, so the lazy path is unchanged. Examples and the convenience functions pass raw
arrays only.

**This is a silent behaviour change** for any external script that passes both `counts` and
`errors` and depends on the Poisson overwrite. Nothing raises; the numbers change. It joins
`legend_ncol`'s removal on the list owed to #6's release notes.

## Testing

Falsifiability is the whole risk here. A fixture whose expected value the *broken* code also
produces proves nothing — that trap produced a false PASS during #8's spike, on this exact
property. Every fixture below uses errors provably unequal to `sqrt(counts)`, and asserts so
in the test itself (`assert not np.allclose(errors, np.sqrt(counts))`), so the fixture cannot
silently drift into coincidence.

- **Pre-binned with supplied errors** → preserved verbatim.
- **Pre-binned with no errors** → still `sqrt(counts)`; the fallback is intact.
- **Raw `array`, no errors, weighted sample** → still `sqrt(sum w**2)`, which for that sample is
  not `sqrt(counts)`.
- **Raw `array` plus supplied errors** → supplied wins. Pins the precedence decision above; this
  is the test that fails if someone later "fixes" it to the array-wins reading.
- **`save` → `load` → `add_entry`** → errors survive the round-trip.
- **`sum_entries` of two weighted entries** → quadrature sum, not `sqrt(total counts)`.
- **Length mismatch** → `ValueError` whose message names the entry and both lengths, not merely
  that something raised.

Each test is verified by breaking the implementation and watching it fail, not by passing against
the fixed code.

## Out of scope

- Validating `counts` against `binning`. Real, pre-existing, unrelated to this fix.
- Converters to/from `hist`/`uproot`. #8 settled the dependency question; conversion is tracked
  separately.
- `#36`'s out-of-range recording, which touches the same class but answers a different question.
