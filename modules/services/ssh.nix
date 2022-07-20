{ options, config, lib, ... }:

with lib;
with lib.my;
let cfg = config.modules.services.ssh;
in {
  options.modules.services.ssh = {
    enable = mkBoolOpt false;
  };

  config = mkIf cfg.enable {
    services.openssh = {
      enable = true;
      kbdInteractiveAuthentication = false;
      # passwordAuthentication = false;

      # TODO: Review from security perspective
      passwordAuthentication = true;
      permitRootLogin = "yes";
    };

    user.openssh.authorizedKeys.keys =
      if config.user.name == "andreym"
      then [ "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCnMqFN2LGQ8tqScQT5EwchVNU+FPcyyqZGyq4zY0l2VzL9BEdX14tu9ChSIHcnRHRvyJ6WCqdkkAfaUhtW9oLHcuS2St7f2BF5LZLQloRQszlKoXdFzH0XHfUEXAhUDFGtuT2/dTqcdod2go3KBHJq3XuvciNpzUwRo2eFz6F6rkENToggiPy/b2BCHDKDUSucPhyzwt+N3D6T5HhP6ESBufhhKU9a1QDIur1OA4FaWT/geCCgfGeDzmM7/LFsapvKcun6HWw+YDlK/NaINZe/Hc+663UXoFKRzmC+8xgd5eTs/1tFOL0fcGm8rissELun0Z582OWPpZYPLQ8fD/OiBZoLffG4Y+OnYXVDJX0CpPjMNBw/Q5XdiIfmzpTiPPB0CPY+/004ZRlxT4FScx6tnCVzGBvcsls1XgJx3o/xvgZLBySqnTwLEb1hOkc2eVzZjhN9wIT4WE9m5XGFzNueVhwMJ/ZAFV7jVuDQNVHCDbXusaR0RGYoEJQHd7s5leY4fzLQEVEFFLx/etsax6D1hzJEnnavE4aPeBsK6AKbjFdhmhyW4c+bvYwtV8syGORcco0hs5lKv97CItNl2FbuSWjYUuePd8fXG0fJdMjPOpv+lNvL1NQeBcPPLOsFtmKIfnNj7UcuM6ML//6MRKn8DYidQNMfwmnDcGxNKZY8Tw== cardno:10 974 704" ]
      else [];
  };
}
