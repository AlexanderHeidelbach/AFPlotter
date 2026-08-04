# `legend_max_rows` Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `BasePlotter.legend_ncol` to `legend_max_rows` with byte-identical rendering, and add the test that pins the semantics the old name got backwards.

**Architecture:** A four-file mechanical rename plus one new behavioural test. The property is a divisor — `ncol = ceil(len(labels) / legend_max_rows)` — so both read sites keep their arithmetic exactly as-is. The only genuinely new code is a test asserting the label-count-to-column-count mapping, which nothing currently covers.

**Tech Stack:** Python 3.10+, matplotlib (Agg backend in tests), pytest, ruff, mypy 2.3.0, uv.

Spec: `docs/superpowers/specs/2026-08-04-legend-max-rows-rename-design.md`
Issue: #26
Branch: `fix/legend-max-rows-rename`, already created off `main` at `3d935b9`. Spec committed at `adecf63`, corrected at `85f13c6`.

## Global Constraints

- **Rendering must not change.** Every arithmetic expression involving the property is copied verbatim. If any committed PNG under `docs/img/workflow/` changes, the task is wrong.
- **No deprecation shim and no raising tombstone.** `legend_ncol` disappears completely. This is deliberate; the silent-failure consequence is documented in the spec's "Breaking change" section.
- **Python 3.10+ typing.** Native `X | Y` unions and builtin generics. No `typing.Optional`/`List`/`Dict`/`Tuple`/`Union`.
- **reST docstrings** (`:param:` / `:return:`) on public functions and properties.
- **Line length 120** (ruff).
- **Falsifiable assertions only.** No `assert x is not None` on something that cannot be `None`, no `len(x) >= 0`. Every assertion must have an answer to "what bug makes this fail?"
- Run commands from the repo root with `uv run`.

---

### Task 1: Rename the property and both read sites

**Files:**
- Modify: `src/afplotter/baseplotter.py:103` (initialiser)
- Modify: `src/afplotter/baseplotter.py:177-183` (property pair)
- Modify: `src/afplotter/baseplotter.py:403` (headroom read site)
- Modify: `src/afplotter/baseplotter.py:430` (divisor read site)
- Test: `tests/test_baseplotter.py:29` (default assertion), `tests/test_baseplotter.py:270` (setter usage)

**Interfaces:**
- Consumes: nothing.
- Produces: `BasePlotter.legend_max_rows` — a read/write `int` property, default `4`. Backed by `self._legend_max_rows: int`. `BasePlotter.legend_ncol` no longer exists in any form. Task 2 and Task 3 both depend on this name.

- [ ] **Step 1: Update the two existing test references so the suite fails**

In `tests/test_baseplotter.py`, at line 29 inside `test_default_properties`, change:

```python
    assert plotter.legend_ncol == 4
```

to:

```python
    assert plotter.legend_max_rows == 4
```

At line 270 inside `test_set_axislimits_linear_expands_ylim_for_legend`, change:

```python
    plotter.legend_ncol = 2
```

to:

```python
    plotter.legend_max_rows = 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_baseplotter.py::test_default_properties -v`

Expected: FAIL with `AttributeError: 'ConcretePlotter' object has no attribute 'legend_max_rows'`.

Note that `test_set_axislimits_linear_expands_ylim_for_legend` will **still pass** at this point, because `plotter.legend_max_rows = 2` silently creates a dead attribute while `_set_axislimits` keeps reading the real `legend_ncol` of 4. That is exactly the silent-failure mode the spec documents. Do not treat its passing as evidence of anything.

- [ ] **Step 3: Rename the backing attribute**

In `src/afplotter/baseplotter.py`, line 103, change:

```python
        self._legend_ncol: int = 4
```

to:

```python
        self._legend_max_rows: int = 4
```

- [ ] **Step 4: Rename the property pair and give it a docstring**

In `src/afplotter/baseplotter.py`, replace lines 177-183:

```python
    @property
    def legend_ncol(self) -> int:
        return self._legend_ncol

    @legend_ncol.setter
    def legend_ncol(self, legend_ncol: int) -> None:
        self._legend_ncol = legend_ncol
```

