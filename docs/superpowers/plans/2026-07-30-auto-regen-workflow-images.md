# Auto-Regenerate README Workflow Images Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GitHub Actions workflow that re-runs `examples/workflow_demo.py` whenever `main` changes, and commits the regenerated `docs/img/workflow/*.png` files back to `main` if the script's output actually differs from what's committed.

**Architecture:** One new workflow file, `.github/workflows/update-workflow-images.yml`, triggered on `push` to `main` (plus `workflow_dispatch` for manual runs — see Global Constraints). It reuses `ci.yml`'s existing `uv`/Python 3.10 setup pattern, runs the script, diffs the output directory, and — only if there's a diff — commits with a bot identity and a `[skip ci]` marker, retrying the push once via rebase if a concurrent merge raced it.

**Tech Stack:** GitHub Actions (YAML), bash, existing `uv run python examples/workflow_demo.py`.

## Global Constraints

- Trigger is `push` to `main` only — not `pull_request` (per spec: images must reflect what's actually merged, not a PR's proposed state).
- Also trigger on `workflow_dispatch` — not in the original spec discussion, but added here so a human can manually verify/re-run the workflow (`gh workflow run ...`) without needing a real merge to `main`, per this plan's Task 1 verification step. This is additive and doesn't change the spec's push-triggered behavior; note it in the PR description as a deliberate small addition.
- If `examples/workflow_demo.py` exits non-zero, the job must fail loudly — no swallowing that error.
- If the regenerated images are byte-identical to what's committed, no commit is made — this must be the observed behavior for a no-op run, not just assumed.
- Commit message must contain `[skip ci]` so the commit doesn't re-trigger `ci.yml`'s test/lint/mypy job.
- Bot identity: `github-actions[bot]` / `github-actions[bot]@users.noreply.github.com`.
- On `git push` failure (e.g. a concurrent merge moved `main`), retry exactly once via `git pull --rebase` then `git push` — fail the job if the retry also fails.
- `main` has no branch protection rules (confirmed via `gh api repos/.../branches/main/protection` → 404 "Branch not protected"), so a direct bot push with the default `GITHUB_TOKEN` and `permissions: contents: write` will succeed without further repo configuration.
- This is a CI-infrastructure change, not library code — no pytest tests apply. Verification is procedural (see Task 1's steps).

---

### Task 1: `.github/workflows/update-workflow-images.yml`

**Files:**
- Create: `.github/workflows/update-workflow-images.yml`

**Interfaces:**
- Consumes: `examples/workflow_demo.py` (existing, unmodified — writes to `docs/img/workflow/01-histogram.png`, `02-stacked-pull.png`, `03-kit-colors.png`) and the same `uv`/Python 3.10 setup steps already proven in `.github/workflows/ci.yml`.
- Produces: nothing consumed by other tasks — this is the only task in this plan.

- [ ] **Step 1: Write the workflow file**

```yaml
# .github/workflows/update-workflow-images.yml
name: Update workflow demo images

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update-images:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install Python 3.10
        run: uv python install 3.10

      - name: Install dependencies
        run: uv sync --extra dev --python 3.10 --locked

      - name: Regenerate workflow demo images
        run: uv run python examples/workflow_demo.py

      - name: Check for changes
        id: diff
        run: |
          if git status --porcelain docs/img/workflow/ | grep -q .; then
            echo "changed=true" >> "$GITHUB_OUTPUT"
          else
            echo "changed=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Commit and push regenerated images
        if: steps.diff.outputs.changed == 'true'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add docs/img/workflow/
          git commit -m "Auto-regenerate workflow demo images [skip ci]"
          for attempt in 1 2; do
            if git push; then
              exit 0
            fi
            if [ "$attempt" -eq 2 ]; then
              echo "push failed after retry" >&2
              exit 1
            fi
            git pull --rebase
          done
```

- [ ] **Step 2: Validate YAML syntax**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/update-workflow-images.yml'))" && echo VALID`
Expected: `VALID` printed, no exception. (`pyyaml` ships transitively via existing dev dependencies; if this specific command errors with `ModuleNotFoundError: yaml`, run `uv run --with pyyaml python -c "..."` instead — do not add `pyyaml` as a project dependency just for this one-off check.)

- [ ] **Step 3: Validate with actionlint if available**

Run: `which actionlint && actionlint .github/workflows/update-workflow-images.yml || echo "actionlint not installed, skipping"`
Expected: either actionlint reports no errors, or the "not installed" message — both are acceptable; actionlint is a nice-to-have static check, not a hard requirement for this repo (it's not currently a project dependency).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/update-workflow-images.yml
git commit -m "$(cat <<'EOF'
Add workflow to auto-regenerate README demo images on merge

examples/workflow_demo.py's output PNGs are committed files with
nothing keeping them in sync with the plotting code. This re-runs the
script whenever main changes and commits the regenerated images back
if they actually differ, so a merge like #11 (which could visibly
affect stacked-signal plots) can't silently leave the README stale.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Push this branch and verify the workflow runs correctly via `workflow_dispatch` before merging**

This step verifies real GitHub Actions behavior, which cannot be checked locally — push the branch first:

```bash
git push -u origin feature/auto-regen-workflow-images
```

Then trigger a manual run on this branch's own workflow definition:

```bash
gh workflow run update-workflow-images.yml --ref feature/auto-regen-workflow-images
```

Wait for it via `gh run watch` (or `gh run list --workflow=update-workflow-images.yml --limit 1` polling), then inspect the run:

- Expected: the "Regenerate workflow demo images" step succeeds (exit 0).
- Expected: the "Check for changes" step's `changed` output is `false` (the images on this branch are already up to date with the code, since Task 1 didn't touch `examples/workflow_demo.py` or any plotting code) — confirm via the step's log output, and confirm the "Commit and push regenerated images" step shows as **skipped** in the run, not executed.
- If `changed` unexpectedly comes back `true`: do not treat this as success. Inspect what differs (`git diff docs/img/workflow/` locally after running the script yourself) — it means something about the branch's committed images and the script's actual output have already drifted, which is a real bug to fix (either in the images or in the script) before this workflow can be trusted, not something to paper over.

