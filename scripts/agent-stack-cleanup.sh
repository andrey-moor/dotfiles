#!/usr/bin/env bash
# agent-stack-cleanup.sh — P4 Task 6: remove GSD/ECC/sentrux/karpathy and
# chezmoi-deployed agent-stack copies from live ~/.claude state.
#
# Default action is a DRY RUN. Pass --apply to actually delete (owner-gated).
# Idempotent: already-absent paths are noted and skipped, never errors.
# Portable: runs on macOS and Linux (behemoth, rocinante, stargazer).
#
# HARD PROTECT-LIST — this script must NEVER touch:
#   ~/.claude/skills/{orrery-*,wrap,code-search,xcodebuildmcp-cli}
#   ~/.claude/plugins/ralph-loop-v2
#   ~/.claude/projects/  ~/.claude/backups/  session/history state
#   ~/.gsd  (GSD *data* stays; only harness integration is removed)
#   ~/.claude.json (only mutated indirectly via `claude mcp remove` CLI)

set -euo pipefail
shopt -s nullglob

CLAUDE_DIR="$HOME/.claude"
INSTALLED_PLUGINS_FILE="$CLAUDE_DIR/plugins/installed_plugins.json"
KNOWN_MARKETPLACES_FILE="$CLAUDE_DIR/plugins/known_marketplaces.json"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
USER_MCP_FILE="$HOME/.claude.json"

APPLY=false
case "${1:---dry-run}" in
  --dry-run) APPLY=false ;;
  --apply)   APPLY=true ;;
  -h|--help)
    echo "Usage: $0 [--dry-run|--apply]   (default: --dry-run)"
    exit 0
    ;;
  *)
    echo "Unknown argument: $1 (use --dry-run or --apply)" >&2
    exit 1
    ;;
esac

WOULD_COUNT=0
DONE_COUNT=0
LEFTOVER_REPORTS=0

note() { printf '%s\n' "$*"; }

section() { printf '\n== %s ==\n' "$*"; }

