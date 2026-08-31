# Env Refactor P3 — kb-engine Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `kb-engine/` out of dotfiles into a private history-preserving repo (`andrey-moor/kb-engine`), then remove it from dotfiles entirely — no nix module survives.

**Architecture:** `git-filter-repo --subdirectory-filter` on a THROWAWAY clone produces the new repo (dotfiles is never rewritten or force-pushed). The new repo is verified working (full pytest suite) at `~/Documents/kb-engine` BEFORE anything is deleted from dotfiles. Removal is one revertable tip commit plus a darwin-rebuild.

**Tech Stack:** git-filter-repo (via `nix run nixpkgs#git-filter-repo`), gh CLI, uv, nix-darwin/`just`.

**Spec:** `docs/superpowers/specs/2026-08-31-kb-engine-extraction-design.md` — read the "Accepted consequences" section; the pipeline/skill degradation is a KNOWING owner choice, not a gap.

## Global Constraints

- **Dotfiles history is NEVER rewritten and NEVER force-pushed.** All filter-repo work happens in a throwaway clone under the session scratchpad.
- New repo is **PRIVATE** (`andrey-moor/kb-engine`). Test fixtures embed vectors derived from the owner's real vault — do not make public, do not copy fixtures anywhere public.
- `gh` must be authenticated as `andrey-moor` (verify with `gh auth status`; switch with `gh auth switch --user andrey-moor` if needed).
- Conventional commits. Dotfiles CI must stay green.
- **Permission-classifier note:** `git-filter-repo` invocations may be denied by the tool-permission classifier even on a throwaway clone. If denied, STOP and report BLOCKED with the exact command — the controller will have the owner run it via `!`. Do not attempt workarounds.
- **sudo note:** `just switch` runs `sudo darwin-rebuild switch` and needs the owner's Touch ID. The implementer stops at `just build` (no sudo); the switch step is explicitly controller/owner-run.
- Do not modify anything under `spikes/`, `chezmoi/`, or the vault. Do not edit kb skill/command files (they degrade by design).

---

### Task 1: Extract kb-engine history into a new private repo

**Files:**
- Create (outside dotfiles): throwaway clone + filtered repo in the session scratchpad; new GitHub repo `andrey-moor/kb-engine`; local clone `~/Documents/kb-engine`.
- No dotfiles changes in this task.

**Interfaces:**
- Produces: private GitHub repo `andrey-moor/kb-engine` whose root is kb-engine's former content with full commit history; working clone at `~/Documents/kb-engine` with the test suite passing. Task 2 depends on both.

- [ ] **Step 1: Verify gh identity**

```bash
gh auth status 2>&1 | grep -A1 "Active account: true" | head -2
```
Expected: `andrey-moor`. If not: `gh auth switch --user andrey-moor` (and note to switch back at the end).

- [ ] **Step 2: Throwaway clone + filter (scratchpad, never the real repo)**

```bash
SCRATCH="$(mktemp -d /tmp/kb-extract.XXXXXX)"
git clone --no-local file:///Users/andreym/Documents/dotfiles "$SCRATCH/extract"
cd "$SCRATCH/extract"
nix run nixpkgs#git-filter-repo -- --subdirectory-filter kb-engine
```
(If the classifier denies filter-repo: STOP, report BLOCKED with this exact command per Global Constraints.)

- [ ] **Step 3: Verify the filtered result**

```bash
cd "$SCRATCH/extract"
ls pyproject.toml src tests uv.lock                # kb-engine content now at ROOT
git log --oneline | wc -l                          # >50 commits expected (kb-engine's history)
git log --oneline --all -- kb-engine | head -1     # EMPTY — no nested kb-engine/ path remains
git ls-files | grep -vE "^(src/|tests/|scripts/|capture/|pyproject|uv.lock|README|\.gitignore|\.python-version)" | head
```
Expected: content at root; double-digit-plus commit count; last command shows nothing unexpected (investigate anything that isn't kb-engine's own file before pushing — this is the private-leak gate: NOTHING from dotfiles outside kb-engine/ may be present).

- [ ] **Step 4: Create the private repo and push**

```bash
cd "$SCRATCH/extract"
gh repo create andrey-moor/kb-engine --private --description "Knowledge-base engine: embeddings, hybrid search, topics, pipeline" --disable-wiki
git remote add origin git@github.com:andrey-moor/kb-engine.git 2>/dev/null || git remote set-url origin git@github.com:andrey-moor/kb-engine.git
git push -u origin main
gh repo view andrey-moor/kb-engine --json visibility --jq .visibility
```
Expected: push succeeds; visibility prints `PRIVATE`. If the default branch in the filtered clone isn't `main`, rename first: `git branch -m main`.

- [ ] **Step 5: Clone to the canonical location and run the FULL test suite**

```bash
git clone git@github.com:andrey-moor/kb-engine.git /Users/andreym/Documents/kb-engine
cd /Users/andreym/Documents/kb-engine
uv run --extra ml --extra topics pytest -q 2>&1 | tail -5
```
Expected: suite passes (recent count ~542 tests; first run downloads the venv — allow several minutes; run detached and poll if it exceeds the 10-minute tool timeout). A failing suite is a STOP: do not proceed to Task 2/3 with a broken extraction; report the failure verbatim.

