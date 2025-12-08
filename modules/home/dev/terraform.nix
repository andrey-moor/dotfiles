# modules/home/dev/terraform.nix -- Terraform infrastructure tools

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.terraform;
in {
  options.modules.dev.terraform = {
    enable = mkEnableOption "Terraform infrastructure tools";
  };

  config = mkIf cfg.enable {
    home.packages = with pkgs; [
      terraform      # Infrastructure as code
      terraform-ls   # Terraform language server
    ];
  };
}
