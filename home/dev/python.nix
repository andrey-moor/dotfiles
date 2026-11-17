# home/dev/python.nix -- Python development tools

{
  pkgs,
  ...
}:

{
  home.packages = with pkgs; [
    (python3.withPackages (
      ps: with ps; [
        pip
        pytest
        pyyaml
      ]
    ))
    uv # Python package manager and runner (uvx)
  ];
}