- [ ] **Step 6: Clean up the scratchpad clone**

```bash
rm -rf "$SCRATCH"
```

---

### Task 2: README manual-run section in the new repo

**Files:**
- Modify: `README.md` in `/Users/andreym/Documents/kb-engine` (the NEW repo, not dotfiles).

**Interfaces:**
- Consumes: Task 1's working clone.
- Produces: documented manual escape hatch (the spec's accepted-consequences remedy).

- [ ] **Step 1: Add a "Running without dotfiles" section near the top of README.md**

```markdown
## Running without dotfiles

As of 2026-08-31 this repo is standalone — nothing installs it. Run directly:

    uv run --project ~/Documents/kb-engine --extra ml --extra topics kb-engine <command>

Secrets (where a command needs them) are still read from
`~/.config/kb-engine/secrets.env`. The scheduled pipeline (launchd) was
retired with the dotfiles module; run `kb-engine pipeline --tier <tier>`
manually if needed.
```

Match the README's existing heading style. Do not rewrite anything else.

- [ ] **Step 2: Commit and push (new repo)**

```bash
cd /Users/andreym/Documents/kb-engine
git add README.md && git commit -m "docs: standalone manual-run instructions (extracted from dotfiles)" && git push
```

---

### Task 3: Remove kb-engine from dotfiles

**Files:**
- Delete: `kb-engine/` (entire tracked directory), `modules/home/dev/kb-engine.nix`
- Modify: `hosts/behemoth/default.nix` (remove the `kb-engine = { ... };` enable block, ~line 202)

**Interfaces:**
- Consumes: Task 1's verified clone (the safety precondition for deleting anything).
- Produces: a dotfiles tree with zero kb-engine references in `modules/` and `hosts/`; `just build` green. The switch itself is controller/owner-run (sudo).

- [ ] **Step 1: Confirm the safety precondition**

```bash
test -d /Users/andreym/Documents/kb-engine/.git && cd /Users/andreym/Documents/kb-engine && git log --oneline -1 && cd /Users/andreym/Documents/dotfiles
```
Expected: the clone exists with history. If not, STOP — Task 1 didn't complete.

- [ ] **Step 2: Remove the directory and module**

```bash
cd /Users/andreym/Documents/dotfiles
git rm -r -q kb-engine
git rm -q modules/home/dev/kb-engine.nix
```

- [ ] **Step 3: Remove the host enable block**

In `hosts/behemoth/default.nix`, delete the entire `kb-engine = { ... };` attribute (starts ~line 202 inside the modules enable section — read the surrounding block first; remove exactly that attrset entry, nothing else).

- [ ] **Step 4: Verify no live references remain**

```bash
git grep -n "kb-engine" -- modules/ hosts/ lib/ justfile flake.nix || echo CLEAN
```
Expected: `CLEAN`. (Hits under `docs/`, `chezmoi/`, and `.github` history are fine per spec — docs stay, skills degrade by design; but a hit in `modules/`/`hosts/` means Step 2/3 missed something.)

- [ ] **Step 5: Build (no sudo)**

```bash
just build 2>&1 | tail -3
```
Expected: succeeds. The removed module is auto-discovered, so deleting the file is sufficient — but an eval error naming `modules.dev.kb-engine` means the host block removal (Step 3) was incomplete.

- [ ] **Step 6: Note the untracked leftovers, do NOT delete them yourself**

```bash
git status --short kb-engine 2>/dev/null | head -3; du -sh kb-engine 2>/dev/null || echo "working dir already clean"
```
The old in-tree `.venv`/caches (~1 GB, untracked) survive `git rm`. Report the leftover size; the CONTROLLER decides deletion after the switch is verified (it is the last rollback copy until then).

- [ ] **Step 7: Commit and push**

```bash
git status --short   # verify: only deletions + the one host file modification
git add -A
git commit -m "refactor: extract kb-engine to andrey-moor/kb-engine (P3) — module removed, no rewire"
git push
```
If commit signing fails with "Could not connect to socket": STOP, report BLOCKED (owner must unlock 1Password — never disable signing).

- [ ] **Step 8 [CONTROLLER/OWNER — not the implementer]: Switch and verify**

```bash
just switch                      # owner confirms sudo via Touch ID
which kb-engine || echo "gone from PATH (expected)"
launchctl list | grep -i kb-engine || echo "no kb-engine launchd jobs (expected)"
```
Then confirm dotfiles CI went green on the push, and delete the leftover in-tree `.venv` (`rm -rf /Users/andreym/Documents/dotfiles/kb-engine`) once the switch is verified.

---

## Completion checklist (controller)

- New private repo live, full history, tests green at `~/Documents/kb-engine`.
- Dotfiles: tracked kb-engine gone, module gone, host block gone, `just switch` applied,
  PATH/launchd clean, CI green, no force-push anywhere.
- Memory updated: `project_obsidian_kb.md` (new home; NOT installed via dotfiles; pipeline
  retired; manual-run command) and `project_env_refactor.md` (P3 done).
- Old in-tree working dir deleted after verification (~1 GB reclaimed).
