# Agent Invariants

Always-on rules for any coding agent (Claude Code, Codex, Copilot, opencode) in this environment.

## Coding style

- Prefer explicit over implicit.
- Keep it simple: the minimum code that solves the problem, nothing speculative.
- No abstractions for single-use code; no flexibility or configurability that wasn't requested.
- Prefer immutable data — return new values instead of mutating inputs.
- Make surgical changes: touch only what the task requires; don't "improve" adjacent
  code, comments, or formatting; match existing style even if you'd do it differently.
- Remove imports/variables/functions that YOUR changes made unused; leave pre-existing
  dead code alone — mention it instead of deleting it.
- Only add comments where logic isn't self-evident.
- Every changed line should trace directly to the request.

## Working with me

- State assumptions explicitly; if uncertain, ask.
- If multiple interpretations exist, present them — don't pick one silently.
- If a simpler approach exists, say so. Push back when warranted.
- For multi-step tasks, define verifiable success criteria up front and verify before
  declaring done ("fix the bug" → a failing test that then passes).

## Environment & machines

- Dotfiles managed with Nix (nix-darwin + home-manager) and Chezmoi.
- Machines: behemoth (macOS, aarch64), rocinante (x86_64 Arch Linux),
  stargazer (aarch64 Linux VM on behemoth).
- Repo lives at `~/Documents/dotfiles` on macOS, `~/dotfiles` on Linux.
- Shell: nushell — pipelines and redirection differ from POSIX; don't paste bash-isms.

## Tools

- Use nix for package management, not brew (exception: GUI casks on macOS).
- In the dotfiles repo, build with `just build`; only the owner runs `just switch`.

## Git

- Conventional commits: `<type>: <description>` with types
  feat, fix, refactor, docs, test, chore, perf, ci.
- Commit and push only when asked.
- Never commit secrets — no hardcoded API keys, tokens, or endpoints;
  `op://` references are fine (pointers, not secrets).
