---
created: 2026-02-02T12:17
title: Retry encrypted VM installation with fixed prl-type.sh
area: tooling
files:
  - scripts/prl-type.sh
  - .planning/phases/01-vm-template-creation/01-01-PLAN.md
---

## Problem

Previous VM installation attempts failed with "Timed out waiting for device /dev/mapper/cryptroot" — the encrypt hook never prompted for LUKS passphrase at boot. Root cause was likely garbled commands from the buggy vm-type.sh script (race condition in shifted character handling caused `:` to become `;`, etc.).

The script has been fixed and refactored:
1. Added sleep after shift key press to fix race condition
2. Refactored to JSON batching (~3x faster)
3. Renamed to prl-type.sh
4. Added testing instructions and verification via `prlctl capture`

## Solution

Re-execute Plan 01-01 from Task 0 (verify prl-type.sh) through Task 11 (verify LUKS boot). The VM "ArchBase-Template" exists but should be recreated fresh for clean installation.

Key commands for verification:
```bash
./scripts/prl-type.sh "TEST: @#$ /dev/sda2"
prlctl capture ArchBase-Template --file /tmp/test.png
```