with:

```python
    @property
    def legend_max_rows(self) -> int:
        """Maximum number of entries stacked in one legend column.

        The legend's column count is derived from this, not set by it:
        ``ncol = ceil(len(labels) / legend_max_rows)``. Raising this value
        therefore produces *fewer*, taller columns; lowering it produces more,
        shorter ones. To force a single column, set it to at least the number
        of legend entries.

        :return: The per-column row cap. Defaults to 4.
        """
        return self._legend_max_rows

    @legend_max_rows.setter
    def legend_max_rows(self, legend_max_rows: int) -> None:
        """Set the maximum number of entries stacked in one legend column.

        :param legend_max_rows: The per-column row cap. Must be at least 1.
        """
        self._legend_max_rows = legend_max_rows
```

- [ ] **Step 5: Update the headroom read site**

In `src/afplotter/baseplotter.py`, line 403, change:

```python
        lines_legend = self.legend_ncol
```

to:

```python
        lines_legend = self.legend_max_rows
```

Do **not** change the arithmetic on lines 408-415 that consumes `lines_legend`. The constant-headroom and log-scale behaviour is deliberately out of scope and is tracked in Task 4.

- [ ] **Step 6: Update the divisor read site**

In `src/afplotter/baseplotter.py`, line 430, change:

```python
            ncol = len(labels) // self.legend_ncol + (1 if len(labels) % self.legend_ncol != 0 else 0)
```

to:

```python
            ncol = len(labels) // self.legend_max_rows + (1 if len(labels) % self.legend_max_rows != 0 else 0)
```

The expression is otherwise identical — same floor division, same remainder correction. The replacement line is 114 characters, within the 120 limit.

- [ ] **Step 7: Verify no reference to the old name survives in code**

Run: `grep -rn "legend_ncol" src/ tests/`

Expected: no output. If anything matches, fix it before continuing.

- [ ] **Step 8: Run the full suite**

Run: `uv run pytest tests/ -q`

Expected: PASS, with the same number of tests as before this task.

- [ ] **Step 9: Commit**

```bash
git add src/afplotter/baseplotter.py tests/test_baseplotter.py
git commit -m "Rename legend_ncol to legend_max_rows

The property is a divisor yielding the maximum rows per legend column,
not the column count -- ncol = ceil(len(labels) / legend_ncol). Anyone
setting it to 2 expecting two columns got two rows per column, with the
column count moving the other way.

Arithmetic at both read sites is unchanged, so rendering is identical.
Adds the docstring the property never had, stating the direction of the
relationship explicitly.

Closes #26"
```

---

### Task 2: Pin the column-count semantics with a test

**Files:**
- Test: `tests/test_baseplotter.py` (append a new test after `test_default_properties`)

**Interfaces:**
- Consumes: `BasePlotter.legend_max_rows` from Task 1. The existing module-level `ConcretePlotter(BasePlotter)` subclass at `tests/test_baseplotter.py:14`, and `BasePlotter._add_legend(ax=...)`.
- Produces: nothing consumed by later tasks.

**Why this test exists:** nothing in the suite currently asserts the label-count-to-column-count mapping. The rename's real hazard is a later contributor reading `legend_max_rows`, assuming it is passed straight to `Axes.legend(ncol=...)`, and "simplifying" the divisor away. This test fails loudly if they do.

**Why rendered geometry, not `Legend._ncols`:** CI runs a matplotlib matrix across the Python 3.10 and 3.14 legs, and `_ncols` is a private attribute whose name and presence differ between versions. Counting distinct x-positions of the legend's text artists uses only public API and is stable across both.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_baseplotter.py`:

