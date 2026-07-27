# Env Refactor P1 — Foundation (security triage + CI safety net) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute spec steps 0–1: rotate the publicly-exposed VNC passwords behind sops-nix, untrack plaintext creds, freeze Omarchy, relieve behemoth's disk pressure, prune dead flake inputs, and stand up CI + weekly flake-lock automation.

**Architecture:** sops-nix (age) becomes the secrets spine, wired into the existing `lib.mkFlake` home-module lists (the flake flatten happens later, in P6 — P1 changes ride the current structure). The wayvnc module switches from a `password` string option to `passwordFile`, rendering its config at service start so no secret ever enters the nix store. CI builds every host closure on free public-repo runners; `update-flake-lock` opens a weekly auto-merging PR gated on those builds.

**Tech Stack:** sops-nix, age, GitHub Actions (`DeterminateSystems/nix-installer-action`, `update-flake-lock`), gh CLI, home-manager.

## Global Constraints

- Repo is **PUBLIC** (`github.com/andrey-moor/dotfiles`): no plaintext secret may ever be committed; sops-encrypted YAML is fine.
- Repo root: `/Users/andreym/Documents/dotfiles` (on behemoth). rocinante clone: `/home/andreym/dotfiles`, reachable via `ssh rocinante` (Tailscale, BatchMode works).
- Commit style: conventional commits (`feat:`, `fix:`, `chore:`, `ci:`, `docs:`); no attribution trailers (disabled globally). Commits go directly to `main` (repo convention).
- After every task: `nix flake check --no-build` must pass on behemoth.
- Do NOT touch `chezmoi/`, `kb-engine/`, `lib/mkFlake.nix` structure (beyond the two sops lines), or anything Omarchy-side on rocinante — those belong to later plans.
- The generated VNC passwords must never appear in the plan, chat logs, or git — only inside sops-encrypted files and 1Password.

---

### Task 1: Baseline verification

**Files:** none (read-only).

**Interfaces:**
- Produces: a known-green baseline; later tasks compare against it.

- [ ] **Step 1: Verify flake evaluates**

Run: `cd /Users/andreym/Documents/dotfiles && nix flake check --no-build 2>&1 | tail -3`
Expected: ends with the "omitted these incompatible systems" warning, no errors.

- [ ] **Step 2: Verify behemoth closure evaluates**

Run: `nix build .#darwinConfigurations.behemoth.system --dry-run 2>&1 | tail -3`
Expected: derivation list / eval warnings only; exit 0.

- [ ] **Step 3: Verify rocinante + stargazer home closures evaluate**

Run: `nix eval --raw .#homeConfigurations.rocinante.activationPackage.drvPath && echo OK && nix eval --raw .#homeConfigurations.stargazer.activationPackage.drvPath && echo OK`
Expected: two `/nix/store/....drv` paths, two `OK`s.

- [ ] **Step 4: Record pre-existing flake.lock drift**

Run: `git diff --stat flake.lock`
Expected: `flake.lock` shows as modified (pre-existing local update). Note it; it gets committed with Task 4.

---

### Task 2: sops-nix bootstrap + wayvnc password rotation

**Files:**
- Modify: `flake.nix` (add `sops-nix` input; leave agenix for Task 4)
- Modify: `lib/mkFlake.nix:88-91` and `lib/mkFlake.nix:137-140` (add sops HM module to both lists)
- Create: `.sops.yaml`
- Create: `secrets/wayvnc.yaml` (sops-encrypted)
- Modify: `modules/home/linux/wayvnc.nix` (password → passwordFile; runtime render)
- Modify: `hosts/rocinante/default.nix:108-112`, `hosts/stargazer/default.nix` (wayvnc block)

**Interfaces:**
- Produces: `modules.linux.wayvnc.passwordFile` (types.path) replacing `password` (types.str); per-host sops secrets named `wayvnc-rocinante`, `wayvnc-stargazer`; admin age key at `~/Library/Application Support/sops/age/keys.txt` (behemoth) and `~/.config/sops/age/keys.txt` (rocinante). P7+ plans consume the same `.sops.yaml`.

- [ ] **Step 1: Add sops-nix input to flake.nix**

In `flake.nix`, after the `agenix` block (line ~18), add:

```nix
    sops-nix = {
      url = "github:Mic92/sops-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
```

- [ ] **Step 2: Wire the sops HM module into both mkFlake module lists**

In `lib/mkFlake.nix`, change **both** `homeModules` definitions (darwin at ~88-91, home at ~137-140) from:

