# CI Python Version Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CI test both dependency sets that `uv.lock` can resolve (Python 3.10 and 3.14), bump mypy to a version that can actually read numpy 2.5's stubs, and fix the three real type defects this exposes.

**Architecture:** Five sequential tasks. The three source fixes land *first*, each verified against an ad-hoc mypy 2.3.0 in a throwaway venv, so CI stays green throughout. Only then is the pinned mypy bumped (Task 4) and the matrix added (Task 5). This ordering is deliberate: bumping the pin first would turn CI red for three commits.

**Tech Stack:** Python 3.10/3.14, uv (locking + interpreter management), pytest, mypy 2.3.0, ruff 0.5.0, GitHub Actions, pre-commit.

**Spec:** `docs/superpowers/specs/2026-08-03-ci-python-version-matrix-design.md`. Resolves #21.

**Branch:** `feature/ci-python-version-matrix` (already exists, spec committed as `8881261`).

## Global Constraints

- **Python 3.10+ typing only**: native `X | Y` unions and builtin generics (`list[X]`, `dict[K, V]`, `tuple[X, Y]`). Never import `typing.Optional`/`List`/`Dict`/`Tuple`/`Union`.
- **No `# type: ignore` anywhere in this branch.** All three defects are real and get real fixes. A suppression is a task failure.
- **`ruff==0.5.0` stays exactly as pinned** in both `pyproject.toml` and `.pre-commit-config.yaml`. Do not bump it.
- **CI and pre-commit must stay pinned to identical tool versions** (CLAUDE.md requirement).
- **Line length 120** (ruff).
- **reST docstrings** (`:param:` / `:return:`) on public functions and classes.
- **Tests must be falsifiable.** Ask of every new assertion: what specific bug makes this fail? `assert x is not None` on a method that cannot return `None` is not acceptable.
- **`plot(save=True)` calls `plt.clf()`** — never assert on axes content after a `save=True` call.
- Tests use the matplotlib `Agg` backend (already set in `tests/conftest.py`).

## Shared Setup: the ad-hoc mypy 2.3.0 check

Tasks 1–3 verify against mypy 2.3.0 *without* changing the pinned version. Create two throwaway venvs once, before Task 1. They live outside the repo and are never committed.

```bash
export MYPY_CHECK_310=/tmp/afplotter-check-310
export MYPY_CHECK_314=/tmp/afplotter-check-314

UV_PROJECT_ENVIRONMENT=$MYPY_CHECK_310 uv sync --extra dev --python 3.10 --locked -q
uv pip install --python $MYPY_CHECK_310/bin/python -q mypy==2.3.0

UV_PROJECT_ENVIRONMENT=$MYPY_CHECK_314 uv sync --extra dev --python 3.14 --locked -q
uv pip install --python $MYPY_CHECK_314/bin/python -q mypy==2.3.0
```

Confirm both are set up correctly:

```bash
$MYPY_CHECK_310/bin/python -m mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
```

Expected right now (before any fix): **exactly 2 errors**

```
src/afplotter/utilities/histogram.py:116: error: Incompatible types in assignment (expression has type "ndarray[tuple[int, ...], dtype[Any]] | None", variable has type "ndarray[Any, Any] | int")  [assignment]
src/afplotter/genericplot.py:30: error: Incompatible return value type (got "Axes | None", expected "Axes")  [return-value]
Found 2 errors in 2 files (checked 17 source files)
```

```bash
$MYPY_CHECK_314/bin/python -m mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
```

Expected right now: **exactly 3 errors** — the two above plus:

```
src/afplotter/baseplotter.py:431: error: No overload variant of "legend" of "Axes" matches argument types "list[Artist]", "list[Any]", "int", "str | None", "str"  [call-overload]
```

If either venv reports a different count, stop and investigate before starting — the plan's red/green expectations depend on these baselines.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/afplotter/utilities/histogram.py` | Modify (line 127) | Widen `Histogram.binning` setter to admit the `None` the getter already advertises |
| `tests/utilities/test_histogram.py` | Modify (append) | New falsifiable test for the `binning is None` round-trip |
| `src/afplotter/genericplot.py` | Modify (lines 24–30) | Bind `ax` to a local so `plot()`'s `-> plt.Axes` contract is provable |
| `src/afplotter/baseplotter.py` | Modify (lines 429–431) | Pass legend kwargs as a `dict[str, Any]` splat |
| `pyproject.toml` | Modify (line 21) | `mypy==1.10.1` → `mypy==2.3.0` |
| `.pre-commit-config.yaml` | Modify (mirrors-mypy rev) | `v1.10.1` → `v2.3.0`, matching CI |
| `.python-version` | Create | Pin local dev interpreter to `3.10` |
| `.github/workflows/ci.yml` | Rewrite | Two jobs: matrixed `test`, single `lint` |

