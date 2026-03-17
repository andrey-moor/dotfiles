Check for updates to everything-claude-code (ECC) and optionally apply them.

## Context

- Current ECC pin: !`cat $DOTFILES/chezmoi/.ecc-version 2>/dev/null`
- ECC rule files: !`ls ~/.claude/rules/common/ 2>/dev/null | wc -l | tr -d ' '`
- ECC agents: !`ls ~/.claude/agents/*-reviewer.md ~/.claude/agents/*-resolver.md ~/.claude/agents/tdd-guide.md ~/.claude/agents/refactor-cleaner.md 2>/dev/null | wc -l | tr -d ' '`

## Steps

1. **Read current pin.** Read `$DOTFILES/chezmoi/.ecc-version`. This contains a
   git commit SHA (preferred) or branch name.

2. **Check latest.** Run via Bash:
   ```
   gh api repos/affaan-m/everything-claude-code/commits/main --jq '.sha,.commit.message,.commit.author.date'
   ```
   Also check latest release:
   ```
   gh api repos/affaan-m/everything-claude-code/releases/latest --jq '.tag_name,.published_at,.body' 2>/dev/null || echo "No releases"
   ```

3. **Show status.** Report:
   - Current pin (commit SHA or branch) from `.ecc-version`
   - Latest commit SHA, message, and date
   - Whether an update is available (compare SHAs)
   - Current file counts (rules, agents)

4. **If user wants to update:** Update `.ecc-version` in the dotfiles repo
   with the new commit SHA. Then run `chezmoi apply` to trigger the
   `run_onchange_install-ecc.sh` script which re-downloads and extracts.

5. **If user wants to force re-download current pin:** Run
   `chezmoi state delete-bucket --bucket=scriptState` then `chezmoi apply`
   to force re-execution of the install script.

6. **Verify.** Count files in `~/.claude/rules/common/` and `~/.claude/agents/`
   to confirm the update applied correctly.