```nix
      homeModules = [
        (import homeModulesPath)
      ] ++ (if inputs ? catppuccin then [ inputs.catppuccin.homeModules.catppuccin ] else [])
        ++ moduleLib.mapModulesRec' homeModulesPath import;
```

to:

```nix
      homeModules = [
        (import homeModulesPath)
      ] ++ (if inputs ? catppuccin then [ inputs.catppuccin.homeModules.catppuccin ] else [])
        ++ (if inputs ? sops-nix then [ inputs.sops-nix.homeManagerModules.sops ] else [])
        ++ moduleLib.mapModulesRec' homeModulesPath import;
```

- [ ] **Step 3: Lock the new input and verify eval still green**

Run: `nix flake lock && nix flake check --no-build 2>&1 | tail -3`
Expected: sops-nix added to flake.lock; check passes.

- [ ] **Step 4: Generate the admin age key (behemoth) and store it**

```bash
mkdir -p "$HOME/Library/Application Support/sops/age"
KEYFILE="$HOME/Library/Application Support/sops/age/keys.txt"
[ -f "$KEYFILE" ] || nix shell nixpkgs#age -c age-keygen -o "$KEYFILE"
chmod 600 "$KEYFILE"
nix shell nixpkgs#age -c age-keygen -y "$KEYFILE"   # prints public key age1...
```

Expected: a public key `age1...` printed. Record it for Step 6.

- [ ] **Step 5: Back the key up to 1Password**

```bash
op item create --category "Secure Note" --title "sops age key (dotfiles admin)" \
  "notesPlain=$(cat "$HOME/Library/Application Support/sops/age/keys.txt")"
```

Expected: item created. If `op` isn't signed in, print the instruction for the user and continue — this backup MUST be confirmed before P1 is declared done.

