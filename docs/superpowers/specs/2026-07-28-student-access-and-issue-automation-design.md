# Student access and issue automation — design

Date: 2026-07-28
Status: approved (pending spec review)

## Motivation

Two related but independent goals for using AFPlotter in a teaching context:

1. Students should be able to get both the `afplotter` package and its Claude
   Code skill with as little setup friction as possible.
2. Experienced students should be able to request changes by opening a GitHub
   issue, and have Claude implement them as a PR for the maintainer to review
   and merge — without the maintainer's API budget being exposed to anyone
   who finds the trigger phrase.

## Precondition: repo goes public

Both parts below assume the `AFPlotter` GitHub repo moves from private to
public. This is a manual, one-time GitHub settings change made by the
maintainer (Alexander Heidelbach) — not something automated as part of this
work, since it's a security/visibility decision outside the scope of a code
change. Everything below is written assuming it has happened.

The `pip install` command stays git-based
(`pip install git+https://github.com/AlexanderHeidelbach/AFPlotter.git`);
publishing to PyPI was considered and explicitly deferred — not part of this
design.

---

## Part 1 — Getting the package and skill to students

### Components

Two independent, low-maintenance distribution paths, both referencing the
*existing* `.claude/skills/afplotter/SKILL.md` directly — nothing is
duplicated or moved.

**A. Claude Code plugin marketplace (primary, documented first in README)**

- `.claude-plugin/marketplace.json` at the repo root, plus a plugin manifest
  that points at `.claude/skills/afplotter/` as the plugin's skill directory.
- Student setup (one-time):
  ```
  claude marketplace add AlexanderHeidelbach/AFPlotter
  claude plugin install afplotter
  ```
- Updates later: `claude plugin update afplotter`.
- This is Claude Code's own supported mechanism for distributing skills —
  shows up in `claude plugin list`, has a real update path, no bespoke
  tooling to maintain.

**B. Install script (alternative, documented second in README)**

- `install.sh` at the repo root, run via:
  ```
  curl -sSL https://raw.githubusercontent.com/AlexanderHeidelbach/AFPlotter/main/install.sh | bash
  ```
- Does two things: `pip install git+https://github.com/AlexanderHeidelbach/AFPlotter.git`,
  then `mkdir -p ~/.claude/skills/afplotter` and writes `SKILL.md` into it.
- Idempotent — safe to re-run, and re-running is how a student without the
  Claude Code plugin workflow picks up a skill update.
- For students who don't want to learn the plugin/marketplace concept at all,
  or who don't have `claude` on PATH yet.

Both paths are optional and non-conflicting — a student can use either,
neither (manual pip install with no skill), or both.

### Alternatives considered and rejected

- **PyPI publishing** — rejected for now; git+https install is acceptable
  and avoids maintaining a release pipeline.
- **`pip install` auto-installing the skill via a build hook** — technically
  possible (installing from git source always runs the build backend
  locally), but rejected: it's a hidden filesystem side effect of installing
  a plotting library, it's inconsistent with this repo's own
  no-import-time-side-effects principle, and it silently stops working if
  the project ever moves to PyPI wheel distribution (wheels don't re-run
  build hooks). It would fail silently with no error, only a student later
  wondering why Claude Code can't find the skill.
- **MCP server instead of a skill** — rejected. An MCP server's real
  advantage is that `claude mcp add` is a single native command with no
  custom install script needed. But it would require rebuilding the
  library's Claude-facing surface as a fixed set of schema'd tool calls,
  which fits the convenience layer (`plot_histogram`, etc.) but fights the
  engine layer's deliberately multi-call, composable design (see this
  repo's `CLAUDE.md` — "composed plots are multi-call by design"). That's a
  separate, much larger project, not a distribution tweak, and it would
  reduce exactly the flexibility advanced students need.
- **Env var / settings.json pointing Claude Code at an arbitrary skill
  path** (e.g. inside the installed package's `site-packages` location) —
  verified against Claude Code's actual docs (env-vars, settings, skills
  reference): no such mechanism exists today. The only documented way to
  load skills from a non-standard directory is the per-session
  `--add-dir` flag, which doesn't persist across sessions. This is a real
  gap in Claude Code relative to how MCP servers are registered
  (config-based, not just directory-copy or session flags), worth
  raising as feedback via `github.com/anthropics/claude-code/issues`
  separately from this implementation.

