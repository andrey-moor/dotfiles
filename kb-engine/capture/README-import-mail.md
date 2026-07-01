# import-mail — Fastmail newsletter ingestion

Fetches `Knowledge Base`-labeled emails from Fastmail via JMAP and writes them
as `Knowledge/inbox/` stubs in the vault.

## Mint a read-only API token

1. Fastmail → Settings → Privacy & Security → API tokens → **New token**.
2. Select **read-only** scope — no calendar, no contacts, no send.
3. Copy the token immediately (shown only once).

## Store the token securely

Store in **1Password** (not in dotfiles or env files committed to git).

Expose to the scheduled run via Nix home-manager:

```nix
# In your home-manager config (never commit the literal value):
home.sessionVariables.FASTMAIL_API_TOKEN = "$(op read 'op://Private/Fastmail KB token/credential')";
```

Or for a one-off run, fetch from 1Password at the shell:

```sh
export FASTMAIL_API_TOKEN=$(op read "op://Private/Fastmail KB token/credential")
uv run --extra mail kb-engine --vault "$VAULT" import-mail --json
```

**Never commit the token.** It is read from the environment only — the CLI
raises an error if `FASTMAIL_API_TOKEN` is unset.

## Fastmail label setup

1. Create a label named **Knowledge Base** in Fastmail.
2. Add a filter rule: *From* matching your allowlist of newsletter senders →
   apply label **Knowledge Base**.
3. Cross-reference the allowlist maintained in
   `docs/superpowers/specs/2026-06-19-kb-capture-cowork-rich-topics-design.md`.

## Run command

```sh
uv run --extra mail kb-engine --vault "$VAULT" import-mail --json
```

Options:
- `--label TEXT`  Fastmail label to ingest (default: `Knowledge Base`)
- `--limit INT`   Max messages per run (default: 50)
- `--json`        Emit JSON output instead of human text

## Idempotency

Re-runs are safe — already-filed messages are skipped via two dedup gates:

1. **Message-ID dedup** — the `message_id` frontmatter field is checked
   vault-wide; duplicate emails are never re-written.
2. **Normalized-URL dedup** — Substack canonical URLs are extracted and
   normalized; a note with the same URL anywhere in `Knowledge/` blocks
   re-import.

No labels are mutated and no messages are deleted. The command is read-only
with respect to Fastmail.