```python
def _legend_column_count(max_rows, n_labels):
    """Render a legend with n_labels entries and count its columns from text x-positions.

    Within a column every label shares an x-position, so the number of distinct
    x-positions is the column count. Uses only public matplotlib API.
    """
    plotter = ConcretePlotter()
    plotter.legend_max_rows = max_rows
    fig, ax = plt.subplots()
    for i in range(n_labels):
        ax.plot([0, 1], [i, i], label=f"entry {i}")
    plotter._add_legend(ax=ax)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    x_positions = {round(text.get_window_extent(renderer).x0) for text in ax.get_legend().get_texts()}
    plt.close(fig)
    return len(x_positions)


def test_legend_max_rows_caps_rows_and_grows_columns():
    """legend_max_rows is a row cap: raising it must *lower* the column count."""
    assert _legend_column_count(max_rows=3, n_labels=6) == 2
    assert _legend_column_count(max_rows=6, n_labels=6) == 1
```

- [ ] **Step 2: Run the test to verify it passes against the Task 1 implementation**

Run: `uv run pytest tests/test_baseplotter.py::test_legend_max_rows_caps_rows_and_grows_columns -v`

Expected: PASS.

This test is written after the implementation rather than before it, because it characterises behaviour that already exists and must not change. Step 3 is what establishes that it is falsifiable — do not skip it.

- [ ] **Step 3: Prove the test can fail**

Temporarily edit `src/afplotter/baseplotter.py:430` to the pass-through implementation this test exists to catch:

```python
            ncol = self.legend_max_rows
```

Run: `uv run pytest tests/test_baseplotter.py::test_legend_max_rows_caps_rows_and_grows_columns -v`

Expected: FAIL. With `max_rows=3` the legend renders 3 columns where the test asserts 2; with `max_rows=6` it renders 6 where the test asserts 1.

Now revert that edit:

```bash
git checkout src/afplotter/baseplotter.py
```

Re-run the test and confirm it passes again before continuing. If it did **not** fail under the pass-through, the test is measuring nothing — stop and fix it rather than committing it.

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest tests/ -q`

Expected: PASS, one test more than after Task 1.

- [ ] **Step 5: Commit**

```bash
git add tests/test_baseplotter.py
git commit -m "Add falsifiable test for legend_max_rows column derivation

Nothing asserted the label-count-to-column-count mapping, so the divisor
could have been 'simplified' into a straight ncol pass-through without a
single test failing. Two data points, because one cannot pin the
direction of the relationship -- and direction is what the old name got
backwards.

Counts columns from rendered text x-positions rather than Legend._ncols,
which is private and differs across the matplotlib versions the 3.10 and
3.14 CI legs resolve."
```

---

### Task 3: Update the example and the docs

**Files:**
- Modify: `examples/workflow_demo.py:93-97`
- Modify: `docs/getting-started.md:25`

**Interfaces:**
- Consumes: `BasePlotter.legend_max_rows` from Task 1.
- Produces: nothing consumed by later tasks.

**Why the example needs prose work, not find-and-replace:** the comment explains *why* the value is raised to 5, and its reasoning is phrased in terms of the old, backwards name.

- [ ] **Step 1: Rewrite the example's comment and assignment**

In `examples/workflow_demo.py`, replace lines 93-97:

```python
    # "(Own Work)". With the default legend_ncol=4 the 5 legend entries here wrap
    # into a 2-column box wide enough to span the axes regardless of anchor, so also
    # force a single narrow column (legend_ncol >= len(labels)) before anchoring it
    # to the upper-right corner, away from the watermark.
    plotter.legend_ncol = 5
```

with:

```python
    # "(Own Work)". With the default legend_max_rows=4 the 5 legend entries here
    # spill into a 2-column box wide enough to span the axes regardless of anchor,
    # so also force a single narrow column (legend_max_rows >= len(labels)) before
    # anchoring it to the upper-right corner, away from the watermark.
    plotter.legend_max_rows = 5
