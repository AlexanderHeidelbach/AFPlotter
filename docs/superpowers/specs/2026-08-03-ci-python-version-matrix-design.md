# Test CI against more than Python 3.10

Resolves #21.

## Context

`pyproject.toml` declares `requires-python = ">=3.10"`, but CI only ever exercises 3.10:

```yaml
# .github/workflows/ci.yml
- run: uv python install 3.10
- run: uv sync --extra dev --python 3.10 --locked
```

The gap is wider than "one untested Python version". `uv.lock` carries
`resolution-markers` and its own `requires-python = ">=3.10"`, so `uv sync --locked` does
**not** pin a single dependency set — it legitimately resolves *newer* dependencies on
newer interpreters. Measured on this repo at commit `ff158e9`:

| | Python 3.10 | Python 3.14 |
|---|---|---|
| matplotlib | 3.10.9 | **3.11.1** |
| numpy | 2.2.6 | **2.5.1** |
| polars | 1.43.1 | 1.43.1 |

So CI has never run against the matplotlib/numpy combination that a current interpreter
selects. There is also no `.python-version` file, which means a fresh clone's interpreter
is whatever `uv` happens to pick — on the maintainer's machine, system Python is 3.14.6,
so a fresh clone lands on the *untested* dependency set while the long-lived local
`.venv` (created earlier, on 3.10.20) stays on the tested one. The two diverge silently.

### What this exposed

Running the full checks against the 3.14 dependency set surfaced 11 mypy errors while CI
stayed green. Investigating those revealed that the pinned `mypy==1.10.1` (June 2024)
predates numpy 2.5's stubs and cannot resolve them — it reports types as
`_HistogramResult?[...]` and `NDArray?[Any]`, where the `?` is mypy's own marker for an
unresolved type. Eight of the eleven were therefore false positives from an outdated
checker, not defects.

Re-running under `mypy==2.3.0` gives the real picture:

| | mypy 1.10.1 | mypy 2.3.0 |
|---|---|---|
| 3.10 dep set | clean | **2 errors** |
| 3.14 dep set | 11 errors | **3 errors** |

Three genuine type defects exist, and **two of them are latent under the current CI
configuration** — invisible only because the pinned mypy is too old to detect them:

1. `src/afplotter/utilities/histogram.py:116` — `ndarray | None` assigned through a
   setter declared `ndarray | int`. Present on **both** dependency sets.
2. `src/afplotter/genericplot.py:30` — returns `Axes | None` where the signature declares
   `Axes`. Present on **both** dependency sets.
3. `src/afplotter/baseplotter.py:431` — `Axes.legend` overload mismatch. The only
   genuinely version-specific defect; matplotlib 3.11 tightened the stub.

pytest (137 tests) and ruff pass on both dependency sets, unchanged.

## Design

### 1. Two-job CI workflow

`.github/workflows/ci.yml` splits into a matrixed `test` job and a single `lint` job:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python: ["3.10", "3.14"]
    steps:
      - checkout / setup-uv
      - run: uv python install ${{ matrix.python }}
      - run: uv sync --extra dev --python ${{ matrix.python }} --locked
      - run: uv run pytest tests/ -v
      - run: uv run mypy --namespace-packages --explicit-package-bases --ignore-missing-imports src/

  lint:
    runs-on: ubuntu-latest
    steps:
      - checkout / setup-uv
      - run: uv python install 3.10
      - run: uv sync --extra dev --python 3.10 --locked
      - run: uv run ruff check .
      - run: uv run ruff format --check .
```

**Why pytest and mypy are matrixed but ruff is not.** pytest and mypy both consume the
resolved dependency set, so their results genuinely differ between the two — that is the
entire bug class this issue addresses. ruff is a pinned standalone binary (`0.5.0`) with
no `target-version` override, so it infers its target from `requires-python` and produces
byte-identical results on both; this was confirmed empirically. Running it twice would
waste CI minutes and report a single formatting slip as two failures.

**Why `fail-fast: false`.** The two matrix legs exist specifically to be *compared*.
Default fail-fast cancels the sibling job on first failure, which destroys the signal the
matrix was added to produce. With it disabled, a failure reveals whether the problem is
one dependency set or both — the difference between "version-specific" and "real bug",
which is exactly the distinction that made the mypy investigation above tractable.

**Endpoints, not exhaustive.** `["3.10", "3.14"]` covers the two dependency sets that
exist. 3.11/3.12/3.13 would add ~2.5× the CI minutes to re-test combinations that are
either identical or interpolate between two already-covered ones. `3.14` is pinned
deliberately rather than floating, so CI cannot turn red from an upstream release the
author did not make; `ci.yml` carries a comment recording that it is the intentional
upper endpoint and should be bumped when 3.15 ships.

### 2. Tooling pins

Bumped together, since CLAUDE.md requires CI and pre-commit stay pinned to the same
versions:

- `pyproject.toml`: `mypy==1.10.1` → `mypy==2.3.0`
- `.pre-commit-config.yaml`: mirrors-mypy `rev: "v1.10.1"` → `rev: "v2.3.0"`

`ruff==0.5.0` is **unchanged** in both files. It is already clean on both dependency
sets; bumping it is unrelated scope.

### 3. `.python-version`

New file at the repo root containing `3.10`. This makes a fresh clone deterministic and
aligned with the matrix's floor, so "works on my machine" means the same thing as "works
in CI's baseline job". CI's 3.14 leg is unaffected because it passes `--python 3.14`
explicitly, which overrides the file.

Accepted trade-off: local development then never exercises the newer dependency set. That
is acceptable precisely because CI now does — which is the point of the matrix.

### 4. The three type fixes

All three are real defects and are fixed as such. **No `# type: ignore` is added
anywhere** — suppressions were considered and rejected, because two of the three defects
are genuine nullability bugs that a suppression would merely re-hide.

