# Issue-Triggered Claude Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the maintainer turn an approved GitHub issue into an implemented PR by commenting `@claude`, using Anthropic's official `claude-code-action`, without exposing API budget to arbitrary public commenters.

**Architecture:** A single new GitHub Actions workflow that triggers on new issues and issue comments, and delegates to `anthropics/claude-code-action@v1`. The action's own default behavior — only users with write access to the repo can trigger it — is the access control; no custom gating logic is written.

**Tech Stack:** GitHub Actions (YAML), `anthropics/claude-code-action@v1`.

## Global Constraints

- This work assumes the `AFPlotter` GitHub repo is already public (owner: `AlexanderHeidelbach`). Do not check or change repo visibility — that's a manual step outside this plan.
- Do **not** set `allowed_non_write_users: true` — the action's own docs flag this as a real prompt-injection risk on a public repo, and it would defeat the entire point of this design (keeping the maintainer as the only one who can spend API budget).
- Do not implement a custom `if:`-condition permission check in the workflow YAML — the action's built-in write-access gate already does this; adding a redundant check is unnecessary complexity.
- The `ANTHROPIC_API_KEY` repository secret must be added manually by the maintainer via GitHub's web UI (Settings → Secrets and variables → Actions). This cannot be done as part of this plan — no task should attempt to set it, and the PR opened at the end must call this out as a required manual step before the workflow will actually run.
- End state is an open pull request against `main` for human review — do not merge it yourself.

---

### Task 1: Add the Claude Code Action workflow

**Files:**
- Create: `.github/workflows/claude.yml`

**Interfaces:**
- Produces: a workflow that fires when `@claude` appears in a newly opened issue's body, or in a comment on an issue, and runs `anthropics/claude-code-action@v1` with the permissions it needs to read the repo, push a branch, open a PR, and comment back.

Verified details (do not deviate): the action's documented input for the API key is `anthropic_api_key` (exact casing), wired to `${{ secrets.ANTHROPIC_API_KEY }}`. The documented `permissions:` block for this use case is exactly `contents: write`, `pull-requests: write`, `issues: write` — no `id-token` needed (that's only for OIDC/workload-identity auth, not used here). The action handles checking out the repository internally; no separate `actions/checkout` step is needed. Both `issues: [opened]` and `issue_comment: [created]` are documented trigger events for this action (confirmed against `anthropics/claude-code-action`'s own `docs/usage.md` examples) — this is what lets a student's issue body itself, or a later comment, both work as the trigger surface once the maintainer types `@claude`.

- [ ] **Step 1: Create `.github/workflows/claude.yml`**

```yaml
name: Claude Code Action

on:
  issues:
    types: [opened]
  issue_comment:
    types: [created]

jobs:
  claude-response:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
      issues: write
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          # By default, only users with write access to this repo can
          # trigger a run by mentioning @claude (the action's own default
          # gate — verified in anthropics/claude-code-action's docs). Do
          # NOT set allowed_non_write_users: true; that removes this gate
          # and is called out by the action's own docs as a real
          # prompt-injection risk on a public repo.
          #
          # To let a specific trusted student trigger this directly,
          # without granting them full collaborator/write access, add:
          # include_comments_by_actor: "username1,username2"
```

- [ ] **Step 2: Validate the workflow YAML parses correctly**

Run:
```bash
uv run --with pyyaml python3 -c "
import yaml, pathlib
yaml.safe_load(pathlib.Path('.github/workflows/claude.yml').read_text())
print('YAML OK')
"
```
Expected: prints `YAML OK` with no error output.

- [ ] **Step 3: Confirm the new workflow doesn't collide with the existing CI workflow's triggers**

Run:
```bash
cat .github/workflows/ci.yml
```
Expected: `ci.yml` triggers on `push` and `pull_request` only (confirm this by reading the output) — disjoint from the new workflow's `issues`/`issue_comment` triggers, so both workflows can coexist without interfering. If `ci.yml` has changed to also listen on `issues`/`issue_comment`, stop and flag this — that would be an unexpected conflict outside this plan's scope.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/claude.yml
git commit -m "Add @claude issue-to-PR automation workflow"
```

---

### Task 2: Open the PR with the manual secret step documented

**Files:** none (PR only)

**Interfaces:** none — this task ships the branch and makes the one required manual follow-up (adding the API key secret) visible to the maintainer.

- [ ] **Step 1: Push the branch**

```bash
git push -u origin HEAD
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "Add @claude issue-to-PR automation workflow" --body "$(cat <<'EOF'
## Summary
- Add `.github/workflows/claude.yml`, using `anthropics/claude-code-action@v1`, triggered when `@claude` appears in a newly opened issue or a comment on one
- Relies on the action's own default access control (only users with write access to the repo can trigger a run) — no custom permission check added
- `include_comments_by_actor` is documented inline in the workflow as a future option for allowlisting specific trusted students without granting them collaborator access

## Required manual step before this works
This workflow will fail every run until an `ANTHROPIC_API_KEY` repository
secret is added: **Settings → Secrets and variables → Actions → New
repository secret**, named exactly `ANTHROPIC_API_KEY`. This can't be done
from a PR/CI — it has to be added by a repo admin through the GitHub UI.

## Test plan
- [x] YAML validated with `python3 -c "import yaml; yaml.safe_load(...)"`
- [x] Confirmed no trigger overlap with the existing `ci.yml` workflow
- [ ] Manual, after merge and after the secret is added: open a real
      low-stakes test issue, comment `@claude`, and confirm a branch gets
      pushed, a PR gets opened referencing the issue, that PR passes the
      existing CI workflow, and a summary comment is posted back on the
      issue — before relying on this for real student-requested changes

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR created against `main`; report the PR URL back. Do not merge it.
