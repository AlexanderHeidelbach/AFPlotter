# Clear the Decks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the outside contributor's PR, reduce the remote branch list to only live branches without losing unmerged work, and leave `main` green.

**Architecture:** This plan changes repository *state*, not library code — no file in `src/` is touched. Every task is therefore verified by observing git and GitHub state rather than by unit tests. The one irreversible action (deleting an unmerged branch) is preceded by a tag that keeps its commits reachable.

**Tech Stack:** `git`, the `gh` CLI, GitHub Actions.

## Global Constraints

Copied from `docs/superpowers/specs/2026-08-03-clear-the-decks-design.md`:

- **No new feature work** until these steps and #21 are done.
- **Merge commits, not squash** — matches existing history (`Merge pull request #20 from …`).
- **Branch merge status is established with `git merge-base --is-ancestor <branch> origin/main`**, never by reading branch names or dates.
- **Never delete an unmerged branch without tagging it first.**
- Step 3 of the spec (#21, the CI matrix) is **not** in this plan. It already has its own plan at `docs/superpowers/plans/2026-08-03-ci-python-version-matrix.md` on `feature/ci-python-version-matrix`.
- Step 4 of the spec (#26, `legend_ncol`) is **not** in this plan. Its design question is still open; it needs its own brainstorming session first. See "Deferred" at the end.

### Known execution hazard

`gh pr merge` was blocked by the Claude Code permission classifier earlier in this session. If it is blocked again, **do not work around it** — stop and ask the maintainer to run the command, or to grant the permission. The same applies to `git push --delete`.

---

### Task 1: Merge PR #27

Closes #23. The diff was already audited in the spec (`uv.lock`: 11 lines, all deletions, only `importlib-resources`); no further code review is required.

**Files:**
- No local files. GitHub state only.

**Interfaces:**
- Consumes: nothing.
- Produces: a new `main` HEAD. Tasks 4 and 5 re-verify against it.

- [ ] **Step 1: Confirm the PR is green and mergeable**

```bash
gh pr checks 27
gh pr view 27 --json mergeable,mergeStateStatus -q '{mergeable:.mergeable,state:.mergeStateStatus}'
```

Expected: `test` shows `pass`; output is `{"mergeable":"MERGEABLE","state":"CLEAN"}`.
If `state` is `BLOCKED` or checks are `action_required`, stop — the maintainer must approve the fork's workflow run.

- [ ] **Step 2: Merge it**

```bash
gh pr merge 27 --merge
```

Expected: reports the PR was merged. If this is blocked by the permission classifier, stop and ask the maintainer to run it.

- [ ] **Step 3: Verify #23 closed automatically and main advanced**

```bash
gh issue view 23 --json state,stateReason -q '{state:.state,reason:.stateReason}'
git fetch origin && git log --oneline origin/main -2
```

Expected: `{"state":"CLOSED","reason":"COMPLETED"}`, and the newest `main` commit is the #27 merge.

- [ ] **Step 4: Verify the dependency is actually gone**

```bash
git show origin/main:pyproject.toml | grep -c importlib_resources
git show origin/main:uv.lock | grep -c 'name = "importlib-resources"'
```

Expected: both print `0`.

- [ ] **Step 5: Confirm CI on main is green and the image bot stayed quiet**

```bash
gh run list --branch main --limit 3 --json workflowName,conclusion \
  -q '.[] | "\(.workflowName) -> \(.conclusion)"'
git fetch origin && git log --oneline origin/main -1
```

Expected: both `CI` and `Update workflow demo images` report `success`, and `main`'s HEAD is still the #27 merge commit — **not** a commit titled `Auto-regenerate workflow demo images [skip ci]`. A bot commit here would mean the demo images became nondeterministic; if that happens, stop and investigate before continuing.

---

### Task 2: File the IceCube registry-example issue

Must happen **before** Task 3, because Task 3's annotated tag message cites the issue number — the issue has to exist first so the tag can reference it. (The tag itself, not the branch, is what the issue's recovery commands point at; nothing requires the branch to stay alive.)

**Files:**
- No local files. GitHub state only.

**Interfaces:**
- Consumes: nothing.
- Produces: an issue number, referenced in Task 3's tag message.

- [ ] **Step 1: Confirm the IceCube files exist on the branch and nowhere else**

```bash
git ls-tree -r --name-only origin/PackageSetup | grep -iE 'i3|icecube'
git ls-tree -r --name-only origin/main | grep -icE 'i3|icecube'
```

Expected: the first lists `src/afplotter/experiments/i3.py` and `src/afplotter/experiments/icecube.mplstyle`; the second prints `0`, confirming `main` has neither.

- [ ] **Step 2: Create the issue**

```bash
gh issue create \
  --title "Add a worked example of registering a custom experiment" \
  --label documentation \
  --body 'CLAUDE.md tells users to register their own experiment rather than adding built-ins:

> Register your own via `afplotter.experiments.registry.register(...)` rather than adding more built-ins for experiments this repo'\''s maintainer isn'\''t part of.

But there is no worked example of doing that anywhere in `docs/` or `examples/`.

The unmerged `PackageSetup` branch (archived as tag `archive/PackageSetup`) contains a ready-made one: `src/afplotter/experiments/i3.py` and `src/afplotter/experiments/icecube.mplstyle`, written before the registry policy existed.

Lift those into a documentation example showing the full path: define an `Experiment`, point it at a bundled `.mplstyle`, call `register(...)`, then `set_experiment(...)`. It should not ship IceCube as a built-in — that is the thing the policy rules out.

Recover the files with:

    git show archive/PackageSetup:src/afplotter/experiments/i3.py
    git show archive/PackageSetup:src/afplotter/experiments/icecube.mplstyle

Related: #22 (dead `Experiment.colors` / `labels["status"]` fields).'
```

Expected: prints the new issue URL. Record the number — call it `<ICEISSUE>` below.

- [ ] **Step 3: Verify it was created**

```bash
gh issue list --state open --limit 5 --json number,title -q '.[] | "#\(.number) \(.title)"'
```

Expected: the new issue appears in the list.

---

### Task 3: Archive and delete `PackageSetup`

This is the only irreversible step in the plan. The tag is what makes it safe: after the branch ref is gone, its commits stay reachable through the tag.

**Files:**
- No local files. Git ref state only.

**Interfaces:**
- Consumes: `<ICEISSUE>` from Task 2.
- Produces: tag `archive/PackageSetup` at the remote.

- [ ] **Step 1: Confirm it is genuinely unmerged (the reason for the tag)**

```bash
git merge-base --is-ancestor origin/PackageSetup origin/main && echo "MERGED" || echo "NOT MERGED"
git rev-list --count origin/main..origin/PackageSetup
```

Expected: `NOT MERGED`, and a count of `7`.
If it prints `MERGED`, the tag is unnecessary — skip to Step 4 and note it in the commit/PR.

- [ ] **Step 2: Create an annotated tag**

Replace `<ICEISSUE>` with the number from Task 2.

```bash
git tag -a archive/PackageSetup origin/PackageSetup \
  -m "Archived unmerged PackageSetup branch (7 commits, 2026-01-29).

Precursor to the experiment registry. Sole copy of the IceCube experiment
(src/afplotter/experiments/i3.py, icecube.mplstyle) -- see #<ICEISSUE>."
```

- [ ] **Step 3: Push the tag and verify it is on the remote before deleting anything**

```bash
git push origin archive/PackageSetup
git ls-remote --tags origin archive/PackageSetup
```

Expected: `ls-remote` prints a line containing `refs/tags/archive/PackageSetup`. **If it prints nothing, stop — do not proceed to Step 4.**

- [ ] **Step 4: Delete the remote branch**

```bash
git push origin --delete PackageSetup
```

- [ ] **Step 5: Verify the branch is gone but its commits survive**

```bash
git ls-remote --heads origin PackageSetup
git show archive/PackageSetup:src/afplotter/experiments/i3.py | head -5
```

Expected: `ls-remote` prints nothing; the `git show` prints the first lines of the IceCube experiment, proving the content is still recoverable.

---

### Task 4: Delete the seven merged branches

**Files:**
- No local files. Git ref state only.

**Interfaces:**
- Consumes: `main` HEAD from Task 1.
- Produces: a pruned remote branch list, asserted in Task 5.

- [ ] **Step 1: Re-verify every branch is merged into the CURRENT main**

`main` moved in Task 1, so this must be re-run rather than trusting the spec's list.

```bash
git fetch origin --prune
for b in docs/claude-md-refresh feature/auto-regen-workflow-images \
         feature/stack-signals-on-top feature/standalone-package-and-skill \
         fix/workflow-demo-signal-not-on-top worktree-agent-a4eeffbfc175ea8ab \
         worktree-readme-workflow-example; do
  git merge-base --is-ancestor "origin/$b" origin/main \
    && echo "OK merged: $b" || echo "!! NOT merged: $b"
done
```

Expected: seven `OK merged` lines and no `!!` lines. **If any branch reports `!! NOT merged`, do not delete that one** — treat it like `PackageSetup` and tag it first.

- [ ] **Step 2: Delete them**

```bash
git push origin --delete \
  docs/claude-md-refresh \
  feature/auto-regen-workflow-images \
  feature/stack-signals-on-top \
  feature/standalone-package-and-skill \
  fix/workflow-demo-signal-not-on-top \
  worktree-agent-a4eeffbfc175ea8ab \
  worktree-readme-workflow-example
```

- [ ] **Step 3: Prune local tracking refs and verify what remains**

```bash
git fetch origin --prune
git branch -r --format='%(refname:short)'
```

Expected: only `origin/main`, `origin/feature/ci-python-version-matrix`, and `origin/docs/clear-the-decks-spec` remain — the last is this plan's own branch, still open at this point and merged by Task 5. `origin/PackageSetup` must be absent.

- [ ] **Step 4: Confirm main is unaffected**

```bash
git log --oneline origin/main -1
uv run pytest tests/ -q 2>&1 | tail -2
```

Expected: `main` HEAD unchanged from Task 1, and the suite passes (137 tests as of this plan's writing).

---

### Task 5: Merge the spec and plan branch

**Files:**
- Modify: none. Merges `docs/clear-the-decks-spec`, which contains this plan and its spec.

**Interfaces:**
- Consumes: nothing.
- Produces: spec and plan on `main`.

- [ ] **Step 1: Push the branch**

The spec and this plan are already committed on `docs/clear-the-decks-spec`. Confirm, then push.

```bash
git log --oneline origin/main..docs/clear-the-decks-spec
git push origin docs/clear-the-decks-spec
```

Expected: two commits listed — one adding the design spec, one adding this plan.

- [ ] **Step 2: Open the PR**

```bash
gh pr create --base main --head docs/clear-the-decks-spec \
  --title "Add spec and plan for clearing the open work" \
  --body 'Sequencing spec and implementation plan covering PR #27 (closes #23), branch hygiene, and the ordering of #21 before #26.

Docs only -- no code changes. #21 and #26 keep their own separate cycles.'
```

- [ ] **Step 3: Wait for CI, then merge**

```bash
gh pr checks --watch
gh pr merge --merge --delete-branch
```

Expected: checks pass, PR merges. If `gh pr merge` is blocked, stop and ask the maintainer.

- [ ] **Step 4: Verify**

```bash
git fetch origin --prune
git ls-tree origin/main --name-only docs/superpowers/plans/ | grep clear-the-decks
```

Expected: prints `docs/superpowers/plans/2026-08-03-clear-the-decks.md`.

---

## Deferred — not tasks in this plan

**#21, the CI matrix.** Has its own plan on `feature/ci-python-version-matrix`. Execute that plan separately. Two exit criteria were added by the spec: both matrix legs observed green on GitHub, and `CLAUDE.md`'s Setup section updated in the same PR (it currently documents the `mypy==1.10.1` behaviour that branch removes).

**#26, `legend_ncol`.** Cannot be planned yet. The spec settled the *break policy* (rename outright, no shim) but deliberately left the design open between issue option 1 (rename only), option 2 (expose `ncol` directly, dropping auto-wrap), and option 3 (rename plus fixing the constant-headroom bug, where a 1-entry legend reserves the same vertical space as a 4-entry one). Those yield different implementations and different tests, so #26 needs its own brainstorming session before a plan can exist. Start it only after #21 has merged — the spec's ordering rationale depends on #21's kwargs-splat rewrite landing first.

Call sites the eventual #26 plan must cover, verified against `baseplotter.py` at `8632989`: the default at `:103`, the property pair at `:178`–`:183`, the headroom read at `:403`, the `ncol` computation at `:430` feeding the legend call at `:431`, plus `docs/getting-started.md:25`, `examples/workflow_demo.py:97` and its comment at `:93`–`:95`, and `tests/test_baseplotter.py:29` and `:270`.

---

## Outcome

`.superpowers/sdd/` is gitignored, so this section is the only committed record that this
plan ran. Recorded factually, without ticking the checkboxes above:

- **Task 1.** PR #27 merged with a merge commit (`9f8e89d`). Issue #23 auto-closed with
  `stateReason: COMPLETED`.
- **Task 2.** Issue #29, "Add a worked example of registering a custom experiment", was
  filed.
- **Task 3.** `PackageSetup` was archived as annotated tag `archive/PackageSetup` (tip
  commit `5509ce3`), carrying the branch's provenance and referencing #29. The tag was
  confirmed present on the remote via `git ls-remote --tags` *before* the branch ref was
  deleted. The IceCube files (`i3.py`, `icecube.mplstyle`) remain recoverable from the tag.
- **Task 4.** The seven verifiably-merged branches were deleted. `git push origin --delete`
  was **blocked by the Claude Code permission classifier**; per the plan's "Known execution
  hazard," the agent did not work around it — the repository maintainer ran the deletion
  manually. The agent's own contribution was limited to the verification steps (merge-base
  checks before, `git branch -r` / CI checks after).
- **Task 5.** This plan's own branch merged as PR #30, merge commit `0a25b7b`.
