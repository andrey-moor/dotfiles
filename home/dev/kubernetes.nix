# home/dev/kubernetes.nix -- Kubernetes development tools

{
  lib,
  config,
  pkgs,
  ...
}:

with lib;
let
  cfg = {
    # helm's nixpkgs packaging breaks recurrently (e.g. 4.2.0 patches a
    # moved test file). Off by default; flip on once upstream is healthy.
    helm = false;
  };
in
{
  config = {
    # Explicit KUBECONFIG so sudo env_keep can pass it through
    home.sessionVariables.KUBECONFIG = "${config.home.homeDirectory}/.kube/config";

    home.packages =
      with pkgs;
      [
        kubectl # Kubernetes CLI
        kubectx # Switch between clusters/namespaces
        kind # Kubernetes in Docker
        kubebuilder # SDK for building K8s APIs
        k9s # Terminal UI for K8s
        stern # Multi-pod log tailing
        kubelogin # Azure AKS authentication
        kubefwd # Bulk port forwarding services for local dev
        argocd # GitOps continuous deployment CLI
      ]
      ++ optional cfg.helm kubernetes-helm; # Helm package manager (opt-in)
  };
}
