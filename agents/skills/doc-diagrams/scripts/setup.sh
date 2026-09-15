#!/usr/bin/env bash
# One-time setup: install the renderer and the word-office color profile for diagram-design.
set -euo pipefail
cd "$(dirname "$0")"
command -v node >/dev/null || { echo "setup: node is required" >&2; exit 1; }
npm install --silent --no-audit --no-fund
PROFILE_DIR="$HOME/.diagram-design/profiles"
mkdir -p "$PROFILE_DIR"
for profile in ../profiles/*.md; do cp "$profile" "$PROFILE_DIR/"; done
if ! ls -d "$HOME/.claude/plugins/cache/diagram-design"/* >/dev/null 2>&1; then
  echo "setup: diagram-design plugin not installed. In Claude Code run:" >&2
  echo "  /plugin marketplace add cathrynlavery/diagram-design" >&2
  echo "  /plugin install diagram-design@diagram-design" >&2
fi
echo "doc-diagrams ready: profiles installed in $PROFILE_DIR: $(cd ../profiles && ls *.md | tr '\n' ' ')"
