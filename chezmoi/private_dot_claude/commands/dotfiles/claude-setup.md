Install or update Claude Code configuration from the dotfiles repo.

## Context

- Current settings: !`cat ~/.claude/settings.json`
- Installed plugins: !`cat ~/.claude/plugins/installed_plugins.json 2>/dev/null | head -80`
- Installed marketplaces: !`ls ~/.claude/plugins/marketplaces/ 2>/dev/null`
- ECC version: !`ls ~/.claude/rules/common/ 2>/dev/null | wc -l | tr -d ' '` rule files
- GSD version: !`cat ~/.claude/get-shit-done/VERSION 2>/dev/null || echo 'not installed'`
- Dotfiles ECC pin: !`cat $DOTFILES/chezmoi/.ecc-version 2>/dev/null`
- Dotfiles GSD pin: !`cat $DOTFILES/chezmoi/.gsd-version 2>/dev/null`

## Steps

1. **Check prerequisites.** Verify these commands exist (via Bash `command -v`):
   - `node`, `npm`, `npx` (required for plugins, GSD, MCPVault)
   - `op` (1Password CLI — required for kagi MCP server)
   - `uvx` (required for kagi and fetch MCP servers)
   - `gh` (optional, used by ECC installer)
   Report any missing prerequisites.

2. **Install marketplaces.** Run via Bash if the marketplace directory doesn't exist:
   - `claude plugin marketplace add anthropics/claude-plugins-official`
   - `claude plugin marketplace add anthropics/skills`
   - `claude plugin marketplace add vercel-labs/agent-browser`
   - `claude plugin marketplace add sentrux/sentrux`

3. **Install missing plugins.** For each plugin below, check installed_plugins.json.
   If missing, tell the user to run the `/plugin install` slash command:
   - `context7@claude-plugins-official`
   - `agent-browser@agent-browser`
   - `sentrux@sentrux-marketplace`
   - `frontend-design@claude-plugins-official`
   - `code-review@claude-plugins-official`
   - `supabase@claude-plugins-official`
   - `swift-lsp@claude-plugins-official`
   - `skill-creator@claude-plugins-official`
   - `document-skills@anthropic-agent-skills`
   - `example-skills@anthropic-agent-skills`

4. **Run chezmoi apply.** Execute `chezmoi apply` to ensure:
   - `~/.claude/settings.json` has portable settings, plugins, MCP servers
   - ECC rules/agents/skills are installed
   - GSD is installed at the pinned version

5. **Verify settings.** Confirm `~/.claude/settings.json` has:
   - `alwaysThinkingEnabled: true`
   - `effortLevel: "high"`
   - `env.CLAUDE_CODE_SHELL: "bash"`
   - `enabledPlugins` with all desired plugins
   - `mcpServers` with kagi, fetch (and obsidian on behemoth)

6. **Verify ECC.** Check that `~/.claude/rules/common/` has rule files and
   `~/.claude/agents/` has reviewer agents (security-reviewer, code-reviewer, etc.).

7. **Verify GSD.** Check that `~/.claude/get-shit-done/VERSION` exists and
   `~/.claude/agents/gsd-*.md` files are present.

8. **Report.** Summarize:
   - Prerequisites: ok/missing
   - Marketplaces: installed/added
   - Plugins: installed/missing (with commands to install)
   - Settings: verified
   - ECC: version and file count
   - GSD: version and agent count
   - MCP servers: configured (list names)
