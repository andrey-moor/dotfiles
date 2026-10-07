# behemoth: aarch64-linux builder, implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** behemoth can build aarch64-linux derivations locally, so evaluating and inspecting the stargazer configuration no longer fails with a platform mismatch.

**Architecture:** Determinate's own nix-darwin module (`determinateNix`) replaces the `nix.enable = false` workaround and manages `/etc/nix/nix.custom.conf` and `/etc/determinate/config.json` declaratively. The builder is Determinate's native Linux builder on the Virtualization framework, declared in that config. Task 1 originally enabled the nixpkgs VM builder as an interim. Access to the native builder arrived the same day, before any switch, so Task 2 replaces that with the native builder. The module allows only one of the two.

**Tech Stack:** Determinate Nix 3.23.1 on behemoth, Determinate flake `https://flakehub.com/f/DeterminateSystems/determinate/3` (darwin module), nixpkgs `darwin.linux-builder` (NixOS VM on QEMU with HVF, SSH on localhost port 31022, well-known insecure key pair bound to localhost by design), nix-darwin.

**Decision record (2026-10-07):** Determinate's native builder is granted per FlakeHub account. The login alone did nothing. The access request was answered within the hour and the builder then worked with zero configuration. The nix-darwin `nix.linux-builder` option asserts `nix.enable` and is blocked under Determinate (nix-darwin issue 1505). The Determinate module's `nixosVmBasedLinuxBuilder` is the same VM without that assertion. stargazer as an SSH builder and nixbuild.net were rejected for now: the first needs the VM running and cannot serve an ISO rebuild, the second adds a vendor.

## Global Constraints

- The repo is public. Commit nothing that names a tenant, domain, UPN or device id.
- Every text a person reads follows plain prose: no em-dashes, no semicolons in prose, no sentence over 30 words.
- Conventional commits with the trailers `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01KXGT9GVA7PmREkR6KhTkiu`. Commit and push only when the owner says so.
- Only the owner runs `just switch`. The implementer builds with `just build` and evaluates.
- After every task: `just lint`, `just build` (behemoth), `nix eval --raw .#nixosConfigurations.stargazer.config.system.build.toplevel.drvPath`, the same for `stargazer-drill`, `nix eval --raw .#homeConfigurations.rocinante.activationPackage.drvPath` unchanged from `/nix/store/bxkygm8sx4qmrdiz56bn4v1jzldayyyg-home-manager-generation.drv`. The behemoth drvPath changes by design in Task 1.
- Harness shell is zsh without nix on PATH: prefix commands with `export PATH=/usr/local/bin:/run/current-system/sw/bin:/etc/profiles/per-user/andreym/bin:/nix/var/nix/profiles/default/bin:$PATH`.
- Do not edit `/etc/determinate/config.json`, `/etc/nix/nix.custom.conf` or `/etc/nix/machines` by hand. The module owns them after the switch.

---

### Task 1: Determinate module and the VM builder with defaults

