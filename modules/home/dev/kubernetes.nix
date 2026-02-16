# modules/home/dev/kubernetes.nix -- Kubernetes development tools

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.kubernetes;
in {
  options.modules.dev.kubernetes = {
    enable = mkEnableOption "Kubernetes development tools";
  };

  config = mkIf cfg.enable {
    # Explicit KUBECONFIG so sudo env_keep can pass it through
    home.sessionVariables.KUBECONFIG = "${config.home.homeDirectory}/.kube/config";

    home.packages = with pkgs; [
      kubectl          # Kubernetes CLI
      kubernetes-helm  # Helm package manager
      kubectx          # Switch between clusters/namespaces
      kind             # Kubernetes in Docker
      kubebuilder      # SDK for building K8s APIs
      k9s              # Terminal UI for K8s
      stern            # Multi-pod log tailing
      kubelogin        # Azure AKS authentication
      kubefwd          # Bulk port forwarding services for local dev
      # argocd         # GitOps continuous deployment CLI (disabled: upstream yarn hash broken in nixpkgs)
    ];

    # kubectl completion and aliases
    programs.bash.initExtra = mkIf config.programs.bash.enable ''
      source <(kubectl completion bash)
      alias k=kubectl
      complete -o default -F __start_kubectl k
    '';

    programs.zsh.initExtra = mkIf config.programs.zsh.enable ''
      source <(kubectl completion zsh)
      alias k=kubectl
    '';
  };
}