### Error handling

- Install script: must `mkdir -p` before writing (target directory may not
  exist yet); safe to re-run for updates or after a failed partial run.
- Marketplace plugin: version drift is handled by the plugin system's own
  `claude plugin update` — not something this design needs to build.

### Testing / verification

Not covered by the existing pytest suite (this is packaging/distribution
tooling, not library code). Verification is manual, done once during
implementation:

- Run `install.sh` in a clean environment (fresh venv or container) and
  confirm both `import afplotter` succeeds and `~/.claude/skills/afplotter/SKILL.md`
  exists with the expected content.
- Run the two marketplace commands against the (by-then-public) repo from a
  clean Claude Code config and confirm the skill loads (`claude plugin list`
  shows it, and a plotting request in that session triggers the skill).

---

## Part 2 — Issue-triggered implementation workflow

### Components

- `.github/workflows/claude.yml` — new GitHub Actions workflow using
  Anthropic's official `claude-code-action`.
- `ANTHROPIC_API_KEY` — added manually by the maintainer as a repo secret
  (Settings → Secrets and variables → Actions). Claude cannot set secret
  values itself; this is a manual step done once during implementation.
- Triggers: `issues: [opened]` and `issue_comment: [created]`, gated on the
  action's default `@claude` trigger phrase appearing in the issue body or
  comment text.
- Permissions: `contents: write`, `pull-requests: write`, `issues: write`.

### Access control (verified against `claude-code-action` docs)

The action's **default behavior already restricts triggering to users with
write access to the repo** — it does not respond to arbitrary public
commenters. No extra configuration is needed to get this, and
`allowed_non_write_users: true` must **not** be set (the action's own docs
flag it as a real prompt-injection risk on a public repo).

Since students won't be repo collaborators, the realistic flow is:

1. Student opens an issue describing the desired change.
2. Maintainer reviews it and, if it's worth doing, comments `@claude` on the
   issue (optionally with extra instructions) to greenlight it.
3. The workflow fires; the write-access check passes because the maintainer
   is the trigger.
4. `claude-code-action` checks out the repo, reads the issue thread and this
   repo's `CLAUDE.md` conventions (same as an interactive session would —
   reST docstrings, 3.10+ typing, no import-time side effects, etc.),
   implements the change.
5. Claude runs `uv run pytest tests/ -v` and the ruff/mypy checks itself
   before finishing, then pushes a branch, opens a PR referencing the issue,
   and comments a summary back on the issue.
6. The PR also runs through the existing `CI` workflow automatically (no
   changes needed there — it already triggers on every `pull_request`),
   giving a second, independent green signal alongside Claude's own
   self-check.
7. Maintainer reviews the PR and merges manually. Nothing auto-merges.

**Future option (documented, not built now):** to let a specific trusted
student trigger Claude directly without granting them collaborator/write
access, set `include_comments_by_actor: "username1,username2"` on the
action. This is an additive config change to the same workflow file, not a
redesign — leave a comment in `claude.yml` noting this is available.

### Error handling

- Non-collaborator comments `@claude`: action silently no-ops per its
  default write-access check — no run, no cost, no visible action needed.
- Missing/invalid `ANTHROPIC_API_KEY`: workflow run fails visibly in the
  Actions tab; no PR is opened.
- Claude's implementation fails its own test/lint check: no clean PR is
  produced (or a PR is opened with failing checks clearly visible via the
  existing CI); nothing merges automatically either way, so failures are
  visible rather than silently swallowed.

### Testing / verification

Not covered by pytest (this is CI/workflow infra). Verification plan: after
implementation, open a real low-stakes test issue, comment `@claude`, and
confirm the full path (branch pushed, PR opened referencing the issue, PR
passes existing CI, summary comment posted back to the issue) before relying
on this for real student-requested changes.

---

## Open follow-ups (not part of this design)

- Filing feedback with Anthropic about the missing skill-path registration
  mechanism (see "Alternatives considered" above) — separate from this
  implementation, to be drafted and filed if the maintainer wants to.
- Per-username allowlisting for trusted students (`include_comments_by_actor`)
  — deferred until actually needed.
