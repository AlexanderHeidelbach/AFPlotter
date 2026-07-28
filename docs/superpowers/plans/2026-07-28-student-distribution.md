# Student Distribution (Marketplace + Install Script) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let students get both the `afplotter` package and its existing Claude Code skill with minimal setup, via a Claude Code plugin marketplace (primary) and a one-command install script (alternative).

**Architecture:** Two static, independent additions to the repo root — a plugin marketplace manifest pair that references the *existing* `.claude/skills/afplotter/SKILL.md` in place, and a small idempotent shell script that pip-installs the package and copies the skill file into `~/.claude/skills/afplotter/`. A README section documents both, marketplace first.

**Tech Stack:** JSON (plugin manifests), POSIX shell (install script), Markdown (README).

## Global Constraints

- This work assumes the `AFPlotter` GitHub repo is already public (owner: `AlexanderHeidelbach`). Do not check or change repo visibility — that's a manual step outside this plan.
- Do not move or duplicate `.claude/skills/afplotter/SKILL.md` — both distribution paths must reference/copy it, not fork its content.
- `pip install` stays git-based: `pip install git+https://github.com/AlexanderHeidelbach/AFPlotter.git`. Do not add PyPI publishing.
- End state is an open pull request against `main` for human review — do not merge it yourself.
- Follow this repo's existing commit style (see `git log` for examples); commit after each task.

---

### Task 1: Plugin marketplace manifest

**Files:**
- Create: `.claude-plugin/marketplace.json`
- Create: `.claude-plugin/plugin.json`

**Interfaces:**
- Produces: a plugin named `afplotter`, installable via `claude marketplace add AlexanderHeidelbach/AFPlotter` then `claude plugin install afplotter`. Task 3 (README) references this exact plugin name and these exact commands.
- Consumes: the existing `.claude/skills/afplotter/SKILL.md` (already in the repo, untouched by this task) via the marketplace entry's `skills` field.

Verified schema notes (do not deviate): `marketplace.json` lives at `.claude-plugin/marketplace.json` at the repo root. Its `plugins[]` entries can point at a skill directory *within* the plugin's own source tree via a `skills` array of relative paths — this is exactly how we include the existing skill without moving it. A same-repo plugin's `source` is `"./"` (repo root, resolved relative to the directory containing `.claude-plugin/`).

- [ ] **Step 1: Create `.claude-plugin/marketplace.json`**

```json
{
  "name": "afplotter-tools",
  "owner": {
    "name": "Alexander Heidelbach",
    "email": "heidelbachalex@gmail.com"
  },
  "plugins": [
    {
      "name": "afplotter",
      "source": "./",
      "skills": ["./.claude/skills/afplotter"],
      "description": "Claude Code skill for the AFPlotter HEP plotting library (Belle II / generic analyses)",
      "version": "1.0.0",
      "author": {
        "name": "Alexander Heidelbach"
      },
      "homepage": "https://github.com/AlexanderHeidelbach/AFPlotter",
      "repository": "https://github.com/AlexanderHeidelbach/AFPlotter"
    }
  ]
}
```

- [ ] **Step 2: Create `.claude-plugin/plugin.json`**

```json
{
  "name": "afplotter",
  "description": "Claude Code skill for the AFPlotter HEP plotting library (Belle II / generic analyses)",
  "version": "1.0.0",
  "author": {
    "name": "Alexander Heidelbach"
  }
}
```

- [ ] **Step 3: Validate both files are syntactically valid JSON**

Run:
```bash
python3 -m json.tool .claude-plugin/marketplace.json > /dev/null && echo "marketplace.json OK"
python3 -m json.tool .claude-plugin/plugin.json > /dev/null && echo "plugin.json OK"
```
Expected: both print their `OK` line with no error output.

- [ ] **Step 4: Confirm the referenced skill file exists at the path used in Step 1**

Run:
```bash
test -f .claude/skills/afplotter/SKILL.md && echo "skill file present"
```
Expected: prints `skill file present`. If this fails, stop — do not create a new skill file; the plan assumes it already exists (it was added in an earlier, unrelated change).

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/marketplace.json .claude-plugin/plugin.json
git commit -m "Add Claude Code plugin marketplace for the afplotter skill"
```

---

### Task 2: Install script

**Files:**
- Create: `install.sh` (repo root)

**Interfaces:**
- Produces: a script named `install.sh` at the repo root, runnable via `curl -sSL https://raw.githubusercontent.com/AlexanderHeidelbach/AFPlotter/main/install.sh | bash`. Task 3 (README) references this exact command.
- Consumes: `.claude/skills/afplotter/SKILL.md` (existing, unmodified) by fetching it from GitHub's raw content host at install time — it does not read from the local checkout, since it must also work for a student who has not cloned the repo.

Note: there is an unrelated pre-existing `setup.sh` at the repo root (currently empty, unreferenced anywhere in the repo per `git log -- setup.sh` and a repo-wide grep). Do not touch, rename, or repurpose it — it's out of scope for this plan. Use the separate filename `install.sh`.