---

### Task 1: Widen the `Histogram.binning` setter

The getter at `src/afplotter/utilities/histogram.py:123` declares `np.ndarray | int | None`, and the class genuinely stores `None` — `from_dict` (line 116) assigns it and `add_entry` (line 139) tests `if self.binning is None`. The setter declaring `np.ndarray | int` is simply wrong.

Note the runtime behaviour is already correct; this is a type-level defect only. That is why the failing check below is mypy, not pytest. The new pytest test exists to *pin* the `None` round-trip, which currently has zero coverage — so a future narrowing of the setter is caught by a test, not just by a type checker.

**Files:**
- Modify: `src/afplotter/utilities/histogram.py:126-128`
- Test: `tests/utilities/test_histogram.py` (append at end)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `Histogram.binning` setter accepting `np.ndarray | int | None`. No call-site changes anywhere; the getter's type is unchanged.

- [ ] **Step 1: Confirm the type error is present**

```bash
$MYPY_CHECK_310/bin/python -m mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/afplotter/utilities/histogram.py
```

Expected: FAIL, including

```
src/afplotter/utilities/histogram.py:116: error: Incompatible types in assignment ... [assignment]
```

- [ ] **Step 2: Write the failing coverage test**

Append to `tests/utilities/test_histogram.py`:

```python
def test_histogram_roundtrip_preserves_unset_binning():
    """A Histogram with no binning must survive as_dict -> from_dict with binning still None.

    Guards the binning setter's None branch: from_dict assigns None directly, so
    narrowing the setter back to `np.ndarray | int` breaks this round-trip.
    """
    hist = Histogram()
    data = hist.as_dict
    assert data["binning"] is None

    restored = Histogram.from_dict(data)
    assert restored.binning is None
    assert restored.entries == {}
    assert restored.signal == {}
```

- [ ] **Step 3: Run the new test**

```bash
uv run pytest tests/utilities/test_histogram.py::test_histogram_roundtrip_preserves_unset_binning -v
```

Expected: **PASS**. This test passes before the fix, because the defect is type-level only — the setter accepts `None` at runtime regardless of its annotation. Its job is regression protection, not driving the fix. Do not "make it fail" by weakening it.

- [ ] **Step 4: Fix the setter**

In `src/afplotter/utilities/histogram.py`, change lines 126–128 from:

```python
    @binning.setter
    def binning(self, bins: np.ndarray | int) -> None:
        self._binning = bins
```

to:

```python
    @binning.setter
    def binning(self, bins: np.ndarray | int | None) -> None:
        self._binning = bins
```

- [ ] **Step 5: Verify the type error is gone**

```bash
$MYPY_CHECK_310/bin/python -m mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
```

Expected: **1 error remaining** — only `genericplot.py:30`. The `histogram.py:116` error must be gone.

- [ ] **Step 6: Run the full suite and lint**

```bash
uv run pytest tests/ -q
uv run ruff check . && uv run ruff format --check .
```

Expected: `138 passed` (137 existing + 1 new), ruff clean.

- [ ] **Step 7: Commit**

```bash
git add src/afplotter/utilities/histogram.py tests/utilities/test_histogram.py
git commit -m "Widen Histogram.binning setter to accept None

The getter already declared np.ndarray | int | None and from_dict assigns
None directly, but the setter's annotation forbade it. Adds a round-trip
test covering the previously-uncovered binning=None path.

Refs #21"
```

---

### Task 2: Make `GenericPlot.plot()`'s return contract provable

`plot()` declares `-> plt.Axes`, guards `if self.ax is None`, then returns `self.ax`. Correct at runtime, but mypy cannot narrow a type across a property setter, so the return is `Axes | None`.

**Files:**
- Modify: `src/afplotter/genericplot.py:24-30`
- Test: `tests/test_genericplot.py` (existing tests provide the behavioural check)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `GenericPlot.plot() -> plt.Axes` unchanged in signature and runtime behaviour. `self.ax` is still assigned when it was `None`, so `InsetPlot` and `GenericPlotter`, which read `.ax` after calling `.plot()`, are unaffected.

- [ ] **Step 1: Confirm the type error is present**