**Files:**
- Modify: `flake.nix` (new input `determinate`, new module in behemoth's `modules`)
- Modify: `hosts/behemoth/default.nix` (replace `nix.enable = false`)
- Modify: `modules/darwin/default.nix` (comment on lines 10 to 11)
- Modify: `CLAUDE.md` (behemoth section, one paragraph)
- Test: `just build`, then after the owner's switch the probe in Step 5

**Interfaces:**
- Produces: `determinateNix.enable = true`, `determinateNix.nixosVmBasedLinuxBuilder.enable = true` with nixpkgs defaults (1 core, 3072 MiB, 20 GiB disk). No `determinateNixd.builder.state` line: the module sets it to disabled while the VM builder runs. A launchd daemon named after `determinateNix.nixosVmBasedLinuxBuilder.hostName` (default `nixos-vm-based-linux-builder`), an entry in `/etc/nix/machines`, an SSH config fragment under `/etc/ssh/ssh_config.d/`.

- [ ] **Step 1: Add the flake input and module**

In `flake.nix` inputs, next to `darwin`:

```nix
    # Determinate's nix-darwin module: manages nix.custom.conf and
    # determinate-nixd's config, and runs the Linux builder VM. The flakehub
    # URL is the vendor's documented form and resolves the 3.x range on update.
    determinate.url = "https://flakehub.com/f/DeterminateSystems/determinate/3";
```

In `darwinConfigurations.behemoth` `modules`, add `inputs.determinate.darwinModules.default` after the home-manager module. Run `nix flake lock` so the lock gains the input. Check the lock entry records a `tarball` or `github` locked URL with a `narHash`.

- [ ] **Step 2: Replace the workaround in the host**

In `hosts/behemoth/default.nix`, replace `nix.enable = false;` with:

```nix
  # Determinate Nix owns /etc/nix/nix.conf. This module turns nix-darwin's
  # Nix management off for us and manages the custom settings file instead.
  determinateNix = {
    enable = true;
    # Linux builder VM from nixpkgs. First switch with the defaults: the VM
    # image is an aarch64-linux build that only the binary cache can supply
    # before a builder exists. Resources are raised in the next generation.
    nixosVmBasedLinuxBuilder.enable = true;
  };
```

Read the module at the locked store path (`nix eval --raw .#inputs.determinate.outPath` or `nix flake metadata --json | jq`) and confirm: `determinateNix.enable` sets `nix.enable = false` itself, `distributedBuilds` defaults to true when a builder is enabled, and `customSettings.builders-use-substitutes = true` is set by the module. If `distributedBuilds` needs an explicit `true`, add it. If the module's `enable` default is already `true` once imported, keep the explicit line anyway for the reader.

Update the comment in `modules/darwin/default.nix` lines 10 to 11 to name `determinateNix.enable` instead of `nix.enable = false`.

- [ ] **Step 3: Confirm the VM image comes from the cache**

```
nix build --dry-run .#darwinConfigurations.behemoth.system 2>&1 | grep -E 'will be built|will be fetched' -A3 | head -20
```

Expected: the linux-builder image and its NixOS closure appear under "will be fetched", nothing aarch64-linux under "will be built". If an aarch64-linux derivation must be built, stop and report BLOCKED with the list: the defaults do not match the cache and the plan needs a different nixpkgs revision for the builder package.

- [ ] **Step 4: Build, lint, document**

`just fmt`, `just lint`, `just build` must pass. `CLAUDE.md` behemoth section gains one paragraph: Determinate Nix is configured through `determinateNix.*` in the host, the Linux builder VM runs as a launchd daemon, `nix build` for aarch64-linux works once switched, and `/etc/determinate/config.json` plus `/etc/nix/nix.custom.conf` are module-owned. Three to five sentences.

- [ ] **Step 5: Owner switches, then the probe**

Owner: `just switch`. The first start downloads the VM image and boots it, allow a few minutes. Then:

```
launchctl print system/org.nixos.nixos-vm-based-linux-builder 2>/dev/null | grep -E 'state|pid' | head -3
cat /etc/nix/machines
nix build --no-link --print-out-paths --print-build-logs --impure --expr 'let f = builtins.getFlake (toString ./.); p = import f.inputs.nixpkgs { system = "aarch64-linux"; }; in p.runCommand "linux-builder-probe" {} "uname -m > $out; cat $out"'
```

Expected: the daemon running, one machines line with `ssh-ng://builder@…` and `aarch64-linux`, the probe prints `aarch64` and a store path. The launchd label may differ, the implementer records the real one from `launchctl print system | grep -i builder`.

- [ ] **Step 6: Commit**

`feat(behemoth): determinate module and the nixpkgs linux builder VM`, body recording the decision record's two blocked alternatives in one sentence each.

---

### Task 2: Switch to the native builder (supersedes the VM builder before it ever ran)

**Why:** Determinate granted the account access on 2026-10-07, minutes after the request. With `determinate-nixd version` listing `native-linux-builder`, a trivial aarch64-linux `runCommand` built on behemoth with no configuration and no switch. Task 1's commit 2854f5a is unpushed and unswitched, and the module's interlock means switching it would disable the native builder. This task corrects that commit with a follow-up commit. The original Task 2 (raise the VM's resources) is void.

**Files:**
- Modify: `hosts/behemoth/default.nix`, `CLAUDE.md`

- [ ] **Step 1: Host block**

Replace the `determinateNix` block with:

```nix
  # Determinate Nix owns /etc/nix/nix.conf. This module turns nix-darwin's
  # Nix management off for us and manages the custom settings file and
  # determinate-nixd's config.json instead.
  determinateNix = {
    enable = true;
    # Determinate's native Linux builder (Virtualization framework). It builds
    # aarch64-linux and x86_64-linux derivations on this Mac. Access is per
    # FlakeHub account and was granted on 2026-10-07. Keep cpuCount at 1, the
    # vendor measured more CPUs as slower. The nixpkgs VM builder is not used:
    # the module allows only one of the two.
    determinateNixd.builder = {
      state = "enabled";
      memoryBytes = 16 * 1024 * 1024 * 1024;
    };
  };
```

`cpuCount` stays at the module default of 1. 16 GiB is for the stargazer closure's two compiled packages (Hyprland with the vmwgfx patch and himmelblau, 8.5 GiB peak observed), behemoth has 128 GiB.

- [ ] **Step 2: CLAUDE.md**

Rewrite the behemoth paragraph from Task 1: Determinate Nix is configured through `determinateNix.*`, its native Linux builder builds aarch64-linux derivations locally, `/etc/determinate/config.json` and `/etc/nix/nix.custom.conf` are module-owned, and `determinate-nixd version` lists the enabled features. Three to five sentences. No mention of the VM builder.

- [ ] **Step 3: Checks and commit**

`just fmt`, `just lint`, `just build`. Then `nix build --dry-run .#darwinConfigurations.behemoth.system` must show no linux-builder image under "will be fetched". Evaluate stargazer, stargazer-drill and rocinante (rocinante unchanged at `bxkygm8s…`). Commit `fix(behemoth): declare the native linux builder, drop the VM builder` with a body saying why 2854f5a is superseded.

- [ ] **Step 4: Owner switches, controller verifies**

`just switch`. Then: `cat /etc/determinate/config.json` shows `"state": "enabled"` and the memory value, `determinate-nixd version` still lists `native-linux-builder`, and the probe from Task 1 Step 5 prints `aarch64`. Also build one real stargazer artifact from behemoth: `nix build --no-link --print-out-paths '.#nixosConfigurations.stargazer.config.environment.etc."xdg/hypr/hyprland.lua".source'`.

---

## Follow-ups outside this plan

- P9b: the catppuccin/nix ruling can be revisited now that import-from-derivation evaluates on behemoth. Not automatic, a separate decision.
- The P9b global check "behemoth drvPath unchanged" takes the new baseline after Task 1.
