# SDD ledger — plan: docs/superpowers/plans/2026-07-23-env-refactor-p1-foundation.md
Task 1: complete (no commits — read-only verification, all PASS; review waived: empty diff, claims cross-checked by controller)
Task 2: minor (deferred): wayvnc render script sets umask 077 after mkdir -p — move umask first for dir perms defense-in-depth
Task 2: minor (deferred): plan Step-7 sops command is broken as written (path_regex matches input path, not redirect) — fix wording before P7+ reuses the pattern
Task 2: note: rocinante checkout was on feat/behemoth-ssh-access (clean, pushed) — implementer switched it to main to deploy
Task 2: complete (commits 238b3b5..bcf7f80, review clean; remote rotation independently verified: active/600/ROTATED)
Task 3: complete (commits bcf7f80..e931a71, review clean)
Task 4: minor (deferred): plan Step-2 literal grep is noisy (transitive lock refs contain nixpkgs-unstable substring) — jq node-keys check is the correct form
Task 4: complete (commits e931a71..dd75fac, review clean)
Task 5: fix round 1/5 (scope extension: brief line-range undershot; controller directed deletion of all 5 remaining OrbStack stargazer recipes; commits b3d4d37..f0674e2)
Task 5: complete (commits dd75fac..f0674e2, review clean)
Task 6: complete (no commits — system maintenance; review waived: empty diff. Freed ~6GiB; system GC skipped (sudo); survey: 5 Parallels VMs ~700G = the disk story, user decision pending)
Task 7: fix round 1/5 (build-stargazer platform mismatch — x86_64 .deb deps need Rosetta; controller adjudicated eval-only downgrade for that job only; commits 9891e37..5030e60)
Task 7: minor (deferred): implementer never wrote task-7-report.md (paper-trail gap; live CI+git state substitutes)
Task 7: minor (deferred): actions pinned to @main floating refs, no permissions: block (brief-specified; supply-chain hygiene nit)
Task 7: complete (commits f0674e2..5030e60, review clean; CI run 30664489481 all 4 jobs green)
Task 8: minor (deferred): both workflows pin DeterminateSystems actions to @main (mutable ref) — future supply-chain hardening pass should pin SHAs
Task 8: minor (deferred): auto-merge safety rests entirely on branch protection remaining configured (workflow has no internal gate) — operational dependency to monitor
Task 8: note: test PR #3 open+unmerged by design — upstream nixpkgs hashicorp.terraform vsix hash mismatch; gate held; self-heals next weekly run
Task 8: complete (commits 5030e60..ac723b4, review clean)
FINAL REVIEW: 1 critical + 4 important + 2 minor findings; ONE fix wave (efd6046, 6c60c48); scoped re-review = 7/7 ADDRESSED
FINAL: parked — unquoted heredoc in scripts/install-arch.sh creds.json generation (special chars in a manually-chosen password break JSON / allow command substitution) — ruling: real but not load-bearing; triggers only outside documented usage (random base64), and the Arch-VM provisioning path is retired entirely by P7-P9. Follow-up: rebuild with jq -n --arg if the script is ever reused.
PHASE P1: COMPLETE (238b3b5..6c60c48, 10 commits; final review fixes merged; CI run 30667237192 all 4 jobs green)