- [ ] **Step 1: Create `install.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Installing afplotter..."
pip install --upgrade "git+https://github.com/AlexanderHeidelbach/AFPlotter.git"

SKILL_DIR="$HOME/.claude/skills/afplotter"
mkdir -p "$SKILL_DIR"

echo "Installing the afplotter Claude Code skill to $SKILL_DIR..."
curl -sSL -o "$SKILL_DIR/SKILL.md" \
  "https://raw.githubusercontent.com/AlexanderHeidelbach/AFPlotter/main/.claude/skills/afplotter/SKILL.md"

echo "Done. Re-run this script any time to pick up updates."
```

- [ ] **Step 2: Make it executable**

Run:
```bash
chmod +x install.sh
```

- [ ] **Step 3: Check shell syntax**

Run:
```bash
bash -n install.sh && echo "syntax OK"
```
Expected: prints `syntax OK` with no error output. (This only checks parse-time syntax — it does not execute the script, since execution needs network access and would install the package into whatever environment runs it.)

- [ ] **Step 4: Manual verification (not automatable in this task — do this yourself before merging)**

Run in a scratch directory with a throwaway `HOME`, to avoid touching your real `~/.claude`:

```bash
HOME=/tmp/afplotter-install-test bash install.sh
test -f /tmp/afplotter-install-test/.claude/skills/afplotter/SKILL.md && echo "skill file installed"
python3 -c "import afplotter; print('afplotter import OK')"
```

Expected: both `echo`/`print` lines succeed. This step needs network access and a real `pip`/`python3`, so it isn't part of the automated task steps — note in the PR description that this manual check should happen before merge.

- [ ] **Step 5: Commit**

```bash
git add install.sh
git commit -m "Add one-command install script for package + Claude Code skill"
```

---

### Task 3: README documentation

**Files:**
- Modify: `README.md:16-18` (insert a new section between the existing `## Install` and `## Quickstart` sections)

**Interfaces:**
- Consumes: the exact plugin name (`afplotter`) and marketplace commands from Task 1; the exact install command from Task 2. Do not invent different command text — use exactly what Tasks 1 and 2 produced.

- [ ] **Step 1: Insert a new "Claude Code skill" section into `README.md`**

Current `README.md` lines 12-18 read:
```
Or for local development:

    git clone https://github.com/AlexanderHeidelbach/AFPlotter.git
    cd AFPlotter
    uv sync --extra dev

## Quickstart
```

Replace that block with (adds a new section, keeps everything else identical):
```
Or for local development:

    git clone https://github.com/AlexanderHeidelbach/AFPlotter.git
    cd AFPlotter
    uv sync --extra dev

## Claude Code skill (optional)

AFPlotter ships a Claude Code skill so you can ask Claude to make plots for
you directly, using this library. Two ways to get it — pick whichever you
prefer:

**Claude Code plugin marketplace (recommended):**

    claude marketplace add AlexanderHeidelbach/AFPlotter
    claude plugin install afplotter

Update later with `claude plugin update afplotter`.

**One-command install** (installs both the package and the skill in one
step, no `claude` CLI concepts required):

    curl -sSL https://raw.githubusercontent.com/AlexanderHeidelbach/AFPlotter/main/install.sh | bash

Re-run the same command any time to pick up updates.

## Quickstart
```

- [ ] **Step 2: Confirm the file still renders as valid Markdown structure**

Run:
```bash
grep -c "^## " README.md
```
Expected: prints `4` (the original 3 section headers — Install, Quickstart, Docs — plus the 1 new "Claude Code skill" header; the repo's `# AFPlotter` title is a level-1 header and not counted here). If the count doesn't match, re-check the edit didn't accidentally duplicate or drop a header.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document Claude Code skill distribution in README"
```

---

### Task 4: Run the existing test suite and open the PR

**Files:** none (verification + PR only)

**Interfaces:** none — this task only verifies Tasks 1-3 didn't break anything and ships the branch.

- [ ] **Step 1: Run the full existing test suite to confirm no regression**

Run:
```bash
uv run pytest tests/ -v
```
Expected: all tests pass (this change touches no `src/afplotter` code, so this is a regression check, not a check of new behavior — the new behavior was verified in Tasks 1-3's own steps).

- [ ] **Step 2: Push the branch**

```bash
git push -u origin HEAD
```

- [ ] **Step 3: Open the PR**

```bash
gh pr create --title "Add Claude Code plugin marketplace and install script for students" --body "$(cat <<'EOF'
## Summary
- Add a Claude Code plugin marketplace (`.claude-plugin/marketplace.json` + `plugin.json`) exposing the existing `afplotter` skill via `claude marketplace add` / `claude plugin install`
- Add `install.sh`, a one-command alternative that pip-installs the package and copies the skill file into `~/.claude/skills/afplotter/`
- Document both paths in the README, marketplace first

## Test plan
- [x] `python3 -m json.tool` validated both new JSON manifests
- [x] `bash -n install.sh` validated script syntax
- [x] `uv run pytest tests/ -v` passes (no regressions — no library code touched)
- [ ] Manual: run `install.sh` end-to-end in a scratch `$HOME` and confirm both the package imports and the skill file lands correctly (see plan Task 2 Step 4)
- [ ] Manual: after merge, run `claude marketplace add AlexanderHeidelbach/AFPlotter && claude plugin install afplotter` against the real repo and confirm `claude plugin list` shows `afplotter`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR created against `main`; report the PR URL back. Do not merge it.
