# Preserve Supplied Bin Errors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `Histogram.add_entry` from overwriting explicitly supplied bin errors with `sqrt(counts)`.

**Architecture:** One rule, enforced in one place. `Histogram.add_entry` already skips `compute_counts` when `counts` are non-empty; the same guard now wraps `compute_errors`, so any binned value a caller supplies is authoritative. A length check in front of it turns mismatched error arrays into an immediate `ValueError` instead of a distant failure. `HistogramEntry.compute_errors` is not modified — both of its branches stay reachable and correct.

**Tech Stack:** Python 3.10+, numpy, pytest. No new dependencies.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-05-preserve-supplied-bin-errors-design.md`. Issue: #37.
- Do **not** modify `HistogramEntry.compute_errors`. Its `array is not None` branch (`sqrt(sum w**2)`) and its `else` branch (Poisson `sqrt(counts)`) both remain correct and reachable.
- Precedence rule, non-negotiable: **explicitly supplied binned values are never recomputed.** An entry carrying both a raw `array` and non-empty `errors` keeps the supplied `errors`. This mirrors how `counts` already behave.
- Every test that asserts on preserved errors MUST use error values that are provably not `sqrt(counts)`, and MUST assert that fact inline with `assert not np.allclose(errors, np.sqrt(counts))`. A fixture whose expected value the *broken* code also produces proves nothing — that exact trap produced a false PASS during issue #8's spike.
- Every test in this plan must be verified by breaking the implementation and watching it fail. "It passes" is not evidence.
- Python 3.10+ typing throughout: native `X | Y`, builtin generics. No `typing.Optional`/`List`/`Dict`.
- Line length 120 (ruff).
- Run the full suite with `uv run pytest tests/ -v`; single tests with `uv run pytest tests/utilities/test_histogram.py::<name> -v`.
- Do not validate `counts` against `binning`. Out of scope, pre-existing, tracked separately.

---

### Task 1: Preserve explicitly supplied errors

**Files:**
- Modify: `src/afplotter/utilities/histogram.py` — `Histogram.add_entry`, the `entry.compute_errors(binning=binning)` call (currently line 249)
- Test: `tests/utilities/test_histogram.py`

**Interfaces:**
- Consumes: `Histogram.add_entry(entry: HistogramEntry, clear: bool = False) -> None`, `HistogramEntry(name=..., counts=..., errors=..., array=..., weight=...)`, both already existing.
- Produces: the behavioural contract Tasks 2 and 3 rely on — after `add_entry`, `hist.entries[name].errors` equals what the caller supplied whenever `len(entry.errors) != 0`.

- [ ] **Step 1: Write the four failing tests**

Append to `tests/utilities/test_histogram.py`:

```python
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
```

- [ ] **Step 2: Run the tests and confirm which fail, and why**

Run:

```bash
uv run pytest tests/utilities/test_histogram.py -k "preserves_supplied_errors or falls_back_to_poisson or computes_weighted_errors or supplied_errors_win" -v
```

Expected on unmodified code: `test_add_entry_preserves_supplied_errors_on_a_prebinned_entry` FAILS (errors come back as `sqrt(counts)` — `[3.16, 4.47, 5.48, 6.32, 7.07]`), and `test_add_entry_supplied_errors_win_over_a_raw_array` FAILS (errors recomputed from the array as `[2.0, sqrt(2)]`). The other two PASS — they document behaviour that must survive the fix, so passing now is correct. If either of those two fails, stop: the baseline is not what this plan assumes.

- [ ] **Step 3: Make the change**

In `Histogram.add_entry`, replace:

```python
        entry.compute_errors(binning=binning)
```

with:

```python
        if len(entry.errors) == 0:
            entry.compute_errors(binning=binning)
```

Leave everything around it — the `binning is None` check, the `compute_counts` block, the `isinstance(binning, int)` raise, the `clear` handling and the type dispatch — untouched.

- [ ] **Step 4: Run the tests to verify they pass**

Run the same command as Step 2. Expected: 4 passed.

- [ ] **Step 5: Verify the tests are falsifiable**

Temporarily revert the guard (make `compute_errors` unconditional again) and re-run. Expected: the two tests named in Step 2 fail again. Restore the guard. Do not skip this — a test that cannot fail is worth nothing here.

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest tests/ -v`

Expected: all pass. If `test_histogram_sum_entries` or any save/load test now behaves differently, that is expected in *direction* (Task 3 covers it) but nothing should fail — report it rather than adjusting an unrelated test.