```bash
$MYPY_CHECK_310/bin/python -m mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/afplotter/genericplot.py
```

Expected: FAIL with

```
src/afplotter/genericplot.py:30: error: Incompatible return value type (got "Axes | None", expected "Axes")  [return-value]
```

- [ ] **Step 2: Record the current behavioural baseline**

```bash
uv run pytest tests/test_genericplot.py -q
```

Expected: `11 passed`. Note the count — Step 5 must match it exactly, proving the refactor changed no behaviour.

- [ ] **Step 3: Bind `ax` to a local**

In `src/afplotter/genericplot.py`, replace lines 24–30:

```python
    def plot(self) -> plt.Axes:
        if self.ax is None:
            self.ax = plt.subplots()[1]
        plotmethod = getattr(self.ax, self.plotmethod)
        plotmethod(*self.args, **self.kwargs)

        return self.ax
```

with:

```python
    def plot(self) -> plt.Axes:
        ax = self.ax
        if ax is None:
            ax = plt.subplots()[1]
            self.ax = ax
        plotmethod = getattr(ax, self.plotmethod)
        plotmethod(*self.args, **self.kwargs)

        return ax
```

The assignment `self.ax = ax` is kept and must not be dropped — callers rely on the side effect of `plot()` populating `.ax`.

- [ ] **Step 4: Verify the type error is gone**

```bash
$MYPY_CHECK_310/bin/python -m mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
```

Expected: **`Success: no issues found in 17 source files`** on the 3.10 dependency set.

- [ ] **Step 5: Confirm no behaviour changed**

```bash
uv run pytest tests/test_genericplot.py -q
uv run pytest tests/ -q
```

Expected: `11 passed` for the genericplot file (matching Step 2), `138 passed` overall.

- [ ] **Step 6: Lint**

```bash
uv run ruff check . && uv run ruff format --check .
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/afplotter/genericplot.py
git commit -m "Bind ax to a local in GenericPlot.plot()

plot() declared -> plt.Axes but returned the ax property, which mypy
cannot narrow across a setter. Behaviour is unchanged, including the
side effect of populating self.ax.

Refs #21"
```

---

### Task 3: Pass legend kwargs as a typed dict

matplotlib 3.11 tightened `Axes.legend`'s `loc` parameter to `Literal[...] | tuple[float, float] | int | None`. `BasePlotter.legend_loc` is declared `str` (line 194), which does not satisfy that union. Keeping the public property as `str` is correct — narrowing it to matplotlib's literal set would couple this library's surface to their stub internals.

This error appears **only on the 3.14 dependency set** (matplotlib 3.11.1), so it must be verified with `$MYPY_CHECK_314`, not `$MYPY_CHECK_310`.

**Files:**
- Modify: `src/afplotter/baseplotter.py:429-431`
- Test: `tests/test_baseplotter.py` (existing legend tests provide the behavioural check)

**Interfaces:**
- Consumes: nothing from Tasks 1–2.
- Produces: no API change. `legend_ncol`, `legend_title`, `legend_loc` keep their current types (`int`, `str | None`, `str`) and semantics. The computed `ncol` value passed to matplotlib is byte-identical to before.

- [ ] **Step 1: Confirm the error is present on 3.14 and absent on 3.10**

```bash
$MYPY_CHECK_314/bin/python -m mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
```

Expected: FAIL with exactly

```
src/afplotter/baseplotter.py:431: error: No overload variant of "legend" of "Axes" matches argument types "list[Artist]", "list[Any]", "int", "str | None", "str"  [call-overload]
Found 1 error in 1 file (checked 17 source files)
```

```bash
$MYPY_CHECK_310/bin/python -m mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
```

Expected: `Success` — confirming this is genuinely version-specific and Tasks 1–2 are still green.

- [ ] **Step 2: Record the current behavioural baseline**

```bash
uv run pytest tests/test_baseplotter.py -q
```

Expected: `29 passed`. Step 5 must match exactly.

- [ ] **Step 3: Collect the kwargs into a typed dict**

In `src/afplotter/baseplotter.py`, replace lines 429–431:

```python
        if labels:
            ncol = len(labels) // self.legend_ncol + (1 if len(labels) % self.legend_ncol != 0 else 0)
            ax[0].legend(lines, labels, ncol=ncol, title=self.legend_title, loc=self.legend_loc)
```

with:

