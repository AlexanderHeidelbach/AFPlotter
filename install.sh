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
