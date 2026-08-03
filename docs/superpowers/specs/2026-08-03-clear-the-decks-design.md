# Clear the decks: sequencing the open work

Covers issues #21, #23 (via PR #27), #26, and repository branch hygiene. Sequencing only —
each item below still gets its own spec and plan where one is needed.

## Context

`main` is at `8632989` with CI green. The repo has ten open issues, one open pull request
from an outside contributor, one in-flight feature branch carrying a spec and plan but no
implementation, and nine remote branches of which most are dead.

The goal for this stretch is to **finish what is already in flight before starting anything
new**. No new feature work is scheduled here.

### What the open work actually looks like

| Item | State on 2026-08-03 |
|---|---|
| PR #27 (closes #23) | Fork PR from `kegodev`, CI held at `action_required` since 15:24Z |
| #21 CI matrix | Spec + plan committed on `feature/ci-python-version-matrix`, no implementation |
| #26 `legend_ncol` | Public API break; collides with #21 on `baseplotter.py:431` |
| #22, #24, #25, #6, #7, #8, #9 | Deferred — see "Out of scope" |

### PR #27 was audited, not assumed

The contributor is unknown to the maintainer and the repository was not expected to have
outside traffic yet, so the diff was checked rather than taken on trust:

- `uv.lock`: 13 changed lines, **all deletions**, touching only `importlib-resources` — its
  two dependency back-references, its `source`, and its sdist/wheel URL+hash entries. No
  package added, no index or registry URL altered, no hash rewritten on any surviving
  package. This is exactly what `uv lock` emits after the dependency is dropped.
- `pyproject.toml`: one line removed. `CLAUDE.md`: the matching follow-up bullet removed.
- Test-merged against `main` at `8632989`: clean, no conflict with PR #28's rewrite.
- Account `kegodev` (Kegorapetse) was created 2026-06-20, 8 public repos, no followers.
  Neutral evidence, recorded for completeness.

Approving the fork's workflow run is low-risk here for a specific, checkable reason: fork
PRs run under the `pull_request` trigger with a read-only `GITHUB_TOKEN` and no secret
access, and `update-workflow-images.yml` — the only workflow with `contents: write` —
triggers solely on push-to-`main` and `workflow_dispatch`, so a fork PR cannot reach it.
The diff touches no `src/` or `tests/` code, so CI executes this repository's code.

`CONTRIBUTING.md` already invites exactly this kind of contribution. The decision recorded
here is to accept it.

## Design

### Sequence

**Step 0 — maintainer action, blocks step 1.** Approve the held workflow run on PR #27.
This cannot be delegated; fork runs require a maintainer.

**Step 1 — PR #27.** Confirm CI green, merge with a merge commit. `Closes #23` fires
automatically.
*Exit: PR merged, #23 closed, `main` CI green.*

**Step 2 — branch hygiene.** Independent of every other step. Three actions, all detailed
under "Branch hygiene" below: delete the seven verifiably-merged branches, tag-then-delete
`PackageSetup`, and file the IceCube-as-registry-example issue before that deletion.
*Exit: `git branch -r` lists only `main`, `feature/ci-python-version-matrix`, and any live
PR branches; `archive/PackageSetup` exists at the remote; the IceCube issue is filed.*

**Step 3 — #21, the CI matrix.** This item **skips brainstorming and writing-plans**: its
design (`2026-08-03-ci-python-version-matrix-design.md`) and plan
(`2026-08-03-ci-python-version-matrix.md`) are already committed on
`feature/ci-python-version-matrix`. It proceeds directly to
`superpowers:subagent-driven-development` against that plan.

Exit criteria are defined in that spec — 137 tests on both dependency sets, mypy clean
under 2.3.0 on both, ruff clean, `verify-examples`, `pre-commit run --all-files` — plus two
additions from this session:

1. **Both matrix legs must be observed green on GitHub.** A local run proves only the 3.10
   leg; the CI run on the PR is the evidence.
2. **`CLAUDE.md`'s Setup section must be updated in the same PR.** It currently documents
   the "local mypy is red on a clean tree" behaviour caused by `mypy==1.10.1`, which this
   branch fixes by bumping to 2.3.0. Leaving it would restart the drift that PR #28 just
   corrected.

**Step 4 — #26, the `legend_ncol` rename.** Full cycle: its own brainstorming session, then
a plan, then implementation on top of merged #21.

