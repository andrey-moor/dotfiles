# Dotfiles

Personal dotfiles repository for system configuration.

## Prerequisites

- [Nix](https://nixos.org/)
- [Just](https://github.com/casey/just) command runner

## Justfile Commands

This repository includes a `justfile` with helpful commands for system management:

### `disko-format`

Format a disk using [disko](https://github.com/nix-community/disko) for a specific host:

```bash
just disko-format <host>
```

Example:
```bash
just disko-format rocinante
```

This command will:
1. Run disko with the disk configuration for the specified host
2. Use `zap_create_mount` mode to wipe and format the disk according to the configuration
3. Mount the formatted partitions

**Warning**: This command will completely erase the target disk. Use with caution!

## Directory Structure

```
.
├── hosts/          # Host-specific configurations
│   └── rocinante/  # Example host
│       └── disk.nix # Disk configuration for disko
└── justfile        # Command runner configuration
```