# Behemoth

macOS workstation (aarch64-darwin), managed by nix-darwin and home-manager.
This file is the new-Mac runbook. It covers what `just switch` sets up and,
more importantly, what it cannot.

Last checked against the real machine: 2026-11-15.

## What is managed where

| Layer | Managed by | Declared in |
|---|---|---|
| Nix itself, Linux builder | Determinate Nix module | `hosts/behemoth/default.nix` |
| System settings, user, login shell, sudo Touch ID | nix-darwin | `modules/darwin/default.nix` |
| GUI apps and a few CLI tools | Homebrew, pinned by flake inputs | `hosts/behemoth/default.nix`, `modules/darwin/homebrew.nix` |
| CLI tools, shell, editors, agents | home-manager | `home/` bundles |
| Background services | launchd agents and daemons | `hosts/behemoth/default.nix`, `modules/darwin/` |
| Editable configs (nvim, nushell, alacritty) | out-of-store symlinks | `config/` |
| Karabiner key remapping | home-manager, through the store | `config/karabiner` |
| Everything in the sections below | you, by hand | this file |

## New Mac, start to finish

1. **Create the macOS account as `andreym`.** It must be the first account, so
   it gets uid 501. `modules/darwin/default.nix` expects both.
2. **Install the Xcode Command Line Tools and Determinate Nix.** Homebrew
   needs the first.
   ```bash
   xcode-select --install
   curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
   ```
   Open a new terminal afterwards.
3. **Clone the repo to `~/Documents/dotfiles`.** The path is fixed in
   `flake.nix` as `dotfilesDir`. The repo is public, so HTTPS needs no key.
   Keep iCloud "Desktop & Documents Folders" sync off, or the clone ends up in
   iCloud Drive.
   ```bash
   nix run nixpkgs#git -- clone https://github.com/andrey-moor/dotfiles ~/Documents/dotfiles
   cd ~/Documents/dotfiles
   ```
4. **Bootstrap.** The dev shell supplies `just` and `git`.
   ```bash
   nix develop --command just bootstrap
   ```
   This builds the system and runs the first `darwin-rebuild switch`. It
   installs Homebrew itself, so do not install Homebrew by hand. Some casks
   ask for the account password. If it stops with "Unexpected files in /etc",
   rename the files the way the message says and run it again.
5. **Log out and back in.** The login shell is now nushell.
6. **Sign in to 1Password**, then turn on two settings under Settings,
   Developer: the SSH agent and the CLI integration. The agent serves the
   items named `GitHub Personal`, `GitHub Microsoft` and `GitHub LinkedIn`.
7. **Switch the repo to SSH.**
   ```bash
   git remote set-url origin git@github.com:andrey-moor/dotfiles.git
   ```
8. **Restore the sops admin key.** It is the 1Password Secure Note
   "sops age key (dotfiles admin)". Save it as
   `~/Library/Application Support/sops/age/keys.txt` with mode 600. Check it
   from nushell. No output means it decrypts.
   ```nu
   sops -d secrets/wayvnc.yaml | ignore
   ```
9. **Log in to FlakeHub** so the native Linux builder works. Access is granted
   per account.
   ```bash
   determinate-nixd login
   determinate-nixd version   # lists the enabled features
   ```
10. Work through **Manual installs**, **Sign-ins** and **Permissions** below.

From then on, `just switch` applies changes. Only the owner runs it.

## Manual installs

### Apps Homebrew cannot provide

| App | Why manual | Where |
|---|---|---|
| VMware Fusion | No Homebrew cask. The download needs a Broadcom account. | support.broadcom.com. `hosts/stargazer/README.md` covers the VM. |
| Xcode | Two versions are kept side by side as `Xcode-26.1.app` and `Xcode-26.3.app`. | App Store (id 497799835) or developer.apple.com |
| Google AI Edge Foresight | No Homebrew cask, not in the App Store. On trial as a meeting note-taker. It updates itself. | developers.google.com/edge/foresight. Copy `Foresight.app` to `/Applications`. |

### Mac App Store

`masApps` in `hosts/behemoth/default.nix` stays empty on purpose. The Homebrew
`mas` integration was unreliable on Apple Silicon. Install these from the App
Store, or with `nix run nixpkgs#mas -- install <id>`.

| App | id |
|---|---|
| 1Password for Safari | 1569813296 |
| Asobi | 6754204833 |
| Craft Web Clipper | 6748613311 |
| Instapaper | 288545208 |
| Kagi for Safari | 1622835804 |
| Numbers Creator Studio | 361304891 |
| Obsidian Web Clipper | 6720708363 |
| Okta Verify | 490179405 |
| Raycast Companion | 6738274497 |
| Screens 5 | 1663047912 |
| Things 3 | 904280696 |
| uBlock Origin Lite | 6745342698 |