is_protected() {
  case "$1" in
    "$HOME/.gsd" | "$HOME/.gsd"/*) return 0 ;;
    "$USER_MCP_FILE") return 0 ;;
    "$CLAUDE_DIR/projects" | "$CLAUDE_DIR/projects"/*) return 0 ;;
    "$CLAUDE_DIR/backups" | "$CLAUDE_DIR/backups"/*) return 0 ;;
    "$CLAUDE_DIR/history"*) return 0 ;;
    "$CLAUDE_DIR/plugins/ralph-loop-v2" | "$CLAUDE_DIR/plugins/ralph-loop-v2"/*) return 0 ;;
    "$CLAUDE_DIR/skills/orrery-"*) return 0 ;;
    "$CLAUDE_DIR/skills/wrap" | "$CLAUDE_DIR/skills/code-search" | "$CLAUDE_DIR/skills/xcodebuildmcp-cli") return 0 ;;
  esac
  return 1
}

remove_path() {
  local p="$1"
  if is_protected "$p"; then
    note "PROTECTED (refusing to touch): $p"
    return 0
  fi
  if [ ! -e "$p" ] && [ ! -L "$p" ]; then
    note "skip (absent): $p"
    return 0
  fi
  if $APPLY; then
    note "REMOVE: $p"
    rm -rf -- "$p"
    DONE_COUNT=$((DONE_COUNT + 1))
  else
    note "WOULD REMOVE: $p"
    WOULD_COUNT=$((WOULD_COUNT + 1))
  fi
}

run_cmd() {
  if $APPLY; then
    note "RUN: $*"
    "$@"
    DONE_COUNT=$((DONE_COUNT + 1))
  else
    note "WOULD RUN: $*"
    WOULD_COUNT=$((WOULD_COUNT + 1))
  fi
}

HAVE_CLAUDE=false
command -v claude >/dev/null 2>&1 && HAVE_CLAUDE=true
HAVE_JQ=false
command -v jq >/dev/null 2>&1 && HAVE_JQ=true

note "agent-stack-cleanup: mode=$($APPLY && echo APPLY || echo DRY-RUN) host=$(hostname) claude=$HAVE_CLAUDE jq=$HAVE_JQ"

# ---------------------------------------------------------------------------
section "1. Plugin + marketplace removal (claude CLI)"
# ---------------------------------------------------------------------------
if ! $HAVE_CLAUDE; then
  note "skip section (claude CLI not found)"
elif ! $HAVE_JQ; then
  note "skip section (jq not found — cannot verify installed plugin names)"
elif [ ! -f "$INSTALLED_PLUGINS_FILE" ]; then
  note "skip section (no installed_plugins.json)"
else
  for plugin_name in sentrux andrej-karpathy-skills supabase swift-lsp clangd-lsp; do
    matches="$(jq -r --arg n "$plugin_name" \
      '.plugins | keys[] | select(split("@")[0] == $n)' "$INSTALLED_PLUGINS_FILE")"
    if [ -z "$matches" ]; then
      note "skip (plugin not installed): $plugin_name"
      continue
    fi
    while IFS= read -r plugin_key; do
      [ -n "$plugin_key" ] || continue
      run_cmd claude plugin uninstall -s user "$plugin_key"
    done <<<"$matches"
  done

  for marketplace in sentrux-marketplace karpathy-skills; do
    if [ -f "$KNOWN_MARKETPLACES_FILE" ] &&
      jq -e --arg m "$marketplace" 'has($m)' "$KNOWN_MARKETPLACES_FILE" >/dev/null; then
      run_cmd claude plugin marketplace remove "$marketplace"
    else
      note "skip (marketplace not configured): $marketplace"
    fi
  done
fi

# ---------------------------------------------------------------------------
section "2. ECC removal (rules dir, 10 agents, 7 skills)"
# ---------------------------------------------------------------------------
remove_path "$CLAUDE_DIR/rules"

ECC_AGENTS=(
  security-reviewer code-reviewer database-reviewer go-reviewer
  go-build-resolver python-reviewer kotlin-reviewer build-error-resolver
  tdd-guide refactor-cleaner
)
for agent in "${ECC_AGENTS[@]}"; do
  remove_path "$CLAUDE_DIR/agents/$agent.md"
done

ECC_SKILLS=(
  api-design security-review tdd-workflow docker-patterns
  deployment-patterns golang-patterns golang-testing
)
for skill in "${ECC_SKILLS[@]}"; do
  remove_path "$CLAUDE_DIR/skills/$skill"
done

# ---------------------------------------------------------------------------
section "3. GSD removal (skills, agents, hooks, state dirs, settings keys)"
# ---------------------------------------------------------------------------
gsd_skill_count=0
for skill_dir in "$CLAUDE_DIR/skills"/gsd-*; do
  remove_path "$skill_dir"
  gsd_skill_count=$((gsd_skill_count + 1))
done
[ "$gsd_skill_count" -eq 0 ] && note "skip (no gsd-* skills present)"

gsd_agent_count=0
for agent_file in "$CLAUDE_DIR/agents"/gsd-*; do
  remove_path "$agent_file"
  gsd_agent_count=$((gsd_agent_count + 1))
done
[ "$gsd_agent_count" -eq 0 ] && note "skip (no gsd-* agents present)"

# Hooks: everything GSD installed there is gsd-* files plus lib/. If anything
# else is present, remove only the gsd-* files and report the rest.
hooks_dir="$CLAUDE_DIR/hooks"
if [ -d "$hooks_dir" ]; then
  non_gsd="$(find "$hooks_dir" -mindepth 1 -maxdepth 1 ! -name 'gsd-*' ! -name lib)"
  if [ -z "$non_gsd" ]; then
    remove_path "$hooks_dir"
  else
    for hook_file in "$hooks_dir"/gsd-*; do
      remove_path "$hook_file"
    done
    note "LEFTOVER REPORT: non-GSD entries found in $hooks_dir — leaving them and lib/ in place:"
    printf '  %s\n' "$non_gsd"
    LEFTOVER_REPORTS=$((LEFTOVER_REPORTS + 1))
  fi
else
  note "skip (absent): $hooks_dir"
fi

remove_path "$CLAUDE_DIR/get-shit-done"
remove_path "$CLAUDE_DIR/gsd-local-patches"
remove_path "$CLAUDE_DIR/gsd-migration-journal"

# settings.json: delete the GSD-owned `hooks` and `statusLine` keys.
if [ ! -f "$SETTINGS_FILE" ]; then
  note "skip (absent): $SETTINGS_FILE"
elif ! $HAVE_JQ; then
  note "LEFTOVER REPORT: jq not found — cannot edit $SETTINGS_FILE (hooks/statusLine keys)"
  LEFTOVER_REPORTS=$((LEFTOVER_REPORTS + 1))
else
  keys_present="$(jq -r 'keys[] | select(. == "hooks" or . == "statusLine")' "$SETTINGS_FILE")"
  if [ -z "$keys_present" ]; then
    note "skip (hooks/statusLine keys already absent): $SETTINGS_FILE"
  elif $APPLY; then
    note "EDIT: $SETTINGS_FILE — jq del(.hooks, .statusLine) [$(echo "$keys_present" | tr '\n' ' ')]"
    tmp_file="$(mktemp "${TMPDIR:-/tmp}/settings.json.XXXXXX")"
    jq 'del(.hooks, .statusLine)' "$SETTINGS_FILE" >"$tmp_file"
    mv "$tmp_file" "$SETTINGS_FILE"
    DONE_COUNT=$((DONE_COUNT + 1))
  else
    note "WOULD EDIT: $SETTINGS_FILE — jq del(.hooks, .statusLine) [present: $(echo "$keys_present" | tr '\n' ' ')]"
    WOULD_COUNT=$((WOULD_COUNT + 1))
  fi
fi

note "NOTE: ~/.gsd left untouched (GSD data, incl. KB .planning target)"

# ---------------------------------------------------------------------------
section "4. MCP dedup (user scope — now served by the HM plugin)"
# ---------------------------------------------------------------------------
if ! $HAVE_CLAUDE; then
  note "skip section (claude CLI not found)"
elif ! $HAVE_JQ; then
  note "skip section (jq not found — cannot verify user-scope MCP servers)"
elif [ ! -f "$USER_MCP_FILE" ]; then
  note "skip section (no ~/.claude.json)"
else
  for server in kagi fetch obsidian; do
    if jq -e --arg s "$server" '.mcpServers // {} | has($s)' "$USER_MCP_FILE" >/dev/null; then
      run_cmd claude mcp remove -s user "$server"
    else
      note "skip (not in user-scope mcpServers): $server"
    fi
  done
fi

# ---------------------------------------------------------------------------
section "5. Chezmoi-deployed copies superseded by home-manager symlinks"
# ---------------------------------------------------------------------------
# Stale packaged skill zip — remove unconditionally.
remove_path "$CLAUDE_DIR/skills/kb.skill"

# These are replaced by HM-generated symlinks on switch; only remove the
# chezmoi-deployed plain file/dir copies. Anything already a symlink is HM's.
CHEZMOI_COPIES=(
  "$CLAUDE_DIR/skills/kb"
  "$CLAUDE_DIR/commands/kb"
  "$CLAUDE_DIR/commands/commit.md"
  "$CLAUDE_DIR/commands/dotfiles"
  "$CLAUDE_DIR/CLAUDE.md"
)
for copy_path in "${CHEZMOI_COPIES[@]}"; do
  if [ -L "$copy_path" ]; then
    note "skip (already a symlink — HM-managed): $copy_path"
  else
    remove_path "$copy_path"
  fi
done

# ---------------------------------------------------------------------------
section "Summary"
# ---------------------------------------------------------------------------
if $APPLY; then
  note "APPLY complete: $DONE_COUNT action(s) executed, $LEFTOVER_REPORTS leftover report(s)."
else
  note "DRY-RUN complete: $WOULD_COUNT action(s) would be executed, $LEFTOVER_REPORTS leftover report(s)."
  note "Re-run with --apply after owner approval to execute."
fi