- [ ] **Step 6: Create `.sops.yaml`** (replace `age1REPLACE` with Step 4's public key)

```yaml
keys:
  - &admin age1REPLACE
creation_rules:
  - path_regex: secrets/.*\.yaml$
    key_groups:
      - age:
          - *admin
```

- [ ] **Step 7: Create the encrypted secret file with freshly generated passwords**

```bash
cd /Users/andreym/Documents/dotfiles && mkdir -p secrets
TMP=$(mktemp)
printf 'wayvnc-rocinante: %s\nwayvnc-stargazer: %s\n' \
  "$(openssl rand -base64 18)" "$(openssl rand -base64 18)" > "$TMP"
nix shell nixpkgs#sops -c sops --encrypt --input-type yaml --output-type yaml "$TMP" > secrets/wayvnc.yaml
rm -f "$TMP"
grep -q 'sops' secrets/wayvnc.yaml && grep -qv 'wayvnc-rocinante: [A-Za-z0-9+/]' secrets/wayvnc.yaml && echo ENCRYPTED-OK
```

Expected: `ENCRYPTED-OK`. The file must contain only ciphertext + sops metadata.

- [ ] **Step 8: Rewrite the wayvnc module — passwordFile + runtime render**

In `modules/home/linux/wayvnc.nix`:

(a) Replace the `password` option (lines 72-76) with:

```nix
    passwordFile = mkOption {
      type = types.path;
      description = "Path to a file containing the VNC password (e.g. a sops secret). Read at service start; never enters the nix store.";
    };
```

(b) Add a render script to the `let` block (after `setResolution`, before `in {`). Note `$(cat ...)` is shell — inside a Nix indented string, `$` before `(` needs no escaping, but `''` rules apply; the exact text below is correct as-is:

```nix
  # Render the wayvnc config at service start so the password never
  # enters the nix store (the config file contains it in plaintext).
  renderConfig = pkgs.writeShellScript "wayvnc-render-config" ''
    set -euo pipefail
    dir="${config.xdg.configHome}/wayvnc"
    mkdir -p "$dir"
    umask 077
    rm -f "$dir/config"
    {
      echo "address=${cfg.address}"
      echo "port=${toString cfg.port}"
      echo "enable_auth=true"
      echo "username=${config.home.username}"
      echo "password=$(cat "${cfg.passwordFile}")"
      echo "rsa_private_key_file=${config.xdg.configHome}/wayvnc/rsa_key.pem"
      echo "relax_encryption=true"
    } > "$dir/config"
  '';
```

(c) Delete the whole `xdg.configFile."wayvnc/config".text = ...;` block (lines 134-142).

(d) In `systemd.user.services.wayvnc.Service`, add before `ExecStart`:

```nix
        ExecStartPre = "${renderConfig}";
```

- [ ] **Step 9: Point both hosts at sops secrets**

In `hosts/rocinante/default.nix`, replace the wayvnc block (lines ~108-112):

```nix
        wayvnc = {
          enable = true;
          passwordFile = config.sops.secrets."wayvnc-rocinante".path;
        };
```

and add alongside the other top-level `config` attrs (same level as `modules = {...}`, e.g. right before it):

```nix
    sops = {
      age.keyFile = "${config.home.homeDirectory}/.config/sops/age/keys.txt";
      defaultSopsFile = ../../secrets/wayvnc.yaml;
      secrets."wayvnc-rocinante" = { };
    };
```

In `hosts/stargazer/default.nix`, same pattern with `"wayvnc-stargazer"` (replace `wayvnc.password = "stargazer";` with `wayvnc.passwordFile = config.sops.secrets."wayvnc-stargazer".path;` and add the sops block with `secrets."wayvnc-stargazer" = { };`).

- [ ] **Step 10: Verify eval catches nothing broken**

Run: `nix flake check --no-build && nix eval --raw .#homeConfigurations.rocinante.activationPackage.drvPath && echo OK`
Expected: pass + drv path + OK.

- [ ] **Step 11: Commit and push** (rocinante pulls from GitHub, so this precedes the remote switch)

```bash
git add flake.nix flake.lock lib/mkFlake.nix .sops.yaml secrets/wayvnc.yaml \
        modules/home/linux/wayvnc.nix hosts/rocinante/default.nix hosts/stargazer/default.nix
git commit -m "feat(secrets): sops-nix bootstrap; rotate wayvnc passwords out of git

wayvnc module: password (plaintext str, landed in nix store + public repo)
-> passwordFile rendered at service start. Hosts read from sops-encrypted
secrets/wayvnc.yaml. Old passwords are rotated and dead."
git push
```

- [ ] **Step 12: Deploy the age key to rocinante, pull, switch**

```bash
ssh rocinante 'mkdir -p ~/.config/sops/age && chmod 700 ~/.config/sops/age'
scp "$HOME/Library/Application Support/sops/age/keys.txt" rocinante:.config/sops/age/keys.txt
ssh rocinante 'chmod 600 ~/.config/sops/age/keys.txt'
ssh rocinante 'cd ~/dotfiles && git pull && nix run home-manager -- switch --flake .#rocinante -b backup'
```

Expected: switch succeeds; sops-nix unit decrypts.

- [ ] **Step 13: Verify rotation took effect on rocinante**

```bash
ssh rocinante 'systemctl --user restart wayvnc; sleep 2; systemctl --user is-active wayvnc; stat -c "%a" ~/.config/wayvnc/config; grep -c "password=" ~/.config/wayvnc/config; grep -q "password=rocinante$" ~/.config/wayvnc/config && echo OLD-PW-STILL-THERE || echo ROTATED'
```

Expected: `active`, `600`, `1`, `ROTATED`.

Note: stargazer is dormant — its switch happens whenever it next boots (P9 replaces it anyway); the *rotation* is effective because the old password no longer works anywhere once rocinante switches (stargazer's old VM still has the old password inside, acceptable: it's usually powered off; flag in task report).

---

### Task 3: Untrack plaintext installer creds

**Files:**
- Modify: `.gitignore`
- Delete (from index only): `scripts/archinstall-creds.json`

- [ ] **Step 1: Untrack and ignore**

```bash
git rm --cached scripts/archinstall-creds.json
printf '\n# never commit installer credentials\nscripts/archinstall-creds.json\n' >> .gitignore
```

- [ ] **Step 2: Verify**

Run: `git status --short scripts/ && git check-ignore scripts/archinstall-creds.json && echo IGNORED`
Expected: file shows as `D` staged, then `IGNORED`.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore(security): untrack archinstall-creds.json"
git push
```

(The file stays on disk for the frozen Omarchy tooling; history rewrite deliberately skipped per spec D.)

---

### Task 4: Prune dead flake inputs

**Files:**
- Modify: `flake.nix` (remove `agenix` block lines ~15-18 and `nixpkgs-unstable` line 7)

**Interfaces:**
- Consumes: Task 2's verified-green state. Note `pkgs.unstable` overlay in `lib/mkFlake.nix:53-58` is conditional (`if inputs ? nixpkgs-unstable`) — no mkFlake edit needed; repo-wide grep confirmed **zero** `pkgs.unstable` users.

- [ ] **Step 1: Remove the two inputs**

In `flake.nix` delete:

```nix
    nixpkgs-unstable.url = "github:nixos/nixpkgs/nixos-unstable";
```

and

```nix
    agenix = {
      url = "github:ryantm/agenix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
```

- [ ] **Step 2: Re-lock and verify**

Run: `nix flake lock && nix flake check --no-build 2>&1 | tail -3 && grep -c 'agenix\|nixpkgs-unstable' flake.lock`
Expected: check passes; grep prints `0`.

- [ ] **Step 3: Verify all three host closures still eval** (same commands as Task 1 Steps 2-3)

- [ ] **Step 4: Commit**

```bash
git add flake.nix flake.lock
git commit -m "chore(flake): prune dead inputs (agenix, redundant nixpkgs-unstable alias)"
git push
```

---

### Task 5: Omarchy freeze marker + justfile/artifact hygiene

**Files:**
- Modify: `hosts/rocinante/README.md` (freeze banner at top)
- Modify: `justfile` (delete stale stargazer-OrbStack section, lines ~120-141)
- Move: root `*.pkg.tar.xz` + `hypr-pkgs/` → `~/Archive/omarchy-pkgs/`; delete `result` symlink

- [ ] **Step 1: Add the freeze banner**

At the very top of `hosts/rocinante/README.md` (after the `# Rocinante` heading), insert:

```markdown
> **⚠️ FROZEN (2026-07): do not run `omarchy-update` or system updates on this install.**
> This Omarchy system is being replaced by NixOS on the second NVMe
> (see `docs/superpowers/specs/2026-07-23-environment-refactor-design.md`).
> It remains the fallback of record until 30 days after cutover.
```

- [ ] **Step 2: Delete the stale justfile section**

Remove the OrbStack-stargazer block (the comment header `# 1. just stargazer-create ...` through the `stargazer-delete:` recipe, justfile lines ~120-141). Verify no other recipe references them: `grep -n 'stargazer' justfile` → expected: no output after the edit.

- [ ] **Step 3: Archive the loose binary artifacts**

```bash
mkdir -p ~/Archive/omarchy-pkgs
mv /Users/andreym/Documents/dotfiles/*.pkg.tar.xz ~/Archive/omarchy-pkgs/
mv /Users/andreym/Documents/dotfiles/hypr-pkgs ~/Archive/omarchy-pkgs/hypr-pkgs
rm -f /Users/andreym/Documents/dotfiles/result
ls /Users/andreym/Documents/dotfiles/*.pkg.tar.xz 2>/dev/null; echo "root clean: $?"
```

Expected: `root clean: 1` (no matches). These were untracked (gitignored) — no git change from the moves.

- [ ] **Step 4: Commit**

```bash
git add hosts/rocinante/README.md justfile
git commit -m "docs: freeze Omarchy install; prune stale OrbStack recipes"
git push
```

---

### Task 6: behemoth disk-pressure relief

**Files:** none in repo (system maintenance; report-only for user data).

- [ ] **Step 1: Record starting point**

Run: `df -h / | tail -1`
Expected: ~30G available (baseline to compare).

- [ ] **Step 2: Garbage-collect nix (user + system profiles)**

```bash
nix-collect-garbage --delete-older-than 14d
sudo nix-collect-garbage --delete-older-than 14d
nix store optimise
```

Expected: "X store paths deleted, Y GiB freed" lines. (If `sudo` prompts interactively and the session can't answer, run the user-level GC only and note it.)

- [ ] **Step 3: Survey the big consumers (report, do NOT delete)**

```bash
du -sh ~/Parallels/* 2>/dev/null | sort -rh | head
du -sh ~/Documents/dotfiles/kb-engine/.venv ~/Documents/dotfiles/kb-engine 2>/dev/null
du -sh ~/Library/Caches/* 2>/dev/null | sort -rh | head -5
df -h / | tail -1
```

Expected: a ranked report. VM images and user data are **listed for the user's decision, never deleted**. kb-engine's venv moves out with P3 anyway.

- [ ] **Step 4: Report** — include before/after `df` and the survey table in the task summary. No commit.

---

### Task 7: CI workflow

**Files:**
- Create: `.github/workflows/ci.yaml`

**Interfaces:**
- Produces: required-check names `flake-check`, `build-behemoth`, `build-rocinante`, `build-stargazer` — Task 8's branch protection references these exact job names.

- [ ] **Step 1: Write the workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:

jobs:
  flake-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: DeterminateSystems/nix-installer-action@main
      - run: nix flake check --no-build --all-systems

  build-behemoth:
    runs-on: macos-15
    steps:
      - uses: actions/checkout@v4
      - uses: DeterminateSystems/nix-installer-action@main
      - run: nix build .#darwinConfigurations.behemoth.system --no-link --fallback

  build-rocinante:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: DeterminateSystems/nix-installer-action@main
      - run: nix build .#homeConfigurations.rocinante.activationPackage --no-link --fallback

  build-stargazer:
    runs-on: ubuntu-24.04-arm
    steps:
      - uses: actions/checkout@v4
      - uses: DeterminateSystems/nix-installer-action@main
      - run: nix build .#homeConfigurations.stargazer.activationPackage --no-link --fallback
```

- [ ] **Step 2: Commit and push**

```bash
git add .github/workflows/ci.yaml
git commit -m "ci: flake check + all-host closure builds on push/PR"
git push
```

- [ ] **Step 3: Watch the first run**

Run: `gh run watch $(gh run list --workflow ci.yaml --limit 1 --json databaseId --jq '.[0].databaseId') --exit-status || gh run view --log-failed $(gh run list --workflow ci.yaml --limit 1 --json databaseId --jq '.[0].databaseId') | tail -40`
Expected: all four jobs green (first run may take 30-60 min uncached).

**Documented fallback:** if `build-behemoth` fails on runner disk space (large unfree GUI closures), replace its run step with eval-only: `nix eval --raw .#darwinConfigurations.behemoth.system.drvPath` and note the downgrade in the commit message (`ci: behemoth eval-only (runner disk)`). Same fallback applies per-host if any closure exceeds the runner.

---

### Task 8: Weekly flake.lock automation with gated auto-merge

**Files:**
- Create: `.github/workflows/update-flake-lock.yaml`

**Interfaces:**
- Consumes: CI job names from Task 7 (required checks).
- Produces: weekly PRs titled `chore: weekly flake.lock update`.

- [ ] **Step 1 [USER — cannot be automated]: create a fine-grained PAT**

PRs created with the default `GITHUB_TOKEN` do **not** trigger CI (GitHub anti-recursion rule), which would let auto-merge land unbuilt updates or hang forever. Ask the user to create a fine-grained PAT: repo `andrey-moor/dotfiles`, permissions **Contents: R/W + Pull requests: R/W**, 1-year expiry, then run:

```bash
gh secret set FLAKE_UPDATE_TOKEN --repo andrey-moor/dotfiles
```

(pasting the token). Block this task until done; other tasks may proceed.

- [ ] **Step 2: Write the workflow**

```yaml
name: update-flake-lock

on:
  schedule:
    - cron: "0 6 * * 1"   # Mondays 06:00 UTC
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: DeterminateSystems/nix-installer-action@main
      - uses: DeterminateSystems/update-flake-lock@main
        id: update
        with:
          token: ${{ secrets.FLAKE_UPDATE_TOKEN }}
          pr-title: "chore: weekly flake.lock update"
          pr-labels: dependencies
      - name: Enable auto-merge (waits on required checks)
        if: steps.update.outputs.pull-request-number != ''
        run: gh pr merge --auto --squash "${{ steps.update.outputs.pull-request-number }}"
        env:
          GH_TOKEN: ${{ secrets.FLAKE_UPDATE_TOKEN }}
          GH_REPO: ${{ github.repository }}
```

- [ ] **Step 3: Enable repo auto-merge + branch protection with required checks**

```bash
gh api -X PATCH repos/andrey-moor/dotfiles -f allow_auto_merge=true
gh api -X PUT repos/andrey-moor/dotfiles/branches/main/protection \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": false,
    "contexts": ["flake-check", "build-behemoth", "build-rocinante", "build-stargazer"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
```

Expected: HTTP 200 both. `enforce_admins=false` keeps the owner's direct pushes to main working; auto-merge PRs wait for the four checks.

- [ ] **Step 4: Commit, push, and fire a manual test run**

```bash
git add .github/workflows/update-flake-lock.yaml
git commit -m "ci: weekly update-flake-lock PR with gated auto-merge"
git push
gh workflow run update-flake-lock.yaml
sleep 20 && gh run list --workflow update-flake-lock.yaml --limit 1
```

Expected: run completes; a PR appears (or "no changes" if lock already current); if a PR appears, verify `gh pr view --json autoMergeRequest` shows auto-merge armed, and that CI is running on it. Report the PR URL.

- [ ] **Step 5: Verify end-to-end** — after CI goes green on the test PR, confirm it merged itself: `gh pr list --state merged --limit 1`. Expected: the weekly-update PR, merged without human action.

---

## Completion checklist (task report to user)

- Old VNC passwords dead on rocinante (stargazer VM dormant — carries old pw until P9; flagged).
- Age key backed up in 1Password (**must be confirmed**, not assumed).
- CI green link + first-run duration; any eval-only downgrades noted.
- Auto-merge test PR link + merge evidence.
- Disk report: freed GB + big-consumer table (user decides on VM images).
- Reminder recorded: spikes (P2) are next and time-boxed by the Aug 2026 Intune 22.04 EOL.