Ordering rationale: #21's "fix 3" rewrites `baseplotter.py:431` from a positional call into
a kwargs splat, and #26 changes how `ncol` is computed. Landing #21 first means #26 edits a
dict entry rather than untangling a positional call, and #26's design is written against
code that already type-checks under mypy 2.3.0. The reverse order forces the larger,
already-planned branch to rebase onto a moving API.

### Decisions already settled for #26

- **Break policy: rename outright, no deprecation shim.** The project is pre-1.0 and
  installed from a moving `main`; the realistic user set does not justify a shim with no
  release cadence to retire it. The break is noted in the PR body.
- **Still open, for #26's own brainstorm:** issue option 1 (rename only) versus option 3
  (rename *and* fix the constant-headroom bug, where a 1-entry legend reserves the same
  vertical space as a 4-entry one). Option 2 (expose `ncol` directly, dropping auto-wrap)
  is also on the table.
- **Call sites that move with the rename:** `docs/getting-started.md:25`,
  `examples/workflow_demo.py:97` and its comment at lines 93–95,
  `tests/test_baseplotter.py:29` and `:270`, the default at `baseplotter.py:103`, the
  property pair at `:178`–`:183`, and the two reads at `:403` (headroom) and `:430` (the
  `ncol` computation feeding the legend call on `:431`).

### Branch hygiene

**Delete — verified merged into `main`** (`git merge-base --is-ancestor` against
`origin/main`), so their commits stay reachable and the deletion is recoverable:

- `docs/claude-md-refresh`
- `feature/auto-regen-workflow-images`
- `feature/stack-signals-on-top`
- `feature/standalone-package-and-skill`
- `fix/workflow-demo-signal-not-on-top`
- `worktree-agent-a4eeffbfc175ea8ab`
- `worktree-readme-workflow-example`

**Keep:** `feature/ci-python-version-matrix` — active, step 3.

**Archive, do not simply delete: `PackageSetup`.** Seven commits from 2026-01-29, *not*
merged. It is the precursor to the experiment registry and the only copy of an IceCube
experiment (`src/afplotter/experiments/i3.py`, `icecube.mplstyle`). Deleting it makes those
commits unreachable — real loss, unlike the seven above.

Plan: tag before removing.

```bash
git tag archive/PackageSetup origin/PackageSetup
git push origin archive/PackageSetup
git push origin --delete PackageSetup
```

`CLAUDE.md` argues against merging IceCube as a built-in ("Register your own via
`afplotter.experiments.registry.register(...)` rather than adding more built-ins for
experiments this repo's maintainer isn't part of"), though that policy postdates the
branch. The repo has **no worked example of registering a custom experiment**, which is the
very thing that policy directs users to do. IceCube is a ready-made one. File an issue to
lift `i3.py` + `icecube.mplstyle` into a docs example; tagging first means nothing is lost
if that extraction proves incomplete.

## Testing and verification

This spec schedules work rather than changing code, so its own verification is limited to
the claims it records:

- Branch merge status was established with `git merge-base --is-ancestor <branch>
  origin/main` for every remote branch, not by reading names or dates.
- PR #27's mergeability was established with `git merge-tree --write-tree origin/main`
  against the fetched PR head, not by GitHub's mergeable flag alone.
- The `uv.lock` audit above was run against the actual diff.

Each scheduled step carries its own exit criteria in the Sequence section. Step 3 inherits
the full criteria from the CI-matrix spec.

## Out of scope

Deferred deliberately; no new feature work until steps 1–4 are done.

- **#24, #25** — `good first issue`. Now worth *keeping* unassigned: the repository has
  outside contributors, and these are the on-ramp.
- **#22** (`Experiment.colors` / `labels["status"]` are never read) — a decision, not code.
  Natural pairing with the IceCube/registry-docs work above; both concern `Experiment`
  fields nothing consumes.
- **#6** (release mechanism) — revisit immediately after #26 lands. That rename is the
  first real API break, and the point at which a version number starts earning its keep.
- **#7** (watermark in plot title) — no dependencies; pick up any time.
- **#8 / #9** — **decide #8 before building #9.** Adopting `hist`/`boost-histogram` brings
  serialization with it, so a save/load mechanism built on the custom `Histogram` class
  risks being discarded. #8 is architecture-level and needs its own brainstorm.
- **Branch protection on `main`** — noted, not scheduled. Outside PRs can currently be
  merged without green CI, which matters more now than it did before #27 arrived.
