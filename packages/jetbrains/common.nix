{ stdenv, lib, makeDesktopItem, makeWrapper, patchelf, writeText
, coreutils, gnugrep, which, git, unzip, libsecret, libnotify, e2fsprogs
, vmopts ? null
}:

{ name, product, version, src, wmClass, jdk, meta, extraLdPath ? [], extraWrapperArgs ? [] }@args:

with lib;

let loName = toLower product;
    hiName = toUpper product;
    mainProgram = concatStringsSep "-" (init (splitString "-" name));
    vmoptsName = loName
               + ( if (with stdenv.hostPlatform; (is32bit || isDarwin))
                   then ""
                   else "64" )
               + ".vmoptions";
in

with stdenv; lib.makeOverridable mkDerivation (rec {
  inherit name src;
  meta = args.meta // { inherit mainProgram; };

  desktopItem = makeDesktopItem {
    name = mainProgram;
    exec = mainProgram;
    comment = lib.replaceChars ["\n"] [" "] meta.longDescription;
    desktopName = product;
    genericName = meta.description;
    categories = "Development;";
    icon = mainProgram;
    extraEntries = ''
      StartupWMClass=${wmClass}
    '';
  };

  vmoptsFile = optionalString (vmopts != null) (writeText vmoptsName vmopts);

  nativeBuildInputs = [ makeWrapper patchelf unzip ];

  postPatch = lib.optionalString (!stdenv.isDarwin) ''
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p $out/{bin,$name,share/pixmaps,libexec/${name}}
    cp -a . $out/$name
    ln -s $out/$name/bin/${loName}.png $out/share/pixmaps/${mainProgram}.png
    
    cp fsnotifier $out/libexec/${name}/.
    
    jdk=${jdk.home}
    item=${desktopItem}
    makeWrapper "$out/$name/bin/${loName}.sh" "$out/bin/${mainProgram}" \
      --set ${hiName}_VM_OPTIONS ${vmoptsFile}
    ln -s "$item/share/applications" $out/share
    runHook postInstall
  '';

} // lib.optionalAttrs (!(meta.license.free or true)) {
  preferLocalBuild = true;
})