- [ ] **Step 6: Report the verification result**

Write a short note (in the PR description, not a new file) confirming: workflow ran via manual dispatch, regeneration step succeeded, no-diff path was correctly taken (no spurious commit). This is the evidence a task reviewer needs — screenshot or `gh run view <run-id> --log` excerpt showing the "Check for changes" step's output and the "Commit and push" step's `skipped` status.

## Self-Review Notes

- **Spec coverage:** push-to-main trigger → workflow `on.push.branches`; reuse of `ci.yml`'s setup pattern → Step 1; script re-run and fail-loud on error → Step 1 (no `continue-on-error`, no `|| true`); diff-check before commit → Step 1's "Check for changes" step; bot identity + `[skip ci]` → Step 1's commit step; retry-once-via-rebase on push race → Step 1's `for attempt in 1 2` loop; "out of scope: phase 2/3" → not touched by this plan, no task references LLM generation or a timeline view.
- **Placeholder scan:** no TBD/TODO; the YAML is complete and copy-pasteable; the actionlint step explicitly allows for the tool being absent rather than leaving a vague "check with a linter" instruction.
- **Type consistency:** N/A — no Python interfaces are introduced; the only "interface" is the workflow's own step-output contract (`steps.diff.outputs.changed`), defined and consumed within the same file/task.
- **One addition beyond the literal spec:** `workflow_dispatch` as a second trigger. The spec's own Testing section calls for merging a throwaway change into `main` to verify behavior — doing that against the user's real `main` to test infrastructure is heavier than necessary. `workflow_dispatch` gives an equivalent, lower-risk verification path (Step 5) without fabricating a real merge, and remains useful afterward as a manual escape hatch. Flagged in Global Constraints and called out again here for visibility at review time.