- [ ] **Step 7: Commit**

```bash
git add src/afplotter/utilities/histogram.py tests/utilities/test_histogram.py
git commit -m "Preserve explicitly supplied bin errors in add_entry

Issue #37. add_entry called compute_errors unconditionally, so a
pre-binned entry's supplied errors were replaced with sqrt(counts).
Recompute only when no errors were supplied, matching how counts
already work.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Reject mismatched error lengths

**Files:**
- Modify: `src/afplotter/utilities/histogram.py` — `Histogram.add_entry`, immediately above the guard added in Task 1
- Test: `tests/utilities/test_histogram.py`

**Interfaces:**
- Consumes: the Task 1 guard `if len(entry.errors) == 0: entry.compute_errors(...)`.
- Produces: `add_entry` raises `ValueError` when `len(entry.errors) not in (0, len(entry.counts))`. No new function or type.

- [ ] **Step 1: Write the failing test**

Append to `tests/utilities/test_histogram.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/utilities/test_histogram.py::test_add_entry_rejects_errors_of_the_wrong_length -v`

Expected: FAIL — `DID NOT RAISE ValueError`. (On unfixed code the errors are silently replaced; after Task 1 they are silently kept at the wrong length. Either way nothing raises.)

- [ ] **Step 3: Add the guard**

In `Histogram.add_entry`, directly above the `if len(entry.errors) == 0:` block from Task 1:

```python
        if len(entry.errors) not in (0, len(entry.counts)):
            raise ValueError(
                f"Entry '{entry.name}' was given {len(entry.errors)} errors "
                f"for {len(entry.counts)} counts. Supplied errors must have one value per bin."
            )
```

Placement matters: counts are resolved earlier in the method, so `len(entry.counts)` here is the real bin count whether the caller supplied it or `compute_counts` produced it.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/utilities/test_histogram.py::test_add_entry_rejects_errors_of_the_wrong_length -v`

Expected: PASS.

- [ ] **Step 5: Verify the message, not just the raise**

Confirm the `pytest.raises(..., match=...)` regex above is what makes it pass — temporarily change the message to a bare `"bad errors"` and re-run. Expected: FAIL on the pattern, proving the test checks the message content and not merely that something raised. Restore the real message.

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest tests/ -v`

Expected: all pass. The guard must not fire for entries built from a raw array (errors empty at that point) or for the round-trip tests.

- [ ] **Step 7: Commit**

```bash
git add src/afplotter/utilities/histogram.py tests/utilities/test_histogram.py
git commit -m "Raise when supplied bin errors do not match the bin count

Issue #37. A wrong-length errors array previously flowed through to
plot time and failed far from its cause, or broadcast silently.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Cover the two in-repo instances and retire the stale docs

**Files:**
- Modify: `src/afplotter/utilities/histogram.py` — the `.. warning::` block in `Histogram.load`'s docstring (currently lines 196-201)
- Modify: `tests/utilities/test_histogram.py` — `test_save_load_round_trip`'s docstring and fixture (currently starting line 181)
- Test: `tests/utilities/test_histogram.py`

**Interfaces:**
- Consumes: the behaviour established by Tasks 1 and 2. No new interface.
- Produces: nothing later tasks depend on. This is the final task.

- [ ] **Step 1: Write the failing test for `sum_entries`**

`sum_entries` combines entries with `__iadd__`, which quadrature-sums their errors and clears `array` — then passes the result to `add_entry`, which used to overwrite that propagated result with `sqrt(counts)`. Append to `tests/utilities/test_histogram.py`:

```python
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
```

- [ ] **Step 2: Write the failing test for the load round-trip**

A histogram whose entries were restored from a file must survive being fed back through `add_entry`. Append to `tests/utilities/test_histogram.py`:

```python
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
```

- [ ] **Step 3: Run both tests to verify they fail on the pre-Task-1 behaviour**

Run: `uv run pytest tests/utilities/test_histogram.py -k "sum_entries_keeps or survive_being_re_added" -v`

Expected against the *fixed* code: both PASS. To prove they are falsifiable, temporarily revert Task 1's guard (unconditional `compute_errors`) and re-run. Expected: `test_sum_entries_keeps_the_propagated_errors` fails with `[4.0, 4.0]` instead of `[5.0, 5.0]`, and `test_loaded_entries_survive_being_re_added` fails with `sqrt(counts)`. Restore the guard before continuing.