```

- [ ] **Step 2: Update the property list in the docs**

In `docs/getting-started.md`, line 25, change:

```markdown
- `legend_ncol`, `legend_title`, `legend_loc`
```

to:

```markdown
- `legend_max_rows`, `legend_title`, `legend_loc`
```

- [ ] **Step 3: Verify the old name survives nowhere that matters**

Run: `grep -rn "legend_ncol" . --exclude-dir=.git`

Expected: matches **only** under `docs/superpowers/specs/` and `docs/superpowers/plans/`. Those are dated artifacts describing the problem as it was, and must be left intact. Any match in `src/`, `tests/`, `examples/`, `docs/getting-started.md`, or `README.md` is a miss — fix it.

- [ ] **Step 4: Run the example and confirm the committed images do not change**

Run: `uv run python examples/workflow_demo.py`

Expected: exits 0.

Run: `git status --short docs/img/workflow/`

Expected: **no output.** The rename must not alter rendering. If any PNG shows as modified, the arithmetic changed somewhere — revert the images with `git checkout docs/img/workflow/`, find the behavioural difference, and fix it before committing. A modified PNG here also means every future push to `main` produces a bot commit from `update-workflow-images.yml`.

- [ ] **Step 5: Commit**

```bash
git add examples/workflow_demo.py docs/getting-started.md
git commit -m "Update example and docs for the legend_max_rows rename

The workflow_demo comment explained its reasoning in terms of the old
backwards name, so it is reworded rather than find-and-replaced.
Rendering is unchanged and the committed PNGs are byte-identical."
```

---

### Task 4: Run the full gate and file the headroom follow-up

**Files:**
- No source changes.

**Interfaces:**
- Consumes: everything from Tasks 1-3.
- Produces: a GitHub issue capturing the spec's out-of-scope findings.

- [ ] **Step 1: Run lint, format, and type checks**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
```

Those are the exact flags `.github/workflows/ci.yml:43` uses — a bare `uv run mypy src/` is a
different check and can disagree. Expected: all three clean. `uv run mypy` is the authoritative type gate — a local `pre-commit` pass is lint/format assurance only, because its mypy hook runs without project dependencies and resolves numpy/matplotlib types to `Any`.

- [ ] **Step 2: Run the full suite one final time**

Run: `uv run pytest tests/ -q`

Expected: PASS, one test more than on `main`.

- [ ] **Step 3: Verify the diff contains no image changes**

Run: `git diff --stat main...HEAD`

Expected: changes confined to `src/afplotter/baseplotter.py`, `tests/test_baseplotter.py`, `examples/workflow_demo.py`, `docs/getting-started.md`, and `docs/superpowers/`. **No file under `docs/img/`.**

- [ ] **Step 4: File the headroom follow-up issue**

The spec deliberately excluded the headroom findings. File them so they are not lost when this branch closes. Ask the user before running this — issue creation is outward-facing.

```bash
gh issue create --title "Legend headroom is computed from the row cap, not the realised legend" --body "$(cat <<'BODY'
Split out of #26, which renamed `legend_ncol` to `legend_max_rows`. The rename was
deliberately behaviour-preserving; these are the behavioural problems it left alone.
Design context: `docs/superpowers/specs/2026-08-04-legend-max-rows-rename-design.md`.

All three live in `BasePlotter._set_axislimits` (`src/afplotter/baseplotter.py:399-417`).

**1. Linear headroom is constant in the number of labels.**

```python
ax.get_ylim()[1] * (1 + 0.1 * lines_legend * np.sign(ax.get_ylim()[1]))
```

`lines_legend` is the *cap* (`legend_max_rows`), not the realised row count, so a 1-entry
legend reserves the same 40% of vertical space as a 4-entry one.

**2. Log headroom is extreme.**

```python
ax.get_ylim()[1] * (1 + 10 ** (max([lines_legend, lines_text]) / 2))
```

At the default of 4 this is `1 + 10**2` — **101x the data maximum** on every log-scale plot.
Rebasing it on a realised row count of 1 would give ~4.2x instead. That re-ranges every log
plot in the library, so it needs a decision about what the formula *should* be, which has
never been asked.

**3. Headroom is reserved even when no legend is drawn.** `_add_legend` returns early when
there are no labels, but `_set_axislimits` adds headroom unconditionally.

**Constraint on any fix: call order differs between the two plotters.**

| Plotter | Order |
|---|---|
| `genericplot.py:164,172` | `_add_legend` then `_set_axislimits` |
| `histogramplot.py:830,832` | `_set_axislimits` then `_add_legend` |

So a realised-row-count headroom cannot read the drawn legend — it must gather labels itself
via `get_legend_handles_labels()`. `Histogram2DPlotter` is unaffected: it sets `self.ylim`
explicitly before calling `_set_axislimits`, so the headroom branch never runs.

Any fix changes rendering, which re-renders the committed PNGs under `docs/img/workflow/`.
BODY
)"
```

