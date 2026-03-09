Sync current Claude Code settings back to the dotfiles chezmoi source.

## Steps

1. **Read current state.** Read `~/.claude/settings.json` and extract:
   - `enabledPlugins` (all entries)
   - `alwaysThinkingEnabled`
   - `effortLevel`

2. **Read chezmoi source.** Read the modify-template at
   `$DOTFILES/chezmoi/private_dot_claude/modify_settings.json`.

3. **Compare.** Show the user:
   - Plugins in settings.json but not in the template (new plugins to add)
   - Plugins in the template but not in settings.json (removed plugins)
   - Scalar settings that differ

4. **Update template.** If the user confirms, edit the modify-template to
   match current state:
   - Add new plugin entries to the `$desired` dict
   - Remove plugins the user wants removed
   - Update scalar values if changed

5. **Report.** Show what was changed. Remind user to commit and push.
