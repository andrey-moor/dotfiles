# hosts/stargazer/tenant.nix -- loader for the gitignored tenant facts.
#
# Returns `{ domain; tenantId; upn; }` when hosts/stargazer/local/tenant.nix
# exists in the evaluated flake source, and `null` when it does not. The repo
# is public, so those three values may never appear in a committed .nix file.
#
# `null` is a supported state, not an error: `github:andrey-moor/dotfiles#stargazer`
# -- the reference the installer, CI and system.autoUpgrade all use -- cannot
# see gitignored files, so the configuration must still evaluate without them.
# hosts/stargazer/default.nix turns that into a loud build-time warning and
# leaves himmelblau disabled.

let
  local = ./local/tenant.nix;
in
if builtins.pathExists local then import local else null
