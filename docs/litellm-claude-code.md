# Using Claude Code with GitHub Copilot via LiteLLM

This setup lets you use Claude Code CLI while routing API calls through GitHub Copilot's backend via LiteLLM proxy.

## Prerequisites

- Docker installed
- GitHub Copilot subscription with CLI access
- Config file: `~/.dotfiles/config/litellm/config.yaml`

## Setup Steps

### 1. Start LiteLLM proxy

```bash
docker run -d --name litellm \
  -p 4000:4000 \
  -v ~/.dotfiles/config/litellm/config.yaml:/app/config.yaml \
  -v ~/.local/share/litellm:/root/.config/litellm \
  ghcr.io/berriai/litellm:main-latest \
  --config /app/config.yaml --num_workers 4
```

The proxy runs on `localhost:4000` and proxies requests to GitHub Copilot's API.

### 2. Configure Claude Code

In your project root, create `.claude/settings.local.json`:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:4000",
    "ANTHROPIC_AUTH_TOKEN": "sk-",
    "ANTHROPIC_MODEL": "claude-sonnet-4.5",
    "ANTHROPIC_SMALL_FAST_MODEL": "claude-sonnet-4.5"
  }
}
```

**Notes:**
- The `sk-` token is a dummy value (matches `master_key` in config.yaml)
- `.local` files are gitignored by default - safe for local settings
- Claude Code will now use the LiteLLM proxy instead of direct Anthropic API

### 3. Verify

Run `claude` in your project directory. It should connect through the proxy without errors.

## How it works

- LiteLLM intercepts Claude API calls
- Wildcard model config (`github_copilot/*`) routes all requests to Copilot
- Rate limiting (`rpm: 20`) prevents upstream throttling
- 10-minute timeout handles long planning sessions
