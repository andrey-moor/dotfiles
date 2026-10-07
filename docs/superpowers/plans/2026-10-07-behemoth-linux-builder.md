# behemoth: aarch64-linux builder, implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** behemoth can build aarch64-linux derivations locally, so evaluating and inspecting the stargazer configuration no longer fails with a platform mismatch.

**Architecture:** Determinate's own nix-darwin module (`determinateNix`) replaces the `nix.enable = false` workaround, manages `/etc/nix/nix.custom.conf` and `/etc/determinate/config.json` declaratively, and runs the nixpkgs Linux builder VM (`pkgs.darwin.linux-builder`) as a launchd daemon with a `builders` entry in `/etc/nix/machines`. The module forbids running its native Linux builder and the VM builder together, so the native one stays off. When Determinate grants the account access, the VM builder is turned off and the native one on, in the same option block. Two phases: the first switch uses the nixpkgs VM defaults, because the VM image is itself an aarch64-linux build and only the cache can supply it. The second switch, built by the running builder, raises the VM's resources.

**Tech Stack:** Determinate Nix 3.23.1 on behemoth, Determinate flake `https://flakehub.com/f/DeterminateSystems/determinate/3` (darwin module), nixpkgs `darwin.linux-builder` (NixOS VM on QEMU with HVF, SSH on localhost port 31022, well-known insecure key pair bound to localhost by design), nix-darwin.

**Decision record (2026-10-07):** Determinate's native builder is granted per FlakeHub account and andrey-moor is not yet enabled, so the login alone did nothing. The nix-darwin `nix.linux-builder` option asserts `nix.enable` and is blocked under Determinate (nix-darwin issue 1505). The Determinate module's `nixosVmBasedLinuxBuilder` is the same VM without that assertion. stargazer as an SSH builder and nixbuild.net were rejected for now: the first needs the VM running and cannot serve an ISO rebuild, the second adds a vendor.

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

### Task 2: Raise the builder's resources

Only after Task 1's probe passed. behemoth has 16 cores and 128 GiB.

**Files:**
- Modify: `hosts/behemoth/default.nix`
- Modify: `docs/vmware-fusion-workarounds.md` is NOT touched (wrong document). Add one row to the behemoth section of `CLAUDE.md` only if the numbers matter to a reader.

- [ ] **Step 1: Set the resources**

```nix
    nixosVmBasedLinuxBuilder = {
      enable = true;
      # Enough for the patched Hyprland and himmelblau builds that the stargazer
      # configuration carries (8.5 GiB peak on the VM with max-jobs 2, cores 4).
      config.virtualisation = {
        cores = 6;
        memorySize = 16384;
        diskSize = 102400;
      };
    };
```

`maxJobs` follows `cores` by the module's default. Keep `speedFactor` at 1.

- [ ] **Step 2: Build with the running builder, switch, re-probe**

`just build` now builds the new VM image through the Task 1 builder. Report how long it took. Owner: `just switch`. Rerun the Step 5 probe and `nix build --no-link .#nixosConfigurations.stargazer.config.environment.etc."xdg/hypr/hyprland.lua".source` as a real aarch64-linux build from behemoth.

- [ ] **Step 3: Commit**

`feat(behemoth): six cores and 16 GiB for the linux builder VM`.

---

## Follow-ups outside this plan

- When Determinate grants access: set `nixosVmBasedLinuxBuilder.enable = false` and `determinateNixd.builder.state = "enabled"` (the module allows only one of the two), switch, verify with the Task 1 probe.
- P9b: the catppuccin/nix ruling can be revisited now that import-from-derivation evaluates on behemoth. Not automatic, a separate decision.
- The P9b global check "behemoth drvPath unchanged" takes the new baseline after Task 1.
