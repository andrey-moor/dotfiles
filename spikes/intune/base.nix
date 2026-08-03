{ lib, pkgs, ... }: {
  services.openssh.enable = true;
  services.openssh.settings.PermitRootLogin = "prohibit-password";
  users.users.root.openssh.authorizedKeys.keyFiles = [ ./spike.key.pub ];
  networking.useDHCP = lib.mkDefault true;
  networking.firewall.enable = false;          # throwaway spike guests only
  time.timeZone = "America/Los_Angeles";
  environment.systemPackages = with pkgs; [ vim curl jq azure-cli ];
  boot.kernelParams = [ "console=ttyS0" ];     # serial.log gets boot output
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;
  system.stateVersion = "25.05";
}
