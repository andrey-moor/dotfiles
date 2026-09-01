# home/dev/terraform.nix -- Terraform infrastructure tools

{
  lib,
  config,
  pkgs,
  ...
}:

with lib;
{
  config = {
    home.packages = with pkgs; [
      terraform # Infrastructure as code
      terraform-ls # Terraform language server
    ];
  };
}
