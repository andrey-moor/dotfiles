Sync current Claude Code settings back to the dotfiles chezmoi source.

## Context

- Current settings: !`cat ~/.claude/settings.json`
- Current template: !`cat $DOTFILES/chezmoi/private_dot_claude/modify_settings.json`
- ECC rule files: !`ls ~/.claude/rules/common/ 2>/dev/null | wc -l | tr -d ' '`
- GSD installed version: !`cat ~/.claude/get-shit-done/VERSION 2>/dev/null`
- GSD dotfiles pin: !`cat $DOTFILES/chezmoi/.gsd-version 2>/dev/null`

## Steps

1. **Read current state.** From `~/.claude/settings.json`, extract:
   - `enabledPlugins` (all entries with their true/false state)
   - `alwaysThinkingEnabled`
   - `effortLevel`
   - `mcpServers` (all entries)

2. **Read chezmoi source.** Read the modify-template at
   `$DOTFILES/chezmoi/private_dot_claude/modify_settings.json`.

3. **Compare plugins.** Show the user:
   - Plugins in settings.json but NOT in the template's `$desired` dict (new to add)
   - Plugins in `$desired` but NOT in settings.json (removed — should drop from template)
   - Plugins explicitly removed by `unset` that reappeared

4. **Compare MCP servers.** Show the user:
   - Servers in settings.json but NOT in the template (user-added locally)
   - Servers in the template but NOT in settings.json (template wants but missing)
   - Servers with different configs (command/args/env changed)

5. **Compare scalars.** Show differences for:
   - `alwaysThinkingEnabled`, `effortLevel`
   - `env.CLAUDE_CODE_SHELL`

6. **Check GSD version drift.** Compare:
   - `~/.claude/get-shit-done/VERSION` (installed)
   - `$DOTFILES/chezmoi/.gsd-version` (pinned in dotfiles)
   If they differ, ask whether to update the pin.

7. **Update template.** If the user confirms changes, edit the modify-template:
   - Add/remove plugin entries in the `$desired` dict
   - Add/remove `unset` calls for deprecated plugins
   - Update MCP server definitions
   - Update scalar values if changed
   - Update `.gsd-version` if user confirms

8. **Report.** Show what was changed. Remind user to commit and push.
