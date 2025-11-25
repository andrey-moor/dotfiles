# modules/home/dev/rust.nix -- Rust development tools (home-manager)

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.rust;
in {
  options.modules.dev.rust = {
    enable = mkEnableOption "Rust development tools";
  };

  config = mkIf cfg.enable {
    home.packages = with pkgs; [
      # Rustup manages the toolchain (rustc, cargo, clippy, rustfmt, rust-analyzer)
      rustup

      # Cargo tools
      cargo-watch
      cargo-edit
      cargo-audit
      cargo-outdated
      cargo-cross

      # Development tools
      bacon
    ];

    home.sessionVariables = {
      RUST_BACKTRACE = "1";
      CARGO_HOME = "$HOME/.cargo";
      RUSTUP_HOME = "$HOME/.rustup";
    };
  };
}