**Fix 1 — `utilities/histogram.py`: getter/setter asymmetry.**
The `binning` getter declares `np.ndarray | int | None` and the class genuinely stores
`None`: `from_dict` (line 116) assigns it, and `add_entry` (line 139) tests
`if self.binning is None`. The setter declaring `np.ndarray | int` is simply wrong. Widen
it to `np.ndarray | int | None`. Signature-only change; no behaviour change.

**Fix 2 — `genericplot.py`: property cannot be narrowed.**
`GenericPlot.plot()` declares `-> plt.Axes`, guards `if self.ax is None`, then returns
`self.ax`. Correct at runtime, but mypy cannot narrow across a property setter. Bind a
local:

```python
def plot(self) -> plt.Axes:
    ax = self.ax
    if ax is None:
        ax = plt.subplots()[1]
        self.ax = ax
    getattr(ax, self.plotmethod)(*self.args, **self.kwargs)
    return ax
```

Same behaviour, and more explicit about the invariant.

**Fix 3 — `baseplotter.py`: `legend_loc` is too broad for matplotlib 3.11.**
`BasePlotter.legend_loc` is declared `str` (line 194); matplotlib 3.11 tightened
`Axes.legend`'s `loc` parameter to `Literal[...] | tuple[float, float] | int | None`,
which a bare `str` does not satisfy. Keeping the public property as `str` is correct —
narrowing it to matplotlib's literal set would couple this library's surface to their
stub internals. Collect the kwargs and splat:

```python
legend_kwargs: dict[str, Any] = {"ncol": ncol, "title": self.legend_title, "loc": self.legend_loc}
ax[0].legend(lines, labels, **legend_kwargs)
```

## Testing and verification

Exit criteria, all of which must hold before the branch is considered done:

- `pytest tests/` — 137 passed on **both** dependency sets (3.10 and 3.14).
- `mypy` — clean on **both** dependency sets, under `mypy==2.3.0`.
- `ruff check .` and `ruff format --check .` — clean.
- `verify-examples` skill — passes. Fixes 2 and 3 touch `genericplot.py` and
  `baseplotter.py`, both on the rendering path, so example output must be confirmed by
  running the examples rather than by inspection.
- `pre-commit run --all-files` — passes with the bumped mypy rev, confirming CI and
  pre-commit genuinely agree.

**New test required.** Fix 1 changes a signature covering a state the suite does not
currently exercise: there is no coverage of `Histogram.from_dict` with
`binning: None`. Per this repo's falsifiability rule, fix 1 ships with a test that
round-trips a `Histogram` whose binning is `None` and asserts `binning is None`
afterwards — a test that fails if the setter is narrowed back or `from_dict` starts
coercing `None`.

Verifying the matrix itself requires the workflow to actually run on GitHub; a local
green run proves only the 3.10 leg. The CI run on the PR is the evidence.

## Out of scope

- **`legend_ncol` is misnamed** — it is a divisor yielding "max rows per column", not a
  column count, and is separately coupled to the headroom calculation at
  `baseplotter.py:403`. Filed as #26. It touches the same statement as fix 3, so expect a
  trivial adjustment depending on merge order, but the changes are independent.
- **`legend_title`'s setter has the same asymmetry as `binning`** (accepts `str`, stores
  `str | None`). mypy does not flag it and it is unrelated to this issue.
- **Bumping `ruff`** — clean on both dependency sets; no reason to touch it here.
- **Adding more built-in experiments, PyPI publishing, release tagging** — unrelated;
  release mechanism is #6.
