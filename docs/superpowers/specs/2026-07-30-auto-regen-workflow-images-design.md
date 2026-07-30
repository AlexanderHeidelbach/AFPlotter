# Auto-regenerate README workflow images on merge

## Context

`examples/workflow_demo.py` (added in PR #17) produces the three PNGs embedded in
README.md's "How you'd actually use this" section: `docs/img/workflow/01-histogram.png`,
`02-stacked-pull.png`, `03-kit-colors.png`. These are committed, non-generated files —
nothing keeps them in sync with the plotting code. PR #11 (merged separately, stacking
`type="signal"` entries on top of the background instead of only overlaying them) is a
concrete example of a merged change that could visibly affect these images, and nothing
would catch or fix that automatically; a human has to remember to re-run the script and
commit the result.

This spec is phase 1 of a larger idea (discussed in `docs/superpowers/specs/` chat
history, not yet written up): automatically keeping the README's demonstration images
honest. Two further phases were explicitly deferred, and are out of scope here:

- **Phase 2**: generating the images by actually running the three README prompts
  through Claude (via the Anthropic API or the Claude Code GitHub Action) instead of
  the deterministic script, so the images pick up real model-driven drift over time.
  Needs an `ANTHROPIC_API_KEY` repo secret, incurs real per-run API cost, and needs a
  policy for a run that fails or produces something visibly broken. Not attempted here.
- **Phase 3**: a historical timeline/gallery showing how the images evolved across
  merged PRs. Would consume phase 1's (or phase 2's) commit history as its data source,
  so it can't be built first.

Phase 1 covers only: re-running the *existing* deterministic script whenever `main`
changes, and committing the result if it actually changed.

## Design

### New workflow file

`.github/workflows/update-workflow-images.yml`, triggered on `push` to `main` only:

```yaml
on:
  push:
    branches: [main]
```

This deliberately does **not** trigger on `pull_request` — the images should reflect
what's actually merged, not a PR's proposed state, and re-running on every push to a
feature branch would be wasted CI time for a change that isn't landed yet.

### Job steps

Mirrors `ci.yml`'s existing setup (same `uv`/Python 3.10 install pattern) plus:

1. Check out `main` with `contents: write` permission (needed for the push-back step)
   and a token that can push — the default `GITHUB_TOKEN` is sufficient for pushing to
   the same repo.
2. `uv sync --extra dev --python 3.10 --locked` (same as `ci.yml`).
3. `uv run python examples/workflow_demo.py` — regenerates the three PNGs in place.
   If this step exits non-zero, the job fails here; nothing downstream runs. This is a
   real signal (the plotting API changed under the script in some incompatible way) and
   must not be swallowed.
4. `git status --porcelain docs/img/workflow/` to check whether the regenerated PNGs
   differ from what's committed.
   - **If the output is empty** (no diff): the job ends successfully here, no commit.
     This is the common case — most merges won't touch code that affects these three
     plots.
   - **If there is a diff**: proceed to the commit step.
5. Commit step (only reached when step 4 found a diff):
   ```bash
   git config user.name "github-actions[bot]"
   git config user.email "github-actions[bot]@users.noreply.github.com"
   git add docs/img/workflow/
   git commit -m "Auto-regenerate workflow demo images [skip ci]"
   git push
   ```
   The `[skip ci]` marker in the commit message prevents this push from re-triggering
   `ci.yml`'s test/lint/mypy job (GitHub Actions honors `[skip ci]`/`[ci skip]` in the
   *head* commit message of a push to suppress workflow runs on that specific push) —
   without it, every image-regeneration commit would spawn a second, pointless CI run
   testing code that didn't change. It does **not** suppress `update-workflow-images.yml`
   itself from re-running on this push (that workflow doesn't check for the marker), but
   that's harmless: the second run's own regeneration step will find no diff (the images
   it would produce are identical to what it just committed) and exit at step 4 with no
   further action — not a loop, just one extra idle run.

### Race with concurrent merges

If two PRs merge to `main` in quick succession, the second workflow run's `git push` in
step 5 could be rejected (the remote moved since checkout). Handle this the simple way:
`git pull --rebase` immediately before `git push`, retried once. This is a docs-only,
generated-file commit with no possibility of a real merge conflict (the only file changed
is the PNGs this same script would regenerate identically), so a single retry is enough —
no need for a more elaborate lock/queue mechanism.

### Testing

This is a CI workflow, not library code — there's no pytest-level test for it. Verification
is procedural:

- Push a commit to a throwaway branch that intentionally changes `workflow_demo.py`'s
  output (e.g. temporarily tweak a color), open it against `main` in a scratch/fork
  context if needed, merge it, and confirm the workflow runs, detects the diff, and
  pushes a commit with the regenerated images.
- Separately confirm a no-op merge (one that doesn't touch anything affecting the three
  images) results in the workflow running but making no commit.
- Confirm the `[skip ci]` commit does not spawn a redundant `ci.yml` run, by checking the
  Actions tab after a real regeneration commit.

## Out of scope

- Phase 2 (LLM-driven prompt evaluation) and phase 3 (historical timeline) as described
  in Context above.
- Any change to `examples/workflow_demo.py` itself, or to which images it produces —
  this phase only wires up *when* it re-runs, not what it does.
- Branch protection / required-status-check configuration for the new workflow — it's
  additive (a bot commit after the fact), not a merge gate, so it doesn't need to block
  anything.
