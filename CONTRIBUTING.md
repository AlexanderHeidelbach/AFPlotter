# Contributing to AFPlotter

## What this project is

AFPlotter is a working plotting library, but it's also deliberately being run
as an experiment: a testbed for **full agentic software development** — using
Claude Code and the [Superpowers](https://github.com/obra/superpowers) skill
set to carry real feature work from idea to merged PR with minimal manual
coding. If you're a developer or student looking to see what that workflow
actually looks like in practice (not just in theory), this repo's commit
history and PRs are the record of it — read a few, not just the diffs but the
design docs and plans they link to.

That framing matters for how you contribute:

- **AI agents are expected to drive most non-trivial changes here.** See
  `CLAUDE.md`'s "Development workflow" section for the required pipeline
  (design → plan → subagent-driven implementation → review). If you're using
  Claude Code, follow it.
- **Human contributors are just as welcome** — the workflow is meant to
  produce reviewable, well-tested changes regardless of who (or what) writes
  the code. Read `CLAUDE.md` first either way; it's the single source of
  truth for architecture, conventions, and the testing philosophy.
- If you're a student experimenting with agentic workflows yourself, treat
  this repo as a sandbox: open an issue describing what you want to try, and
  a PR that documents what happened (including where the agent got it wrong)
  is exactly the kind of contribution this project wants.

## Setup

```bash
uv sync --extra dev
uv run pytest tests/ -v
```

`pre-commit install` sets up ruff (lint + format) and mypy locally — run
`pre-commit run --all-files` before opening a PR.

If you're using Claude Code, run `/init` at the start of a fresh session. It
won't overwrite `CLAUDE.md`; it re-derives the guide from the code and reports
where the two have drifted apart. Since `CLAUDE.md` is this project's source of
truth and nothing checks it against the code automatically, that report is worth
acting on — see `CLAUDE.md`'s "Run `/init` when starting fresh".

Note that a raw local `mypy` run is red even on a clean checkout — that's a
toolchain mismatch, not your branch. `CLAUDE.md`'s Setup section explains it.

## Before opening a PR

- Full test suite passes: `uv run pytest tests/ -v`.
- New tests are falsifiable (see `CLAUDE.md`'s "Testing philosophy") — assert
  on rendered data, not "didn't crash."
- If you touched `examples/`, run them — they're verified by execution, not
  inspection.
- If you're working with Claude Code, the `pr-check` and `verify-examples`
  skills in `.claude/skills/` automate the above.

## Questions

Open an issue. There's no other contributor chat yet — this is a small,
early-stage project.
