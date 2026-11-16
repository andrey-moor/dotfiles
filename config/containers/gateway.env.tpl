# Secrets for the containers in compose.yaml, as 1Password references.
# This file holds pointers, not secrets, so it is safe in a public repo.
#
# `just gateway-secrets` resolves it with `op inject` and writes the result to
# ~/.config/behemoth-containers/gateway.env, readable by the owner only. Run it
# again after changing a key in 1Password, then `just gateway-up`.
#
# A provider whose key is still empty in 1Password is simply unusable. The
# gateway starts regardless.

# The gateway itself. Generated once, never typed anywhere.
BIFROST_VIRTUAL_KEY={{ op://Private/llm-gateway-behemoth/gateway/virtual-key }}
BIFROST_ENCRYPTION_KEY={{ op://Private/llm-gateway-behemoth/gateway/encryption-key }}

# Hosted providers.
OPENAI_API_KEY={{ op://Private/llm-gateway-behemoth/providers/openai }}
OPENROUTER_API_KEY={{ op://Private/llm-gateway-behemoth/providers/openrouter }}
ANTHROPIC_PERSONAL_KEY={{ op://Private/llm-gateway-behemoth/providers/anthropic-personal }}
ANTHROPIC_WORK_KEY={{ op://Private/llm-gateway-behemoth/providers/anthropic-work }}
AZURE_OPENAI_KEY={{ op://Private/llm-gateway-behemoth/providers/azure-openai-key }}
# The Azure resource address is private, so it lives in 1Password too.
AZURE_OPENAI_BASE_URL={{ op://Private/llm-gateway-behemoth/providers/azure-openai-base-url }}
