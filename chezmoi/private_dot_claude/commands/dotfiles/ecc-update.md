Check for updates to everything-claude-code (ECC) and optionally apply them.

## Steps

1. **Read current config.** Read the ECC version file from the dotfiles repo:
   `$DOTFILES/chezmoi/.ecc-version` (or `~/Documents/dotfiles/chezmoi/.ecc-version`).
   This contains the git ref being tracked (branch name or commit SHA).

2. **Check latest.** Run via Bash:
   ```
   gh api repos/affaan-m/everything-claude-code/commits/main --jq '.sha,.commit.message,.commit.author.date'
   ```
   Also check latest release:
   ```
   gh api repos/affaan-m/everything-claude-code/releases/latest --jq '.tag_name,.published_at,.body' 2>/dev/null || echo "No releases"
   ```

3. **Show status.** Report:
   - Current tracking ref from `.ecc-version`
   - Latest commit SHA, message, and date
   - Latest release tag (if any)
   - Whether an update is available

4. **If user wants to pin to a commit:** Update `.ecc-version` in the dotfiles repo
   with the desired commit SHA (or branch name). Then run `chezmoi apply` to trigger
   the `run_onchange_install-ecc.sh` script which re-downloads and extracts.

5. **If user just wants to re-download current ref:** Run `chezmoi state delete-bucket --bucket=scriptState`
   then `chezmoi apply` to force re-execution of the install script.

6. **Verify.** List a few files from `~/.claude/rules/common/` and `~/.claude/agents/`
   to confirm the update applied correctly.
