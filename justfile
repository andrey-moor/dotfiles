# Format disk using disko for a specific host
disko-format host:
    sudo nix run \
        --extra-experimental-features nix-command \
        --extra-experimental-features flakes \
        github:nix-community/disko \
        -- --mode zap_create_mount ./hosts/{{host}}/disk.nix