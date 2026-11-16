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
| Codex | `~/.codex/config.toml` is written by hand. See `home/dev/codex.nix`. |
| Google Cloud, Azure | `gcloud auth login`, `az login` |

App accounts and licences (Raycast, Obsidian, Craft, Fantastical, Granola,
Things, Parallels, CrossOver, Little Snitch, Mullvad, ChatGPT) are signed in
inside each app.

## Permissions

macOS asks for these once. All are under System Settings, Privacy & Security.

| Permission | For | Why |
|---|---|---|
| App Management | The terminal that runs `just switch` (Ghostty) | home-manager copies Nix apps into `~/Applications/Home Manager Apps`. Without it the switch stops with a message. |
| Accessibility | Lan Mouse | Keyboard and mouse sharing with rocinante |
| Input Monitoring, driver extension | Karabiner-Elements | Key remapping |
| Network extension | Little Snitch, Tailscale, Mullvad | Each app prompts on first launch |

Little Snitch needs two rules of its own:

- Allow UDP 4242 for Lan Mouse.
- Allow every outgoing connection for VMware's NAT process, as a rule for all
  users:
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
| Codex provider config | `~/.codex/config.toml` | Copy by hand |
| Project LaunchAgents | `~/Library/LaunchAgents/com.andreym.*.plist` | Each belongs to a project, which installs it. One of them expects an npm-installed `codex` at `/opt/homebrew/bin/codex`. |

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
- On rocinante the client is one binary at `~/.local/bin/vhclientx86_64`,
  downloaded from virtualhere.com. The script starts it as a transient systemd
  unit. Nothing is installed permanently there.

Two things to know:

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

## Things that are deliberately not reproducible

- **Homebrew casks marked `auto_updates`.** Those apps update themselves
  between switches.