```python
        if labels:
            ncol = len(labels) // self.legend_ncol + (1 if len(labels) % self.legend_ncol != 0 else 0)
            legend_kwargs: dict[str, Any] = {
                "ncol": ncol,
                "title": self.legend_title,
                "loc": self.legend_loc,
            }
            ax[0].legend(lines, labels, **legend_kwargs)
```

The `ncol` computation is copied verbatim — do not change it. It is misleadingly named (`legend_ncol` is a divisor yielding max rows per column) and that is tracked separately as #26; fixing it here is out of scope.

- [ ] **Step 4: Confirm `Any` is imported**

`from typing import Any` is already line 1 of `src/afplotter/baseplotter.py`, so the annotation resolves with no new import. Confirm it is still there rather than adding a duplicate:

```bash
head -1 src/afplotter/baseplotter.py
```

Expected: `from typing import Any`. Do not add a second import line.

- [ ] **Step 5: Verify clean on both dependency sets**

```bash
$MYPY_CHECK_314/bin/python -m mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
$MYPY_CHECK_310/bin/python -m mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
```

Expected: **`Success: no issues found in 17 source files`** from *both*. This is the first point at which the branch is type-clean everywhere.

- [ ] **Step 6: Confirm no behaviour changed, and check the rendered legend**

```bash
uv run pytest tests/test_baseplotter.py -q
uv run pytest tests/ -q
```

Expected: `29 passed` (matching Step 2), `138 passed` overall.

Then verify the legend still renders, since this touches the plot path — use the `verify-examples` skill, or at minimum:

```bash
uv run python examples/histogram_with_pull.py && ls -la examples/output/
```

Expected: exit 0 and a written PNG.

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff check . && uv run ruff format --check .
git add src/afplotter/baseplotter.py
git commit -m "Pass legend kwargs as a typed dict in _add_legend

matplotlib 3.11 narrowed Axes.legend's loc to a Literal union, which our
legend_loc: str does not satisfy. Splatting a dict[str, Any] keeps our
public property as str rather than coupling it to matplotlib's stubs.

Refs #21"
```

---

### Task 4: Bump the pinned mypy and pin the local interpreter

With the source clean under mypy 2.3.0 on both dependency sets, the pin can move. `pyproject.toml` and `.pre-commit-config.yaml` must change together — CLAUDE.md requires CI and pre-commit run identical versions.

`.python-version` is added here too: it makes a fresh clone deterministic and aligned with the matrix's floor. CI's 3.14 leg is unaffected because it passes `--python 3.14` explicitly, which overrides the file.

**Files:**
- Modify: `pyproject.toml:21`
- Modify: `.pre-commit-config.yaml` (mirrors-mypy `rev`)
- Create: `.python-version`

**Interfaces:**
- Consumes: a type-clean `src/` from Tasks 1–3. **Do not start this task until Task 3's Step 5 shows `Success` on both dependency sets** — bumping the pin before that turns CI red.
- Produces: `mypy==2.3.0` available via `uv run mypy`, so Task 5's workflow can invoke it directly.

- [ ] **Step 1: Bump the pin in `pyproject.toml`**

Change line 21 from:

```toml
dev = ["pytest", "pytest-cov", "ruff==0.5.0", "mypy==1.10.1"]
```

to:

```toml
dev = ["pytest", "pytest-cov", "ruff==0.5.0", "mypy==2.3.0"]
```

`ruff==0.5.0` is unchanged.

- [ ] **Step 2: Bump the matching pre-commit rev**

In `.pre-commit-config.yaml`, change:

```yaml
-   repo: https://github.com/pre-commit/mirrors-mypy
    rev: "v1.10.1"
```

to:

```yaml
-   repo: https://github.com/pre-commit/mirrors-mypy
    rev: "v2.3.0"
```

Leave the `args` list exactly as it is. (`v2.3.0` is confirmed to exist as a tag in that repo.)

- [ ] **Step 3: Create `.python-version`**

A single line, at the repo root:

```
3.10
```

- [ ] **Step 4: Re-sync and confirm the new mypy is what runs**

```bash
uv sync --extra dev --locked
uv run mypy --version
```

Expected: `mypy 2.3.0` (…). If it reports 1.10.1, the sync did not pick up the change — re-run without `--locked` and commit the resulting `uv.lock` change alongside.

- [ ] **Step 5: Verify the project's own tooling is now clean**

```bash
uv run mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/
uv run pytest tests/ -q
uv run ruff check . && uv run ruff format --check .
```

Expected: mypy `Success`, `138 passed`, ruff clean — all via the *pinned* tooling, no scratch venv.

- [ ] **Step 6: Verify pre-commit agrees with CI**

```bash
pre-commit run --all-files
```

Expected: all hooks pass. This is the check that proves the two pins are genuinely in lockstep. If mypy fails here but passed in Step 5, the `args` in `.pre-commit-config.yaml` have drifted from the CI invocation — reconcile them.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .pre-commit-config.yaml .python-version
git commit -m "Bump mypy to 2.3.0 and pin local Python to 3.10

mypy 1.10.1 predates numpy 2.5's stubs and could not resolve them,
reporting 8 false positives on newer dependency sets while missing two
real defects on the current one. 2.3.0 reads both correctly.

.python-version makes a fresh clone deterministic and aligned with CI's
floor; the 3.14 CI leg overrides it via --python.

Refs #21"
```

