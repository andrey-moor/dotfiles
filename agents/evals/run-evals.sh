#!/usr/bin/env bash
# Run this eval suite against a plugin root: the working copy, or a snapshot of an older version.
# Usage: evals/run-evals.sh <plugin-root> [claude plugin eval options, such as --case NAME --runs 1]
#
# Copies the cases into <plugin-root>/evals when the root is not this suite's own root, and copies the
# diagram-design plugin into <plugin-root>/.eval-deps/, because a case may load plugins only from inside
# the root. Passes --scaffold, because the cases and their setup scripts are this suite's own. Grants Write only: runs that grant Bash are refused on machines whose ~/.ssh holds symlinks,
# so scripts are covered by each skill's tests/ instead. The model is pinned so that scores stay
# comparable across runs; set SKILL_EVAL_MODEL to change it.
set -euo pipefail
[ $# -ge 1 ] || { echo "usage: run-evals.sh <plugin-root> [claude plugin eval options]" >&2; exit 2; }
ROOT=$(cd "$1" && pwd); shift
SUITE=$(cd "$(dirname "$0")" && pwd)
[ -f "$ROOT/.claude-plugin/plugin.json" ] || { echo "run-evals: $ROOT has no .claude-plugin/plugin.json" >&2; exit 2; }

if [ "$SUITE" != "$ROOT/evals" ]; then
  mkdir -p "$ROOT/evals"
  # Replace each copied folder whole, so a grader deleted from the suite is deleted from the copy too.
  (cd "$SUITE" && find . -mindepth 1 -maxdepth 1 ! -name results -exec rm -rf "$ROOT/evals/{}" \; -exec cp -R {} "$ROOT/evals/" \;)
fi

PLUGIN=$(ls -d "$HOME"/.claude/plugins/cache/diagram-design/diagram-design/*/ 2>/dev/null | sort -V | tail -1 || true)
[ -n "$PLUGIN" ] || PLUGIN="$HOME/.copilot/installed-plugins/_direct/cathrynlavery--diagram-design/"
[ -f "$PLUGIN/.claude-plugin/plugin.json" ] || { echo "run-evals: diagram-design plugin not found; doc-diagrams cases need it" >&2; exit 1; }
rm -rf "$ROOT/.eval-deps/diagram-design" && mkdir -p "$ROOT/.eval-deps" && cp -R "$PLUGIN" "$ROOT/.eval-deps/diagram-design"

exec claude plugin eval "$ROOT" --trust-plugin --no-publish --scaffold --allow-tools Write \
  --model "${SKILL_EVAL_MODEL:-claude-opus-5}" --judge-model "${SKILL_EVAL_JUDGE:-claude-sonnet-5}" "$@"
