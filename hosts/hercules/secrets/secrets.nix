let
  hercules = {
    andreym = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEek7RDKTnX/9BZyMv37cYEbYnZpNMgHHWFFJkMjm9Qp andreym@hercules";
  };
  allKeys = [
    hercules.andreym
  ];
in
{
  "hercules.age".publicKeys = allKeys;
}