---

### Task 5: Split CI into a matrixed `test` job and a single `lint` job

**Files:**
- Rewrite: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `mypy==2.3.0` from Task 4, and type-clean source from Tasks 1–3. If any earlier task is incomplete, the 3.14 leg fails.
- Produces: no code interface. The observable output is two green matrix legs on the PR.

- [ ] **Step 1: Rewrite the workflow**

Replace the entire contents of `.github/workflows/ci.yml` with:

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      # Do not cancel a sibling leg on first failure: the two legs exist to be
      # compared. uv.lock's resolution-markers mean 3.10 and 3.14 resolve
      # different matplotlib/numpy versions, and knowing whether a failure hits
      # one leg or both is the difference between "version-specific" and "real bug".
      fail-fast: false
      matrix:
        # 3.14 is the deliberate upper endpoint, pinned rather than floating so
        # CI cannot turn red from an upstream release nobody here made.
        # Bump it when 3.15 ships.
        python: ["3.10", "3.14"]
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install Python ${{ matrix.python }}
        run: uv python install ${{ matrix.python }}

      - name: Install dependencies
        run: uv sync --extra dev --python ${{ matrix.python }} --locked

      - name: Run tests
        run: uv run pytest tests/ -v

      - name: Type check (mypy)
        run: uv run mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/

  lint:
    runs-on: ubuntu-latest
    # ruff is a pinned standalone binary with no target-version override, so it
    # infers its target from requires-python and produces identical results on
    # every interpreter. Matrixing it would double the cost and report one
    # formatting slip as two failures.
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install Python 3.10
        run: uv python install 3.10

      - name: Install dependencies
        run: uv sync --extra dev --python 3.10 --locked

      - name: Lint (ruff check)
        run: uv run ruff check .

      - name: Format check (ruff format)
        run: uv run ruff format --check .
```

- [ ] **Step 2: Validate the YAML parses**

`pyyaml` is not a project dependency, so pull it in ephemerally with `--with` rather than adding it:

```bash
uv run --with pyyaml python -c "import yaml, pathlib; d = yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text()); print(sorted(d['jobs'])); print(d['jobs']['test']['strategy'])"
```

Expected:

```
['lint', 'test']
{'fail-fast': False, 'matrix': {'python': ['3.10', '3.14']}}
```

If `fail-fast` comes back `True` or missing, the key is misspelled — it is `fail-fast`, not `fail_fast`.

- [ ] **Step 3: Confirm pre-commit's YAML hook is happy**

```bash
pre-commit run check-yaml --all-files
```

Expected: pass.

- [ ] **Step 4: Commit and push**

```bash
git add .github/workflows/ci.yml
git commit -m "Split CI into a matrixed test job and a single lint job

test runs pytest + mypy across Python 3.10 and 3.14, which uv.lock
resolves to different matplotlib/numpy versions -- the dependency set CI
had never exercised. fail-fast is disabled so both legs always report.
lint stays single-version: ruff's output cannot vary by interpreter.