- [ ] **Step 5: Push the branch and open the PR**

Ask the user before running this — pushing and opening a PR are outward-facing.

```bash
git push -u origin fix/legend-max-rows-rename
gh pr create --title "Rename legend_ncol to legend_max_rows" --body "$(cat <<'BODY'
Closes #26.

`legend_ncol` never set the legend's column count. It is a divisor:
`ncol = ceil(len(labels) / legend_ncol)`. It caps *rows* and lets columns grow, so
setting it to 2 expecting two columns gave two rows per column, with the column count
moving the other way.

Renamed to `legend_max_rows`. The arithmetic at both read sites is copied verbatim, so
rendering is byte-identical and the committed PNGs under `docs/img/workflow/` are
unchanged.

## Breaking change, with a sharp edge

`legend_ncol` is removed outright — no deprecation shim, no raising tombstone, matching
the project's pre-1.0 status and installation from a moving `main`.

`BasePlotter` defines no `__slots__` and no `__setattr__` guard, so **stale caller code
fails silently**:

```python
plotter.legend_ncol = 5   # creates a dead attribute, no error
plotter.plot()            # renders with legend_max_rows = 4, the default
```

No `AttributeError`, no warning — the legend just lays out differently. This was raised
during design and accepted deliberately; see the "Breaking change" section of
`docs/superpowers/specs/2026-08-04-legend-max-rows-rename-design.md`. It belongs in the
release notes once #6 lands.

## Tests

Adds a test for the label-count-to-column-count mapping, which nothing covered. Two data
points, because one cannot pin the *direction* of the relationship — and direction is what
the old name got backwards. Column count is measured from rendered text x-positions rather
than `Legend._ncols`, which is private and differs across the matplotlib versions the 3.10
and 3.14 CI legs resolve.

## Deliberately not fixed

#26 also floated fixing the coupled headroom calculation. Investigation showed the
log-scale branch computes `1 + 10**(n/2)` — 101x the data maximum at the default — so
rebasing it on a realised row count re-ranges every log plot in the library. Split out
into its own issue rather than ridden along on a rename.
BODY
)"
```

---

## Outcome

<!-- Fill this in when the plan has been executed. The SDD ledger under .superpowers/ is
     gitignored and vanishes with the working copy, so unticked checkboxes above prove
     nothing about what ran. Record here: final commit SHA, test count, what was verified
     on which Python version, and anything that deviated from the plan. -->

Executed 2026-08-04 via superpowers:subagent-driven-development on branch
`fix/legend-max-rows-rename`.

- Task 1 — commit 02e6e7f — rename across `baseplotter.py` and `tests/test_baseplotter.py`.
  Review clean.
- Task 2 — commit 6d3a179 — the column-count test. Review clean. The falsification step was
  performed and independently reproduced by the controller: patching the divisor to
  `ncol = self.legend_max_rows` makes the test fail, restoring makes it pass.
- Task 3 — commit 70144e9 — example and docs. Review clean. The three committed PNGs under
  `docs/img/workflow/` were confirmed byte-identical after a fresh run of
  `examples/workflow_demo.py`, both by the implementer and independently by the controller.
- Task 4 gate: `ruff check` clean, `ruff format --check` clean,
  `mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/` reported
  Success, and the suite went 139 → 140 passing. Verified on Python 3.10 locally; the 3.14
  leg runs in CI.
- One extra commit, eeddeb8, added `.superpowers/` to `.gitignore` — it had never been
  ignored anywhere despite a note claiming otherwise.
- Final whole-branch review found no Critical or Important issues. Four Minor findings;
  three were fixed in a follow-up commit (test bucket tolerance, setter docstring accuracy,
  this Outcome section). The fourth — three commits missing `Co-Authored-By`/`Claude-Session`
  trailers — was accepted as-is rather than rewriting history for a cosmetic inconsistency.
