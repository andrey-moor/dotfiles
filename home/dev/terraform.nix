# home/dev/terraform.nix -- Terraform infrastructure tools

{
  pkgs,
  ...
}:

{
  home.packages = with pkgs; [
    terraform # Infrastructure as code
    terraform-ls # Terraform language server
  ];
}