### Developer tools kept outside Nix

Nix installs `rustup`, `uv` and `nodejs`. What they install afterwards is
per-project state and is not declared.

| Tool | Installed with | Notes |
|---|---|---|
| Rust stable toolchain | `rustup default stable` | Needed once. Projects with a `rust-toolchain` file fetch their own version. |
| Rust Linux target | `rustup target add aarch64-unknown-linux-gnu` | For cross builds |
| maturin, resvg, tauri-cli | `cargo install` | From crates.io |
| Personal tools | `cargo install --path`, `uv tool install` | Built from their own repos. `cargo install --list` and `uv tool list` on the old Mac show them. |

## Sign-ins

These hold tokens that no file in this repo can supply.

| Service | How |
|---|---|
| 1Password | App, then the two Developer settings in step 6 |
| FlakeHub | `determinate-nixd login` |
| Tailscale | App. rocinante and stargazer are reached over it. |
| GitHub CLI | `gh auth login` |
| Atuin | `atuin login`, then `atuin sync` |
| Claude Code | `claude`, then `/login` |
| Codex | `codex login`, with the ChatGPT plan. The ChatGPT app shares that login. Other providers: "Local models and the LLM gateway" below. |
| Google Cloud, Azure | `gcloud auth login`, `az login` |

App accounts and licences (Raycast, Obsidian, Craft, Fantastical, Granola,
Things, Parallels, CrossOver, Little Snitch, Mullvad, ChatGPT) are signed in
inside each app.

## Permissions

macOS asks for these once. All are under System Settings, Privacy & Security.

| Permission | For | Why |
|---|---|---|
| App Management | The terminal that runs `just switch` (Ghostty) | home-manager copies Nix apps into `~/Applications/Home Manager Apps`. Without it the switch stops with a message. |
| Input Monitoring, driver extension | Karabiner-Elements | Key remapping |
| Network extension | Little Snitch, Tailscale, Mullvad | Each app prompts on first launch |

Little Snitch needs one rule of its own. Allow every outgoing connection for
VMware's NAT process, as a rule for all users:
`/Library/Application Support/VMware/VMware Fusion/Services/Contents/Library/vmnet-natd`

The second rule matters more than it looks. All of stargazer's traffic leaves
through that process. Little Snitch cannot see the VM's encrypted DNS, so it
guesses a hostname from each address. Google serves `proxy.golang.org` and
`sum.golang.org` from addresses it shares with hostnames on tracker blocklists,
and Little Snitch then refuses the connection. Without the rule, every Go
module download on the VM fails with "connection refused", and the VM's
nightly upgrade fails with it. That went on from 2026-11-09 to 2026-11-16.

To see what Little Snitch did with an address:

```bash
sudo "/Applications/Little Snitch.app/Contents/Components/littlesnitch" log-traffic -b "2026-11-16 09:00:00" | grep 142.251.33.209
```

The columns after the port are connections allowed and connections denied.

Open OrbStack once to finish its own setup.

## Config that is not in this repo

| What | Where it lives | How to carry it over |
|---|---|---|
| Raycast settings and extensions | Raycast's own store | Raycast Settings, Advanced, Export and Import |
| Little Snitch rules | Little Snitch | Its own backup and restore |
| Extra SSH hosts | `~/.ssh/extra_config` | Copy by hand. It is private, and this repo is public. |
| Codex provider config | `~/.codex/config.toml`, `~/.codex/azure.config.toml`, `~/.codex/model-catalog.json` | Copy by hand. They name a private Azure endpoint, and this repo is public. |
| Project LaunchAgents | `~/Library/LaunchAgents/com.andreym.*.plist` | Each belongs to a project, which installs it. One of them expects an npm-installed `codex` at `/opt/homebrew/bin/codex`. |
| npm global packages `gsd-pi` and `xcodebuildmcp` | `/opt/homebrew/lib/node_modules` | `npm install -g` by hand, from before Nix led on PATH. They sit in Homebrew's `node`, which no file declares. Homebrew installed it only as a dependency of `agent-browser` and `firebase-cli`. A new `npm install -g` goes to `~/.npm-global`, set in `config/nushell/env.nu`. |
| OrbStack's Kubernetes | OrbStack's settings | Turn it on in OrbStack's settings. `orbctl config show` prints `k8s.enable: true` when it is on. |
| Dock layout | macOS | Arrange it by hand. `modules/darwin/default.nix` sets the Dock's size and behaviour, not which apps are in it. |

## Lending the YubiKey to rocinante

