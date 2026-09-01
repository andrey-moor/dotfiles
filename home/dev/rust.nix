# home/dev/rust.nix -- Rust development tools (home-manager)

{ lib, config, pkgs, ... }:

with lib;
{
  config = {
    home.packages = with pkgs; [
      # Rustup manages the toolchain (rustc, cargo, clippy, rustfmt, rust-analyzer)
      rustup

      # Cargo tools
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
