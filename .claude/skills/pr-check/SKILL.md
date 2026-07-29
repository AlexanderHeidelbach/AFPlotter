---
name: pr-check
description: Use when finishing a branch or preparing to open/update a PR in this repo, before claiming tests/lint/mypy are clean.
---

# PR Check

## Overview

This repo carries pre-existing lint/mypy debt on `main` (see `CLAUDE.md`), so a
raw `ruff check` or `mypy` run reports a nonzero count on a clean branch too.
The question that matters is never "how many errors are there" — it's
"did this branch add any." Answer that by diffing against the base branch,
never by mutating the repo.

**Never run `pre-commit run --all-files`, bare `ruff format` (no `--check`), or
`ruff check --fix` across the whole repo as a check step.** These mutate
files this branch never touched, reformatting them under whatever `ruff`
version happens to be installed locally — producing unrelated churn that
looks like part of the diff and is easy to accidentally commit. If a baseline
run does this, the fix is `git status` + `git checkout -- .` on the
untouched files it reformatted, not committing the reformat.

## Steps

1. **Tests**: `uv run pytest tests/ -v`. Must be 100% pass. Report the count.
2. **Lint/type delta vs base**, on both the merge-base commit and HEAD, read-only:
   ```
   uv run ruff check .
   uv run ruff format --check .   # --check only, never bare `ruff format`
   uv run mypy src/
   ```
   Compare HEAD's output against the same commands run at the branch's
   merge-base (`git merge-base main HEAD`, checked out in a worktree or
   `git stash`/`git worktree add` — never by resetting the current tree).
   Report: any error/file newly present at HEAD that wasn't at the base is a
   regression to fix; everything else is pre-existing debt, not this branch's
   problem.
3. **Examples**: run the verify-examples check (**REQUIRED SUB-SKILL:** use
   `verify-examples`) — this repo's examples are gitignored-output scripts
   that must actually execute, not just import cleanly.
4. Report one pass/fail line per gate item (tests, lint delta, format delta,
   mypy delta, examples), then an explicit overall verdict.

## Quick Reference

| Gate | Command | Pass condition |
|---|---|---|
| Tests | `uv run pytest tests/ -v` | 100% pass |
| Lint delta | `uv run ruff check .` at base vs HEAD | no new errors |
| Format delta | `uv run ruff format --check .` at base vs HEAD | no newly-dirty files this branch touched |
| Type delta | `uv run mypy src/` at base vs HEAD | no new errors |
| Examples | `verify-examples` skill | all documented examples exit 0 with real output |

## Common Mistakes

- Reporting raw `ruff`/`mypy` error counts as if they mean something on their
  own — this repo's counts are nonzero on a clean `main`. Always diff against base.
- Running a repo-wide autofix/reformat as a "check" and leaving the tree dirty.
- Skipping the examples check because tests passed — tests don't execute
  `examples/`, and it's a separate, real gate `CLAUDE.md` calls out.