rocinante has no YubiKey, and Entra sign-in there needs one. The key stays
plugged into this Mac and travels over VirtualHere.

```bash
just yubikey          # start sharing, attach the key on rocinante
just yubikey-status   # show both ends
just yubikey-back     # release the key, stop sharing
```

While the key is lent, this Mac cannot use it. That includes 1Password and
VMware Fusion.

How it is built:

- `modules/darwin/yubikey-share.nix` declares the VirtualHere server as a root
  launchd daemon. It is stopped by default and shares YubiKeys only.
- `scripts/yubikey` starts the daemon with `sudo` (Touch ID), then drives the
  client on rocinante over ssh.
- On rocinante the client is one binary, `vhclientx86_64`. `packages/vhclient`
  pins it and `home/linux/vhclient.nix` installs it into `~/.nix-profile/bin`.
  The script starts it as a transient systemd unit.

Three things to know:

- **Do not open the VirtualHere app by hand.** Started that way it runs as your
  user, cannot take the key from macOS, and shares every USB device. The
  script stops such a server and starts the launchd one.
- **A `just switch` can end a lend.** When the daemon's definition changed,
  activation reloads it, and rocinante loses the key. Run `just yubikey`
  again.
- **The server has no password.** The free edition cannot bind to one interface
  or check who connects. While sharing is on, anyone who can reach TCP 7575 on
  this Mac can take the key. That is why the daemon is off by default. Run
  `just yubikey-back` when you are done.

Logs: `/var/log/vhusbd.log` here, `journalctl -u vhclient` on rocinante.

## Local models and the LLM gateway

One gateway, Bifrost, sits in front of every model provider. Codex and other
tools talk to it with one key. It runs in a container. The model server cannot:
no container on macOS can use the Apple GPU, so LM Studio runs on the host.

```
Codex --profile local ──► Bifrost (container, :8080) ──► LM Studio (host, :1234)
                                   ├──► OpenRouter, OpenAI
                                   ├──► Anthropic, personal key
                                   ├──► Anthropic, work key
                                   └──► Azure OpenAI
```

| Piece | Where it is declared |
|---|---|
| Containers | `config/containers/compose.yaml`, images pinned by tag and digest |
| Gateway config | `config/containers/bifrost/config.json` |
| Secret references | `config/containers/gateway.env.tpl`, `op://` pointers only |
| The agent that applies it, and LM Studio's server | `modules/darwin/containers.nix` |
| Codex profiles | `home/dev/codex-gateway.nix` |

### First setup, and after changing a key

1. Paste the provider keys into the 1Password item `llm-gateway-behemoth`,
   vault Private. A provider with an empty key just does not work.
2. `just gateway-secrets` renders them to
   `~/.config/behemoth-containers/gateway.env`, readable by you only.
3. `just gateway-up` applies the Compose file. `just gateway-status` checks it.

On a new Mac, open LM Studio once before the first login that should start
its server. `~/.lmstudio/bin/lms` does not exist until then.

### Using it

```bash
codex --profile local          # Qwen3.8-27B on this Mac
codex --profile openrouter     # hosted open-weight models
codex --profile claude         # Claude, personal API key
codex --profile claude-work    # Claude, work API key
codex --profile openai-api     # OpenAI API key, billed per token
codex --profile azure          # the work Azure deployment, direct
codex                          # your ChatGPT plan, direct
```

Two routes do not use the gateway:

- **Plain `codex` and the ChatGPT app** use the plan login from `codex login`.
  A plan login works only with OpenAI directly. The `openai-api` profile is
  for an API key and can stay unused.
- **`codex --profile azure`** is written by hand in `~/.codex`, because the
  endpoint is private. `azure.config.toml` picks the provider and the model.
  The provider block in `config.toml` gets its key from 1Password when Codex
  starts, so no key sits in a file or in the shell:

  ```toml
  [model_providers.azure.auth]
  command = "/etc/profiles/per-user/andreym/bin/op"
  args = ["read", "--no-newline", "op://Private/llm-gateway-behemoth/providers/azure-openai-key"]
  refresh_interval_ms = 0
  ```

Add `-m provider/model` for another model. Changing provider needs a new
session. A Claude subscription cannot be used here: Anthropic allows that
login only in Claude Code. The `claude` profiles use API keys.

### Adding a local model

Download it in LM Studio, or with `lms get`. Nothing else: LM Studio serves
every downloaded model by name and loads it on first request, and the gateway
passes any `lmstudio/<name>` through. LM Studio loads a model with its largest
context by default. Set a per-model default in LM Studio if memory gets tight.

### What is and is not pinned