- [ ] **Step 4: Delete the stale warning from `Histogram.load`'s docstring**

The block documenting this bug as known and unfixed is now false. Remove exactly:

```
        .. warning::
            Returned entries are binned-only; their stored ``errors`` are authoritative for
            a weighted sample (``sqrt(sum(w**2))``), not necessarily ``sqrt(counts)``. Passing
            such an entry back through :meth:`add_entry` recomputes ``errors`` from ``counts``
            (since ``array`` is ``None``) and silently overwrites the restored value with the
            wrong number. Not fixed here — tracked as issue #37.
```

Leave the rest of the docstring — the summary line, the "no raw event data" paragraph, `:param:`, `:return:` and `:raises:` — unchanged.

- [ ] **Step 5: Document the new contract on `add_entry`**

`Histogram.add_entry` has no docstring. Add one directly under its `def` line:

```python
        """Bin an entry and store it under its name.

        Values the caller supplies are authoritative and are never recomputed: ``counts``
        are binned from ``array`` only when empty, and ``errors`` likewise. An entry with
        no ``errors`` gets ``sqrt(sum(w**2))`` when it carries a raw ``array``, and the
        Poisson ``sqrt(counts)`` when it is pre-binned.

        :param entry: The entry to add. Dispatched to ``self.entries`` or ``self.signal``
            on its ``type``.
        :param clear: Drop the entry's raw ``array`` after binning.
        :raises ValueError: If the binning is unset or unresolved, if supplied ``errors``
            do not have one value per bin, or if ``entry.type`` is unrecognised.
        """
```

- [ ] **Step 6: Update `test_save_load_round_trip` to stop working around the bug**

Its docstring currently explains that errors must be assigned *after* `add_entry` because `add_entry` would overwrite them. That workaround is obsolete. Replace the docstring with:

```python
    """Counts, errors, binning, signal split and styling must survive a save/load cycle.

    The errors here are deliberately not ``sqrt(counts)``, so a ``load`` that recomputes
    them instead of restoring them fails this test. They are passed straight into the
    ``HistogramEntry`` constructor -- ``add_entry`` preserves supplied errors (issue #37).
    """
```

Then move the error arrays into the constructors and delete the two post-hoc assignments: pass `errors=np.array([1.5, 2.5, 3.5, 4.5, 5.5])` to the `bkg` entry and drop `hist.entries["bkg"].errors = bkg_errors`; pass `errors=np.array([0.5, 0.5, 0.5, 0.5, 0.5])` to the `sig` entry and drop `hist.signal["sig"].errors = sig_errors`. Keep the local names `bkg_errors` / `sig_errors` bound to those same arrays so the existing assertions still read against literals.

- [ ] **Step 7: Run the full suite, lint and types**

```bash
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
uv run mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
```

Expected: all tests pass, ruff clean, mypy `Success`. Note that only `uv run mypy` inside the synced project venv is a real type-check gate — a local pre-commit pass is lint/format assurance only.

- [ ] **Step 8: Confirm the reproduction from issue #37 is fixed**

```bash
uv run python -c "
import numpy as np
from afplotter import Histogram, HistogramEntry
h = Histogram(); h.binning = np.linspace(0, 5, 6)
h.add_entry(HistogramEntry(name='pre', counts=np.array([10.,20.,30.,40.,50.]), errors=np.ones(5)))
print(h.get_bin_errors()[0])
"
```

Expected: `[1. 1. 1. 1. 1.]`.

- [ ] **Step 9: Commit**

```bash
git add src/afplotter/utilities/histogram.py tests/utilities/test_histogram.py
git commit -m "Cover sum_entries and load round-trips, retire the #37 warning

sum_entries' quadrature-summed errors and Histogram.load's restored
errors were both being replaced with sqrt(counts) by add_entry. Both
are now covered by tests. Removes load's warning documenting the bug
and documents the new contract on add_entry.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Notes for the final review

- The spec records a **silent behaviour change**: an external script that passes both `counts` and `errors` and relies on the Poisson overwrite now gets different numbers with nothing raised. This is owed to issue #6's release notes, alongside `legend_ncol`'s removal. It needs no code, but it must not be forgotten at release time.
- `LazyHistWrapper` is deliberately untouched: its entry templates carry empty `counts`/`errors` and it sets only `array`, so the lazy path's behaviour is unchanged. Confirm this rather than assuming it.
