---
name: verify-examples
description: Use when checking that AFPlotter's examples/ scripts still work — before finishing a branch/PR, after touching plotting code, colors, or experiment styles, or when asked to verify the examples.
---

# Verify Examples

## Overview

This repo's testing philosophy (`CLAUDE.md`) requires examples to be verified
by **running them**, not by reading the code. "Didn't crash" isn't enough —
confirm each one produced real output.

## Steps

1. Read `examples/README.md`'s bullet list — that's the source of truth for
   which `.py` files are runnable examples. Do not blindly glob `examples/*.py`:
   the directory also holds non-example helpers (files like `_synthetic_data.py`,
   imported by the examples, not run directly) and can accumulate stray files
   that look like examples but aren't (e.g. an empty, undocumented `.py` file).
2. For each documented example, run it for real:
   ```
   uv run python examples/<name>.py
   ```
   Confirm exit code 0. A traceback or non-zero exit is a failure — don't
   downgrade it to a warning.
3. Confirm each run produced a new/updated file in `examples/output/` (PNG,
   non-zero size). An example that exits 0 but writes nothing didn't actually
   verify anything.
4. Flag drift: any `.py` file in `examples/` that is neither listed in
   `examples/README.md` nor a leading-underscore helper (`_*.py`) is stray —
   report it (empty file, forgotten script, or an example that needs adding to
   the README) rather than silently ignoring it.

## Quick Reference

| Check | Pass condition |
|---|---|
| Each documented example runs | exit code 0 |
| Each documented example produces output | new/updated file in `examples/output/`, non-zero size |
| No undocumented example-shaped files | every non-`_*.py` file in `examples/` is listed in `examples/README.md` |

## Common Mistakes

- Reading the example's source and reasoning "this looks correct" instead of
  running it — the repo's stated philosophy explicitly rejects this.
- Treating exit-0-with-no-output as a pass.
- Globbing all `.py` files and reporting a false failure on `_synthetic_data.py`
  (it's a helper module, not an entry point — it has no `if __name__` block).