| Thing | Pinned? | Updated by |
|---|---|---|
| Bifrost image | Yes, tag and digest | Renovate, one pull request a week, releases at least 7 days old, never merged automatically |
| Codex | Yes, `flake.lock` | The weekly lock pull request |
| LM Studio | No. The app updates itself. | Itself |
| Model files | No | You, in LM Studio |

Read Bifrost's release notes before merging its update. It releases every
few days, has shipped regressions in patch releases, and does not label
breaking changes. After the merge: `just switch`, then one real request,
`codex --profile local`.

### Known limits, measured on 2026-11-16

- Codex through Bifrost to LM Studio keeps Codex's file-edit tool and the
  prompt cache. The same task took about three minutes with or without the
  gateway.
- Bifrost's built-in Ollama provider translates between API styles and loses
  the edit tool. That is why LM Studio is set up as a generic provider.
- The gateway needs its small database for keys to be enforced. The config
  file still wins at every start (`source_of_truth`).
- It listens on this Mac and on the tailnet, never on the LAN, and refuses
  requests without the key. Prompt logging is off.
- The dashboard at port 8080 loads but can do nothing. No admin account and
  no setup token are configured, so Bifrost refuses every management request.
  All settings come from `config.json`. CI checks that this stays so.
- With Tailscale off at login, the gateway serves this Mac only. Run
  `just gateway-up` once Tailscale is connected.
- Codex warns "Model metadata not found" for gateway models and assumes a
  default context size. Bifrost cannot yet hand Codex its model list in
  Codex's format. Bifrost pull request 10096 adds that. Once it ships, one
  gateway profile with a working `/model` picker can replace the five.

## Apps upgraded while running

`just switch` upgrades Homebrew casks. An upgrade replaces the app on disk
while the old copy keeps running. macOS then no longer trusts the running
copy, and what breaks depends on the app:

| App | What broke on 2026-11-16 |
|---|---|
| Ghostty | It filters key presses for its global shortcut. macOS refused the old copy, and every key press on the Mac was dropped. |
| LM Studio | Model loads failed with "file not found". |

The switch now ends with a warning that names each such app. Quit and reopen
every app it lists. If the keyboard is already dead, quit Ghostty with the
mouse. LM Studio's server ignores a normal quit:

```bash
launchctl kickstart -k gui/$(id -u)/org.nixos.lmstudio-server
```

`scripts/stale-apps` does the comparing, and `modules/darwin/homebrew.nix`
runs it before and after Homebrew.

## Linux builds and Mullvad

Determinate's native Linux builder builds aarch64-linux and x86_64-linux
derivations on this Mac. Its VM gets DNS from macOS at 192.168.64.1.

The builder has no disk of its own. Its build directory lives in memory and
gets half of `determinateNixd.builder.memoryBytes`. A build that fails there
with "no space left on device" ran out of that, not out of disk. The Mac's
own disk is a separate matter: `/nix/store` is shared into the builder.

Mullvad's daemon breaks that DNS, even when the VPN is disconnected. It holds
a UDP socket on port 53, so macOS never answers the builder's UDP queries.
Builds that download anything then fail with name resolution errors. There is
no Mullvad or Determinate setting for this.

Before a Linux build, stop the daemon. Afterwards, start it again.

```bash
sudo launchctl bootout system/net.mullvad.daemon
sudo launchctl bootstrap system /Library/LaunchDaemons/net.mullvad.daemon.plist
```

Unknown: whether starting Mullvad after the builder VM is already up avoids the
problem. It was never tested to the end.

## Sources pinned by hand

These are pinned in the repo, and no updater watches them. The weekly lock
pull request covers `flake.lock` only, and Renovate covers container images
and GitHub Actions only. Bump each by hand.

| Source | Pinned in | How to bump |
|---|---|---|
| hunk | `packages/hunk` | Update `version` and the four `sha256` values |
| GhidraMCP extension | `overlays/ghidra-extensions/ghydramcp.nix` | Update `version` and the hash |
| bat theme | `home/shell/bat.nix` | Update `rev` and `sha256` |
| nu_scripts | `home/shell/nushell.nix` | Update `rev` and `sha256`, see the comment there |
| Copilot CLI | `home/dev/copilot-pin.json` | `just bump-copilot` |
| MCP servers (kagimcp, mcp-server-fetch, mcpvault) | `home/dev/claude.nix` | Update the version in each server's arguments |
| VirtualHere client (rocinante) | `packages/vhclient` | The URL is unversioned. A hash mismatch means upstream released a new build: update `sha256` and `version` |

## Things that are deliberately not reproducible

- **Homebrew casks marked `auto_updates`.** Those apps update themselves
  between switches.
