Install or update Claude Code configuration from the dotfiles repo.

## Steps

1. **Check current state.** Read `~/.claude/settings.json` and list installed plugins
   (check `~/.claude/plugins/installed_plugins.json`).

2. **Install marketplaces.** Run these via Bash if not already present:
   - `claude plugin marketplace add anthropics/claude-plugins-official`
   - `claude plugin marketplace add anthropics/skills`

3. **Install missing plugins.** For each plugin below, check if it exists in
   installed_plugins.json. If missing, tell the user to run `/plugin install <name>`:
   - context7@claude-plugins-official
   - playwright@claude-plugins-official
   - frontend-design@claude-plugins-official
   - code-review@claude-plugins-official
   - supabase@claude-plugins-official
   - document-skills@anthropic-agent-skills
   - example-skills@anthropic-agent-skills

4. **Verify settings.** Confirm `~/.claude/settings.json` has the expected
   portable keys (alwaysThinkingEnabled, effortLevel, enabledPlugins).

5. **Report.** Summarize what was installed/verified.