Closes #21"
git push -u origin feature/ci-python-version-matrix
```

- [ ] **Step 5: Verify both legs actually pass on GitHub**

A local run only ever proves the 3.10 leg. The CI run is the evidence.

```bash
gh run watch --exit-status
```

Then confirm both legs are present and green:

```bash
gh run list --branch feature/ci-python-version-matrix --limit 1
gh run view --log-failed 2>/dev/null | head -40 || echo "no failures"
```

Expected: jobs `test (3.10)`, `test (3.14)`, and `lint` all succeeded. **Do not mark this task complete until the 3.14 leg is confirmed green on GitHub** — it is the entire point of the change and cannot be verified locally.

- [ ] **Step 6: Clean up the scratch venvs**

```bash
rm -rf /tmp/afplotter-check-310 /tmp/afplotter-check-314
```

---

## Final Verification

Before opening the PR, confirm every exit criterion from the spec:

- [ ] `gh run list --branch feature/ci-python-version-matrix` shows `test (3.10)`, `test (3.14)`, `lint` all green.
- [ ] `uv run pytest tests/ -q` → `138 passed` (137 pre-existing + 1 new).
- [ ] `uv run mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/` → `Success`.
- [ ] `uv run ruff check . && uv run ruff format --check .` → clean.
- [ ] `pre-commit run --all-files` → all hooks pass, proving CI and pre-commit pins agree.
- [ ] `verify-examples` skill passes — Tasks 2 and 3 touch `genericplot.py` and `baseplotter.py`, both on the rendering path.
- [ ] `grep -rn "type: ignore" src/` returns nothing added by this branch.
- [ ] `git log --oneline origin/main..HEAD` shows the spec commit plus five task commits.

Then use `superpowers:finishing-a-development-branch` to decide how to integrate.

## Out of Scope

Do not do any of these, even if tempting while in the files:

- **`legend_ncol`'s misleading name** — it is a divisor yielding max rows per column, and is coupled to the headroom calculation at `baseplotter.py:403`. Tracked as #26.
- **`legend_title`'s setter asymmetry** (accepts `str`, stores `str | None`) — mypy does not flag it; unrelated.
- **Bumping `ruff`** — already clean on both dependency sets.
- **The unused `importlib_resources` dependency** — that is #23, and touching `pyproject.toml` here does not make it in scope.
- **Adding 3.11/3.12/3.13 to the matrix** — endpoints were chosen deliberately; see the spec.

## Outcome

Executed 2026-08-03 via `superpowers:subagent-driven-development`, one implementer plus an
independent reviewer per task. Recorded here because the SDD ledger is git-ignored and would
otherwise leave no committed evidence the plan ran.

| Task | Commit | Result |
|---|---|---|
| 1 — `binning` setter | `2160ae4` | Widened to `np.ndarray \| int \| None`; suite 137 → 138 |
| 2 — `GenericPlot.plot()` | `eb4c494` | `ax` bound to a local; `self.ax` side effect preserved |
| 3 — legend kwargs | `f5630d5` | `dict[str, Any]` splat; first point both dep sets are mypy-clean |
| 4 — mypy pin | `540a336` | `2.3.0` in `pyproject.toml` + `.pre-commit-config.yaml`; `.python-version`; `uv.lock` regenerated (dev-side only) |
| 6 — `CLAUDE.md` (added) | `035a73f` | Guide updated for the new toolchain; not in the original plan, required by the clear-the-decks spec |
| 5 — CI matrix | `527db7a`, `f709d75` | Matrixed `test` + single `lint`; **initially failed** — see below |

**Task 5 failed on first attempt, and the cause was a defect in this plan.** Task 4's
`.python-version` (3.10) and Task 5's verbatim workflow interact: the bare `uv run pytest` /
`uv run mypy` steps carry no `--python`, so on the 3.14 leg `uv` honoured `.python-version`,
discarded the environment the sync step had just built, rebuilt `.venv` for 3.10 *without*
`--extra dev`, and died with `Failed to spawn: pytest`. Neither task could see this alone.
Fixed in `f709d75` with a job-level `env: UV_PYTHON: ${{ matrix.python }}`.

**Final review** (`be2ef1c..f709d75`) approved the branch and raised four items, all fixed in
`73dff7e`, `b1a8ee6`, `5aa4e68`:

- The `lint` job lacked `UV_PYTHON` and survived only because `.python-version` happened to
  match its hardcoded `--python 3.10` — latent form of the same failure.
- `CLAUDE.md` overclaimed that pre-commit and CI agree. The mirrors-mypy hook runs with no
  project dependencies, so numpy/matplotlib types resolve to `Any`; it could not have caught
  any of the three defects this branch fixed. `additional_dependencies` was considered and
  rejected — those deps would resolve independently of `uv.lock` and reintroduce the
  local-vs-CI divergence this branch removed.
- A stale Conventions bullet still claimed local mypy is expected to be red.
- Nothing pinned the `self.ax` side effect; a falsifiable identity test now does.

**Final state:** HEAD `5aa4e68`, 139 tests, mypy `Success` and `uv sync --locked` verified on
both 3.10 and 3.14, CI run `30854245424` green on `test (3.10)`, `test (3.14)`, and `lint`.
